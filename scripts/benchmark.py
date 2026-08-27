# -*- coding: utf-8 -*-
"""Phase 2 性能基准: 截图 / OCR / 模板检测。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml
import numpy as np
from automation.window import WindowManager
from vision.capture import capture_window
from vision.ocr import OCREngine
from vision.detector import TemplateMatcher

wm = WindowManager()
win = wm.bind_account("梦幻西游 ONLINE")
print(f"窗口: {win.title} ({win.w}x{win.h})")

# 1. 截图
N = 20
t0 = time.perf_counter()
for _ in range(N):
    img, size = capture_window(win)
t1 = time.perf_counter()
print(f"截图: {N/(t1-t0):.1f} FPS (每次 {(t1-t0)/N*1000:.1f} ms)")

# 2. OCR
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "templates.yaml"), "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}
ocr = OCREngine("rapidocr")
t0 = time.perf_counter()
for _ in range(3):
    texts = ocr.text_only(img, size)
t1 = time.perf_counter()
print(f"OCR: {(t1-t0)/3*1000:.1f} ms/次, {len(texts)} 行文本")

# 3. 模板检测
matcher = TemplateMatcher(cfg)
w, h = size
bgr = np.frombuffer(img, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
t0 = time.perf_counter()
for _ in range(N):
    elems = matcher.match_all(bgr)
t1 = time.perf_counter()
print(f"模板检测: {N/(t1-t0):.1f} FPS (每次 {(t1-t0)/N*1000:.1f} ms), {len(elems)}/{len(matcher.available)} 元素")

# 4. 完整观察循环(截图+OCR+检测)
t0 = time.perf_counter()
for _ in range(3):
    img, size = capture_window(win)
    texts = ocr.text_only(img, size)
    w, h = size
    bgr = np.frombuffer(img, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
    matcher.match_all(bgr)
t1 = time.perf_counter()
print(f"完整观察循环: {(t1-t0)/3*1000:.1f} ms/次 -> {3/(t1-t0):.1f} FPS")
