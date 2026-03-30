from ultralytics import YOLO
from config import YOLO_MODEL

model = YOLO(YOLO_MODEL)


def detect(frame):
    results = model(frame)
    return results