# -*- coding: utf-8 -*-
"""真实执行演示: 激活窗口 -> 识别 -> 真实点击 -> 验证效果。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
from automation.window import WindowManager
from automation.input_driver import InputDriver
from vision.capture import capture_window
from vision.ocr import OCREngine
from vision.detector import TemplateMatcher
from core.state_machine import StateMachine
import yaml
import numpy as np

wm = WindowManager()
win = wm.bind_account("梦幻西游 ONLINE")
print("绑定窗口:", win.title, win.rect)
wm.activate(win)
time.sleep(1.0)

driver = InputDriver(win)
driver._pyautogui()
print("pyautogui: 已加载")

tpl_path = "D:/Deepseek/mhxy/config/templates.yaml"
with open(tpl_path, "r", encoding="utf-8") as f:
    tpl_cfg = yaml.safe_load(f) or {}
matcher = TemplateMatcher(tpl_cfg)
ocr = OCREngine("rapidocr")
sm = StateMachine("acc1")

def observe():
    img, size = capture_window(win)
    texts = ocr.text_only(img, size)
    gs = sm.update(texts, img, size)
    bgr = np.frombuffer(img, dtype="uint8").reshape(size[1], size[0], 3)[:, :, ::-1].copy()
    elems = matcher.match_all(bgr)
    return gs, elems

print("\n== 步骤1: 观察当前状态 ==")
gs, elems = observe()
print("状态:", gs.status.value, "| 地图:", gs.map_name, "| 任务:", gs.task_name, gs.task_progress)

if "task_track_btn" in elems:
    cx, cy = elems["task_track_btn"].center
    print(f"\n== 步骤2: 真实点击任务追踪按钮 @窗口内({cx},{cy}) ==")
    print(f"  屏幕坐标: ({win.x+cx}, {win.y+cy})")
    r = driver.click(cx, cy)
    print("  点击结果:", "成功" if r.ok else ("失败: " + str(r.error)))
    time.sleep(1.2)
    print("\n== 步骤3: 点击后重新观察 ==")
    gs2, elems2 = observe()
    print("点击后状态:", gs2.status.value)
    print("点击后对话框:", gs2.dialog_text[:80])
else:
    print("未检测到任务追踪按钮")
print("\n== 真实执行演示完成 ==")