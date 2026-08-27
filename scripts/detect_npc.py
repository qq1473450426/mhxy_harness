import sys, os
sys.path.insert(0, "D:/Deepseek/mhxy")
from ultralytics import YOLO
model = YOLO("D:/Deepseek/mhxy/yolov8n.pt")
img = "D:/Deepseek/mhxy/logs/scan/20260827_212912.png"
results = model(img)
r = results[0]
print("检测到人物数:", len(r.boxes))
# 打印每个人物的像素坐标(窗口内)
for i, box in enumerate(r.boxes):
    x1, y1, x2, y2 = box.xyxy[0].tolist()
    cx, cy = int((x1+x2)/2), int((y1+y2)/2)
    print(f"  [{i}] cls={box.cls.item()} conf={round(box.conf.item(),2)} 中心=({cx},{cy}) 框=({int(x1)},{int(y1)},{int(x2)},{int(y2)})")
print("YOLO person检测完成")