# -*- coding: utf-8 -*-
"""动作执行器 (Phase 4, 规格书 §9/§40)。

把 LLM/任务的语义决策转成真实鼠标键盘动作:
    Decision -> Coordinate Resolver -> InputDriver -> Result Validator

Result Validator(§40): 动作后重新截图识别, 确认状态变化,
否则视为失败(重新规划, 而不是盲目认为成功)。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from automation.input_driver import Action, ActionResult, InputDriver
from .brain import Decision
from .game_state import GameState
from .resolver import CoordinateResolver, ResolveError

logger = logging.getLogger(__name__)


class Executor:
    """语义动作 -> 真实输入。"""

    def __init__(self, driver: Optional[InputDriver] = None,
                 resolver: Optional[CoordinateResolver] = None,
                 max_retry: int = 3) -> None:
        self.driver = driver
        self.resolver = resolver or CoordinateResolver()
        self.max_retry = max_retry

    # ---------------- 执行 ----------------
    def execute(self, decision: Decision, gs: Optional[GameState] = None) -> ActionResult:
        """执行语义决策。返回动作结果。"""
        if self.driver is None:
            return ActionResult(False, "输入驱动未就绪")
        action = self._build_action(decision)
        if action is None:
            return ActionResult(False, f"无法执行 {decision.action}")
        # 重试(规格书 §30)
        last = None
        for i in range(self.max_retry):
            last = self.driver.exec(action)
            if last.ok:
                return last
        return last or ActionResult(False, "执行失败")

    # ---------------- 决策 -> 基础动作 ----------------
    def _build_action(self, d: Decision) -> Optional[Action]:
        """把语义决策映射为基础 Action。"""
        a = d.action
        # 需要坐标解析的动作
        if a in ("CLICK", "CLICK_NPC", "SELECT_NPC", "SELECT_TARGET",
                 "ACCEPT_TASK", "SUBMIT_TASK", "INTERACT", "DIALOG_CHOICE"):
            if d.target:
                pos = self.resolver.resolve_or_none(d.target)
                if pos is None:
                    logger.warning("目标 %s 无法解析, 动作跳过", d.target)
                    return None
                return Action("CLICK", x=pos[0], y=pos[1], desc=d.reason or a)
            return Action("CLICK", x=0, y=0, desc="点击(坐标待定)")

        if a in ("MOVE", "NAVIGATE"):
            # 移动: 地图上点击目标附近(Phase 4 简化: 点击当前目标)
            if d.target:
                pos = self.resolver.resolve_or_none(d.target)
                if pos:
                    return Action("CLICK", x=pos[0], y=pos[1], desc="导航点击")
            return Action("WAIT", ms=1000, desc="移动中")

        # 键盘动作
        key_map = {
            "OPEN_TASK": ("alt+q", "打开任务面板"),
            "OPEN_MAP": ("tab", "打开地图"),
            "OPEN_INVENTORY": ("alt+e", "打开背包"),
            "ESC": ("esc", "关闭"),
            "ENTER": ("enter", "确认"),
            "BATTLE_AUTO": ("alt+a", "自动战斗"),
            "RECOVER": ("alt+f", "恢复"),
            "REST": ("alt+h", "休息"),
        }
        if a in key_map:
            key, desc = key_map[a]
            return Action("PRESS", key=key, desc=d.reason or desc)

        if a in ("WAIT", "IDLE"):
            return Action("WAIT", ms=1500, desc="等待")

        if a in ("UNKNOWN", "RECOVERY"):
            return None  # 不做任何事

        logger.warning("未实现动作 %s", a)
        return None

    # ---------------- 验证器(§40) ----------------
    def validate_change(self, before: GameState, after: GameState) -> bool:
        """比较动作前后状态, 判断是否有实质变化。"""
        if before.status != after.status:
            return True
        if before.dialog_text != after.dialog_text:
            return True
        if before.map_name != after.map_name:
            return True
        if before.task_progress != after.task_progress:
            return True
        # 元素集合变化
        b_elems = set(before.extra.get("elements", {}).keys())
        a_elems = set(after.extra.get("elements", {}).keys())
        if b_elems != a_elems:
            return True
        return False
