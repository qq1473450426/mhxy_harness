# -*- coding: utf-8 -*-
"""统一 Windows 输入驱动，桌面端默认使用 pywin32。"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from .window import WindowInfo

logger = logging.getLogger(__name__)

@dataclass
class ActionResult:
    ok: bool
    desc: str = ""
    error: Optional[str] = None

@dataclass
class Action:
    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    key: Optional[str] = None
    mods: list = field(default_factory=list)
    text: Optional[str] = None
    ms: int = 0
    desc: str = ""

class InputDriver:
    """真实 Windows 鼠标/键盘输入，坐标使用窗口左上角相对坐标。"""
    def __init__(self, win: Optional[WindowInfo] = None, backend: str = "win32",
                 failsafe: bool = True, move_duration: float = 0.08) -> None:
        self.win = win
        self.backend_name = backend or "win32"
        self._failsafe = failsafe
        self.move_duration = max(0.0, float(move_duration))

    def bind(self, win: WindowInfo) -> None:
        self.win = win

    def to_abs(self, x: int, y: int) -> tuple:
        if self.win is None:
            raise RuntimeError("InputDriver 未绑定窗口")
        return self.win.x + int(x), self.win.y + int(y)

    @staticmethod
    def _win32():
        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
            return win32api, win32con
        except Exception as exc:
            raise RuntimeError(f"pywin32 不可用: {exc}") from exc

    def _move(self, x: int, y: int) -> None:
        api, _ = self._win32()
        cur_x, cur_y = api.GetCursorPos()
        duration = self.move_duration
        if duration <= 0:
            api.SetCursorPos((x, y)); return
        steps = max(2, int(duration * 60))
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3.0 - 2.0 * t)
            api.SetCursorPos((round(cur_x + (x - cur_x) * t), round(cur_y + (y - cur_y) * t)))
            time.sleep(duration / steps)

    def exec(self, action: Action) -> ActionResult:
        try:
            if action.type == "MOVE":
                self._move(*self.to_abs(action.x, action.y))
            elif action.type == "CLICK":
                api, con = self._win32(); self._move(*self.to_abs(action.x, action.y))
                api.mouse_event(con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); time.sleep(0.035)
                api.mouse_event(con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif action.type == "DBL_CLICK":
                self.exec(Action("CLICK", x=action.x, y=action.y)); time.sleep(0.08)
                self.exec(Action("CLICK", x=action.x, y=action.y))
            elif action.type == "RIGHT_CLICK":
                api, con = self._win32(); self._move(*self.to_abs(action.x, action.y))
                api.mouse_event(con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0); time.sleep(0.035)
                api.mouse_event(con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            elif action.type == "PRESS":
                self._press(action.key)
            elif action.type == "HOTKEY":
                self._hotkey(list(action.mods) + ([action.key] if action.key else []))
            elif action.type == "TYPE":
                self._type_text(action.text or "")
            elif action.type == "WAIT":
                time.sleep(max(0, action.ms) / 1000.0)
            else:
                return ActionResult(False, action.desc, f"未知动作类型 {action.type}")
            return ActionResult(True, action.desc or action.type)
        except Exception as exc:
            logger.warning("动作执行失败 %s: %s", action, exc)
            return ActionResult(False, action.desc, str(exc))

    def _press(self, key: Optional[str]) -> None:
        if not key: return
        if "+" in key:
            self._hotkey([p.strip() for p in key.split("+") if p.strip()]); return
        api, con = self._win32(); vk = _vk(key)
        api.keybd_event(vk, 0, 0, 0); api.keybd_event(vk, 0, con.KEYEVENTF_KEYUP, 0)

    def _hotkey(self, keys: list) -> None:
        api, con = self._win32(); vks = [_vk(str(k)) for k in keys]
        for vk in vks: api.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks): api.keybd_event(vk, 0, con.KEYEVENTF_KEYUP, 0)

    def _type_text(self, text: str) -> None:
        for ch in text:
            if not ch.isascii():
                raise ValueError("TYPE 当前仅支持 ASCII；中文输入请使用上层剪贴板适配")
            self._press(ch)

    def click(self, x: int, y: int, desc: str = "") -> ActionResult:
        return self.exec(Action("CLICK", x=x, y=y, desc=desc))
    def move(self, x: int, y: int, desc: str = "") -> ActionResult:
        return self.exec(Action("MOVE", x=x, y=y, desc=desc))
    def press(self, key: str, desc: str = "") -> ActionResult:
        return self.exec(Action("PRESS", key=key, desc=desc))
    def type(self, text: str, desc: str = "") -> ActionResult:
        return self.exec(Action("TYPE", text=text, desc=desc))
    def wait(self, ms: int, desc: str = "") -> ActionResult:
        return self.exec(Action("WAIT", ms=ms, desc=desc))


def _vk(key: str) -> int:
    key_l = key.lower()
    if key_l in _VK: return _VK[key_l]
    if len(key) == 1 and key.isascii(): return ord(key.upper())
    raise ValueError(f"不支持的按键: {key}")

_VK = {
    "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "space": 0x20, "tab": 0x09,
    "backspace": 0x08, "delete": 0x2E, "left": 0x25, "up": 0x26, "right": 0x27,
    "down": 0x28, "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
