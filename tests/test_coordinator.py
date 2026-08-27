# -*- coding: utf-8 -*-
"""test_coordinator.py (规格书 §41): 五开协调器测试。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.coordinator import Coordinator
from core.team import TeamState, TeamStatus

SETTINGS = {
    "logging": {"dir": "logs", "level": "WARNING"},
    "accounts": {
        "leader": "account_01",
        "list": [
            {"id": "account_01", "role": "leader", "enabled": True, "window_title": "SIM1"},
            {"id": "account_02", "role": "follower", "enabled": True, "window_title": "SIM2"},
            {"id": "account_03", "role": "follower", "enabled": True, "window_title": "SIM3"},
            {"id": "account_04", "role": "follower", "enabled": False, "window_title": "SIM4"},
        ],
    },
    "tasks": {},
}


def _coord():
    return Coordinator(SETTINGS)


def test_build_from_config():
    c = _coord()
    n = c.build_from_config()
    assert n == 3
    assert c.team.leader == "account_01"
    assert set(c.team.members) == {"account_01", "account_02", "account_03"}


def test_backup_leader():
    c = _coord()
    c.build_from_config()
    assert c.team.backup_leader == "account_02"


def test_task_manager_attached():
    c = _coord()
    c.build_from_config()
    assert c.task_manager is not None
    # 内置任务已注册
    assert "shimen" in c.task_manager.available
    assert "guigua" in c.task_manager.available
    assert "fengyao" in c.task_manager.available


def test_bind_task():
    c = _coord()
    c.build_from_config()
    t = c.bind_task("shimen")
    assert t is not None
    assert c.team.task == "师门"  # task.name


def test_status_structure():
    c = _coord()
    c.build_from_config()
    s = c.status()
    assert "team" in s
    assert "accounts" in s
    assert "agents_running" in s


def test_stop_safe():
    c = _coord()
    c.build_from_config()
    c.stop()
    assert c.team.status == TeamStatus.IDLE
