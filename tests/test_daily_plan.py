# -*- coding: utf-8 -*-
"""逐日计划生成器测试。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.daily_plan import plan_for_day, milestone_roadmap


def test_plan_day_7():
    p = plan_for_day(7)
    assert p["level_range"] == "20-40"
    assert "师门" in p["daily_flow"]
    assert p["five_status"] == "5号齐练"


def test_plan_day_30():
    p = plan_for_day(30)
    assert p["level_range"] == "60-69"
    assert "师门" in p["daily_flow"]
    assert "停级" in p["note"]


def test_plan_day_1():
    p = plan_for_day(1)
    assert p["five_status"] == "只练主号"
    assert "主线" in p["daily_flow"]


def test_plan_has_flow():
    """每天都要有可执行的流程列表。"""
    for day in (1, 3, 5, 7, 14, 20, 30, 60):
        p = plan_for_day(day)
        assert len(p["daily_flow"]) >= 1


def test_daily_order_priority():
    """流程应体现优先级(师门在前)。"""
    p = plan_for_day(30)
    assert p["daily_flow"][0] == "师门"


def test_milestone_roadmap():
    m = milestone_roadmap()
    assert len(m) >= 5
    assert m[0]["day"] == 1
    assert m[-1]["day"] >= 60


def test_out_of_range():
    # 999天命中"长期搬砖期"(61-999), 返回正常计划而非崩溃
    p = plan_for_day(999)
    assert len(p["daily_flow"]) >= 1
    assert "day" in p

