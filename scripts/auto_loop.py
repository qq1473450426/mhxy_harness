# -*- coding: utf-8 -*-
"""持续自主循环: 遇怪自动战斗, 战斗结束检查师门任务是否可交。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
from automation.window import WindowManager
from vision.capture import capture_window
from vision.ocr import OCREngine
from core.battle_monitor import BattleMonitor
from core.state_machine import StateMachine

wm = WindowManager()
win = wm.bind_account("梦幻西游")
wm.activate(win)
ocr = OCREngine("rapidocr")
sm = StateMachine("loop")
mon = BattleMonitor(win)

def observe():
    img, size = capture_window(win)
    return sm.update(ocr.text_only(img, size), img, size)

print("持续自主循环开始(遇怪自动打, 战斗结束检查师门)...")
for i in range(30):
    gs = observe()
    print(f"  [{i*3}s] 状态={gs.status.value} 位置={gs.position}")
    if gs.status.value == "BATTLE":
        print("  进入战斗, 自动监控...")
        r = mon.monitor_once(max_wait=120.0)
        print("  战斗结果:", r)
    else:
        # 非战斗, 检查是否到师父/可交任务
        if "师门" in gs.dialog_text or "师父" in gs.dialog_text or "报告" in gs.dialog_text:
            print("  发现师门任务:", gs.dialog_text[:40])
            if "完成" in gs.dialog_text or "报告" in gs.dialog_text:
                print("  师门任务可交! (打alt+q看面板, 或已到师父处)")
                break
    time.sleep(3.0)
print("循环结束")