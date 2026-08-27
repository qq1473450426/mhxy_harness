# -*- coding: utf-8 -*-
"""test_memory.py (规格书 §41): 长期记忆测试。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import LongTermMemory

DB = os.path.join(tempfile.gettempdir(), "mhxy_spec_mem.db")


def _fresh():
    if os.path.exists(DB):
        os.remove(DB)
    return LongTermMemory(DB)


def test_record_and_track_action():
    m = _fresh()
    m.record_action("师门", "NAVIGATE", True, 25.0)
    m.record_action("师门", "NAVIGATE", True, 20.0)
    m.record_action("师门", "NAVIGATE", False, 90.0)
    stats = m.task_stats("师门")
    assert stats[0]["success"] == 2
    assert stats[0]["fail"] == 1
    m.close()


def test_best_action():
    m = _fresh()
    m.record_action("抓鬼", "BATTLE_AUTO", True, 5.0)
    m.record_action("抓鬼", "BATTLE_AUTO", True, 4.0)
    assert m.best_action("抓鬼") == "BATTLE_AUTO"
    m.close()


def test_npc_location():
    m = _fresh()
    m.record_npc("钟馗", "长安城", 155, 110)
    npc = m.get_npc("钟馗")
    assert npc["map"] == "长安城"
    m.record_npc("钟馗", "长安城", 160, 115)
    assert m.get_npc("钟馗")["found"] == 2
    m.close()


def test_item_price():
    m = _fresh()
    m.record_price("金柳露", 8000)
    m.record_price("金柳露", 9000)
    p = m.get_price("金柳露")
    assert p["min"] == 8000
    assert p["max"] == 9000
    m.close()


def test_task_runs():
    m = _fresh()
    m.record_run("师门", 20, "COMPLETED", 1800, "完成")
    runs = m.recent_runs()
    assert len(runs) == 1
    assert runs[0]["task"] == "师门"
    m.close()


def test_stats():
    m = _fresh()
    m.record_action("师门", "NAVIGATE", True, 10.0)
    s = m.stats()
    assert s["task_experience"] >= 1
    m.close()
