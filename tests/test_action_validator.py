# -*- coding: utf-8 -*-
"""Action 安全校验测试(规格书 §41 test_action_validator.py)。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import ActionValidator
from core.brain import Decision
from core.game_state import GameState, GameStatus


def _val(decision, status):
    gs = GameState(account_id="t", status=status)
    return ActionValidator().validate(decision, gs)


def test_risky_action_blocked():
    ok, reason = _val(Decision("SELL", confidence=0.99), GameStatus.CITY)
    assert not ok
    assert "禁止" in reason


def test_battle_forbidden():
    ok, reason = _val(Decision("OPEN_MAP", confidence=0.99), GameStatus.BATTLE)
    assert not ok


def test_low_confidence_blocked():
    ok, reason = _val(Decision("CLICK_NPC", confidence=0.3), GameStatus.CITY)
    assert not ok
    assert "人工" in reason


def test_safe_action_passes():
    ok, reason = _val(Decision("OPEN_TASK", confidence=0.95), GameStatus.CITY)
    assert ok
