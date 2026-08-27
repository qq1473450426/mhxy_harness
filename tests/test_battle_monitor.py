# -*- coding: utf-8 -*-
"""战斗监控器测试(核心逻辑, 不实际点游戏)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.battle_monitor import BattleMonitor
from core.game_state import GameStatus


class _FakeWin:
    x = y = 0
    w = h = 320
    hwnd = 1
    title = "fake"
    def is_valid(self): return True


class _FakeDriver:
    def press(self, key):
        return type("R", (), {"ok": True, "error": None})()


def _m():
    return BattleMonitor(_FakeWin())


def test_ensure_auto_battle():
    m = _m()
    m.driver = _FakeDriver()
    assert m.ensure_auto_battle() is True


def test_not_in_battle():
    m = _m()
    m.observe = lambda: type("GS", (), {"status": GameStatus.CITY, "battle_round": None})()
    r = m.monitor_once(max_wait=1.0)
    assert r["battled"] is False


def test_battle_then_end():
    m = _m()
    m.poll_interval = 0.01
    seq = [GameStatus.BATTLE, GameStatus.BATTLE, GameStatus.CITY]
    def fake_obs():
        s = seq.pop(0) if seq else GameStatus.CITY
        return type("GS", (), {"status": s, "battle_round": 3 if s == GameStatus.BATTLE else None})()
    m.observe = fake_obs
    m.ensure_auto_battle = lambda: True
    r = m.monitor_once(max_wait=5.0)
    assert r["battled"] is True


def test_to_dict():
    m = _m()
    d = m.to_dict()
    assert "total_battles" in d
    assert "rounds" in d
