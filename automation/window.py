# -*- coding: utf-8 -*-
"""Windows 游戏窗口管理 (Level 1)。

职责:
- 枚举所有可见窗口, 按标题子串匹配梦幻西游客户端
- 保存 HWND / 窗口矩形
- 激活(置前) / 最小化 / 恢复
- 校验窗口是否仍然有效

设计原则(规格书 §27):
- 必须能够发现窗口、识别标题、保存 HWND、绑定账号、激活、最小化/恢复
- 支持多窗口(五开)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

try:  # pragma: no cover - Windows only
    import win32gui  # type: ignore
    import win32con  # type: ignore
    import win32api  # type: ignore
    HAS_WIN32 = True
except Exception:  # pragma: no cover
    win32gui = win32con = win32api = None
    HAS_WIN32 = False

logger = logging.getLogger(__name__)


class WindowError(Exception):
    """窗口管理通用错误(未找到/依赖缺失等)。"""


class WindowLost(WindowError):
    """窗口句柄失效(游戏关闭/崩溃)。"""


@dataclass
class WindowInfo:
    """一个游戏窗口的完整描述。"""

    hwnd: int
    title: str
    x: int
    y: int
    w: int
    h: int
    visible: bool = True

    @property
    def rect(self) -> tuple:
        return (self.x, self.y, self.w, self.h)

    def is_valid(self) -> bool:
        """句柄是否仍然指向有效窗口。"""
        if not HAS_WIN32:
            return False
        try:
            return bool(win32gui.IsWindow(self.hwnd))
        except Exception:
            return False

    def is_visible(self) -> bool:
        if not HAS_WIN32:
            return False
        try:
            return bool(win32gui.IsWindowVisible(self.hwnd))
        except Exception:
            return False


class WindowManager:
    """窗口发现与管理。

    用法:
        wm = WindowManager()
        wins = wm.find("梦幻西游")        # 找所有匹配窗口
        win = wins[0]
        wm.activate(win)                  # 置前
        wm.minimize(win) / wm.restore(win)
    """

    def __init__(self) -> None:
        self._windows: List[WindowInfo] = []
        if not HAS_WIN32:
            logger.warning("未安装 pywin32, 窗口管理不可用")

    @property
    def available(self) -> bool:
        return HAS_WIN32

    # ---------------- 发现 ----------------
    def find(self, title_substr: str = "", visible_only: bool = True) -> List[WindowInfo]:
        """按标题子串查找窗口。空子串返回所有可见窗口。"""
        if not HAS_WIN32:
            return []
        found: List[WindowInfo] = []

        def _cb(hwnd, _):
            if visible_only and not win32gui.IsWindowVisible(hwnd):
                return
            t = win32gui.GetWindowText(hwnd) or ""
            if title_substr and title_substr not in t:
                return
            try:
                x, y, r, b = win32gui.GetWindowRect(hwnd)
                if r <= x or b <= y:  # 退化矩形(最小化窗口被移到 -32000)
                    if not visible_only:
                        found.append(WindowInfo(hwnd, t, x, y, 0, 0, visible=False))
                    return
                found.append(WindowInfo(hwnd, t, x, y, r - x, b - y, visible=True))
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)
        self._windows = found
        return found

    def find_game_windows(self, title: str = "梦幻西游") -> List[WindowInfo]:
        """查找所有游戏客户端窗口(排除浏览器等辅助窗口)。"""
        all_wins = self.find(title, visible_only=True)
        # 游戏主窗口标题一般含 "ONLINE", 浏览器标题含 "Chrome"/"Harness"
        game = [
            w for w in all_wins
            if "ONLINE" in w.title or "畅玩服" in w.title
        ]
        return game or all_wins

    def bind_account(self, window_title: str) -> WindowInfo:
        """按账号配置的窗口标题绑定第一个匹配窗口。"""
        wins = self.find_game_windows(window_title) if window_title else []
        if not wins:
            raise WindowError(f"未找到标题包含 '{window_title}' 的游戏窗口, 请先启动游戏")
        return wins[0]

    # ---------------- 操作 ----------------
    def activate(self, win: WindowInfo) -> bool:
        """将窗口置前并激活(若支持)。"""
        if not HAS_WIN32:
            return False
        try:
            win32gui.ShowWindow(win.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(win.hwnd)
            return True
        except Exception as e:
            logger.warning("激活窗口失败 hwnd=%s: %s", win.hwnd, e)
            return False

    def minimize(self, win: WindowInfo) -> bool:
        if not HAS_WIN32:
            return False
        try:
            win32gui.ShowWindow(win.hwnd, win32con.SW_MINIMIZE)
            return True
        except Exception:
            return False

    def restore(self, win: WindowInfo) -> bool:
        """恢复最小化窗口。

        实测: 梦幻西游窗口 ShowWindow(SW_RESTORE) 无效,
        需 SendMessage(WM_SYSCOMMAND, SC_RESTORE)。
        """
        if not HAS_WIN32:
            return False
        try:
            win32gui.ShowWindow(win.hwnd, win32con.SW_RESTORE)
            win32api.SendMessage(win.hwnd, win32con.WM_SYSCOMMAND,
                                 win32con.SC_RESTORE, 0)
            return True
        except Exception:
            return False

    def bring_front(self, win: WindowInfo) -> bool:
        return self.activate(win)

    # ---------------- 校验 ----------------
    def ensure_valid(self, win: WindowInfo) -> None:
        if not win.is_valid():
            raise WindowLost(f"窗口已失效 hwnd={win.hwnd} title={win.title!r}")
        if not win.is_visible():
            logger.info("窗口当前不可见(可能最小化) hwnd=%s", win.hwnd)
