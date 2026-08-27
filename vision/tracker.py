# -*- coding: utf-8 -*-
"""目标跟踪器 (Phase 3 完整实现, Phase 2 提供接口 + 模板检测桥接)。

设计原则(规格书 §23/§24):
- 视觉模型负责 Seeing: YOLO/RT-DETR/Grounding DINO 等可替换
- Phase 2 用 TemplateMatcher 提供基础"检测-跟踪"能力
- Phase 3 换 YOLO 时只需实现 detect() 返回同样 Element 结构
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .detector import Element, TemplateMatcher

logger = logging.getLogger(__name__)


class Tracker:
    """目标跟踪: 检测 + 简单帧间稳定性(平滑抖动)。

    Phase 2: 基于模板匹配的检测 + 位置平滑。
    Phase 3: 可替换为 YOLO 检测 + 跟踪(如 ByteTrack)。
    """

    def __init__(self, matcher: Optional[TemplateMatcher] = None,
                 smooth_factor: float = 0.3) -> None:
        self.matcher = matcher or TemplateMatcher()
        self.smooth_factor = smooth_factor
        self._prev: Dict[str, tuple] = {}   # name -> (cx, cy)

    def detect(self, image_bgr: np.ndarray) -> Dict[str, Element]:
        """检测所有元素(模板匹配)。"""
        return self.matcher.match_all(image_bgr)

    def track(self, image_bgr: np.ndarray) -> Dict[str, Element]:
        """检测 + 平滑位置, 返回 {元素名: Element}。"""
        found = self.detect(image_bgr)
        out: Dict[str, Element] = {}
        for name, el in found.items():
            cx, cy = el.center
            prev = self._prev.get(name)
            if prev is not None and self.smooth_factor > 0:
                cx = int(prev[0] * self.smooth_factor + cx * (1 - self.smooth_factor))
                cy = int(prev[1] * self.smooth_factor + cy * (1 - self.smooth_factor))
                el.x = max(0, cx - el.w // 2)
                el.y = max(0, cy - el.h // 2)
            self._prev[name] = (cx, cy)
            out[name] = el
        # 消失的元素
        for name in list(self._prev.keys()):
            if name not in out:
                del self._prev[name]
        return out

    def reset(self) -> None:
        self._prev.clear()

    # ---------------- 坐标解析(规格书 §8) ----------------
    def resolve_target(self, found: Dict[str, Element], target: str) -> Optional[Element]:
        """把语义目标(如"师门师父")解析为实际元素坐标。

        查找顺序: 精确名 -> 包含匹配 -> 任务面板关联。
        Phase 3 由 YOLO/知识库增强。
        """
        if target in found:
            return found[target]
        for name, el in found.items():
            if target in name or name in target:
                return el
        return None
