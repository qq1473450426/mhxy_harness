# -*- coding: utf-8 -*-
"""决策大脑接口 (Phase 3 完整实现, Phase 1 提供规则版)。

分层大脑(规格书 §5/§23):
- 第一层: 快速视觉模型(Seeing) -> vision/
- 第二层: 状态机(Understanding State) -> core/state_machine.py
- 第三层: 本地 LLM(Reasoning) -> 本模块接口

Phase 1 使用 RuleBrain(规则决策), Phase 3 接入本地 LLM。
LLM 不允许直接输出坐标(规格书 §8), 只输出语义 Action。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .game_state import GameState

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """大脑的一次决策输出(规格书 §45 结构化 JSON)。"""

    action: str                 # 语义 Action 名, 如 NAVIGATE / CLICK_NPC
    target: str = ""            # 目标, 如 "师门师父"
    reason: str = ""
    confidence: float = 0.5
    need_knowledge: bool = False
    need_replan: bool = False
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "confidence": self.confidence,
            "need_knowledge": self.need_knowledge,
            "need_replan": self.need_replan,
            "params": self.params,
        }


class Brain(ABC):
    """决策大脑抽象。"""

    @abstractmethod
    def decide(self, state: GameState, goal: str = "", knowledge: Optional[str] = None) -> Decision:
        """根据当前状态+目标+知识库输出决策。"""


class RuleBrain(Brain):
    """Phase 1 规则决策: 快速、稳定、可预测。

    规则(规格书 §22): 明显安全情况用规则系统, 复杂情况 Phase 3 交给 LLM。
    """

    def decide(self, state: GameState, goal: str = "", knowledge: Optional[str] = None) -> Decision:
        s = state.status.value
        if state.in_battle or s == "BATTLE":
            return Decision("BATTLE_AUTO", reason="战斗中, 开启自动战斗", confidence=0.95)
        if s == "DEATH":
            return Decision("RECOVER", reason="角色死亡, 需要恢复", confidence=0.8,
                            need_replan=True)
        if s == "DISCONNECT":
            return Decision("RECONNECT", reason="掉线, 需要重连", confidence=0.9,
                            need_replan=True)
        if s == "LOGIN":
            return Decision("WAIT", reason="登录界面, 等待人工或自动登录", confidence=0.5)
        if s == "LOADING":
            return Decision("WAIT", reason="加载中", confidence=0.9)
        if s == "NPC_DIALOG" or s == "TASK_DIALOG":
            return Decision("DIALOG_CHOICE", reason="对话框出现, 选择下一步",
                            confidence=0.85, need_knowledge=True)
        if state.task_name:
            if state.task_progress:
                return Decision("SUBMIT_TASK", target="师门师父",
                                reason=f"任务完成待提交: {state.task_progress}",
                                confidence=0.85, need_knowledge=True)
            return Decision("OPEN_TASK", reason=f"当前任务: {state.task_name}",
                            confidence=0.8, need_knowledge=True)
        if s in ("CITY", "MAP"):
            return Decision("IDLE", reason="场景内待命", confidence=0.9)
        return Decision("UNKNOWN", reason="状态不确定, 停止并人工接管",
                        confidence=0.3, need_knowledge=True, need_replan=True)


class LLMBrain(Brain):
    """Phase 3: 本地 LLM 决策大脑(RAG 增强)。

    流程(规格书 §7/§45/§46):
        state + goal + (knowledge 若 need) -> LLM -> 结构化 JSON Decision

    Confidence 系统(§46):
        >= 0.9 自动执行
        0.7~0.9 增加视觉检查
        < 0.7 重新查询知识库或重新观察
        < 0.4 人工确认模式
    """

    # 系统提示(规格书 §44)
    SYSTEM_PROMPT = (
        "你不是鼠标机器人。你是《梦幻西游》游戏任务规划器。",
        "你只能根据: 1.当前游戏状态 2.视觉信息 3.游戏知识 4.历史经验, 制定下一步 Action。",
        "禁止编造游戏状态。如果不确定, 返回 UNKNOWN。如果当前动作失败, 重新规划。",
        "禁止连续执行高风险动作。",
        "输出必须是 JSON 对象, 格式: {\"reason\": 理由, \"action\": {\"type\": 动作名, \"target\": 目标}, \"confidence\": 0~1, \"need_knowledge\": 布尔, \"need_replan\": 布尔}",
        "动作名只能从以下选择: MOVE, CLICK, DBL_CLICK, RIGHT_CLICK, TYPE, PRESS_KEY, WAIT,",
        "SELECT_NPC, SELECT_TARGET, USE_ITEM, USE_SKILL, ATTACK, DEFEND, ESC, ENTER,",
        "OPEN_TASK, OPEN_MAP, OPEN_INVENTORY, ACCEPT_TASK, SUBMIT_TASK, FOLLOW_TEAM,",
        "JOIN_TEAM, LEAVE_TEAM, TRADE, BUY, SELL, REST, RECOVER, BATTLE_AUTO, IDLE, UNKNOWN",
    )

    def __init__(self, llm: Optional[Any] = None,
                 retriever: Optional[Any] = None) -> None:
        """llm: LLMClient; retriever: knowledge.retriever.Retriever"""
        self.llm = llm
        self.retriever = retriever
        self._last_knowledge: str = ""

    def _build_messages(self, state: GameState, goal: str,
                        knowledge: Optional[str]) -> List[Dict[str, str]]:
        state_desc = (
            f"状态: {state.status.value} | 地图: {state.map_name or '未知'} | "
            f"位置: {state.position if state.position else '未知'} | "
            f"任务: {state.task_name or '无'} {state.task_progress} | "
            f"战斗: {state.in_battle} | 对话框: {state.dialogue_open} | "
            f"NPC: {state.npc_detected} | 队伍: {state.team_members}人 | "
            f"背包满: {state.inventory_full}"
        )
        if state.dialog_text:
            state_desc += f"\n画面文字: {state.dialog_text[:300]}"
        msg = f"目标: {goal}\n{state_desc}"
        if knowledge:
            msg += f"\n\n知识库参考:\n{knowledge[:2000]}"
        return [
            {"role": "system", "content": "\n".join(self.SYSTEM_PROMPT)},
            {"role": "user", "content": msg},
        ]

    def decide(self, state: GameState, goal: str = "",
               knowledge: Optional[str] = None) -> Decision:
        """LLM 决策。knowledge 为 None 且 need_knowledge 时自动检索。"""
        if self.llm is None:
            logger.warning("LLMBrain 未配置 LLM, 回退规则决策")
            return RuleBrain().decide(state, goal)
        try:
            data = self.llm.chat_json(self._build_messages(state, goal, knowledge))
        except Exception as e:
            logger.warning("LLM 决策失败(%s), 回退规则决策", e)
            return RuleBrain().decide(state, goal)

        # 解析结构化输出(规格书 §45)
        action_data = data.get("action", {}) or {}
        action_type = str(action_data.get("type", "UNKNOWN")).upper()
        conf = float(data.get("confidence", 0.5))
        need_knowledge = bool(data.get("need_knowledge", False))
        need_replan = bool(data.get("need_replan", False))
        # 动作名校验: 只允许白名单
        if action_type not in ACTION_WHITELIST:
            action_type = "UNKNOWN"
        decision = Decision(
            action=action_type,
            target=str(action_data.get("target", "")),
            reason=str(data.get("reason", "")),
            confidence=conf,
            need_knowledge=need_knowledge,
            need_replan=need_replan,
        )

        # Confidence 处理(§46): need_knowledge 且无知识 -> 自动检索
        if need_knowledge and self.retriever is not None:
            query = goal or state.task_name or state.status.value
            self._last_knowledge = self.retriever.retrieve_text(query, top_k=3)
            decision.params["knowledge"] = self._last_knowledge[:500]
        return decision

    @property
    def last_knowledge(self) -> str:
        return self._last_knowledge


ACTION_WHITELIST = {
    "MOVE", "CLICK", "DBL_CLICK", "RIGHT_CLICK", "TYPE", "PRESS_KEY", "WAIT",
    "SELECT_NPC", "SELECT_TARGET", "USE_ITEM", "USE_SKILL", "ATTACK", "DEFEND",
    "ESC", "ENTER", "OPEN_TASK", "OPEN_MAP", "OPEN_INVENTORY", "ACCEPT_TASK",
    "SUBMIT_TASK", "FOLLOW_TEAM", "JOIN_TEAM", "LEAVE_TEAM", "TRADE", "BUY",
    "SELL", "REST", "RECOVER", "BATTLE_AUTO", "IDLE", "UNKNOWN",
}