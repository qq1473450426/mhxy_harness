# -*- coding: utf-8 -*-
"""GameState 基础数据结构 (规格书 §6/§12)。

状态机把视觉信息转换成标准状态, LLM 不直接读原始截图。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class GameStatus(str, Enum):
    """游戏状态枚举(规格书 §6)。"""

    UNKNOWN = "UNKNOWN"
    LOGIN = "LOGIN"
    LOADING = "LOADING"
    CITY = "CITY"
    MAP = "MAP"
    MOVING = "MOVING"
    NPC_DIALOG = "NPC_DIALOG"
    TASK_DIALOG = "TASK_DIALOG"
    BATTLE = "BATTLE"
    BATTLE_RESULT = "BATTLE_RESULT"
    TEAM = "TEAM"
    INVENTORY = "INVENTORY"
    TRADE = "TRADE"
    DEATH = "DEATH"
    DISCONNECT = "DISCONNECT"
    ERROR = "ERROR"


@dataclass
class GameState:
    """一个账号在某一时刻的完整状态描述。"""

    account_id: str
    status: GameStatus = GameStatus.UNKNOWN
    # 位置/地图
    map_name: str = ""
    position: Optional[Tuple[int, int]] = None
    # 角色
    hp: Optional[int] = None
    mp: Optional[int] = None
    # 任务
    task_name: str = ""
    task_progress: str = ""
    # 界面
    npc_detected: bool = False
    dialogue_open: bool = False
    dialog_options: List[str] = field(default_factory=list)
    in_battle: bool = False
    battle_round: Optional[int] = None
    team_members: int = 0
    inventory_full: bool = False
    # 原始信息
    dialog_text: str = ""
    ocr_texts: List[str] = field(default_factory=list)
    detail: str = ""
    raw_image: Optional[bytes] = None
    raw_size: Optional[Tuple[int, int]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "account_id": self.account_id,
            "status": self.status.value,
            "map_name": self.map_name,
            "position": list(self.position) if self.position else None,
            "hp": self.hp,
            "mp": self.mp,
            "task_name": self.task_name,
            "task_progress": self.task_progress,
            "npc_detected": self.npc_detected,
            "dialogue_open": self.dialogue_open,
            "dialog_options": self.dialog_options[:6],
            "in_battle": self.in_battle,
            "battle_round": self.battle_round,
            "team_members": self.team_members,
            "inventory_full": self.inventory_full,
            "dialog_text": self.dialog_text[:200],
            "detail": self.detail,
        }
        return d


@dataclass
class AccountState:
    """账号运行时状态(规格书 §12)。"""

    account_id: str
    role: str = "follower"          # leader | follower | support | attacker | healer
    window_title: str = ""
    character_name: str = ""
    level: int = 0
    state: GameStatus = GameStatus.UNKNOWN
    hp: int = 0
    mp: int = 0
    map: str = ""
    task: str = ""
    enabled: bool = True
    # 窗口绑定信息(Phase 1: 由 WindowManager 填充)
    hwnd: Optional[int] = None
    win_rect: Optional[Tuple[int, int, int, int]] = None
    # 运行控制
    running: bool = False
    last_activity: str = ""
    anomaly: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "role": self.role,
            "character_name": self.character_name,
            "level": self.level,
            "state": self.state.value,
            "hp": self.hp,
            "mp": self.mp,
            "map": self.map,
            "task": self.task,
            "enabled": self.enabled,
            "running": self.running,
            "last_activity": self.last_activity,
            "anomaly": self.anomaly,
        }
