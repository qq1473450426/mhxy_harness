# -*- coding: utf-8 -*-
"""精确点击师父NPC身体触发对话。"""
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
print("师父匹配:", round(mv,2), "位置:", ml)
x, y = ml
cx, cy = x + tpl.shape[1]//2, y + tpl.shape[0]//2
target = (cx, cy + 15)
print("点击师父身体:", target)
r2 = driver.click(target[0], target[1])
print("点击结果:", "成功" if r2.ok else str(r2.error))
time.sleep(2.5)

img2, size2 = capture_window(win)
ocr = OCREngine("rapidocr")
lines = ocr.text_only(img2, size2)
print("\n点击后OCR:")
for t in lines:
    if any(k in t for k in ("交出", "什么", "吩咐", "选择", "给予", "完成", "任务", "确定")):
        print("   ", t[:30])
print("--- 前6个文本 ---")
for t in lines[:6]:
    print("   ", t[:24])