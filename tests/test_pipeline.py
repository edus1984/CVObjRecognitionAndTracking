import sys
from datetime import datetime
from types import SimpleNamespace

import numpy as np

from db.models import Event, Video
from vision.pipeline import process_video


class FakeCapture:
    def __init__(self, frames=4, fps=1.0):
        self.frames = frames
        self.fps = fps
        self.current = 0

    def read(self):
        if self.current < self.frames:
            self.current += 1
            return True, np.zeros((32, 32, 3), dtype=np.uint8)
        return False, None

    def get(self, _):
        return self.fps

    def release(self):
        return None


class FakeTracks:
    def __init__(self, ids):
        self.tracker_id = ids
        self.xyxy = np.array([[1, 1, 10, 10] for _ in ids], dtype=np.float32)


class FakeWriter:
    def __init__(self, *_args, **_kwargs):
        self.frames = 0
        self.released = False

    def isOpened(self):
        return True

    def write(self, _frame):
        self.frames += 1

    def release(self):
        self.released = True


def test_process_video_persists_events(monkeypatch, test_db_session):
    import vision.pipeline as pipeline

    video = Video(
        original_filename="20260324T150520_C0104_SouthEast28.mp4",
        stored_filename="20260324T150520_C0104_SouthEast28.mp4",
        file_path="videos/20260324T150520_C0104_SouthEast28.mp4",
        capture_started_at=datetime(2026, 3, 24, 15, 5, 20),
        camera_id="C0104",
        location_name="SouthEast",
        sector_number=28,
        status="uploaded",
    )
    test_db_session.add(video)
    test_db_session.commit()
    test_db_session.refresh(video)

    monkeypatch.setattr(pipeline.cv2, "VideoCapture", lambda _path: FakeCapture(frames=4, fps=1.0))
    monkeypatch.setattr(pipeline, "_create_video_writer", lambda *_args, **_kwargs: FakeWriter())

    fake_detector_module = SimpleNamespace(detect=lambda frame: {"frame": frame})
    fake_tracker_module = SimpleNamespace(track=lambda _detections: FakeTracks([1]))
    monkeypatch.setitem(sys.modules, "vision.detector", fake_detector_module)
    monkeypatch.setitem(sys.modules, "vision.tracker", fake_tracker_module)

    summary = process_video(
        path=video.file_path,
        db=test_db_session,
        video_id=video.id,
        capture_started_at=video.capture_started_at,
    )

    stored_video = test_db_session.query(Video).filter(Video.id == video.id).first()
    stored_events = test_db_session.query(Event).filter(Event.video_id == video.id).all()

    assert summary["video_id"] == video.id
    assert summary["frames"] == 4
    assert summary["bound_boxes_file_path"].endswith(video.stored_filename)
    assert stored_video.status == "completed"
    assert stored_video.events_count == 0
    assert len(stored_events) == 0
