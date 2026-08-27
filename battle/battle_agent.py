# -*- coding: utf-8 -*-
"""战斗 Agent (Phase 6, 规格书 §21/§22/§52)。

战斗决策分层(不让 LLM 高频运行):
    明显安全情况 -> 规则系统(RuleBattlePolicy)
    复杂情况     -> 模型策略(预留接口)
    完全未知     -> Vision + LLM(事件触发)

决策触发: 按回合触发, 不是每帧(§52)。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .battle_state import BattleParser, BattleState
from .battle_policy import BattleDecision, RuleBattlePolicy, HealerPolicy

logger = logging.getLogger(__name__)


class BattleAgent:
    """战斗决策引擎: 解析 -> 分层决策。"""

    def __init__(self, role: str = "attacker",
                 policy: Optional[RuleBattlePolicy] = None) -> None:
        self.role = role
        self.parser = BattleParser()
        if policy is not None:
            self.policy = policy
        elif role in ("healer", "support"):
            self.policy = HealerPolicy()
        else:
            self.policy = RuleBattlePolicy()
        self._last_round = 0
        self._last_decision: Optional[BattleDecision] = None
        self._last_state: Optional[BattleState] = None
        self._llm: Any = None

    def decide(self, ocr_texts: List[str], task_type: str = "") -> BattleDecision:
        """解析 OCR 并决策。仅在回合变化时重新决策(§52)。"""
        bs = self.parser.parse(ocr_texts, task_type)
        if bs.round == self._last_round and self._last_decision is not None:
            return self._last_decision
        self._last_round = bs.round
        decision = self.policy.decide(bs)
        if decision.action == "AUTO" and bs.enemy_count > 3 and bs.hp_ratio < 0.6:
            decision = self._model_or_llm(bs)
        self._last_decision = decision
        self._last_state = bs
        return decision

    def _model_or_llm(self, bs: BattleState) -> BattleDecision:
        """复杂情况: 模型策略/LLM(预留)。"""
        if self._llm is not None:
            try:
                return self._llm_decide(bs)
            except Exception as e:
                logger.warning("LLM 战斗决策失败: %s, 回退规则", e)
        return BattleDecision("ATTACK", reason="复杂战况未接入高级策略, 普攻",
                              confidence=0.7, via="rule")

    def _llm_decide(self, bs: BattleState) -> BattleDecision:
        """LLM 战斗决策(需配置 LLMClient)。"""
        prompt = ("战斗状态: 回合" + str(bs.round) +
                  " 自身HP " + str(bs.hp_ratio) +
                  " MP " + str(bs.mp_ratio) +
                  " 敌人" + str(bs.enemy_count) + "个" +
                  " 队友" + str(bs.team_count) + "个" +
                  " 任务类型:" + bs.task_type +
                  " 决定动作(ATTACK/SKILL/DEFEND/HEAL/SEAL), 输出JSON")
        data = self._llm.chat_json([{"role": "user", "content": prompt}])
        action = str(data.get("action", "ATTACK")).upper()
        return BattleDecision(action=action, skill=str(data.get("skill", "")),
                              target=str(data.get("target", "")),
                              reason=str(data.get("reason", "")),
                              confidence=float(data.get("confidence", 0.8)),
                              via="llm")

    def bind_llm(self, llm: Any) -> None:
        """绑定 LLMClient(可选)。"""
        self._llm = llm

    @property
    def last_state(self) -> Optional[BattleState]:
        return self._last_state

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "policy": type(self.policy).__name__}
        if self.last_state:
            d["battle"] = self.last_state.to_dict()
        if self._last_decision is not None:
            d["decision"] = self._last_decision.to_dict()
        return d
