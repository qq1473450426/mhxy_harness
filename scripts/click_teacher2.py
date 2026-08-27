# -*- coding: utf-8 -*-
"""真实点击师门师父交任务。"""
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
time.sleep(0.8)
driver = InputDriver(win)
driver._pyautogui()

def find_teacher(img_bgr):
    tpl = cv2.imread("D:/Deepseek/mhxy/logs/teacher_2.png")
    r = cv2.matchTemplate(img_bgr, tpl, cv2.TM_CCOEFF_NORMED)
    _, mv, _, ml = cv2.minMaxLoc(r)
    if mv > 0.55:
        x, y = ml
        return (x + tpl.shape[1]//2, y + tpl.shape[0]//2, mv)
    return None

print("== 截图定位师父 ==")
img, size = capture_window(win)
bgr = np.frombuffer(img, dtype="uint8").reshape(size[1], size[0], 3)[:, :, ::-1].copy()
res = find_teacher(bgr)
if not res:
    print("未找到师父NPC")
    raise SystemExit
cx, cy, conf = res
print("师父位置: 窗口内("+str(cx)+","+str(cy)+") 置信度"+str(round(conf,2)))
print("== 真实点击师父 ==")
r = driver.click(cx, cy)
print("点击结果:", "成功" if r.ok else str(r.error))
time.sleep(2.0)

img2, size2 = capture_window(win)
ocr = OCREngine("rapidocr")
lines = ocr.text_only(img2, size2)
print("\n点击后OCR(找对话/交任务):")
for t in lines:
    if any(k in t for k in ("交出", "交", "任务", "给予", "什么", "吩咐", "选择", "完成", "确定")):
        print("   ", t[:30])