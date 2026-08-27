# -*- coding: utf-8 -*-
"""状态机扩充测试(对话框选项/战斗详情/队伍)。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_machine import StateMachine
from core.game_state import GameStatus


def test_dialog_options():
    gs = StateMachine("t").update(
        ["请选择", "接受任务", "提交任务", "取消"])
    assert gs.dialogue_open is True
    assert any("接受任务" in o for o in gs.dialog_options)
    assert any("提交任务" in o for o in gs.dialog_options)


def test_battle_round():
    gs = StateMachine("t").update(["战斗", "回合 5", "气血 700/1000"])
    assert gs.status == GameStatus.BATTLE
    assert gs.in_battle is True
    assert gs.battle_round == 5


def test_team_members():
    gs = StateMachine("t").update(["队伍 3/5", "长安城"])
    assert gs.team_members == 3


def test_inventory_full():
    gs = StateMachine("t").update(["背包已满", "长安城"])
    assert gs.inventory_full is True


def test_npc_detected():
    gs = StateMachine("t").update(["听说你需要帮忙"])
    assert gs.npc_detected is True
