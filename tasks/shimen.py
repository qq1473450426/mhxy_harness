# -*- coding: utf-8 -*-
"""师门任务状态机：面向真实桌面执行的安全状态推进。"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from core.game_state import GameState, GameStatus
from .base import Task

logger = logging.getLogger(__name__)


class ShimenPhase(str, Enum):
    INIT = "INIT"
    GET_TASK = "GET_TASK"
    RUN = "RUN"
    INTERACT = "INTERACT"
    SUBMIT = "SUBMIT"
    VERIFY = "VERIFY"
    DONE = "DONE"
    RECOVERY = "RECOVERY"


@dataclass
class ShimenState:
    phase: ShimenPhase = ShimenPhase.INIT
    current_round: int = 0
    target_rounds: int = 20
    task_type: str = ""
    same_phase_count: int = 0
    start_time: float = field(default_factory=time.time)
    max_minutes: int = 60
    errors: list = field(default_factory=list)

    def stuck(self) -> bool:
        return self.same_phase_count >= 8

    def timeout(self) -> bool:
        return (time.time() - self.start_time) / 60.0 > self.max_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "round": self.current_round,
            "target_rounds": self.target_rounds,
            "task_type": self.task_type,
            "errors": len(self.errors),
        }


class ShimenTask(Task):
    """师门任务状态机。

    所有真实点击均通过 Agent -> Resolver -> InputDriver 完成；本类只产生语义动作。
    """

    def __init__(self, max_rounds: int = 20, max_minutes: int = 60, **_: Any) -> None:
        super().__init__(name="师门", max_runtime=max_minutes * 60)
        self.state = ShimenState(target_rounds=max_rounds, max_minutes=max_minutes)
        self.set_progress(0, max_rounds)
        self._hooks: Dict[str, Any] = {}

    def bind(self, **hooks) -> None:
        self._hooks.update(hooks)

    def _call(self, name: str, *args, **kwargs) -> Any:
        hook = self._hooks.get(name)
        return hook(*args, **kwargs) if hook else False

    def bump(self, new_phase: ShimenPhase) -> None:
        if new_phase == self.state.phase:
            self.state.same_phase_count += 1
        else:
            self.state.same_phase_count = 0
            self.state.phase = new_phase

    @staticmethod
    def _texts(gs: GameState) -> str:
        return " ".join([*(gs.ocr_texts or []), gs.dialog_text or "", gs.task_name or ""])

    def _has(self, gs: GameState, *words: str) -> bool:
        text = self._texts(gs)
        return any(w in text for w in words)

    def step(self, gs: GameState) -> Dict[str, Any]:
        s = self.state
        if s.stuck():
            s.phase = ShimenPhase.RECOVERY
            s.errors.append("阶段无进展")
            return {"action": "RECOVERY", "reason": "阶段无进展"}
        if s.timeout():
            s.phase = ShimenPhase.RECOVERY
            s.errors.append("任务超时")
            return {"action": "RECOVERY", "reason": "任务超时"}

        if gs.status in (GameStatus.DEATH, GameStatus.DISCONNECT):
            s.phase = ShimenPhase.RECOVERY
            return {"action": "RECOVERY", "reason": f"异常状态 {gs.status.value}"}

        if gs.in_battle or gs.status == GameStatus.BATTLE:
            self.bump(ShimenPhase.RUN)
            return {"action": "BATTLE_AUTO", "reason": "战斗中，自动战斗"}

        # 对话框已经出现：优先点击明确的“师门任务”选项，绝不点击(0,0)。
        if gs.dialogue_open or gs.status in (GameStatus.NPC_DIALOG, GameStatus.TASK_DIALOG):
            if "师门任务" in (gs.dialog_options or []) or self._has(gs, "师门任务"):
                self.bump(ShimenPhase.GET_TASK)
                return {"action": "DIALOG_CHOICE", "target": "师门任务", "reason": "选择师门任务"}
            if self._has(gs, "交谈") and s.phase in (ShimenPhase.INIT, ShimenPhase.GET_TASK):
                return {"action": "DIALOG_CHOICE", "target": "交谈", "reason": "打开师父对话"}

        if s.phase == ShimenPhase.INIT:
            # 你的实际画面中任务追踪区直接出现“师父”，优先从 OCR 坐标点击。
            if self._has(gs, "师父"):
                self.bump(ShimenPhase.GET_TASK)
                return {"action": "CLICK_NPC", "target": "师父", "reason": "点击任务追踪中的师父"}
            self.bump(ShimenPhase.GET_TASK)
            return {"action": "OPEN_TASK", "reason": "打开任务面板"}

        if s.phase == ShimenPhase.GET_TASK:
            if self._has(gs, "师父") and not gs.dialogue_open:
                return {"action": "CLICK_NPC", "target": "师父", "reason": "点击任务追踪中的师父"}
            if self._has(gs, "师门任务"):
                return {"action": "DIALOG_CHOICE", "target": "师门任务", "reason": "选择师门任务"}
            if gs.task_name and "师门" in gs.task_name:
                self.bump(ShimenPhase.RUN)
                s.current_round = max(1, s.current_round)
                return {"action": "NAVIGATE", "target": "师门师父", "reason": "已有师门任务，前往目标"}
            self.bump(ShimenPhase.GET_TASK)
            return {"action": "WAIT", "reason": "等待任务面板识别"}

        if s.phase == ShimenPhase.RUN:
            if gs.dialogue_open or gs.npc_detected:
                self.bump(ShimenPhase.INTERACT)
                if self._has(gs, "师门任务"):
                    return {"action": "DIALOG_CHOICE", "target": "师门任务", "reason": "选择师门任务"}
                return {"action": "INTERACT", "reason": "出现 NPC 对话"}
            if self._has(gs, "师父") and not gs.task_name:
                return {"action": "CLICK_NPC", "target": "师父", "reason": "点击师父"}
            self._call("run", gs)
            self.bump(ShimenPhase.RUN)
            return {"action": "NAVIGATE", "target": "师门师父", "reason": "跑图中"}

        if s.phase == ShimenPhase.INTERACT:
            if self._has(gs, "完成", "报告"):
                self.bump(ShimenPhase.SUBMIT)
                return {"action": "SUBMIT_TASK", "target": "师父", "reason": "任务完成，提交"}
            if self._has(gs, "师门任务"):
                return {"action": "DIALOG_CHOICE", "target": "师门任务", "reason": "选择师门任务"}
            self._call("interact", gs)
            self.bump(ShimenPhase.INTERACT)
            return {"action": "INTERACT", "reason": "等待交互结果"}

        if s.phase == ShimenPhase.SUBMIT:
            self._call("submit", gs)
            ok = self._call("verify", gs)
            self.bump(ShimenPhase.VERIFY if ok else ShimenPhase.RUN)
            return {"action": "SUBMIT_TASK", "target": "师父", "reason": "提交并验证"}

        if s.phase == ShimenPhase.VERIFY:
            if s.current_round >= s.target_rounds:
                self.bump(ShimenPhase.DONE)
                self.set_progress(s.current_round, s.target_rounds)
                self.complete()
                return {"action": "DONE", "reason": f"完成 {s.current_round} 环"}
            self.set_progress(s.current_round, s.target_rounds)
            self.bump(ShimenPhase.RUN)
            return {"action": "NAVIGATE", "reason": f"第 {s.current_round + 1} 环"}

        if s.phase == ShimenPhase.DONE:
            return {"action": "DONE", "reason": "任务已全部完成"}

        return {"action": "RECOVERY", "reason": "需要人工接管"}

    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()
