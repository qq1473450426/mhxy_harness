# -*- coding: utf-8 -*-
"""MockGame 模拟器 (规格书 §42)。

在无真实游戏的情况下测试 Agent:
- 模拟城市/地图/NPC/任务/战斗/弹窗/死亡/掉线
- 支持师门任务完整流程: 接任务->跑图->交互->交任务->加环
- 通过 Screen 接口让 Agent 的观察流程无缝工作
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .game_state import GameStatus


@dataclass
class MockScreen:
    """模拟的游戏画面(由 OCR 文本组成)。"""

    texts: List[str] = field(default_factory=list)

    def render(self) -> bytes:
        """模拟 RGB 画面(纯色, 仅供流程测试)。"""
        return b"\x40\x40\x40" * (320 * 240)

    @property
    def size(self):
        return (320, 240)


class MockGame:
    """模拟游戏世界: 提供观察 + 动作反馈。"""

    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        self.map_name = "长安城"
        self.position = (304, 137)
        self.hp = 800
        self.mp = 600
        self.task = "师门任务"
        self.round = 1
        self.in_battle = False
        self.dialog_open = False
        self.task_done = False
        self.dead = False
        self.disconnected = False
        self._phase = "idle"

    def observe(self) -> MockScreen:
        """生成当前画面文本。"""
        texts = [
            f"X:{self.position[0]} Y:{self.position[1]}",
            self.map_name,
            f"气血 {self.hp}/1000",
        ]
        if self.task:
            if self.task_done:
                texts.append(f"{self.task} 完成，找师父交报告去")
            else:
                texts.append(f"{self.task} 第{self.round}次")
        if self.in_battle:
            texts.extend(["战斗", f"回合 {self.round}"])
        if self.dialog_open:
            texts.extend(["请选择", "接受", "提交"])
        if self.dead:
            texts.append("你已阵亡")
        if self.disconnected:
            texts.append("连接已断开")
        return MockScreen(texts)

    def act(self, action: str) -> bool:
        """模拟动作执行, 返回是否改变状态。"""
        if action == "OPEN_TASK":
            self.dialog_open = True
        elif action == "ACCEPT_TASK":
            self.task_done = False
            self.round += 1
        elif action == "NAVIGATE":
            # 跑图: 到达目标后触发交互
            self.position = (400, 200)
            self.dialog_open = True
            self.task_done = True
        elif action == "INTERACT":
            self.dialog_open = False
            self.task_done = True
        elif action == "SUBMIT_TASK":
            self.dialog_open = False
            self.task_done = False
            self.round += 1
        elif action == "BATTLE_AUTO":
            self.in_battle = False
        elif action in ("IDLE", "WAIT"):
            pass
        return True
