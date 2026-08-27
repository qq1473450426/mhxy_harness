# -*- coding: utf-8 -*-
"""用 BattleMonitor 真实监控当前战斗到结束。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from automation.window import WindowManager
from core.battle_monitor import BattleMonitor

wm = WindowManager()
win = wm.bind_account("梦幻西游")
wm.activate(win)
mon = BattleMonitor(win)
print("开始监控当前战斗(遇怪自动alt+a)...")
r = mon.monitor_once(max_wait=150.0)
print("战斗监控结果:", r)