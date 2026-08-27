# -*- coding: utf-8 -*-
"""重新精确裁剪右侧绿衣师父NPC。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from PIL import Image
im = Image.open("D:/Deepseek/mhxy/logs/scan/20260827_212912.png")
# 右侧绿衣黑胡师父: 从原图看约 (420-540, 250-430)
teacher = im.crop((415, 245, 540, 430))
teacher.save("D:/Deepseek/mhxy/logs/teacher_2.png")
print("teacher_2:", teacher.size)
# 放大查看
teacher.resize((teacher.width*2, teacher.height*2)).save("D:/Deepseek/mhxy/logs/teacher_2_zoom.png")
print("teacher_2_zoom:", teacher.size[0]*2, teacher.size[1]*2)