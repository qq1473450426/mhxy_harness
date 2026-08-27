# -*- coding: utf-8 -*-
"""从截图裁剪师父NPC区域, 生成训练样本。"""
import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from PIL import Image

src = "D:/Deepseek/mhxy/logs/scan/20260827_212912.png"
im = Image.open(src)
print("原图:", im.size)

# 师父NPC(绿衣黑胡男性)大致在画面中央 (350-490, 280-400)
# 先后保存几块候选区参考
candidates = {
    "teacher_c1": (350, 280, 490, 400),   # 师父候选1
    "teacher_c2": (300, 250, 450, 420),   # 师父候选2(更宽)
    "npc_group": (280, 240, 500, 430),    # NPC群
}
for name, box in candidates.items():
    c = im.crop(box)
    c.save(f"D:/Deepseek/mhxy/logs/{name}.png")
    print(f"保存 {name}: {c.size}")
print("裁剪完成")