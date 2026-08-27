# -*- coding: utf-8 -*-
"""统一输入驱动 (InputDriver)。

设计原则(规格书 §28):
- 业务代码不直接调用 pyautogui.click(), 而是 input_driver.click(account_id, ...)
- 支持后端切换: pyautogui | win32 SendInput(预留)
- 所有动作基于"窗口内相对坐标", 由驱动换算为屏幕绝对坐标
- 未来可以接入 DirectInput / 硬件级输入

Action 类型(规格书 §9 子集, Phase 1 先实现基础集):
    MOVE / CLICK / DBL_CLICK / RIGHT_CLICK / PRESS / HOTKEY / TYPE / WAIT
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .window import WindowInfo

logger = logging.getLogger(__name__)

# 紧急停止快捷键(规格书安全原则): 鼠标甩到屏幕角落由 pyautogui failsafe 处理


@dataclass
class ActionResult:
    """一次动作执行结果。"""

    ok: bool
    desc: str = ""
    error: Optional[str] = None


@dataclass
class Action:
    """统一动作描述。type 见 _SUPPORTED, x/y 为窗口内相对坐标。"""

    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    key: Optional[str] = None          # PRESS/HOTKEY 用
    mods: list = field(default_factory=list)  # HOTKEY 修饰键
    text: Optional[str] = None         # TYPE 用
    ms: int = 0                        # WAIT 用
    desc: str = ""


class InputDriver:
    """输入驱动: 持有窗口绑定信息, 提供统一动作执行。"""

    def __init__(self, win: Optional[WindowInfo] = None, backend: str = "pyautogui",
                 failsafe: bool = True) -> None:
        self.win = win
        self.backend_name = backend
        self._pg = None
        self._failsafe = failsafe

    # ---------------- 后端加载 ----------------
    def _pyautogui(self):
        """延迟加载 pyautogui。"""
        if self._pg is None:
            try:
                import pyautogui  # type: ignore
                pyautogui.FAILSAFE = self._failsafe
                pyautogui.PAUSE = 0.05
                self._pg = pyautogui
            except Exception as e:
                raise RuntimeError(f"未安装 pyautogui: {e}") from e
        return self._pg

    # ---------------- 坐标换算 ----------------
    def bind(self, win: WindowInfo) -> None:
        """绑定(或换绑)窗口。"""
        self.win = win

    def to_abs(self, x: int, y: int) -> tuple:
        """窗口内相对坐标 -> 屏幕绝对坐标。"""
        if self.win is None:
            raise RuntimeError("InputDriver 未绑定窗口, 无法换算坐标")
        return (self.win.x + int(x), self.win.y + int(y))

    # ---------------- 核心执行 ----------------
    def exec(self, action: Action) -> ActionResult:
        """执行单个动作。"""
        try:
            if action.type == "MOVE":
                self._pyautogui().moveTo(*self.to_abs(action.x, action.y))
            elif action.type == "CLICK":
                self._pyautogui().click(*self.to_abs(action.x, action.y))
            elif action.type == "DBL_CLICK":
                self._pyautogui().doubleClick(*self.to_abs(action.x, action.y))
            elif action.type == "RIGHT_CLICK":
                self._pyautogui().rightClick(*self.to_abs(action.x, action.y))
            elif action.type == "PRESS":
                self._press(action.key)
            elif action.type == "HOTKEY":
                keys = list(action.mods) + [action.key]
                self._pyautogui().hotkey(*keys)
            elif action.type == "TYPE":
                self._pyautogui().write(action.text or "", interval=0.02)
            elif action.type == "WAIT":
                time.sleep(max(0, action.ms) / 1000.0)
            else:
                return ActionResult(False, action.desc, f"未知动作类型 {action.type}")
            return ActionResult(True, action.desc or action.type)
        except Exception as e:  # pragma: no cover
            logger.warning("动作执行失败 %s: %s", action, e)
            return ActionResult(False, action.desc, str(e))

    def _press(self, key: Optional[str]) -> None:
        """按键, 支持 "alt+q" 组合风格。"""
        if not key:
            return
        pg = self._pyautogui()
        if "+" in key:
            parts = [p.strip() for p in key.split("+") if p.strip()]
            if len(parts) >= 2:
                pg.hotkey(*parts)
            else:
                pg.press(parts[0])
        else:
            pg.press(key)

    # ---------------- 便捷方法 ----------------
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
