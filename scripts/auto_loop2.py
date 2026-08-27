# -*- coding: utf-8 -*-
"""持续自主循环v2: 遇怪自动打, 战斗结束打开任务面板确认能否交。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
from automation.window import WindowManager
from automation.input_driver import InputDriver
from vision.capture import capture_window
from vision.ocr import OCREngine
from core.battle_monitor import BattleMonitor
from core.state_machine import StateMachine

wm = WindowManager()
win = wm.bind_account("梦幻西游")
wm.activate(win)
driver = InputDriver(win)
driver._pyautogui()
ocr = OCREngine("rapidocr")
sm = StateMachine("loop2")
mon = BattleMonitor(win)

def observe():
    img, size = capture_window(win)
    return sm.update(ocr.text_only(img, size), img, size)

print("持续自主循环v2开始(遇怪自动打, 结束检查师门并打开面板)...")
can_submit = False
for i in range(20):
    gs = observe()
    print(f"  [{i*3}s] 状态={gs.status.value} 位置={gs.position}")
    if gs.status.value == "BATTLE":
        r = mon.monitor_once(max_wait=100.0)
        print("  战斗结果:", r)
        if r.get("after_status") == "TASK_DIALOG":
            print("  战斗结束回到任务面板")
    else:
        if "师门" in gs.dialog_text and ("完成" in gs.dialog_text or "报告" in gs.dialog_text or "师父" in gs.dialog_text):
            print("  ★ 检测到师门可交! 打开任务面板确认")
            driver.press("alt+q")
            can_submit = True
            break
    time.sleep(3.0)
print("循环结束, can_submit:", can_submit)