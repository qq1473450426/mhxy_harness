# -*- coding: utf-8 -*-
"""模板校准工具 (Phase 2)。

用法:
    python scripts/calibrate.py --name task_btn --box 600,200,80,30
    python scripts/calibrate.py --list-snaps

从最近一张 scan 截图裁剪 (x,y,w,h) 区域保存为 vision/templates/<name>.png,
并自动登记到 config/templates.yaml。

设计原则(规格书 §35/§2):
- 先校准模板, 识别才可用
- 未校准元素 -> UNKNOWN(安全优先)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from PIL import Image

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(PROJECT, "logs", "scan")
TPL_DIR = os.path.join(PROJECT, "vision", "templates")
CFG_PATH = os.path.join(PROJECT, "config", "templates.yaml")


def latest_snap() -> str:
    snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.endswith(".png"))
    if not snaps:
        raise SystemExit(f"没有截图, 先运行: python app.py --scan (截图在 {SNAP_DIR})")
    return os.path.join(SNAP_DIR, snaps[-1])


def add_template(name: str, box: str, threshold: float = 0.85) -> None:
    x, y, w, h = (int(v) for v in box.replace(" ", "").split(","))
    snap = latest_snap()
    img = Image.open(snap)
    W, H = img.size
    if x < 0 or y < 0 or x + w > W or y + h > H:
        raise SystemExit(f"裁剪区域越界: 截图 {W}x{H}, 请求 ({x},{y},{w}x{h})")
    crop = img.crop((x, y, x + w, y + h))
    os.makedirs(TPL_DIR, exist_ok=True)
    out = os.path.join(TPL_DIR, f"{name}.png")
    crop.save(out)
    # 登记配置(含 region 加速搜索: 模板位置附近区域)
    cfg = {"elements": {}}
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {"elements": {}}
    region = [max(0, x - 30), max(0, y - 30), min(W, x + w + 60), min(H, y + h + 60)]
    cfg.setdefault("elements", {})[name] = {
        "file": f"{name}.png", "threshold": threshold, "region": region}
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"模板已保存: {out}")
    print(f"已登记: config/templates.yaml  elements.{name}  region={region}")


def list_snaps() -> None:
    snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.endswith(".png"))
    if not snaps:
        print("暂无截图")
        return
    print("可用截图:")
    for s in snaps[-10:]:
        print(f"  {s}")


def main() -> None:
    ap = argparse.ArgumentParser(description="模板校准工具")
    ap.add_argument("--name", help="元素名, 如 task_btn")
    ap.add_argument("--box", help="裁剪区域 x,y,w,h (相对最近截图)")
    ap.add_argument("--threshold", type=float, default=0.85)
    ap.add_argument("--list-snaps", action="store_true")
    args = ap.parse_args()
    if args.list_snaps:
        list_snaps()
    elif args.name and args.box:
        add_template(args.name, args.box, args.threshold)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
