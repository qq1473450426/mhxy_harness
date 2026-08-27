# -*- coding: utf-8 -*-
"""放大中央NPC区, 看师父名字和位置。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from PIL import Image
im = Image.open("D:/Deepseek/mhxy/logs/scan/20260827_213329.png")
crop = im.crop((330, 250, 600, 480))
crop = crop.resize((crop.width*2, crop.height*2))
crop.save("D:/Deepseek/mhxy/logs/npc_center_zoom.png")
print("中央NPC区放大:", crop.size)