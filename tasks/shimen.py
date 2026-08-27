# -*- coding: utf-8 -*-
"""师门任务状态机 (Phase 4, 规格书 §36/§37/§4)。

流程:
    接任务 -> 跑图 -> 对话/给予/战斗 -> 交任务 -> 验证环数 -> 循环

状态:
    INIT -> GET_TASK -> RUN -> INTERACT -> SUBMIT -> VERIFY -> (下一环) | DONE

异常: 超时/重复 -> RECOVERY(暂停+截图+人工)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from core.game_state import GameState, GameStatus
from .base import Task, TaskStatus

logger = logging.getLogger(__name__)


class ShimenPhase(str, Enum):
    INIT = "INIT"
    GET_TASK = "GET_TASK"          # 接任务
    RUN = "RUN"                    # 跑图/寻找目标
    INTERACT = "INTERACT"          # 对话/给予/战斗
    SUBMIT = "SUBMIT"              # 交任务
    VERIFY = "VERIFY"              # 验证环数
    DONE = "DONE"
    RECOVERY = "RECOVERY"


@dataclass
class ShimenState:
    """师门任务运行时状态。"""

    phase: ShimenPhase = ShimenPhase.INIT
    current_round: int = 0
    target_rounds: int = 20
    task_type: str = ""        # kill | collect | talk
    same_phase_count: int = 0  # 卡死检测
    start_time: float = field(default_factory=time.time)
    max_minutes: int = 60
    errors: list = field(default_factory=list)

    def stuck(self) -> bool:
        return self.same_phase_count >= 5

    def timeout(self) -> bool:
        return (time.time() - self.start_time) / 60.0 > self.max_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {"phase": self.phase.value, "round": self.current_round,
                "target_rounds": self.target_rounds, "task_type": self.task_type,
                "errors": len(self.errors)}


class ShimenTask(Task):
    """师门任务执行器(单账号)。

    通过回调与外部 Agent 交互:
        on_get_task(): 执行接任务动作
        on_run(): 执行跑图/导航
        on_interact(): 执行对话/给予/战斗
        on_submit(): 执行交任务
        on_verify(): 验证环数, 返回 True/False
    """

    def __init__(self, max_rounds: int = 20, max_minutes: int = 60) -> None:
        super().__init__(name="师门", max_runtime=max_minutes * 60)
        self.state = ShimenState(target_rounds=max_rounds, max_minutes=max_minutes)
        self.set_progress(0, max_rounds)
        self._hooks: Dict[str, Any] = {}

    def bind(self, **hooks) -> None:
        """绑定动作钩子: get_task/run/interact/submit/verify。"""
        self._hooks.update(hooks)

    def _call(self, name: str, *args, **kwargs) -> Any:
        hook = self._hooks.get(name)
        if hook is None:
            logger.warning("未绑定钩子 %s", name)
            return False
        return hook(*args, **kwargs)

    # ---------------- 状态推进 ----------------
    def bump(self, new_phase: ShimenPhase) -> None:
        """推进阶段(或同阶段停留), 维护卡死计数。"""
        if new_phase == self.state.phase:
            self.state.same_phase_count += 1
        else:
            self.state.same_phase_count = 0
            self.state.phase = new_phase

    # ---------------- 主循环 ----------------
    def step(self, gs: GameState) -> Dict[str, Any]:
        """根据当前游戏状态推进一阶段。返回动作描述。"""
        s = self.state
        # 卡死/超时检测
        if s.stuck():
            s.phase = ShimenPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "阶段无进展"}
        if s.timeout():
            s.phase = ShimenPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "任务超时"}

        # 战斗优先处理
        if gs.in_battle or gs.status == GameStatus.BATTLE:
            self.bump(ShimenPhase.RUN)
            return {"action": "BATTLE_AUTO", "reason": "战斗中, 自动战斗"}

        # 死亡/掉线
        if gs.status in (GameStatus.DEATH, GameStatus.DISCONNECT):
            s.phase = ShimenPhase.RECOVERY
            return {"action": "RECOVERY", "reason": f"异常状态 {gs.status.value}"}

        if s.phase == ShimenPhase.INIT:
            self.bump(ShimenPhase.GET_TASK)
            return {"action": "OPEN_TASK", "reason": "打开任务面板"}

        if s.phase == ShimenPhase.GET_TASK:
            # 任务面板已有任务 -> 进入跑图
            if gs.task_name or "任务" in gs.dialog_text:
                self.bump(ShimenPhase.RUN)
                s.current_round += 1
                return {"action": "NAVIGATE", "target": "师门师父", "reason": "去师父处"}
            self._call("get_task")
            self.bump(ShimenPhase.GET_TASK)  # 同阶段停留, 计数卡死
            return {"action": "ACCEPT_TASK", "reason": "接取师门任务"}

        if s.phase == ShimenPhase.RUN:
            # 检测到对话框/NPC -> 交互
            if gs.dialogue_open or gs.npc_detected:
                self.bump(ShimenPhase.INTERACT)
                return {"action": "DIALOG_CHOICE", "reason": "出现对话框"}
            self._call("run")
            self.bump(ShimenPhase.RUN)
            return {"action": "NAVIGATE", "target": "师门师父", "reason": "跑图中"}

        if s.phase == ShimenPhase.INTERACT:
            # 任务完成提示 -> 交任务
            if "完成" in gs.dialog_text or "交" in gs.dialog_text or "报告" in gs.dialog_text:
                self.bump(ShimenPhase.SUBMIT)
                return {"action": "SUBMIT_TASK", "reason": "任务完成, 提交"}
            self._call("interact")
            self.bump(ShimenPhase.INTERACT)
            return {"action": "INTERACT", "reason": "交互中(对话/给予/战斗)"}

        if s.phase == ShimenPhase.SUBMIT:
            self._call("submit")
            ok = self._call("verify")
            self.bump(ShimenPhase.VERIFY if ok else ShimenPhase.RUN)
            return {"action": "SUBMIT_TASK", "reason": "提交并验证"}

        if s.phase == ShimenPhase.VERIFY:
            if s.current_round >= s.target_rounds:
                self.bump(ShimenPhase.DONE)
                self.set_progress(s.current_round, s.target_rounds)
                self.complete()
                return {"action": "DONE", "reason": f"完成 {s.current_round} 环"}
            self.set_progress(s.current_round, s.target_rounds)
            self.bump(ShimenPhase.RUN)
            return {"action": "NAVIGATE", "reason": f"第 {s.current_round+1} 环"}

        if s.phase == ShimenPhase.DONE:
            self.bump(ShimenPhase.DONE)
            return {"action": "DONE", "reason": "任务已全部完成"}

        # RECOVERY: 需要人工
        self.bump(ShimenPhase.RECOVERY)
        return {"action": "RECOVERY", "reason": "需要人工接管"}

    # ---------------- 工具 ----------------
    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()
