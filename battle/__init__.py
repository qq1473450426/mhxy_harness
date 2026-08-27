"""battle 包: 战斗 AI (Phase 6)。

分层决策(规格书 §22):
- 明显安全情况 -> 规则系统(RuleBattlePolicy)
- 复杂情况     -> 模型策略(预留)
- 完全未知     -> Vision + LLM

决策触发: 按回合触发(§52), 不让 LLM 高频运行。
"""
from .battle_state import BattleState, BattleUnit, BattleParser  # noqa: F401
from .battle_policy import BattleDecision, RuleBattlePolicy, HealerPolicy  # noqa: F401
from .battle_agent import BattleAgent  # noqa: F401
