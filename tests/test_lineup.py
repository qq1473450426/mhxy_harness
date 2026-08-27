# -*- coding: utf-8 -*-
"""五开阵容生成器测试。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.lineup import build_lineup, role_for


def test_role_mapping():
    assert role_for("方寸山") == "封印/控场"
    assert role_for("无底洞") == "治疗/固伤"


def test_build_low_for_fangcun():
    r = build_lineup("方寸山", "low")
    assert r["lead_sector"] == "方寸山"
    assert r["compatible"] is True
    assert len(r["lineup"]) == 5
    assert r["lineup"][0]["src"] == "已有"
    assert r["lineup"][1]["src"] == "推荐"


def test_build_all_budgets():
    for b in ("low", "balance", "high"):
        r = build_lineup("方寸山", b)
        assert len(r["lineup"]) == 5


def test_incompatible_sector():
    """纯物理输出门派与低投入固伤流可能不完全契合, 但应有阵容。"""
    r = build_lineup("大唐官府", "low")
    assert len(r["lineup"]) == 5
    assert r["lead_role"] == "物理输出"


def test_breakpoints_exist():
    r = build_lineup("方寸山", "low")
    assert 69 in r["breakpoints"]
    assert 109 in r["breakpoints"]


def test_lead_is_leader():
    r = build_lineup("方寸山", "low")
    assert r["lineup"][0]["slot"] == "1(队长)"
    assert r["lineup"][0]["sector"] == "方寸山"
