from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from db.models import Video


def test_upload_rejects_invalid_filename(monkeypatch, test_db_session, temp_videos_dir):
    import api.main as api_main

    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "VIDEOS_DIR", temp_videos_dir)
    monkeypatch.setattr(
        api_main,
        "process_video",
        lambda path, db, video_id, capture_started_at: {"video_id": video_id, "frames": 0, "events": 0, "fps": 0},
    )

    def override_get_db():
        yield test_db_session

    api_main.app.dependency_overrides[api_main.get_db] = override_get_db

    with TestClient(api_main.app) as client:
        response = client.post(
            "/upload",
            files={"file": ("invalid_name.mp4", b"binarycontent", "video/mp4")},
        )

    api_main.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Invalid video filename format" in response.json()["detail"]


def test_upload_persists_video_and_calls_pipeline(monkeypatch, test_db_session, temp_videos_dir):
    import api.main as api_main

    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "VIDEOS_DIR", temp_videos_dir)

    captured = {}

    def fake_process_video(path, db, video_id, capture_started_at):
        captured["path"] = path
        captured["video_id"] = video_id
        captured["capture_started_at"] = capture_started_at
        row = db.query(Video).filter(Video.id == video_id).first()
        row.status = "completed"
        row.events_count = 2
        db.commit()
        return {"video_id": video_id, "frames": 20, "events": 2, "fps": 10.0}

    monkeypatch.setattr(api_main, "process_video", fake_process_video)

    def override_get_db():
        yield test_db_session

    api_main.app.dependency_overrides[api_main.get_db] = override_get_db

    filename = "20260324T150520_C0104_SouthEast28.mp4"

    with TestClient(api_main.app) as client:
        response = client.post(
            "/upload",
            files={"file": (filename, b"binarycontent", "video/mp4")},
        )

        list_response = client.get("/videos")

    api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"

    assert Path(captured["path"]).name == filename
    assert captured["capture_started_at"] == datetime(2026, 3, 24, 15, 5, 20)

    videos = list_response.json()
    assert list_response.status_code == 200
    assert len(videos) == 1
    assert videos[0]["original_filename"] == filename
    assert videos[0]["camera_id"] == "C0104"
