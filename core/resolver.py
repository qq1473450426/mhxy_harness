# -*- coding: utf-8 -*-
"""坐标解析器 (Phase 4, 规格书 §8)。

LLM 不允许输出坐标, 只输出语义 Action(如 CLICK_NPC "师门师父")。
由本模块把语义目标解析为实际窗口内坐标:

    Vision -> Target Detector -> Coordinate Resolver -> Input Driver

解析策略(按优先级):
1. 模板匹配结果(元素名/标签匹配)
2. OCR 文本位置(目标名出现在屏幕哪个位置)
3. 固定注册表(UI 元素固定坐标, 配置驱动)
4. 相对位置启发式(任务面板右侧等)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ResolveError(Exception):
    """目标坐标解析失败。"""


class CoordinateResolver:
    """把语义目标解析为窗口内坐标。"""

    def __init__(self, fixed_ui: Optional[Dict[str, Tuple[int, int]]] = None) -> None:
        """fixed_ui: {元素名: (x, y)} 固定坐标注册表(配置驱动)。"""
        self.fixed_ui = fixed_ui or {}
        self._last_ocr: List[Tuple[str, int, int]] = []  # (text, x, y)
        self._last_elements: Dict[str, Any] = {}         # 模板检测结果

    # ---------------- 上下文注入 ----------------
    def update_context(self, ocr_lines: List[Tuple[str, int, int]],
                       elements: Optional[Dict[str, Any]] = None) -> None:
        """每帧更新 OCR 文本位置和模板检测结果。"""
        self._last_ocr = ocr_lines
        if elements:
            self._last_elements = elements

    # ---------------- 解析主入口 ----------------
    def resolve(self, target: str) -> Tuple[int, int]:
        """解析目标 -> (x, y) 窗口内坐标。抛 ResolveError。"""
        # 1. 模板匹配元素
        for name, el in self._last_elements.items():
            label = el.get("label", "")
            if target in name or (label and target in label) or name in target:
                cx = el["x"] + el["w"] // 2
                cy = el["y"] + el["h"] // 2
                logger.info("目标 %s -> 模板元素 %s @ (%d,%d)", target, name, cx, cy)
                return (cx, cy)
        # 2. OCR 文本位置(精确/包含匹配)
        best = None
        for text, x, y in self._last_ocr:
            if target in text or text in target:
                # 取多个匹配的中间位置
                if best is None or (x, y) != (0, 0):
                    best = (x + len(text) * 6, y + 8)  # 粗略估算文本中心
                    break
        if best:
            logger.info("目标 %s -> OCR 文本 @ %s", target, best)
            return best
        # 3. 固定注册表
        if target in self.fixed_ui:
            return self.fixed_ui[target]
        # 4. 常见 UI 元素别名
        alias = {
            "任务": (600, 200), "任务面板": (600, 200),
            "背包": (100, 450), "队伍": (150, 450),
            "技能": (200, 450), "地图": (250, 450),
        }
        if target in alias:
            return alias[target]
        raise ResolveError(f"无法解析目标: {target}")

    # ---------------- 工具 ----------------
    def resolve_or_none(self, target: str) -> Optional[Tuple[int, int]]:
        try:
            return self.resolve(target)
        except ResolveError:
            return None
