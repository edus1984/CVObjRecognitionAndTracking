import sys
from datetime import datetime
from types import SimpleNamespace

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
            return True, f"frame-{self.current}"
        return False, None

    def get(self, _):
        return self.fps

    def release(self):
        return None


class FakeTracks:
    def __init__(self, ids):
        self.tracker_id = ids


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
    assert stored_video.status == "completed"
    assert stored_video.events_count == 1
    assert len(stored_events) == 1
    assert stored_events[0].event_type == "customer_seated"
