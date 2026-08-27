# -*- coding: utf-8 -*-
"""战斗监控器(真实模式): 识别战斗->确认自动->监控到结束->记录。

基于真实验证的 battle_assist 逻辑固化, 供 game_runner 调用。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from automation.input_driver import InputDriver
from automation.window import WindowManager, WindowInfo
from vision.capture import capture_window
from vision.ocr import OCREngine
from core.state_machine import StateMachine
from core.game_state import GameState, GameStatus

logger = logging.getLogger(__name__)


class BattleMonitor:
    """战斗监控: 遇怪自动处理 + 记录(经验学习)。"""

    def __init__(self, win: WindowInfo, auto_key: str = "alt+a") -> None:
        self.win = win
        self.driver = InputDriver(win)
        self.ocr = OCREngine("rapidocr")
        self.sm = StateMachine("battle_monitor")
        self.auto_key = auto_key
        self.battle_started = 0
        self.rounds = 0
        self.total_battles = 0
        self.poll_interval = 2.0   # 轮询间隔(测试可调小)

    def observe(self) -> GameState:
        img, size = capture_window(self.win)
        return self.sm.update(self.ocr.text_only(img, size), img, size)

    def ensure_auto_battle(self) -> bool:
        """确保自动战斗开启(按 alt+a, 已自动则无害)。"""
        try:
            r = self.driver.press(self.auto_key)
            return bool(r.ok)
        except Exception:
            return False

    def monitor_once(self, max_wait: float = 180.0) -> Dict[str, Any]:
        """监控一次战斗: 从进入战斗到结束。返回战斗统计。"""
        t0 = time.time()
        start_status = self.observe().status
        if start_status != GameStatus.BATTLE:
            return {"battled": False, "reason": "未进入战斗"}
        self.battle_started = time.time()
        self.total_battles += 1
        auto_confirmed = 0
        while time.time() - t0 < max_wait:
            gs = self.observe()
            if gs.status == GameStatus.BATTLE:
                ok = self.ensure_auto_battle()
                if ok:
                    auto_confirmed += 1
                self.rounds = gs.battle_round or self.rounds
            else:
                # 战斗结束
                duration = time.time() - self.battle_started
                logger.info("战斗结束: %.1fs 回合~%s 确认自动%d次", duration, self.rounds, auto_confirmed)
                return {
                    "battled": True,
                    "duration": round(duration, 1),
                    "rounds": self.rounds,
                    "auto_confirmed": auto_confirmed,
                    "after_status": gs.status.value,
                }
            time.sleep(self.poll_interval)
        return {"battled": False, "reason": "监控超时", "rounds": self.rounds}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_battles": self.total_battles,
            "rounds": self.rounds,
            "battle_started": self.battle_started > 0,
        }
