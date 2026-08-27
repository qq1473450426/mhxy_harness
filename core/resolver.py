# -*- coding: utf-8 -*-
"""坐标解析器：把 OCR/模板语义目标转换成窗口坐标。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ResolveError(Exception):
    pass


class CoordinateResolver:
    def __init__(self, fixed_ui: Optional[Dict[str, Tuple[int, int]]] = None) -> None:
        self.fixed_ui = fixed_ui or {}
        self._last_ocr: List[Tuple[str, int, int]] = []
        self._last_elements: Dict[str, Any] = {}

    def update_context(self, ocr_lines: List[Tuple[str, int, int]], elements: Optional[Dict[str, Any]] = None) -> None:
        self._last_ocr = ocr_lines
        if elements is not None:
            self._last_elements = elements

    def resolve(self, target: str) -> Tuple[int, int]:
        # 1. 模板元素
        for name, el in self._last_elements.items():
            label = el.get("label", "")
            if target in name or (label and target in label) or name in target:
                cx = int(el["x"] + el["w"] / 2)
                cy = int(el["y"] + el["h"] / 2)
                logger.info("目标 %s -> 模板元素 %s @ (%d,%d)", target, name, cx, cy)
                return cx, cy

        # 2. OCR：如果目标只是整行的一部分，按字符串比例定位目标中心。
        best: Optional[Tuple[int, int, float]] = None
        for text, x, y in self._last_ocr:
            if not text:
                continue
            if target in text:
                start = text.find(target)
                # RapidOCR 的当前数据结构只保留左上角，因此按常见中文字宽估算。
                char_w = max(5.0, min(16.0, 12.0 if any("\u4e00" <= c <= "\u9fff" for c in text) else 7.0))
                target_x = int(x + (start + len(target) / 2.0) * char_w)
                target_y = int(y + 10)
                score = 1.0 if start >= 0 else 0.0
                if best is None or score > best[2]:
                    best = (target_x, target_y, score)
            elif text in target:
                cx = int(x + max(1, len(text)) * 6)
                best = (cx, int(y + 8), 0.5)
        if best:
            logger.info("目标 %s -> OCR 子串 @ (%d,%d)", target, best[0], best[1])
            return best[0], best[1]

        # 3. 固定 UI 注册表
        if target in self.fixed_ui:
            return self.fixed_ui[target]

        # 4. 常见别名
        alias = {
            "任务": (600, 200), "任务面板": (600, 200),
            "背包": (100, 450), "队伍": (150, 450),
            "技能": (200, 450), "地图": (250, 450),
        }
        if target in alias:
            return alias[target]
        raise ResolveError(f"无法解析目标: {target}")

    def resolve_or_none(self, target: str) -> Optional[Tuple[int, int]]:
        try:
            return self.resolve(target)
        except ResolveError:
            return None
