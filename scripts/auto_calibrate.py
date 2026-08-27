# -*- coding: utf-8 -*-
"""自动校准: 从最新截图按 OCR 文本坐标裁剪 UI 元素模板。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.ocr import OCREngine
from vision.capture import capture_to_png
from PIL import Image
import yaml

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(PROJECT, "logs", "scan")
TPL_DIR = os.path.join(PROJECT, "vision", "templates")
CFG_PATH = os.path.join(PROJECT, "config", "templates.yaml")

# 读取最新截图
snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.endswith(".png"))
snap = os.path.join(SNAP_DIR, snaps[-1])
img = Image.open(snap)
W, H = img.size
print(f"截图: {snap} ({W}x{H})")

# OCR 全图
ocr = OCREngine("rapidocr")
data = open(snap, "rb").read()
# 直接调 rapidocr 用 PIL 图
from rapidocr_onnxruntime import RapidOCR
import numpy as np
eng = RapidOCR()
arr = np.asarray(img.convert("RGB"))
result, _ = eng(arr)
print(f"OCR 识别 {len(result or [])} 行")

# 关键 UI 元素映射: (文本关键词, 元素名, 扩展边距)
TARGETS = [
    ("指引", "guide_btn", 4),
    ("日历", "calendar_btn", 4),
    ("商城", "mall_btn", 4),
    ("首充", "first_charge_btn", 4),
    ("任务追踪", "task_track_btn", 4),
    ("成长试炼", "growth_trial_btn", 4),
    ("尊享权益", "vip_btn", 4),
    ("师门任务", "shimen_task_panel", 8),
    ("雁塔试炼", "yanta_task_panel", 8),
    ("仙石天机", "xianshi_task_panel", 8),
    ("斜叶江庭", "char_name", 2),
]

os.makedirs(TPL_DIR, exist_ok=True)
cfg = {"elements": {}}
if os.path.exists(CFG_PATH):
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {"elements": {}}

saved = []
for item in (result or []):
    box, text, score = item[0], item[1], item[2]
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    cx, cy = int(sum(xs)/len(xs)), int(sum(ys)/len(ys))
    t = text.strip()
    for kw, name, pad in TARGETS:
        if kw in t and name not in cfg["elements"]:
            x0 = max(0, int(min(xs)) - pad)
            y0 = max(0, int(min(ys)) - pad)
            x1 = min(W, int(max(xs)) + pad)
            y1 = min(H, int(max(ys)) + pad)
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            crop = img.crop((x0, y0, x1, y1))
            out = os.path.join(TPL_DIR, f"{name}.png")
            crop.save(out)
            cfg["elements"][name] = {"file": f"{name}.png", "threshold": 0.82}
            saved.append((name, f"({x0},{y0},{x1-x0}x{y1-y0})", t))
            print(f"  [{name}] {t} -> {out}")

with open(CFG_PATH, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
print(f"\n已保存 {len(saved)} 个模板")
for name, box, t in saved:
    print(f"  {name}: {box} ({t})")
