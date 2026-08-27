# -*- coding: utf-8 -*-
"""Phase 8 测试: 长期记忆/经验学习/Replay。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import LongTermMemory
from core.replay import ReplayRecorder, ReplayPlayer


def _db_path():
    return os.path.join(tempfile.gettempdir(), "mhxy_test_mem.db")


def _fresh_memory():
    p = _db_path()
    if os.path.exists(p):
        os.remove(p)
    return LongTermMemory(p)


def test_memory_record_and_stats():
    m = _fresh_memory()
    m.record_action("师门", "NAVIGATE", True, 25.0)
    m.record_action("师门", "NAVIGATE", True, 20.0)
    m.record_action("师门", "NAVIGATE", False, 90.0)
    stats = m.task_stats("师门")
    assert len(stats) == 1
    assert stats[0]["success"] == 2
    assert stats[0]["fail"] == 1
    m.close()


def test_memory_best_action():
    """§20: 学习最优动作。"""
    m = _fresh_memory()
    m.record_action("抓鬼", "BATTLE_AUTO", True, 5.0)
    m.record_action("抓鬼", "BATTLE_AUTO", True, 4.0)
    m.record_action("抓鬼", "NAVIGATE", False, 80.0)
    assert m.best_action("抓鬼") == "BATTLE_AUTO"
    m.close()


def test_memory_npc_and_price():
    m = _fresh_memory()
    m.record_npc("钟馗", "长安城", 155, 110)
    npc = m.get_npc("钟馗")
    assert npc is not None
    assert npc["map"] == "长安城"
    assert npc["x"] == 155
    # 更新位置(第二次发现)
    m.record_npc("钟馗", "长安城", 160, 115)
    npc2 = m.get_npc("钟馗")
    assert npc2["x"] == 160
    assert npc2["found"] == 2
    # 价格
    m.record_price("金柳露", 8000)
    m.record_price("金柳露", 9000)
    price = m.get_price("金柳露")
    assert price["min"] == 8000
    assert price["max"] == 9000
    assert price["samples"] == 2
    m.close()


def test_memory_runs():
    m = _fresh_memory()
    m.record_run("师门", 20, "COMPLETED", 1800, "全部完成")
    m.record_run("抓鬼", 10, "FAILED", 600, "掉线")
    runs = m.recent_runs()
    assert len(runs) == 2
    assert runs[0]["task"] in ("师门", "抓鬼")
    m.close()


def test_memory_stats():
    m = _fresh_memory()
    m.record_action("师门", "NAVIGATE", True, 10.0)
    m.record_npc("钟馗", "长安城", 1, 2)
    s = m.stats()
    assert s["task_experience"] >= 1
    assert s["npc_locations"] >= 1
    m.close()


def test_replay_record_and_play():
    """§43: 记录并回放。"""
    rdir = os.path.join(tempfile.gettempdir(), "mhxy_test_replay")
    import shutil
    if os.path.exists(rdir):
        shutil.rmtree(rdir)
    rec = ReplayRecorder(rdir, "acc1")
    n1 = rec.record_step(b"\x40\x40\x40" * (100 * 100),
                         {"status": "CITY", "map": "长安城", "_size": [100, 100]},
                         {"action": "OPEN_TASK", "confidence": 0.9},
                         {"validated": True, "action_result": {"ok": True}})
    n2 = rec.record_step(None,
                         {"status": "CITY", "map": "长安城"},
                         {"action": "IDLE"},
                         {"validated": True})
    assert n1 == 1 and n2 == 2
    rec.finish("completed", "测试")

    # 回放
    player = ReplayPlayer(rec.path)
    steps = player.list_steps()
    assert steps == [1, 2]
    meta = player.meta()
    assert meta["status"] == "completed"
    step1 = player.get_step(1)
    assert step1["state"]["map"] == "长安城"
    assert "screenshot" in step1
    assert step1["action"]["decision"]["action"] == "OPEN_TASK"
    shutil.rmtree(rdir)


def test_agent_with_memory_and_replay():
    """Agent 集成: 模拟模式 + 记忆 + Replay 闭环。"""
    from core.account import Account
    from core.agent import GameAgent
    from core.sim import MockGame
    from core.memory import LongTermMemory
    from core.replay import ReplayRecorder
    import shutil

    p = _db_path()
    if os.path.exists(p):
        os.remove(p)
    mem = LongTermMemory(p)
    rdir = os.path.join(tempfile.gettempdir(), "mhxy_test_agent_replay")
    if os.path.exists(rdir):
        shutil.rmtree(rdir)
    rec = ReplayRecorder(rdir, "sim1")

    settings = {"logging": {"dir": "logs", "level": "WARNING"}}
    account = Account({"id": "sim1", "role": "leader", "enabled": True, "window_title": "SIM"}, settings)
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

    agent = _SimAgent(account, memory=mem, replay=rec, tick_seconds=0.01)
    agent.run(goal="测试", max_steps=3)
    rec.finish()
    # 记忆有记录
    assert mem.stats()["task_experience"] > 0
    # Replay 有步骤
    assert rec.step_count >= 1
    mem.close()
    shutil.rmtree(rdir)
