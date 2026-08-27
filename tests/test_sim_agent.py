# -*- coding: utf-8 -*-
"""模拟模式 Agent Loop 端到端测试(规格书 §42 MockGame)。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sim import MockGame
from core.state_machine import StateMachine


def test_mock_observe():
    sim = MockGame()
    screen = sim.observe()
    assert any("长安城" in t for t in screen.texts)
    assert any("师门任务" in t for t in screen.texts)


def test_mock_battle_rounds():
    sim = MockGame()
    sim.in_battle = True
    s1 = sim.observe()
    r1 = [t for t in s1.texts if "回合" in t][0]
    sim.act("BATTLE_AUTO")
    assert sim.in_battle is False


def test_agent_loop_sim():
    from core.account import Account
    from core.agent import GameAgent

    settings = {"logging": {"dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"), "level": "WARNING"}}
    acc_cfg = {"id": "sim_01", "role": "leader", "enabled": True, "window_title": "SIM"}
    account = Account(acc_cfg, settings)
    account.win = type("W", (), {"hwnd": 1, "title": "SIM", "x": 0, "y": 0, "w": 320, "h": 240,
                                 "is_valid": lambda self: True})()
    sim = MockGame()

    class _SimAgent(GameAgent):
        def observe(self):
            s = sim.observe()
            return self.account.sm.update(s.texts, s.render(), s.size)

        def act(self, decision, gs):
            sim.act(decision.action)
            return type("AR", (), {"ok": True, "desc": decision.action, "error": None})()

    agent = _SimAgent(account, tick_seconds=0.01)
    agent.run(goal="完成师门任务", max_steps=3)
    assert not agent.running
    assert account.state.last_activity != ""
