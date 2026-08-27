# -*- coding: utf-8 -*-
"""全局 Planner (Phase 5, 规格书 §49/§50)。

1 个全局 Planner + 5 个轻量 State Agent:
- Global Planner 决定整个队伍下一阶段干什么
- Account Agent 负责当前账号如何执行

任务分解: 把共享目标拆成每个账号的具体动作。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .team import TeamState, TeamStatus

logger = logging.getLogger(__name__)


@dataclass
class TeamPlan:
    """一个队伍级的行动计划。"""

    task: str = ""
    phase: str = ""          # PREPARE / RUN / FIGHT / END
    role_actions: Dict[str, str] = field(default_factory=dict)  # 账号 -> 动作
    wait_for: str = ""       # 同步点说明
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"task": self.task, "phase": self.phase,
                "role_actions": self.role_actions, "wait_for": self.wait_for,
                "reason": self.reason}


class GlobalPlanner:
    """队伍全局规划器。"""

    # 任务 -> 阶段模板
    TASK_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
        "抓鬼": [
            {"phase": "PREPARE", "leader": "接取抓鬼任务", "follower": "跟随队长"},
            {"phase": "RUN", "leader": "寻找钟馗", "follower": "跟随移动"},
            {"phase": "FIGHT", "leader": "自动战斗", "follower": "自动战斗"},
            {"phase": "END", "leader": "提交任务", "follower": "等待"},
        ],
        "师门": [
            {"phase": "PREPARE", "leader": "打开任务面板", "follower": "打开任务面板"},
            {"phase": "RUN", "leader": "跑图寻NPC", "follower": "跟随队长"},
            {"phase": "FIGHT", "leader": "自动战斗", "follower": "自动战斗"},
            {"phase": "END", "leader": "提交任务", "follower": "等待"},
        ],
        "封妖": [
            {"phase": "PREPARE", "leader": "组队", "follower": "加入队伍"},
            {"phase": "RUN", "leader": "寻找妖怪", "follower": "跟随队长"},
            {"phase": "FIGHT", "leader": "自动战斗", "follower": "自动战斗"},
        ],
    }

    def __init__(self, team: Optional[TeamState] = None) -> None:
        self.team = team
        self.current_phase_idx = 0
        self.current_task = ""
        self._last_plan: Optional[TeamPlan] = None

    # ---------------- 规划 ----------------
    def plan(self, task: str = "") -> TeamPlan:
        """为队伍规划下一步。返回 TeamPlan。"""
        if self.team is None:
            return TeamPlan(reason="队伍未初始化")
        task = task or self.team.task
        if task not in self.TASK_TEMPLATES:
            return TeamPlan(task=task, reason="未知任务, 按通用模板")

        steps = self.TASK_TEMPLATES[task]
        # 阶段推进
        if task != self.current_task:
            self.current_task = task
            self.current_phase_idx = 0
        elif self.current_phase_idx < len(steps) - 1:
            self.current_phase_idx += 1

        step = steps[self.current_phase_idx]
        phase = step.get("phase", "RUN")
        role_actions = {}
        for member in self.team.members:
            role = "leader" if member == self.team.leader else "follower"
            role_actions[member] = step.get(role, step.get("follower", "等待"))

        plan = TeamPlan(
            task=task,
            phase=phase,
            role_actions=role_actions,
            wait_for=f"等待全队完成阶段 {phase}",
            reason=f"队伍任务 {task} 第 {self.current_phase_idx+1} 阶段: {phase}",
        )
        self._last_plan = plan
        return plan

    def to_dict(self) -> Dict[str, Any]:
        if self._last_plan is not None:
            return self._last_plan.to_dict()
        return TeamPlan().to_dict()
