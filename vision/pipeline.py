import cv2
from vision.detector import detect
from vision.tracker import track
from vision.events import EventEngine

engine = EventEngine()


def process_video(path):
    cap = cv2.VideoCapture(path)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = detect(frame)
        tracks = track(detections)

        events = engine.update(tracks)

    cap.release()