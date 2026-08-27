# -*- coding: utf-8 -*-
"""双击师父NPC触发对话(梦幻西游双击NPC)。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
import cv2
import numpy as np
from automation.window import WindowManager
from automation.input_driver import InputDriver
from vision.capture import capture_window
from vision.ocr import OCREngine

wm = WindowManager()
win = wm.bind_account("梦幻西游")
wm.activate(win)
time.sleep(0.5)
driver = InputDriver(win)
driver._pyautogui()

img, size = capture_window(win)
bgr = np.frombuffer(img, dtype="uint8").reshape(size[1], size[0], 3)[:, :, ::-1].copy()
tpl = cv2.imread("D:/Deepseek/mhxy/logs/teacher_2.png")
r = cv2.matchTemplate(bgr, tpl, cv2.TM_CCOEFF_NORMED)
_, mv, _, ml = cv2.minMaxLoc(r)
print("师父匹配:", round(mv,2))
x, y = ml
cx, cy = x + tpl.shape[1]//2, y + tpl.shape[0]//2
# 点师父身体中心
print("双击师父 @", (cx, cy))
r2 = driver.exec(__import__("automation.input_driver", fromlist=["Action"]).Action("DBL_CLICK", x=cx, y=cy, desc="双击师父"))
print("双击结果:", "成功" if r2.ok else str(r2.error))
time.sleep(2.5)

img2, size2 = capture_window(win)
ocr = OCREngine("rapidocr")
lines = ocr.text_only(img2, size2)
print("\n双击后OCR:")
for t in lines:
    if any(k in t for k in ("交出", "什么", "吩咐", "选择", "给予", "完成", "任务", "确定", "听说")):
        print("   ", t[:30])
print("--- 完整文本前8 ---")
for t in lines[:8]:
    print("   ", t[:26])