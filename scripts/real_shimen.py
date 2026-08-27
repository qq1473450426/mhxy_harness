# -*- coding: utf-8 -*-
"""完整真实师门执行器: 绑定窗口 -> 识别 -> 状态机 -> 真实点击接/交任务。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
from automation.window import WindowManager
from automation.input_driver import InputDriver
from vision.capture import capture_window
from vision.ocr import OCREngine
from vision.detector import TemplateMatcher
from core.state_machine import StateMachine
from tasks.shimen import ShimenTask
import yaml
import numpy as np

wm = WindowManager()
win = wm.bind_account("梦幻西游 ONLINE")
print("绑定窗口:", win.title)
wm.activate(win)
time.sleep(0.8)

driver = InputDriver(win)
driver._pyautogui()

tpl_path = "D:/Deepseek/mhxy/config/templates.yaml"
with open(tpl_path, "r", encoding="utf-8") as f:
    tpl_cfg = yaml.safe_load(f) or {}
matcher = TemplateMatcher(tpl_cfg)
ocr = OCREngine("rapidocr")
sm = StateMachine("acc1")

# 师门任务(绑定真实动作钩子)
task = ShimenTask(max_rounds=20)

def observe():
    img, size = capture_window(win)
    texts = ocr.text_only(img, size)
    gs = sm.update(texts, img, size)
    bgr = np.frombuffer(img, dtype="uint8").reshape(size[1], size[0], 3)[:, :, ::-1].copy()
    elems = matcher.match_all(bgr)
    return gs, elems

def ctrl(fn, *args):
    """安全执行动作并打印结果。"""
    try:
        r = fn(*args)
        print("    [点击]", "成功" if r.ok else str(r.error))
        return r
    except Exception as e:
        print("    [动作异常]", str(e)[:60])
        return None

print("\n== 完整真实师门执行(最多10步) ==")
for step in range(10):
    gs, elems = observe()
    print(f"\n--- 第{step+1}步: 状态={gs.status.value} 任务={gs.task_name}{gs.task_progress} ---")
    print("  对话框:", gs.dialog_text[:50])

    # 根据状态机决策并真实执行
    action = task.step(gs)
    act = action.get("action")
    print(f"  决策: {act} - {action.get(chr(114)+chr(101)+chr(97)+chr(115)+chr(111)+chr(110), chr(39)+chr(39))}")

    if act == "OPEN_TASK":
        ctrl(driver.press, "alt+q")   # 打开任务面板
    elif act in ("SUBMIT_TASK", "DIALOG_CHOICE"):
        # 交任务(点任务追踪或确认按钮)
        if "task_track_btn" in elems:
            cx, cy = elems["task_track_btn"].center
            ctrl(driver.click, cx, cy)
        else:
            ctrl(driver.press, "enter")
    elif act == "BATTLE_AUTO":
        ctrl(driver.press, "alt+a")
    elif act == "ACCEPT_TASK":
        ctrl(driver.press, "enter")
    elif act in ("NAVIGATE", "RUN"):
        print("    [跑图] 需坐标定位, 跳过(等待用户手动或校准)")
    elif act == "DONE":
        print("  == 师门任务完成! ==")
        break
    time.sleep(1.5)

print("\n== 真实师门执行结束 ==")