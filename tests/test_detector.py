# -*- coding: utf-8 -*-
"""模板匹配检测器测试(机制正确性, 不假设特定游戏状态)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml
import numpy as np
from PIL import Image

from vision.detector import TemplateMatcher

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(PROJECT, "config", "templates.yaml")
SNAP_DIR = os.path.join(PROJECT, "logs", "scan")


def _matcher():
    if not os.path.exists(CFG):
        return None
    with open(CFG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    m = TemplateMatcher(cfg)
    return m if m.available else None


def _snap_bgr():
    snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.endswith(".png"))
    if not snaps:
        return None
    img = Image.open(os.path.join(SNAP_DIR, snaps[-1])).convert("RGB")
    arr = np.asarray(img)
    return arr[:, :, ::-1].copy()


def test_templates_loaded():
    m = _matcher()
    if m is None:
        return
    assert len(m.available) >= 5


def test_match_coordinates_valid():
    """若匹配到元素, 坐标必须在截图范围内(保证机制正确)。"""
    m, bgr = _matcher(), _snap_bgr()
    if m is None or bgr is None:
        return
    h, w = bgr.shape[:2]
    found = m.match_all(bgr)
    for name, el in found.items():
        assert el.x >= 0 and el.y >= 0
        assert el.x + el.w <= w and el.y + el.h <= h


def test_match_returns_dict():
    """match_all 必须返回 dict(即使为空)。"""
    m, bgr = _matcher(), _snap_bgr()
    if m is None or bgr is None:
        return
    found = m.match_all(bgr)
    assert isinstance(found, dict)


def test_no_false_crash_on_empty():
    """任意截图(如选服界面)匹配不应崩溃。"""
    m, bgr = _matcher(), _snap_bgr()
    if m is None or bgr is None:
        return
    found = m.match_all(bgr)
    assert found is not None


def test_confidence_in_range():
    """匹配置信度必须在 [0,1]。"""
    m, bgr = _matcher(), _snap_bgr()
    if m is None or bgr is None:
        return
    found = m.match_all(bgr)
    for name, el in found.items():
        assert 0.0 <= el.confidence <= 1.0
