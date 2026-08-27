# -*- coding: utf-8 -*-
"""Phase 5 测试: 五开协调器/队伍状态/全局规划器。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.team import TeamState, TeamStatus
from core.planner import GlobalPlanner, TeamPlan
from core.coordinator import Coordinator


def test_team_basic():
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    t.add_member("acc3")
    assert t.leader == "acc1"
    assert len(t.members) == 3
    assert t.status == TeamStatus.IDLE


def test_team_sync():
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    t.add_member("acc3")
    assert not t.all_synced()
    t.mark_synced("acc1")
    t.mark_synced("acc2")
    assert not t.all_synced()
    t.mark_synced("acc3")
    assert t.all_synced()


def test_leader_failover():
    """队长掉线 -> 备用队长接管(规格书 §13)。"""
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    t.add_member("acc3")
    t.backup_leader = "acc2"
    t.remove_member("acc1")   # 队长掉线
    assert t.leader == "acc2"
    assert "acc1" not in t.members


def test_leader_failover_no_backup():
    """无备用队长时取第一个成员。"""
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    t.backup_leader = ""
    t.remove_member("acc1")
    assert t.leader == "acc2"


def test_planner_task_phases():
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    t.task = "抓鬼"
    p = GlobalPlanner(t)
    plan = p.plan("抓鬼")
    assert plan.task == "抓鬼"
    assert plan.phase == "PREPARE"
    assert "acc1" in plan.role_actions
    assert "acc2" in plan.role_actions
    # 队长做 leader 动作, 队员跟随
    assert "接取" in plan.role_actions["acc1"]
    assert "跟随" in plan.role_actions["acc2"]


def test_planner_progresses():
    t = TeamState()
    t.set_leader("acc1")
    t.add_member("acc2")
    p = GlobalPlanner(t)
    phases = [p.plan("师门").phase for _ in range(5)]
    # 应循环 PREPARE/RUN/FIGHT/END
    assert phases[0] == "PREPARE"
    assert phases[1] == "RUN"
    assert phases[2] == "FIGHT"
    assert phases[3] == "END"


def test_planner_unknown_task():
    t = TeamState()
    t.set_leader("acc1")
    p = GlobalPlanner(t)
    plan = p.plan("不存在任务")
    assert plan.task == "不存在任务"


def test_coordinator_build_from_config():
    settings = {
        "logging": {"dir": "logs", "level": "WARNING"},
        "accounts": {
            "leader": "account_01",
            "list": [
                {"id": "account_01", "role": "leader", "enabled": True, "window_title": "SIM1"},
                {"id": "account_02", "role": "follower", "enabled": True, "window_title": "SIM2"},
                {"id": "account_03", "role": "follower", "enabled": False, "window_title": "SIM3"},
            ],
        },
        "tasks": {},
    }
    coord = Coordinator(settings)
    n = coord.build_from_config()
    assert n == 2
    assert coord.team.leader == "account_01"
    assert set(coord.team.members) == {"account_01", "account_02"}
    assert coord.team.backup_leader == "account_02"
    # 状态序列化
    s = coord.status()
    assert "team" in s and "accounts" in s
