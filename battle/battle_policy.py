# -*- coding: utf-8 -*-
"""战斗策略 (Phase 6, 规格书 §21/§22)。

分层决策:
    明显安全情况 -> 规则系统(本模块)
    复杂情况     -> 模型策略(Phase 6+)
    完全未知     -> Vision + LLM

规则策略根据: 自身血量/蓝量/队友血量/怪物数量/技能冷却/任务类型
决定: 普通攻击/技能/防御/治疗/封印/保护/召唤
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .battle_state import BattleState

logger = logging.getLogger(__name__)


@dataclass
class BattleDecision:
    """一次战斗回合的决策。"""

    action: str = "ATTACK"
    skill: str = ""
    target: str = ""
    reason: str = ""
    confidence: float = 0.9
    via: str = "rule"

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action, "skill": self.skill, "target": self.target,
                "reason": self.reason, "confidence": self.confidence, "via": self.via}


class RuleBattlePolicy:
    """规则战斗策略: 快速、稳定、可预测。"""

    HEAL_THRESHOLD = 0.35
    MANA_SAVE_THRESHOLD = 0.25
    ENEMY_DANGER = 6

    def decide(self, bs: BattleState) -> BattleDecision:
        """根据战斗状态返回决策。"""
        hp_pct = int(bs.hp_ratio * 100)
        mp_pct = int(bs.mp_ratio * 100) if bs.player_mp is not None else 100

        # 1. 生命危险 -> 防御/治疗
        if bs.hp_ratio <= self.HEAL_THRESHOLD:
            if bs.player_mp is not None and bs.mp_ratio >= 0.3:
                return BattleDecision("HEAL", skill="回血", target="自己",
                                      reason="血量低(" + str(hp_pct) + "%), 使用治疗",
                                      confidence=0.95)
            return BattleDecision("DEFEND", target="自己",
                                  reason="血量低且蓝不足, 防御保命",
                                  confidence=0.9)

        # 2. 敌人过多 -> 群攻技能(若有蓝)
        if bs.enemy_count >= self.ENEMY_DANGER:
            if bs.player_mp is not None and bs.mp_ratio >= 0.4:
                return BattleDecision("SKILL", skill="群攻", target="全体",
                                      reason="敌人" + str(bs.enemy_count) + "个, 使用群攻",
                                      confidence=0.9)
            return BattleDecision("ATTACK", reason="敌人多但蓝不足, 普攻",
                                  confidence=0.85)

        # 3. 低蓝 -> 节省(普攻)
        if bs.player_mp is not None and bs.mp_ratio <= self.MANA_SAVE_THRESHOLD:
            return BattleDecision("ATTACK", reason="蓝量低, 普攻省蓝",
                                  confidence=0.9)

        # 4. 单个强敌 -> 技能
        if bs.enemy_count == 1:
            return BattleDecision("SKILL", skill="单体攻击", target="敌方首领",
                                  reason="单目标, 使用单体技能",
                                  confidence=0.85)

        # 5. 默认: 自动战斗
        return BattleDecision("AUTO", reason="情况安全, 自动战斗",
                              confidence=0.95)


class HealerPolicy(RuleBattlePolicy):
    """治疗辅助角色策略: 优先保队友。"""

    def decide(self, bs: BattleState) -> BattleDecision:
        # 队友血量低 -> 治疗队友(若自身状态允许)
        if bs.hp_ratio > 0.5:
            low_teammates = [t for t in bs.teammates if t.is_alive and t.hp is not None]
            if low_teammates and bs.mp_ratio >= 0.3:
                return BattleDecision("HEAL", skill="群体治疗", target="队友",
                                      reason="队友需要治疗", confidence=0.9)
        return super().decide(bs)
