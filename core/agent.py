# -*- coding: utf-8 -*-
"""单账号真实桌面 Agent：截图 -> 观察 -> 决策 -> 输入 -> 轻量验证。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from automation.input_driver import Action, ActionResult
from automation.window import WindowLost
from vision.capture import CaptureError, capture_window
from vision.ocr import OCREngine
from vision.tracker import Tracker
from .action_verifier import ActionVerifier
from .executor import Executor
from .resolver import CoordinateResolver
from .account import Account
from .brain import Brain, Decision, RuleBrain
from .game_state import GameState, GameStatus

logger = logging.getLogger(__name__)


class ActionValidator:
    RISKY_ACTIONS = {"TRADE", "BUY", "SELL", "DROP_ITEM", "LEAVE_TEAM", "QUIT_CLIENT"}
    BATTLE_FORBIDDEN = {"OPEN_MAP", "LEAVE_TEAM", "QUIT_CLIENT", "OPEN_INVENTORY"}

    def validate(self, decision: Decision, state: GameState) -> tuple:
        if decision.action in self.RISKY_ACTIONS:
            return False, f"危险动作 {decision.action} 禁止自动执行"
        if state.status == GameStatus.BATTLE and decision.action in self.BATTLE_FORBIDDEN:
            return False, f"战斗状态下禁止 {decision.action}"
        if decision.confidence < 0.4:
            return False, f"置信度过低({decision.confidence:.2f}), 需人工确认"
        return True, ""


class GameAgent:
    """单账号 Agent，支持真实桌面输入后的低成本画面变化验证。"""

    def __init__(self, account: Account, brain: Optional[Brain] = None,
                 ocr_backend: str = "rapidocr", tick_seconds: float = 0.5,
                 max_retry: int = 3, tracker: Optional[Any] = None,
                 ocr_every_n: int = 1, task: Optional[Any] = None,
                 memory: Optional[Any] = None, replay: Optional[Any] = None,
                 verify_actions: bool = True, verify_settle_ms: int = 350,
                 verify_threshold: float = 0.012) -> None:
        self.account = account
        self.brain = brain or RuleBrain()
        self.validator = ActionValidator()
        self.ocr = OCREngine(ocr_backend)
        self.tick = tick_seconds
        self.max_retry = max_retry
        self.tracker = tracker
        self.resolver = None
        self.executor = None
        self.task = task
        self.memory = memory
        self.replay = replay
        self.ocr_every_n = max(1, ocr_every_n)
        self._ocr_frame = 0
        self.running = False
        self.loop_count = 0
        self.verify_actions = bool(verify_actions)
        self.action_verifier = ActionVerifier(threshold=verify_threshold, settle_ms=verify_settle_ms)
        if account.driver is not None:
            self.resolver = CoordinateResolver()
            self.executor = Executor(account.driver, self.resolver, max_retry=max_retry)

    def observe(self) -> GameState:
        win = self.account.win
        if win is None:
            raise WindowLost("窗口未绑定")
        if not win.is_valid():
            raise WindowLost(f"窗口失效 {win.title}")
        try:
            img, size = capture_window(win)
        except CaptureError as e:
            raise WindowLost(str(e)) from e
        self._ocr_frame += 1
        if self._ocr_frame % self.ocr_every_n == 0:
            ocr_lines = self.ocr.recognize(img, size)
            texts = [ln.text for ln in ocr_lines]
            gs = self.account.sm.update(texts, img, size)
            if self.resolver is not None:
                self.resolver.update_context(
                    [(ln.text, ln.x, ln.y) for ln in ocr_lines],
                    gs.extra.get("elements"))
        else:
            gs = self.account.sm.update([], img, size)
            gs.extra["ocr_skipped"] = True
        if self.tracker is not None:
            import numpy as np  # type: ignore
            w, h = size
            bgr = np.frombuffer(img, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
            elems = self.tracker.track(bgr)
            gs.extra["elements"] = {k: v.to_dict() for k, v in elems.items()}
            if "battle_auto_btn" in elems:
                gs.in_battle = True
        gs.map_name = gs.map_name or self.account.state.map
        return gs

    def think(self, gs: GameState, goal: str = "") -> Decision:
        return self.brain.decide(gs, goal)

    def act(self, decision: Decision, gs: GameState) -> ActionResult:
        driver = self.account.driver
        if driver is None:
            return ActionResult(False, "输入驱动未就绪")
        if self.executor is not None:
            return self.executor.execute(decision, gs)
        mapping = {
            "WAIT": Action("WAIT", ms=1000, desc="等待"),
            "OPEN_TASK": Action("PRESS", key="alt+q", desc="打开任务面板"),
            "BATTLE_AUTO": Action("PRESS", key="alt+a", desc="自动战斗"),
            "RECOVER": Action("PRESS", key="alt+f", desc="恢复"),
            "IDLE": Action("WAIT", ms=2000, desc="待命"),
        }
        action = mapping.get(decision.action)
        if action is None:
            return ActionResult(False, f"未实现动作 {decision.action}")
        return driver.exec(action)

    def _needs_visual_verification(self, decision: Decision) -> bool:
        return decision.action in {
            "CLICK", "CLICK_NPC", "SELECT_NPC", "SELECT_TARGET",
            "ACCEPT_TASK", "SUBMIT_TASK", "INTERACT", "DIALOG_CHOICE",
        }

    def step(self, goal: str = "") -> Dict[str, Any]:
        self.loop_count += 1
        gs = self.observe()
        if self.task is not None:
            task_action = self.task.step(gs)
            decision = Decision(
                action=task_action.get("action", "UNKNOWN"),
                target=task_action.get("target", ""),
                reason=task_action.get("reason", ""),
                confidence=0.9,
            )
        else:
            decision = self.think(gs, goal)

        ok, reason = self.validator.validate(decision, gs)
        result: Dict[str, Any] = {"validated": ok, "reason": reason, "action_result": None}
        if ok:
            before = None
            # 仅对鼠标点击类动作做轻量画面验证，不额外运行 OCR/YOLO。
            if self.verify_actions and self._needs_visual_verification(decision) and self.account.win is not None:
                try:
                    before = self.action_verifier.snapshot(self.account.win)
                except Exception as exc:
                    logger.debug("动作前截图失败，跳过轻量验证: %s", exc)
            for attempt in range(1, self.max_retry + 1):
                ar = self.act(decision, gs)
                result["action_result"] = {"ok": ar.ok, "desc": ar.desc, "error": ar.error}
                if ar.ok:
                    break
                time.sleep(0.3)
            # 画面变化仅作为验证信息；不把“无变化”直接当成输入失败，避免误伤合法的等待/无视觉反馈动作。
            if before is not None and self.account.win is not None and ar.ok:
                try:
                    change = self.action_verifier.verify(self.account.win, before)
                    result["visual_verification"] = {
                        "changed": change.changed,
                        "score": round(change.score, 6),
                        "elapsed_ms": round(change.elapsed_ms, 1),
                        "reason": change.reason,
                    }
                    if not change.changed:
                        result["verification_warning"] = "输入已发送，但动作后画面变化不足；下一步观察将决定是否重规划"
                except Exception as exc:
                    result["verification_warning"] = f"动作后画面验证失败: {exc}"
        else:
            result["action_result"] = {"ok": False, "desc": reason}

        self.account.logger.record_decision(gs.to_dict(), decision.to_dict(), result)
        self.account.state.last_activity = f"{decision.action}({decision.confidence:.2f})"
        self.account.state.state = gs.status
        self.account.state.map = gs.map_name
        self.account.state.hp = gs.hp or 0
        self.account.state.task = gs.task_name

        if self.memory is not None:
            task_name = gs.task_name or (self.task.name if self.task else "通用")
            ar = result.get("action_result") or {}
            self.memory.record_action(task_name, decision.action,
                                      success=bool(ar.get("ok", False)), duration=self.tick)
        if self.replay is not None:
            gs_dict = gs.to_dict()
            gs_dict["_size"] = list(gs.raw_size) if gs.raw_size else None
            self.replay.record_step(gs.raw_image, gs_dict, decision.to_dict(), result)
        return {"state": gs.to_dict(), "decision": decision.to_dict(), "result": result}

    def run(self, goal: str = "", max_steps: Optional[int] = None,
            stop_event: Optional[Any] = None) -> None:
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
                if self.account.sm.stuck:
                    self.account.logger.warning("状态无变化次数超限, 进入 Recovery")
                    self.account.state.anomaly = True
                    break
                time.sleep(self.tick)
        finally:
            self.running = False
            self.account.stop()
            self.account.logger.info(f"Agent 停止, 共执行 {steps} 步")
