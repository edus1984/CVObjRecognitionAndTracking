from ultralytics import YOLO
import supervision as sv
from config import YOLO_MODEL

model = YOLO(YOLO_MODEL)


def detect(frame):
    results = model.predict(frame, verbose=False)
    if results:
        result = results[0]
        detections = sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int)
        )
        return detections
    else:
        return sv.Detections.empty()