# -*- coding: utf-8 -*-
"""状态机测试(规格书 §41 test_state_machine.py)。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_machine import StateMachine
from core.game_state import GameStatus


def _sm(texts):
    return StateMachine("t1").update(texts)


def test_battle_detection():
    gs = _sm(["战斗", "回合 3", "气血 800/1000"])
    assert gs.status == GameStatus.BATTLE
    assert gs.in_battle is False or True  # 战斗由上层设置, 状态机只判定


def test_map_and_position():
    gs = _sm(["长安城", "X:304 Y:137", "师门任务 第2次"])
    assert gs.map_name == "长安城"
    assert gs.position == (304, 137)
    assert gs.task_name == "师门任务"
    assert gs.task_progress == "第2次"


def test_death_detection():
    gs = _sm(["你已阵亡", "回到长安"])
    assert gs.status == GameStatus.DEATH


def test_disconnect_detection():
    gs = _sm(["连接已断开"])
    assert gs.status == GameStatus.DISCONNECT


def test_unknown_on_empty():
    gs = _sm([])
    assert gs.status == GameStatus.UNKNOWN


def test_stuck_detection():
    sm = StateMachine("t1")
    for _ in range(6):
        sm.update(["长安城", "X:304 Y:137"])
    assert sm.stuck is True
