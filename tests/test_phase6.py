# -*- coding: utf-8 -*-
"""Phase 6 测试: 战斗状态解析/规则策略/分层决策。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from battle.battle_state import BattleParser, BattleState, BattleUnit
from battle.battle_policy import RuleBattlePolicy, HealerPolicy, BattleDecision
from battle.battle_agent import BattleAgent


def test_parse_round_and_hp():
    p = BattleParser()
    bs = p.parse(["战斗", "回合 3", "气血 800/1000", "魔法 400/600"], "师门")
    assert bs.round == 3
    assert bs.player_hp == 800
    assert bs.player_max_hp == 1000
    assert bs.player_mp == 400
    assert bs.task_type == "师门"


def test_parse_enemies():
    p = BattleParser()
    bs = p.parse(["战斗", "敌方 骷髅怪 800", "敌方 僵尸 500"])
    assert len(bs.enemies) >= 1
    assert bs.enemies[0].name != ""


def test_hp_ratio_low_heal():
    bs = BattleState(player_hp=200, player_max_hp=1000,
                     player_mp=500, player_max_mp=600)
    d = RuleBattlePolicy().decide(bs)
    assert d.action == "HEAL"
    assert d.confidence >= 0.9


def test_hp_low_no_mp_defend():
    bs = BattleState(player_hp=100, player_max_hp=1000,
                     player_mp=50, player_max_mp=600)
    d = RuleBattlePolicy().decide(bs)
    assert d.action == "DEFEND"


def test_many_enemies_aoe():
    bs = BattleState(player_hp=800, player_max_hp=1000,
                     player_mp=500, player_max_mp=600)
    for i in range(7):
        bs.enemies.append(BattleUnit(name="怪" + str(i), is_enemy=True))
    d = RuleBattlePolicy().decide(bs)
    assert d.action == "SKILL"
    assert d.skill == "群攻"


def test_safe_auto():
    bs = BattleState(player_hp=900, player_max_hp=1000,
                     player_mp=500, player_max_mp=600)
    bs.enemies.append(BattleUnit(name="怪1", is_enemy=True))
    bs.enemies.append(BattleUnit(name="怪2", is_enemy=True))
    d = RuleBattlePolicy().decide(bs)
    assert d.action == "AUTO"


def test_healer_prefers_team():
    bs = BattleState(player_hp=800, player_max_hp=1000,
                     player_mp=500, player_max_mp=600)
    bs.teammates.append(BattleUnit(name="队友A", hp=200, is_enemy=False))
    d = HealerPolicy().decide(bs)
    assert d.action == "HEAL"


def test_battle_agent_round_trigger():
    """回合不变时不重复决策(§52)。"""
    agent = BattleAgent(role="attacker")
    texts = ["战斗", "回合 1", "气血 900/1000"]
    d1 = agent.decide(texts, "师门")
    d2 = agent.decide(texts, "师门")
    assert d1 == d2  # 同回合复用决策
    # 回合变化 -> 重新决策
    d3 = agent.decide(["战斗", "回合 2", "气血 300/1000", "魔法 500/600"], "师门")
    assert d3.action == "HEAL"


def test_battle_agent_to_dict():
    agent = BattleAgent(role="healer")
    agent.decide(["战斗", "回合 1", "气血 800/1000"], "抓鬼")
    d = agent.to_dict()
    assert d["role"] == "healer"
    assert "battle" in d
    assert "decision" in d
