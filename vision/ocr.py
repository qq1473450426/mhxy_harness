# -*- coding: utf-8 -*-
"""OCR 识别：支持多 ROI，避免把左侧聊天区送入 OCR。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OCRLine:
    text: str
    x: int
    y: int
    score: float
    box: Optional[list] = None


class OCRBackend:
    name = "base"

    def recognize(self, image_rgb: bytes, size: Tuple[int, int]) -> List[OCRLine]:
        raise NotImplementedError


class RapidOCRBackend(OCRBackend):
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
            lines.append(OCRLine(text=text, x=int(min(xs)), y=int(min(ys)), score=float(score), box=box))
        return lines


class OCREngine:
    """统一 OCR 入口。

    roi 可以是多个 (x, y, w, h)；坐标既可写像素，也可写 0~1 的归一化比例。
    多 ROI 结果会自动恢复到完整游戏窗口坐标，Resolver 无需知道裁剪发生过。
    """

    def __init__(self, backend: str = "rapidocr", roi: Optional[Sequence[Tuple[float, float, float, float]]] = None) -> None:
        self.backend_name = backend
        self._backend: Optional[OCRBackend] = None
        self.roi = list(roi or [])

    def set_roi(self, roi: Optional[Sequence[Tuple[float, float, float, float]]]) -> None:
        self.roi = list(roi or [])

    def _get(self) -> OCRBackend:
        if self._backend is None:
            if self.backend_name == "rapidocr":
                self._backend = RapidOCRBackend()
            else:
                raise RuntimeError(f"未知 OCR 后端: {self.backend_name}")
        return self._backend

    @staticmethod
    def _rect(spec: Tuple[float, float, float, float], size: Tuple[int, int]) -> Tuple[int, int, int, int]:
        w, h = size
        x, y, rw, rh = spec
        if 0 <= x <= 1 and 0 <= y <= 1 and 0 < rw <= 1 and 0 < rh <= 1:
            x, y, rw, rh = x * w, y * h, rw * w, rh * h
        x = max(0, min(w - 1, int(x)))
        y = max(0, min(h - 1, int(y)))
        rw = max(1, min(w - x, int(rw)))
        rh = max(1, min(h - y, int(rh)))
        return x, y, rw, rh

    def recognize(self, image_rgb: bytes, size: Tuple[int, int]) -> List[OCRLine]:
        try:
            if not self.roi:
                return self._get().recognize(image_rgb, size)

            import numpy as np  # type: ignore
            w, h = size
            img = np.frombuffer(image_rgb, dtype=np.uint8).reshape(h, w, 3)
            all_lines: List[OCRLine] = []
            for spec in self.roi:
                x, y, rw, rh = self._rect(spec, size)
                crop = np.ascontiguousarray(img[y:y + rh, x:x + rw])
                crop_bytes = crop.tobytes()
                lines = self._get().recognize(crop_bytes, (rw, rh))
                for ln in lines:
                    box = None
                    if ln.box:
                        box = [[float(px) + x, float(py) + y] for px, py in ln.box]
                    all_lines.append(OCRLine(ln.text, ln.x + x, ln.y + y, ln.score, box))
            return all_lines
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("OCR 识别异常: %s", e)
            return []

    def text_only(self, image_rgb: bytes, size: Tuple[int, int]) -> List[str]:
        return [ln.text for ln in self.recognize(image_rgb, size)]
