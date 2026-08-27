# -*- coding: utf-8 -*-
"""列出所有梦幻西游窗口及位置。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
import win32gui, win32con
wins = []
def cb(h, _):
    if not win32gui.IsWindowVisible(h):
        return
    t = win32gui.GetWindowText(h) or ""
    if "梦幻西游" in t and "Chrome" not in t:
        r = win32gui.GetWindowRect(h)
        wins.append((h, t[:30], r))
win32gui.EnumWindows(cb, None)
for h, t, r in wins:
    print("hwnd", h, "| title", t, "| rect", r)
print("窗口总数:", len(wins))