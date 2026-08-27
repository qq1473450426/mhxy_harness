# -*- coding: utf-8 -*-
"""最小可运行 Agent Loop (规格书 §38/§4)。

循环: 截图 -> 观察(OCR) -> 状态机 -> 决策(规则/LLM) -> 执行 -> 记录

安全原则(规格书 §30/§39/§40):
- Action 超时/重试上限
- 状态无变化检测(stuck -> Recovery)
- 异常即停 + 截图 + 日志 + 人工接管

Phase 1: 单账号 Agent。五开由 Phase 5 Coordinator 编排。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from automation.input_driver import Action, ActionResult
from automation.window import WindowLost
from vision.capture import CaptureError, capture_window
from vision.ocr import OCREngine
from vision.tracker import Tracker
from .executor import Executor
from .resolver import CoordinateResolver
from .account import Account
from .brain import Brain, Decision, RuleBrain
from .game_state import GameState, GameStatus

logger = logging.getLogger(__name__)


class ActionValidator:
    """Action 安全校验(规格书 §10)。

    任何 AI 决定的操作都不能直接执行:
    LLM Decision -> Action Validator -> State Validator -> Risk Validator -> Executor
    """

    # 危险动作: 默认禁止自动执行(规格书 §54)
    RISKY_ACTIONS = {"TRADE", "BUY", "SELL", "DROP_ITEM", "LEAVE_TEAM", "QUIT_CLIENT"}

    # 战斗状态下禁止的动作(规格书 §10)
    BATTLE_FORBIDDEN = {"OPEN_MAP", "LEAVE_TEAM", "QUIT_CLIENT", "OPEN_INVENTORY"}

    def validate(self, decision: Decision, state: GameState) -> tuple:
        """返回 (ok, reason)。"""
        if decision.action in self.RISKY_ACTIONS:
            return False, f"危险动作 {decision.action} 禁止自动执行"
        if state.status == GameStatus.BATTLE and decision.action in self.BATTLE_FORBIDDEN:
            return False, f"战斗状态下禁止 {decision.action}"
        if decision.confidence < 0.4:
            return False, f"置信度过低({decision.confidence:.2f}), 需人工确认"
        return True, ""


class GameAgent:
    """单账号 Agent: 观察-思考-行动闭环。"""

    def __init__(self, account: Account, brain: Optional[Brain] = None,
                 ocr_backend: str = "rapidocr",
                 tick_seconds: float = 0.5,
                 max_retry: int = 3,
                 tracker: Optional[Any] = None,
                 ocr_every_n: int = 1,
                 task: Optional[Any] = None,
                 memory: Optional[Any] = None,
                 replay: Optional[Any] = None) -> None:
        self.account = account
        self.brain = brain or RuleBrain()
        self.validator = ActionValidator()
        self.ocr = OCREngine(ocr_backend)
        self.tick = tick_seconds
        self.max_retry = max_retry
        self.tracker = tracker
        # Phase 4: 执行器 + 坐标解析器 + 任务
        self.resolver = None
        self.executor = None
        self.task = task
        # Phase 8: 长期记忆 + Replay
        self.memory = memory
        self.replay = replay
        # OCR 降频(规格书 §52 事件驱动): 每 N 帧做一次全图 OCR
        self.ocr_every_n = max(1, ocr_every_n)
        self._ocr_frame = 0
        self.running = False
        self.loop_count = 0
        # Phase 4: 输入驱动就绪后初始化执行器
        if account.driver is not None:
            self.resolver = CoordinateResolver()
            self.executor = Executor(account.driver, self.resolver,
                                     max_retry=max_retry)

    # ---------------- 观察 ----------------
    def observe(self) -> GameState:
        """截图 + OCR -> GameState。"""
        win = self.account.win
        if win is None:
            raise WindowLost("窗口未绑定")
        if not win.is_valid():
            raise WindowLost(f"窗口失效 {win.title}")
        try:
            img, size = capture_window(win)
        except CaptureError as e:
            raise WindowLost(str(e)) from e
        # OCR 降频: 每 ocr_every_n 帧做一次全图 OCR
        self._ocr_frame += 1
        if self._ocr_frame % self.ocr_every_n == 0:
            ocr_lines = self.ocr.recognize(img, size)
            texts = [ln.text for ln in ocr_lines]
            gs = self.account.sm.update(texts, img, size)
            # Phase 4: OCR 位置喂给坐标解析器
            if self.resolver is not None:
                self.resolver.update_context(
                    [(ln.text, ln.x, ln.y) for ln in ocr_lines],
                    gs.extra.get("elements"))
        else:
            gs = self.account.sm.update([], img, size)
            gs.extra["ocr_skipped"] = True
        # 模板检测(Phase 2): 每帧执行(38 FPS), UI 元素存入 extra
        if self.tracker is not None:
            import numpy as np  # type: ignore
            w, h = size
            bgr = np.frombuffer(img, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
            elems = self.tracker.track(bgr)
            gs.extra["elements"] = {k: v.to_dict() for k, v in elems.items()}
            # 检测到战斗按钮 -> 战斗中
            if "battle_auto_btn" in elems:
                gs.in_battle = True
        gs.map_name = gs.map_name or self.account.state.map
        return gs

    # ---------------- 决策 ----------------
    def think(self, gs: GameState, goal: str = "") -> Decision:
        return self.brain.decide(gs, goal)

    # ---------------- 执行 ----------------
    def act(self, decision: Decision, gs: GameState) -> ActionResult:
        """把语义决策解析为具体动作并执行。

        Phase 4: 优先 Executor(坐标解析+语义动作映射), 回退基础映射。
        """
        driver = self.account.driver
        if driver is None:
            return ActionResult(False, "输入驱动未就绪")
        # Phase 4: 用 Executor 执行
        if self.executor is not None:
            return self.executor.execute(decision, gs)
        # 回退: 基础映射
        mapping = {
            "WAIT": Action("WAIT", ms=1000, desc="等待"),
            "OPEN_TASK": Action("PRESS", key="alt+q", desc="打开任务面板"),
            "SUBMIT_TASK": Action("CLICK", x=0, y=0, desc="提交任务(需坐标解析)"),
            "BATTLE_AUTO": Action("PRESS", key="alt+a", desc="自动战斗"),
            "RECOVER": Action("PRESS", key="alt+f", desc="恢复"),
            "IDLE": Action("WAIT", ms=2000, desc="待命"),
        }
        action = mapping.get(decision.action)
        if action is None:
            return ActionResult(False, f"未实现动作 {decision.action}")
        return driver.exec(action)

    # ---------------- 主循环 ----------------
    def step(self, goal: str = "") -> Dict[str, Any]:
        """单步: 观察->决策->校验->执行->记录。"""
        self.loop_count += 1
        gs = self.observe()
        # Phase 4: 任务驱动模式(师门任务状态机)
        if self.task is not None:
            task_action = self.task.step(gs)
            decision = Decision(
                action=task_action.get("action", "UNKNOWN"),
                target=task_action.get("target", ""),
                reason=task_action.get("reason", ""),
                confidence=0.9,
            )
            if decision.action in ("DONE", "RECOVERY"):
                self.account.logger.info(f"任务结束: {task_action}")
        else:
            decision = self.think(gs, goal)

        ok, reason = self.validator.validate(decision, gs)
        result = {"validated": ok, "reason": reason, "action_result": None}
        if ok:
            # 执行(带重试上限, 规格书 §30)
            for attempt in range(1, self.max_retry + 1):
                ar = self.act(decision, gs)
                result["action_result"] = {"ok": ar.ok, "desc": ar.desc, "error": ar.error}
                if ar.ok:
                    break
                time.sleep(0.3)
                if attempt == self.max_retry:
                    result["reason"] = f"动作重试 {self.max_retry} 次仍失败"
        else:
            result["action_result"] = {"ok": False, "desc": reason}

        # 记录
        self.account.logger.record_decision(
            gs.to_dict(), decision.to_dict(), result)
        self.account.state.last_activity = f"{decision.action}({decision.confidence:.2f})"
        self.account.state.state = gs.status
        self.account.state.map = gs.map_name
        self.account.state.hp = gs.hp or 0
        self.account.state.task = gs.task_name

        # Phase 8: 长期记忆(经验学习 §20)
        if self.memory is not None:
            task_name = gs.task_name or (self.task.name if self.task else "通用")
            ar = result.get("action_result") or {}
            self.memory.record_action(
                task_name, decision.action,
                success=bool(ar.get("ok", False)),
                duration=self.tick)

        # Phase 8: Replay 记录(§43)
        if self.replay is not None:
            gs_dict = gs.to_dict()
            gs_dict["_size"] = list(gs.raw_size) if gs.raw_size else None
            self.replay.record_step(gs.raw_image, gs_dict,
                                    decision.to_dict(), result)
        return {"state": gs.to_dict(), "decision": decision.to_dict(), "result": result}

    def run(self, goal: str = "", max_steps: Optional[int] = None,
            stop_event: Optional[Any] = None) -> None:
        """持续运行, 直到手动停止/超步数/异常。"""
        self.running = True
        self.account.start()
        steps = 0
        try:
            while self.running:
                if stop_event is not None and stop_event.is_set():
                    break
                if max_steps is not None and steps >= max_steps:
                    break
                try:
                    self.step(goal)
                    steps += 1
                except WindowLost as e:
                    self.account.logger.error(f"窗口丢失: {e}")
                    self.account.state.anomaly = True
                    break
                except Exception as e:
                    self.account.logger.error(f"Agent 异常: {e}")
                    self.account.state.anomaly = True
                    break
                # 卡死检测 -> Recovery
                if self.account.sm.stuck:
                    self.account.logger.warn("状态无变化次数超限, 进入 Recovery")
                    self.account.state.anomaly = True
                    break
                time.sleep(self.tick)
        finally:
            self.running = False
            self.account.stop()
            self.account.logger.info(f"Agent 停止, 共执行 {steps} 步")
