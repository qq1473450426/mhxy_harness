# -*- coding: utf-8 -*-
"""实时截图 (Level 1)。

设计原则(规格书 §26):
- 主截图方案使用 mss(快), 禁用 PIL ImageGrab 作为主方案
- 按窗口区域截图, 返回 RGB 字节流 + (w, h)
"""
from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class CaptureError(Exception):
    """截图失败。"""


def capture_window(win) -> Tuple[bytes, Tuple[int, int]]:
    """抓取窗口客户区截图。

    Args:
        win: WindowInfo(需要 .x .y .w .h 属性)

    Returns:
        (RGB bytes w*h*3, (width, height))
    """
    try:
        import mss  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:
        raise CaptureError(f"截图需要 mss + numpy: {e}") from e

    rect = {"left": win.x, "top": win.y, "width": win.w, "height": win.h}
    try:
        with mss.mss() as sct:
            shot = sct.grab(rect)
    except Exception as e:
        raise CaptureError(f"mss 截图失败: {e}") from e

    arr = np.asarray(shot)  # BGRA
    rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
    return rgb.tobytes(), (rgb.shape[1], rgb.shape[0])


def capture_window_pil(win) -> Tuple[bytes, Tuple[int, int]]:
    """备用: PIL ImageGrab 截图(速度慢, 仅作 fallback)。"""
    try:
        from PIL import ImageGrab  # type: ignore
    except Exception as e:
        raise CaptureError(f"PIL 不可用: {e}") from e
    img = ImageGrab.grab(bbox=(win.x, win.y, win.x + win.w, win.y + win.h))
    return img.tobytes(), img.size


def capture_to_png(win, path: str) -> bool:
    """截图并保存 PNG(用于日志/Replay)。"""
    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        logger.error("保存截图需要 Pillow: %s", e)
        return False
    data, (w, h) = capture_window(win)
    img = Image.frombytes("RGB", (w, h), data)
    img.save(path)
    return True
