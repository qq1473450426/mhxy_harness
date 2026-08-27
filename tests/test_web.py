# -*- coding: utf-8 -*-
"""Web 后端测试: Pydantic 模型 + 状态 API。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_server import get_status_dict, update_state, STATE


def test_status_dict_structure():
    STATE["status"] = "running"
    STATE["started_at"] = 1000.0
    d = get_status_dict()
    assert d["status"] == "running"
    assert "team" in d and "accounts" in d and "tasks" in d
    assert d["uptime"] >= 0


def test_update_state():
    update_state("tasks", {"师门": {"status": "RUNNING"}})
    assert STATE["tasks"]["师门"]["status"] == "RUNNING"


def test_account_model():
    from web_server import AccountOut
    a = AccountOut(account_id="acc1", role="leader", state="CITY", hp=800)
    assert a.account_id == "acc1"
    assert a.hp == 800
    assert a.state == "CITY"


def test_team_model():
    from web_server import TeamOut
    t = TeamOut(leader="acc1", members=["acc1", "acc2"], total=2)
    assert t.leader == "acc1"
    assert len(t.members) == 2
    assert t.total == 2
