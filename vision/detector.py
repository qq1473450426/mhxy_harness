# -*- coding: utf-8 -*-
"""目标检测器 (Phase 2: 模板匹配; Phase 3 可换 YOLO)。

设计原则(规格书 §5 第一层快速视觉模型):
- 追求速度/稳定/低延迟
- Phase 2 用 OpenCV 模板匹配(TM_CCOEFF_NORMED)
- 配置驱动: config/templates.yaml 登记 元素名 -> 模板文件 + 阈值
- 输出: 元素名 -> Element(窗口内相对坐标 + 尺寸 + 置信度)
- 与状态机解耦: 检测器只回答"屏幕上有什么、在哪"
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


@dataclass
class Element:
    """检测到的 UI 元素。"""

    name: str
    x: int
    y: int
    w: int
    h: int
    confidence: float = 0.0
    label: str = ""

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "x": self.x, "y": self.y,
                "w": self.w, "h": self.h, "confidence": round(self.confidence, 3),
                "center": list(self.center)}


class TemplateMatcher:
    """OpenCV 模板匹配器。"""

    def __init__(self, templates_cfg: Optional[Dict[str, Any]] = None,
                 templates_dir: str = TEMPLATES_DIR) -> None:
        self.templates_dir = templates_dir
        self._templates: Dict[str, dict] = {}
        self._cv2 = None
        try:
            import cv2  # type: ignore
            self._cv2 = cv2
        except Exception as e:
            logger.warning("OpenCV 不可用: %s", e)
        cfg = templates_cfg or {}
        for name, item in (cfg.get("elements") or {}).items():
            if not isinstance(item, dict):
                continue
            fname = item.get("file")
            if not fname:
                continue
            path = os.path.join(templates_dir, fname)
            if os.path.exists(path):
                self._templates[name] = {
                    "path": path,
                    "threshold": float(item.get("threshold", 0.85)),
                    "region": item.get("region"),   # [x,y,w,h] 限定搜索区域
                }
        if self._templates:
            logger.info("模板加载 %d 个: %s", len(self._templates),
                        ", ".join(sorted(self._templates)))

    @property
    def available(self) -> List[str]:
        return sorted(self._templates.keys())

    def has(self, name: str) -> bool:
        return name in self._templates

    # ---------------- 模板缓存 ----------------
    def _load_gray(self, tpl: dict):
        """缓存模板灰度图(避免每帧 imread, 性能关键)。"""
        gray = tpl.get("_gray")
        if gray is None:
            if self._cv2 is None:
                return None
            gray = self._cv2.imread(tpl["path"], self._cv2.IMREAD_GRAYSCALE)
            tpl["_gray"] = gray
        return gray

    # ---------------- 单模板匹配 ----------------
    def match_one(self, image_bgr: np.ndarray, name: str) -> Optional[Element]:
        """在截图中匹配单个模板, 返回最佳位置(仅匹配度最高处)。

        支持 region 限定搜索区域(校准时可记录模板位置, 大幅提速)。
        """
        tpl = self._templates.get(name)
        if tpl is None or self._cv2 is None:
            return None
        try:
            t = self._load_gray(tpl)
            if t is None:
                return None
            h, w = image_bgr.shape[:2]
            th, tw = t.shape[:2]
            if th > h or tw > w:
                return None
            gray = self._cv2.cvtColor(image_bgr, self._cv2.COLOR_BGR2GRAY)
            # region 限定: [x, y, w, h] 只在该区域搜索
            region = tpl.get("region")
            if region:
                rx, ry, rw, rh = (int(v) for v in region)
                rx = max(0, min(rx, w - tw))
                ry = max(0, min(ry, h - th))
                rw = min(rw, w - rx - tw)
                rh = min(rh, h - ry - th)
                if rw <= 0 or rh <= 0:
                    return None
                sub = gray[ry:ry + rh, rx:rx + rw]
                res = self._cv2.matchTemplate(sub, t, self._cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = self._cv2.minMaxLoc(res)
                abs_x, abs_y = rx + int(max_loc[0]), ry + int(max_loc[1])
            else:
                res = self._cv2.matchTemplate(gray, t, self._cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = self._cv2.minMaxLoc(res)
                abs_x, abs_y = int(max_loc[0]), int(max_loc[1])
            if max_val >= tpl["threshold"]:
                return Element(name=name, x=abs_x, y=abs_y,
                               w=tw, h=th, confidence=float(max_val), label=name)
        except Exception as e:
            logger.warning("模板匹配失败 %s: %s", name, e)
        return None

    # ---------------- 多位置匹配 ----------------
    def match_all_positions(self, image_bgr: np.ndarray, name: str,
                            max_hits: int = 5, min_distance: int = 20) -> List[Element]:
        """匹配模板的所有出现位置(去重)。"""
        tpl = self._templates.get(name)
        if tpl is None or self._cv2 is None:
            return []
        try:
            t = self._cv2.imread(tpl["path"], self._cv2.IMREAD_GRAYSCALE)
            if t is None:
                return []
            h, w = image_bgr.shape[:2]
            th, tw = t.shape[:2]
            if th > h or tw > w:
                return []
            gray = self._cv2.cvtColor(image_bgr, self._cv2.COLOR_BGR2GRAY)
            region = tpl.get("region")
            if region:
                rx, ry, rw, rh = (int(v) for v in region)
                rx = max(0, min(rx, w - tw))
                ry = max(0, min(ry, h - th))
                sub = gray[ry:ry + rh, rx:rx + rw]
                res = self._cv2.matchTemplate(sub, t, self._cv2.TM_CCOEFF_NORMED)
            else:
                res = self._cv2.matchTemplate(gray, t, self._cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= tpl["threshold"])
            hits: List[Element] = []
            for pt in zip(*loc[::-1]):
                x, y = int(pt[0]), int(pt[1])
                if region:
                    x, y = x + rx, y + ry
                # 与已有命中去重
                if all(abs(x - e.x) >= min_distance or abs(y - e.y) >= min_distance
                       for e in hits):
                    hits.append(Element(name=name, x=x, y=y, w=tw, h=th,
                                        confidence=float(res[y, x]), label=name))
                if len(hits) >= max_hits:
                    break
            return hits
        except Exception as e:
            logger.warning("模板多位置匹配失败 %s: %s", name, e)
            return []

    # ---------------- 全量匹配 ----------------
    def match_all(self, image_bgr: np.ndarray) -> Dict[str, Element]:
        """匹配所有已登记模板。返回 {元素名: Element}。"""
        found: Dict[str, Element] = {}
        for name in self._templates:
            el = self.match_one(image_bgr, name)
            if el is not None:
                found[name] = el
        return found

    # ---------------- RGB 字节流入口 ----------------
    def match_all_rgb(self, image_rgb: bytes, size: Tuple[int, int]) -> Dict[str, Element]:
        """从 RGB 字节流(截图输出格式)匹配全部模板。"""
        w, h = size
        bgr = np.frombuffer(image_rgb, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
        return self.match_all(bgr)
