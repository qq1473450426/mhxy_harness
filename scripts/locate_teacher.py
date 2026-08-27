# -*- coding: utf-8 -*-
"""模板匹配定位师父NPC -> 准备点击。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
import cv2
import numpy as np

screen = cv2.imread("D:/Deepseek/mhxy/logs/scan/20260827_212912.png")
tpl = cv2.imread("D:/Deepseek/mhxy/logs/teacher_2.png")
print("屏幕:", screen.shape, "模板:", tpl.shape)

result = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
_, max_val, _, max_loc = cv2.minMaxLoc(result)
print(f"模板匹配: 置信度={max_val:.3f} 位置={max_loc}")

if max_val > 0.6:
    x, y = max_loc
    cx, cy = x + tpl.shape[1]//2, y + tpl.shape[0]//2
    print(f"师父NPC 中心坐标(窗口内) = ({cx},{cy})")
    print("屏幕绝对坐标 =", (1+cx, 3+cy))
else:
    print("匹配度低, 师父可能不在当前画面或需更新模板")