# -*- coding: utf-8 -*-
"""规则大脑测试。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.brain import RuleBrain
from core.game_state import GameState, GameStatus


def test_battle_decision():
    gs = GameState(account_id="t", status=GameStatus.BATTLE, in_battle=True)
    d = RuleBrain().decide(gs)
    assert d.action == "BATTLE_AUTO"


def test_task_decision():
    gs = GameState(account_id="t", status=GameStatus.CITY, task_name="师门任务",
                   task_progress="第2次")
    d = RuleBrain().decide(gs)
    assert d.action == "SUBMIT_TASK"


def test_unknown_low_confidence():
    gs = GameState(account_id="t", status=GameStatus.UNKNOWN)
    d = RuleBrain().decide(gs)
    assert d.action == "UNKNOWN"
    assert d.confidence < 0.4
