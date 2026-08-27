# -*- coding: utf-8 -*-
"""封妖任务状态机 (Phase 7)。

流程:
    组队 -> 找妖怪 -> 战斗(封印/击杀) -> 下一处 -> 完成

状态:
    INIT -> TEAM -> RUN -> BATTLE -> VERIFY -> (下一处) | DONE
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from core.game_state import GameState, GameStatus
from .base import Task

logger = logging.getLogger(__name__)


class FengyaoPhase(str, Enum):
    INIT = "INIT"
    TEAM = "TEAM"
    RUN = "RUN"
    BATTLE = "BATTLE"
    VERIFY = "VERIFY"
    DONE = "DONE"
    RECOVERY = "RECOVERY"


@dataclass
class FengyaoState:
    phase: FengyaoPhase = FengyaoPhase.INIT
    cleared: int = 0
    target: int = 5
    same_phase_count: int = 0
    start_time: float = field(default_factory=time.time)
    max_minutes: int = 60

    def stuck(self) -> bool:
        return self.same_phase_count >= 5

    def timeout(self) -> bool:
        return (time.time() - self.start_time) / 60.0 > self.max_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {"phase": self.phase.value, "cleared": self.cleared, "target": self.target}


class FengyaoTask(Task):
    """封妖任务(五开组队)。"""

    def __init__(self, target: int = 5, max_minutes: int = 60) -> None:
        super().__init__(name="封妖", max_runtime=max_minutes * 60)
        self.state = FengyaoState(target=target, max_minutes=max_minutes)
        self.set_progress(0, target)
        self._hooks: Dict[str, Any] = {}

    def bind(self, **hooks) -> None:
        self._hooks.update(hooks)

    def _call(self, name: str, *args, **kwargs) -> Any:
        hook = self._hooks.get(name)
        if hook is None:
            logger.warning("未绑定钩子 %s", name)
            return False
        return hook(*args, **kwargs)

    def _bump(self, new_phase: FengyaoPhase) -> None:
        if new_phase == self.state.phase:
            self.state.same_phase_count += 1
        else:
            self.state.same_phase_count = 0
            self.state.phase = new_phase

    def step(self, gs: GameState) -> Dict[str, Any]:
        s = self.state
        if s.stuck():
            s.phase = FengyaoPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "封妖阶段无进展"}
        if s.timeout():
            s.phase = FengyaoPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "封妖超时"}

        if gs.in_battle or gs.status == GameStatus.BATTLE:
            self._bump(FengyaoPhase.BATTLE)
            return {"action": "BATTLE_AUTO", "reason": "战斗中, 自动战斗"}

        if gs.status in (GameStatus.DEATH, GameStatus.DISCONNECT):
            s.phase = FengyaoPhase.RECOVERY
            return {"action": "RECOVERY", "reason": f"异常 {gs.status.value}"}

        if s.phase == FengyaoPhase.INIT:
            self._bump(FengyaoPhase.TEAM)
            return {"action": "JOIN_TEAM", "reason": "组队准备"}

        if s.phase == FengyaoPhase.TEAM:
            if gs.team_members > 0 or "队长" in gs.dialog_text:
                self._bump(FengyaoPhase.RUN)
                return {"action": "NAVIGATE", "target": "妖怪", "reason": "寻找妖怪"}
            self._call("team")
            self._bump(FengyaoPhase.TEAM)
            return {"action": "JOIN_TEAM", "reason": "组队中"}

        if s.phase == FengyaoPhase.RUN:
            if gs.dialog_open or gs.npc_detected:
                self._bump(FengyaoPhase.BATTLE)
                return {"action": "BATTLE_AUTO", "reason": "遇到妖怪"}
            self._call("run")
            self._bump(FengyaoPhase.RUN)
            return {"action": "NAVIGATE", "target": "妖怪", "reason": "跑图中"}

        if s.phase == FengyaoPhase.BATTLE:
            if not gs.in_battle:
                self.state.cleared += 1
                self.set_progress(self.state.cleared, self.state.target)
                self._bump(FengyaoPhase.VERIFY)
                return {"action": "VERIFY", "reason": f"封妖 {self.state.cleared}/{self.state.target}"}
            self._bump(FengyaoPhase.BATTLE)
            return {"action": "BATTLE_AUTO", "reason": "战斗中"}

        if s.phase == FengyaoPhase.VERIFY:
            if self.state.cleared >= self.state.target:
                self._bump(FengyaoPhase.DONE)
                self.complete()
                return {"action": "DONE", "reason": f"封妖完成 {self.state.cleared} 处"}
            self._bump(FengyaoPhase.RUN)
            return {"action": "NAVIGATE", "reason": f"下一处 ({self.state.cleared}/{self.state.target})"}

        if s.phase == FengyaoPhase.DONE:
            self._bump(FengyaoPhase.DONE)
            return {"action": "DONE", "reason": "封妖已完成"}

        self._bump(FengyaoPhase.RECOVERY)
        return {"action": "RECOVERY", "reason": "需要人工接管"}

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["fengyao"] = self.state.to_dict()
        return d
