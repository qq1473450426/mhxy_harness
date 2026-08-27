# -*- coding: utf-8 -*-
"""多账号管理 (规格书 §11/§12/§27)。

每个账号绑定一个游戏窗口, 持有独立的:
- 窗口句柄(WindowManager 发现)
- 输入驱动(InputDriver)
- 状态机(StateMachine)
- 日志(AccountLogger)
- Agent(GameAgent)

五开协调(Coordinator)在 Phase 5 实现, 此处提供单账号运行时。
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from automation.window import WindowManager, WindowInfo
from automation.input_driver import InputDriver
from .game_state import AccountState, GameState
from .state_machine import StateMachine
from .logging import AccountLogger

logger = logging.getLogger(__name__)


class Account:
    """一个账号的运行时容器。"""

    def __init__(self, cfg: Dict[str, Any], settings: Dict[str, Any],
                 wm: Optional[WindowManager] = None) -> None:
        self.cfg = cfg
        self.account_id: str = cfg["id"]
        self.role: str = cfg.get("role", "follower")
        self.enabled: bool = cfg.get("enabled", True)
        self.window_title: str = cfg.get("window_title", "梦幻西游")

        self.state = AccountState(
            account_id=self.account_id, role=self.role,
            window_title=self.window_title, enabled=self.enabled)

        # 组件
        self.wm = wm or WindowManager()
        self.win: Optional[WindowInfo] = None
        self.driver: Optional[InputDriver] = None
        self.sm = StateMachine(self.account_id)
        self.logger = AccountLogger(
            self.account_id,
            log_dir=settings.get("logging", {}).get("dir", "logs"),
            level=getattr(logging, settings.get("logging", {}).get("level", "INFO").upper()),
            max_bytes=settings.get("logging", {}).get("max_bytes", 5 * 1024 * 1024),
        )
        self.agent = None  # 由 agent.py 设置, 避免循环导入

    # ---------------- 窗口绑定 ----------------
    def bind_window(self) -> bool:
        """查找并绑定游戏窗口。"""
        if not self.wm.available:
            self.logger.error("pywin32 不可用, 无法绑定窗口")
            return False
        try:
            self.win = self.wm.bind_account(self.window_title)
            self.state.hwnd = self.win.hwnd
            self.state.win_rect = (self.win.x, self.win.y, self.win.w, self.win.h)
            self.driver = InputDriver(self.win, backend="pyautogui")
            self.logger.info(f"绑定窗口成功: {self.win.title} rect={self.win.rect}")
            return True
        except Exception as e:
            self.logger.error(f"绑定窗口失败: {e}")
            return False

    def refresh_window(self) -> bool:
        """窗口可能移动, 重新获取矩形。"""
        if self.win is None or not self.win.is_valid():
            return self.bind_window()
        wins = self.wm.find(self.window_title)
        for w in wins:
            if w.hwnd == self.win.hwnd:
                self.win = w
                self.state.win_rect = (w.x, w.y, w.w, w.h)
                if self.driver:
                    self.driver.bind(w)
                return True
        return False

    # ---------------- 运行控制 ----------------
    def start(self) -> None:
        self.state.running = True
        self.logger.info("账号启动")

    def stop(self) -> None:
        self.state.running = False
        self.logger.info("账号停止")

    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()
