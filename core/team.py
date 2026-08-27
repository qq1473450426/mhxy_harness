# -*- coding: utf-8 -*-
"""队伍状态模型 (Phase 5, 规格书 §48)。

TeamState: 五开全局状态
    leader / members / team_ready / task / shared_goal

五开不是五个独立机器人(§11):
    五个账号共享一个任务目标, 协调器统一分配角色。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TeamStatus(str, Enum):
    """队伍整体状态。"""

    IDLE = "IDLE"                # 待命
    FORMING = "FORMING"          # 组队中
    READY = "READY"              # 队伍就绪
    TASKING = "TASKING"          # 执行任务中
    SYNCING = "SYNCING"          # 同步等待中
    ERROR = "ERROR"              # 异常


@dataclass
class TeamState:
    """五开队伍全局状态(规格书 §48)。"""

    leader: str = ""                      # 队长账号 id
    members: List[str] = field(default_factory=list)  # 全体成员(含队长)
    status: TeamStatus = TeamStatus.IDLE
    task: str = ""                        # 当前任务, 如 "抓鬼"
    shared_goal: str = ""                 # 共享目标, 如 "完成第10环"
    team_ready: bool = False
    backup_leader: str = ""               # 备用队长(§13)
    sync_waiting: Dict[str, bool] = field(default_factory=dict)  # 账号 -> 是否已同步

    # ---------------- 角色 ----------------
    def set_leader(self, account_id: str) -> None:
        self.leader = account_id
        if account_id not in self.members:
            self.members.append(account_id)

    def add_member(self, account_id: str) -> None:
        if account_id not in self.members:
            self.members.append(account_id)
        self.sync_waiting[account_id] = False

    def remove_member(self, account_id: str) -> None:
        if account_id in self.members:
            self.members.remove(account_id)
        self.sync_waiting.pop(account_id, None)
        if self.leader == account_id:
            # 队长掉线 -> 自动切换备用队长(§13)
            self._promote_backup()

    def _promote_backup(self) -> None:
        """队长掉线时提升备用队长。"""
        if self.backup_leader and self.backup_leader in self.members:
            self.leader = self.backup_leader
        elif self.members:
            self.leader = self.members[0]

    # ---------------- 同步机制(§14) ----------------
    def mark_synced(self, account_id: str) -> None:
        self.sync_waiting[account_id] = True

    def reset_sync(self) -> None:
        self.sync_waiting = {m: False for m in self.members}

    def all_synced(self) -> bool:
        """所有在线成员是否都已同步。"""
        return bool(self.members) and all(self.sync_waiting.get(m, False) for m in self.members)

    # ---------------- 序列化 ----------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "leader": self.leader,
            "members": list(self.members),
            "status": self.status.value,
            "task": self.task,
            "shared_goal": self.shared_goal,
            "team_ready": self.team_ready,
            "backup_leader": self.backup_leader,
            "synced": sum(1 for v in self.sync_waiting.values() if v),
            "total": len(self.members),
        }
