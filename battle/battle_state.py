# -*- coding: utf-8 -*-
"""战斗状态 (Phase 6, 规格书 §21)。

BattleState:
    round / player_hp / player_mp / enemies / teammates / skill_cd / task_type

由 OCR 战斗界面解析而来, 供战斗策略决策使用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BattleUnit:
    """战斗中的一个单位(敌方或队友)。"""

    name: str = ""
    hp: Optional[int] = None
    is_enemy: bool = True
    is_alive: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "hp": self.hp,
                "is_enemy": self.is_enemy, "is_alive": self.is_alive}


@dataclass
class BattleState:
    """一次战斗的完整状态。"""

    round: int = 1
    player_hp: Optional[int] = None
    player_mp: Optional[int] = None
    player_max_hp: Optional[int] = None
    player_max_mp: Optional[int] = None
    enemies: List[BattleUnit] = field(default_factory=list)
    teammates: List[BattleUnit] = field(default_factory=list)
    skill_cd: Dict[str, int] = field(default_factory=dict)   # 技能 -> 剩余冷却回合
    task_type: str = ""          # 师门/抓鬼/封妖...
    raw_text: str = ""

    # ---------------- 便捷判断 ----------------
    @property
    def enemy_count(self) -> int:
        return sum(1 for e in self.enemies if e.is_alive)

    @property
    def team_count(self) -> int:
        return sum(1 for t in self.teammates if t.is_alive)

    @property
    def hp_ratio(self) -> float:
        if not self.player_max_hp or self.player_max_hp <= 0:
            return 1.0
        return (self.player_hp or 0) / self.player_max_hp

    @property
    def mp_ratio(self) -> float:
        if not self.player_max_mp or self.player_max_mp <= 0:
            return 1.0
        return (self.player_mp or 0) / self.player_max_mp

    # ---------------- 序列化 ----------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "player_hp": self.player_hp, "player_mp": self.player_mp,
            "hp_ratio": round(self.hp_ratio, 2), "mp_ratio": round(self.mp_ratio, 2),
            "enemies": [e.to_dict() for e in self.enemies],
            "teammates": [t.to_dict() for t in self.teammates],
            "enemy_count": self.enemy_count, "team_count": self.team_count,
            "task_type": self.task_type,
        }


class BattleParser:
    """从 OCR 文本解析战斗详情。"""

    # 敌方血量正则: "敌方 骷髅怪 800/1000" 或 "怪物 123"
    _ENEMY_RE = re.compile(r"(?:敌方|怪物|野怪|妖怪|怪)[:：]?\s*([\u4e00-\u9fff]{1,8})\s*(\d+)?\s*/?\s*(\d+)?")
    # 回合正则
    _ROUND_RE = re.compile(r"回合\s*(\d+)")
    # 己方血量: "气血 800/1000" "HP 700/900"
    _HP_RE = re.compile(r"(?:气血|HP|血)[:：]?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
    # 魔法: "魔法 500/600" "MP 400/500"
    _MP_RE = re.compile(r"(?:魔法|MP|法力)[:：]?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)

    def parse(self, texts: List[str], task_type: str = "") -> BattleState:
        """解析 OCR 文本 -> BattleState。"""
        joined = " ".join(texts)
        bs = BattleState(raw_text=joined[:300], task_type=task_type)

        # 回合
        m = self._ROUND_RE.search(joined)
        if m:
            bs.round = int(m.group(1))

        # 血量
        m = self._HP_RE.search(joined)
        if m:
            bs.player_hp = int(m.group(1))
            bs.player_max_hp = int(m.group(2))

        # 魔法
        m = self._MP_RE.search(joined)
        if m:
            bs.player_mp = int(m.group(1))
            bs.player_max_mp = int(m.group(2))

        # 敌方(粗略: 每行一个敌人或 "敌方X个")
        for t in texts:
            m = self._ENEMY_RE.search(t)
            if m and m.group(1):
                bs.enemies.append(BattleUnit(
                    name=m.group(1),
                    hp=int(m.group(2)) if m.group(2) else None,
                    is_enemy=True))
        # 敌方数量描述: "敌方 5 个"
        m = re.search(r"敌方\s*(\d+)\s*个", joined)
        if m and not bs.enemies:
            for i in range(int(m.group(1))):
                bs.enemies.append(BattleUnit(name=f"敌人{i+1}", is_enemy=True))

        return bs
