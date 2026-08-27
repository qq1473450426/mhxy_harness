# -*- coding: utf-8 -*-
"""抓鬼任务状态机 (Phase 7, 规格书 §36/§37)。

流程:
    组队 -> 找钟馗接任务 -> 跑图找鬼 -> 战斗 -> 返回交任务 -> 下一环

状态:
    INIT -> TEAM -> GET_TASK -> RUN -> BATTLE -> SUBMIT -> VERIFY -> (下一环) | DONE
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


class GuiguaPhase(str, Enum):
    INIT = "INIT"
    TEAM = "TEAM"              # 组队
    GET_TASK = "GET_TASK"      # 找钟馗接任务
    RUN = "RUN"                # 跑图找鬼
    BATTLE = "BATTLE"          # 战斗
    SUBMIT = "SUBMIT"          # 交任务
    VERIFY = "VERIFY"          # 验证环数
    DONE = "DONE"
    RECOVERY = "RECOVERY"


@dataclass
class GuiguaState:
    phase: GuiguaPhase = GuiguaPhase.INIT
    current_round: int = 0
    target_rounds: int = 10
    same_phase_count: int = 0
    start_time: float = field(default_factory=time.time)
    max_minutes: int = 60

    def stuck(self) -> bool:
        return self.same_phase_count >= 5

    def timeout(self) -> bool:
        return (time.time() - self.start_time) / 60.0 > self.max_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {"phase": self.phase.value, "round": self.current_round,
                "target_rounds": self.target_rounds}


class GuiguaTask(Task):
    """抓鬼任务(五开: 队长接任务, 全队跟随战斗)。"""

    def __init__(self, max_rounds: int = 10, max_minutes: int = 60) -> None:
        super().__init__(name="抓鬼", max_runtime=max_minutes * 60)
        self.state = GuiguaState(target_rounds=max_rounds, max_minutes=max_minutes)
        self.set_progress(0, max_rounds)
        self._hooks: Dict[str, Any] = {}

    def bind(self, **hooks) -> None:
        self._hooks.update(hooks)

    def _call(self, name: str, *args, **kwargs) -> Any:
        hook = self._hooks.get(name)
        if hook is None:
            logger.warning("未绑定钩子 %s", name)
            return False
        return hook(*args, **kwargs)

    def _bump(self, new_phase: GuiguaPhase) -> None:
        if new_phase == self.state.phase:
            self.state.same_phase_count += 1
        else:
            self.state.same_phase_count = 0
            self.state.phase = new_phase

    def step(self, gs: GameState) -> Dict[str, Any]:
        """根据游戏状态推进抓鬼任务。"""
        s = self.state
        if s.stuck():
            s.phase = GuiguaPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "抓鬼阶段无进展"}
        if s.timeout():
            s.phase = GuiguaPhase.RECOVERY
            return {"action": "RECOVERY", "reason": "抓鬼超时"}

        # 战斗优先
        if gs.in_battle or gs.status == GameStatus.BATTLE:
            self._bump(GuiguaPhase.BATTLE)
            return {"action": "BATTLE_AUTO", "reason": "战斗中, 自动战斗"}

        # 异常状态
        if gs.status in (GameStatus.DEATH, GameStatus.DISCONNECT):
            s.phase = GuiguaPhase.RECOVERY
            return {"action": "RECOVERY", "reason": f"异常 {gs.status.value}"}

        if s.phase == GuiguaPhase.INIT:
            self._bump(GuiguaPhase.TEAM)
            return {"action": "JOIN_TEAM", "reason": "组队准备"}

        if s.phase == GuiguaPhase.TEAM:
            # 队伍就绪 -> 接任务
            if gs.team_members > 0 or "队长" in gs.dialog_text:
                self._bump(GuiguaPhase.GET_TASK)
                return {"action": "NAVIGATE", "target": "钟馗", "reason": "找钟馗接任务"}
            self._call("team")
            self._bump(GuiguaPhase.TEAM)
            return {"action": "JOIN_TEAM", "reason": "组队中"}

        if s.phase == GuiguaPhase.GET_TASK:
            if "钟馗" in gs.dialog_text or gs.task_name == "抓鬼":
                self._bump(GuiguaPhase.RUN)
                s.current_round += 1
                return {"action": "NAVIGATE", "target": "鬼", "reason": "寻找鬼怪"}
            self._call("get_task")
            self._bump(GuiguaPhase.GET_TASK)
            return {"action": "ACCEPT_TASK", "reason": "接取抓鬼任务"}

        if s.phase == GuiguaPhase.RUN:
            if gs.dialog_open or gs.npc_detected:
                self._bump(GuiguaPhase.BATTLE)
                return {"action": "BATTLE_AUTO", "reason": "遇到鬼, 进入战斗"}
            self._call("run")
            self._bump(GuiguaPhase.RUN)
            return {"action": "NAVIGATE", "target": "鬼", "reason": "跑图中"}

        if s.phase == GuiguaPhase.BATTLE:
            if not gs.in_battle:
                self._bump(GuiguaPhase.SUBMIT)
                return {"action": "SUBMIT_TASK", "reason": "战斗结束, 交任务"}
            self._bump(GuiguaPhase.BATTLE)
            return {"action": "BATTLE_AUTO", "reason": "战斗中"}

        if s.phase == GuiguaPhase.SUBMIT:
            self._call("submit")
            ok = self._call("verify")
            self._bump(GuiguaPhase.VERIFY if ok else GuiguaPhase.RUN)
            return {"action": "SUBMIT_TASK", "reason": "提交并验证"}

        if s.phase == GuiguaPhase.VERIFY:
            if s.current_round >= s.target_rounds:
                self._bump(GuiguaPhase.DONE)
                self.set_progress(s.current_round, s.target_rounds)
                self.complete()
                return {"action": "DONE", "reason": f"完成 {s.current_round} 环"}
            self.set_progress(s.current_round, s.target_rounds)
            self._bump(GuiguaPhase.RUN)
            return {"action": "NAVIGATE", "reason": f"第 {s.current_round+1} 环"}

        if s.phase == GuiguaPhase.DONE:
            self._bump(GuiguaPhase.DONE)
            return {"action": "DONE", "reason": "抓鬼已完成"}

        self._bump(GuiguaPhase.RECOVERY)
        return {"action": "RECOVERY", "reason": "需要人工接管"}

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["guigua"] = self.state.to_dict()
        return d
