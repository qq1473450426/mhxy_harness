# -*- coding: utf-8 -*-
"""强制激活窗口后用SendMessage点击, 规避SetForegroundWindow拒绝。"""
import sys, os, time
sys.path.insert(0, "D:/Deepseek/mhxy")
import win32gui, win32con, win32api

# 找到游戏窗口并强制激活
hwnd = None
def cb(h, _):
    global hwnd
    t = win32gui.GetWindowText(h) or ""
    if "梦幻西游" in t and "Chrome" not in t:
        hwnd = h
win32gui.EnumWindows(cb, None)
print("游戏窗口hwnd:", hwnd)
if hwnd:
    # 强制恢复到前台
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32api.SendMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_RESTORE, 0)
    win32gui.SetForegroundWindow(hwnd)
    print("窗口已尝试激活")
    time.sleep(1.0)
    # 获取窗口位置
    rect = win32gui.GetWindowRect(hwnd)
    print("窗口rect:", rect)