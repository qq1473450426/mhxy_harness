import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from ultralytics import YOLO
import torch
print("设备:", "CUDA" if torch.cuda.is_available() else "CPU")
model = YOLO("D:/Deepseek/mhxy/yolov8n.pt")
# 截图当前游戏窗口
from automation.window import WindowManager
from vision.capture import capture_window
from PIL import Image
wm = WindowManager()
win = wm.bind_account("梦幻西游")
img, size = capture_window(win)
im = Image.frombytes("RGB", size, img)
im.save("D:/Deepseek/mhxy/logs/yolo_test.png")
print("截图OK, 尺寸", size)
# GPU推理
results = model("D:/Deepseek/mhxy/logs/yolo_test.png")
print("检测结果数:", len(results[0].boxes))
for b in results[0].boxes[:5]:
    print("  cls", b.cls.item(), "conf", round(b.conf.item(),2))
print("YOLO GPU 推理 OK")