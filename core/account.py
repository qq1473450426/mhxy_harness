# -*- coding: utf-8 -*-
"""多账号运行时容器。"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from automation.window import WindowManager, WindowInfo
from automation.input_driver import InputDriver
from .game_state import AccountState
from .state_machine import StateMachine
from .logging import AccountLogger

logger = logging.getLogger(__name__)

class Account:
    def __init__(self, cfg: Dict[str, Any], settings: Dict[str, Any], wm: Optional[WindowManager] = None) -> None:
        self.cfg = cfg
        self.account_id: str = cfg["id"]
        self.role: str = cfg.get("role", "follower")
        self.enabled: bool = cfg.get("enabled", True)
        self.window_title: str = cfg.get("window_title", "梦幻西游")
        self.state = AccountState(account_id=self.account_id, role=self.role,
                                  window_title=self.window_title, enabled=self.enabled)
        self.settings = settings
        self.wm = wm or WindowManager()
        self.win: Optional[WindowInfo] = None
        self.driver: Optional[InputDriver] = None
        self.sm = StateMachine(self.account_id)
        self.logger = AccountLogger(self.account_id,
            log_dir=settings.get("logging", {}).get("dir", "logs"),
            level=getattr(logging, settings.get("logging", {}).get("level", "INFO").upper()),
            max_bytes=settings.get("logging", {}).get("max_bytes", 5 * 1024 * 1024))
        self.agent = None

    def bind_window(self) -> bool:
        if not self.wm.available:
            self.logger.error("pywin32 不可用, 无法绑定窗口")
            return False
        try:
            self.win = self.wm.bind_account(self.window_title)
            self.state.hwnd = self.win.hwnd
            self.state.win_rect = self.win.rect
            inp = self.settings.get("input", {})
            self.driver = InputDriver(self.win,
                backend=inp.get("backend", "win32"),
                failsafe=bool(inp.get("failsafe", True)),
                move_duration=float(inp.get("move_duration", 0.08)))
            self.logger.info("绑定窗口成功: %s rect=%s input=%s", self.win.title, self.win.rect, self.driver.backend_name)
            return True
        except Exception as exc:
            self.logger.error("绑定窗口失败: %s", exc)
            return False

    def refresh_window(self) -> bool:
        if self.win is None or not self.win.is_valid():
            return self.bind_window()
        for w in self.wm.find(self.window_title):
            if w.hwnd == self.win.hwnd:
                self.win = w
                self.state.win_rect = w.rect
                if self.driver: self.driver.bind(w)
                return True
        return False

    def start(self) -> None:
        self.state.running = True
        self.logger.info("账号启动")

    def stop(self) -> None:
        self.state.running = False
        self.logger.info("账号停止")

    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()
