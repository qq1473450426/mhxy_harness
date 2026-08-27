# -*- coding: utf-8 -*-
"""任务推荐联动测试(攻略 task_db 接入系统)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.task_db import filter_by_level, TASK_DB, TaskEntry


def test_task_db_has_data():
    assert len(TASK_DB) >= 10


def test_filter_by_level_109():
    tasks = filter_by_level(109)
    assert len(tasks) >= 10
    # 109 应包含师门(S级)和周末活动(S级)
    names = [t.name for t in tasks]
    assert "师门任务" in names
    # S级排最前
    assert tasks[0].tier == "S"


def test_filter_by_level_lower():
    # 20级只应包含低门槛任务
    tasks = filter_by_level(20)
    for t in tasks:
        assert t.min_level <= 20


def test_filter_only_usable():
    # 过滤: 只保留当前等级 >= min_level
    tasks = filter_by_level(50)
    for t in tasks:
        assert t.min_level <= 50


def test_filter_sort_by_cash():
    tasks = filter_by_level(109, sort="cash")
    # 现金评级排序应合法
    assert all(t.cash in ("高", "中", "低", "稳", "无") for t in tasks)


def test_task_entry_to_dict():
    t = TASK_DB[0]
    d = t.to_dict()
    assert d["name"] == t.name
    assert d["tier"] == t.tier
    assert d["min_level"] == t.min_level
