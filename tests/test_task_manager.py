# -*- coding: utf-8 -*-
"""test_task_manager.py (规格书 §41): 任务管理器测试。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.task_manager import TaskManager
from tasks.shimen import ShimenTask
from tasks.fengyao import FengyaoTask
from core.game_state import GameState, GameStatus


def _mk():
    m = TaskManager()
    m.register("shimen", ShimenTask)
    m.register("fengyao", FengyaoTask)
    return m


def test_register_and_available():
    m = _mk()
    assert "shimen" in m.available
    assert "fengyao" in m.available


def test_create_task_planning():
    m = _mk()
    t = m.create("shimen", max_rounds=20)
    assert t is not None
    assert t.status.name == "PLANNING"  # created -> planning


def test_create_unknown_returns_none():
    m = _mk()
    assert m.create("不存在") is None


def test_next_task_priority():
    m = _mk()
    t1 = m.create("shimen")
    t2 = m.create("fengyao")
    t2.priority = 1  # 更高优先级
    assert m.next_task() == t2


def test_run_next_returns_action():
    m = _mk()
    t = m.create("shimen", max_rounds=20)
    gs = GameState(account_id="t", status=GameStatus.CITY, map_name="长安城")
    action = m.run_next(gs)
    assert action is not None
    assert "action" in action


def test_status_dict():
    m = _mk()
    m.create("shimen")
    s = m.status()
    assert "available" in s
    assert "tasks" in s
    assert len(s["tasks"]) == 1


def test_unregister():
    m = _mk()
    m.unregister("shimen")
    assert "shimen" not in m.available
