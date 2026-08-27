# -*- coding: utf-8 -*-
"""test_navigation.py (规格书 §41): 坐标解析/导航测试。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resolver import CoordinateResolver, ResolveError


def test_resolve_from_elements():
    r = CoordinateResolver()
    r.update_context([], {"task_btn": {"x": 100, "y": 200, "w": 40, "h": 20, "label": "task_btn"}})
    pos = r.resolve("task_btn")
    assert pos == (120, 210)


def test_resolve_from_ocr():
    r = CoordinateResolver()
    r.update_context([("钟馗", 400, 300)])
    pos = r.resolve("钟馗")
    assert pos[0] > 400
    assert pos[1] == 308


def test_resolve_fixed_registry():
    r = CoordinateResolver(fixed_ui={"钟馗": (400, 300)})
    assert r.resolve("钟馗") == (400, 300)


def test_resolve_alias():
    r = CoordinateResolver()
    assert r.resolve("任务") == (600, 200)
    assert r.resolve("背包") == (100, 450)


def test_resolve_unknown_raises():
    r = CoordinateResolver()
    try:
        r.resolve("不存在")
        assert False
    except ResolveError:
        pass


def test_resolve_or_none():
    r = CoordinateResolver()
    assert r.resolve_or_none("不存在") is None
    assert r.resolve_or_none("任务") == (600, 200)


def test_context_update_ocr():
    r = CoordinateResolver()
    r.update_context([("A", 10, 20), ("B", 30, 40)], {"btn": {"x": 1, "y": 2, "w": 3, "h": 4, "label": ""}})
    assert r.resolve("A")[0] > 10
    assert r.resolve("btn") == (2, 4)
