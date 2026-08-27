# -*- coding: utf-8 -*-
"""桌面真实输入后的轻量验证器。

用于在不再次运行完整 YOLO/OCR 的情况下判断点击是否造成画面变化。
真正的语义状态验证仍由 GameAgent.observe() / Task 状态机负责。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

from automation.window import WindowInfo
from vision.capture import capture_window


@dataclass
class VisualChange:
    changed: bool
    score: float
    before_size: Tuple[int, int]
    after_size: Tuple[int, int]
    elapsed_ms: float
    reason: str = ""


class ActionVerifier:
    """对真实桌面动作做低成本画面变化检测。"""

    def __init__(self, threshold: float = 0.012, settle_ms: int = 350) -> None:
        self.threshold = float(threshold)
        self.settle_ms = max(0, int(settle_ms))

    @staticmethod
    def _score(a: bytes, b: bytes, size_a: Tuple[int, int], size_b: Tuple[int, int]) -> float:
        if size_a != size_b or not a or not b:
            return 1.0
        wa, ha = size_a
        wb, hb = size_b
        if wa != wb or ha != hb:
            return 1.0
        x = np.frombuffer(a, dtype=np.uint8)
        y = np.frombuffer(b, dtype=np.uint8)
        if x.size != y.size:
            return 1.0
        # 每隔一个像素采样，降低验证成本；只计算平均绝对变化。
        return float(np.mean(np.abs(x[::2].astype(np.int16) - y[::2].astype(np.int16))) / 255.0)

    def snapshot(self, window: WindowInfo) -> Tuple[bytes, Tuple[int, int]]:
        return capture_window(window)

    def verify(self, window: WindowInfo, before: Tuple[bytes, Tuple[int, int]],
               settle_ms: Optional[int] = None) -> VisualChange:
        started = time.perf_counter()
        delay = self.settle_ms if settle_ms is None else max(0, int(settle_ms))
        if delay:
            time.sleep(delay / 1000.0)
        after = self.snapshot(window)
        score = self._score(before[0], after[0], before[1], after[1])
        return VisualChange(
            changed=score >= self.threshold,
            score=score,
            before_size=before[1],
            after_size=after[1],
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            reason="画面发生变化" if score >= self.threshold else "画面变化不足",
        )
