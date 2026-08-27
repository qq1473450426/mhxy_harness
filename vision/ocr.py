# -*- coding: utf-8 -*-
"""OCR 识别 (Level 2 Reading)。

设计原则(规格书 §2/§23):
- OCR 负责 Reading, 与状态机解耦
- 默认 rapidocr-onnxruntime(本地离线), 可切换后端
- 输出结构化: (box, text, score)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OCRLine:
    """一行 OCR 识别结果。"""

    text: str
    x: int  # 左上角 x
    y: int  # 左上角 y
    score: float
    box: Optional[list] = None


class OCRBackend:
    """OCR 后端抽象。"""

    name = "base"

    def recognize(self, image_rgb: bytes, size: Tuple[int, int]) -> List[OCRLine]:
        raise NotImplementedError


class RapidOCRBackend(OCRBackend):
    """rapidocr-onnxruntime 本地离线 OCR。"""

    name = "rapidocr"

    def __init__(self) -> None:
        self._engine = None

    def _load(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore
                self._engine = RapidOCR()
                logger.info("RapidOCR 加载成功")
            except Exception as e:
                raise RuntimeError(f"未安装 rapidocr-onnxruntime: {e}") from e
        return self._engine

    def recognize(self, image_rgb: bytes, size: Tuple[int, int]) -> List[OCRLine]:
        import numpy as np  # type: ignore
        w, h = size
        img = np.frombuffer(image_rgb, dtype=np.uint8).reshape(h, w, 3)
        result, _ = self._load()(img)
        lines: List[OCRLine] = []
        for item in (result or []):
            box, text, score = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append(OCRLine(text=text, x=int(min(xs)), y=int(min(ys)),
                                 score=float(score), box=box))
        return lines


class OCREngine:
    """统一 OCR 引擎入口, 按配置选择后端。"""

    def __init__(self, backend: str = "rapidocr") -> None:
        self.backend_name = backend
        self._backend: Optional[OCRBackend] = None

    def _get(self) -> OCRBackend:
        if self._backend is None:
            if self.backend_name == "rapidocr":
                self._backend = RapidOCRBackend()
            else:
                raise RuntimeError(f"未知 OCR 后端: {self.backend_name}")
        return self._backend

    def recognize(self, image_rgb: bytes, size: Tuple[int, int]) -> List[OCRLine]:
        try:
            return self._get().recognize(image_rgb, size)
        except RuntimeError:
            raise
        except Exception as e:  # pragma: no cover
            logger.warning("OCR 识别异常: %s", e)
            return []

    def text_only(self, image_rgb: bytes, size: Tuple[int, int]) -> List[str]:
        """仅返回文本列表(状态机用)。"""
        return [ln.text for ln in self.recognize(image_rgb, size)]
