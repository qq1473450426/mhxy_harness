# -*- coding: utf-8 -*-
"""test_takeover.py: 单账号人工接管(规格书 §47)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.coordinator import Coordinator

SETTINGS = {
    "logging": {"dir": "logs", "level": "WARNING"},
    "accounts": {
        "leader": "account_01",
        "list": [
            {"id": "account_01", "role": "leader", "enabled": True, "window_title": "SIM1"},
            {"id": "account_02", "role": "follower", "enabled": True, "window_title": "SIM2"},
            {"id": "account_03", "role": "follower", "enabled": True, "window_title": "SIM3"},
        ],
    },
    "tasks": {},
}


def _coord():
    c = Coordinator(SETTINGS)
    c.build_from_config()
    return c


def test_pause_account():
    c = _coord()
    ok = c.pause_account("account_02")
    assert ok is True
    assert "account_02" in c.paused_accounts()


def test_pause_unknown():
    c = _coord()
    assert c.pause_account("不存在") is False


def test_resume_account():
    c = _coord()
    c.pause_account("account_02")
    assert c.resume_account("account_02") is True
    assert "account_02" not in c.paused_accounts()


def test_pause_does_not_stop_others():
    """暂停单账号后, 其他账号仍在 accounts 中(未被移除)。"""
    c = _coord()
    c.pause_account("account_02")
    assert "account_01" in c.accounts
    assert "account_03" in c.accounts


def test_manual_set():
    c = _coord()
    c.pause_account("account_02")
    assert "account_02" in c._manual
    c.resume_account("account_02")
    assert "account_02" not in c._manual


def test_multiple_pause():
    c = _coord()
    c.pause_account("account_02")
    c.pause_account("account_03")
    assert set(c.paused_accounts()) == {"account_02", "account_03"}
    c.resume_account("account_02")
    c.resume_account("account_03")
    assert c.paused_accounts() == []
