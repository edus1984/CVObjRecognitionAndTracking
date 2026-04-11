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

    videos_payload = list_response.json()
    assert list_response.status_code == 200
    assert videos_payload["pagination"]["total"] == 1
    assert len(videos_payload["items"]) == 1
    assert videos_payload["items"][0]["original_filename"] == filename
    assert videos_payload["items"][0]["camera_id"] == "C0104"


def test_list_videos_supports_filters_and_pagination(monkeypatch, test_db_session, temp_videos_dir):
    import api.main as api_main

    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "VIDEOS_DIR", temp_videos_dir)

    rows = [
        Video(
            original_filename="20260324T150520_C0104_SouthEast28.mp4",
            stored_filename="20260324T150520_C0104_SouthEast28.mp4",
            file_path="videos/20260324T150520_C0104_SouthEast28.mp4",
            capture_started_at=datetime(2026, 3, 24, 15, 5, 20),
            camera_id="C0104",
            location_name="SouthEast",
            sector_number=28,
            status="completed",
            events_count=3,
        ),
        Video(
            original_filename="20260325T110000_C9999_North1.mp4",
            stored_filename="20260325T110000_C9999_North1.mp4",
            file_path="videos/20260325T110000_C9999_North1.mp4",
            capture_started_at=datetime(2026, 3, 25, 11, 0, 0),
            camera_id="C9999",
            location_name="North",
            sector_number=1,
            status="failed",
            events_count=0,
        ),
    ]
    test_db_session.add_all(rows)
    test_db_session.commit()

    def override_get_db():
        yield test_db_session

    api_main.app.dependency_overrides[api_main.get_db] = override_get_db

    with TestClient(api_main.app) as client:
        response = client.get("/videos", params={"camera_id": "C0104", "status": "completed", "skip": 0, "limit": 1})

    api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["pagination"]["returned"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["camera_id"] == "C0104"
    assert payload["items"][0]["status"] == "completed"


def test_kpis_endpoint_returns_aggregates(monkeypatch, test_db_session, temp_videos_dir):
    import api.main as api_main
    from db.models import Event

    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "VIDEOS_DIR", temp_videos_dir)

    completed = Video(
        original_filename="20260324T150520_C0104_SouthEast28.mp4",
        stored_filename="20260324T150520_C0104_SouthEast28.mp4",
        file_path="videos/20260324T150520_C0104_SouthEast28.mp4",
        capture_started_at=datetime(2026, 3, 24, 15, 5, 20),
        camera_id="C0104",
        location_name="SouthEast",
        sector_number=28,
        status="completed",
    )
    failed = Video(
        original_filename="20260325T110000_C9999_North1.mp4",
        stored_filename="20260325T110000_C9999_North1.mp4",
        file_path="videos/20260325T110000_C9999_North1.mp4",
        capture_started_at=datetime(2026, 3, 25, 11, 0, 0),
        camera_id="C9999",
        location_name="North",
        sector_number=1,
        status="failed",
    )
    test_db_session.add_all([completed, failed])
    test_db_session.commit()
    test_db_session.refresh(completed)

    test_db_session.add_all(
        [
            Event(
                video_id=completed.id,
                person_id=1,
                event_type="customer_seated",
                frame_index=10,
                event_second=1.0,
                event_timestamp=datetime(2026, 3, 24, 15, 5, 21),
            ),
            Event(
                video_id=completed.id,
                person_id=2,
                event_type="customer_seated",
                frame_index=20,
                event_second=2.0,
                event_timestamp=datetime(2026, 3, 24, 15, 5, 22),
            ),
        ]
    )
    test_db_session.commit()

    def override_get_db():
        yield test_db_session

    api_main.app.dependency_overrides[api_main.get_db] = override_get_db

    with TestClient(api_main.app) as client:
        response = client.get("/kpis")

    api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_videos"] == 2
    assert payload["completed_videos"] == 1
    assert payload["failed_videos"] == 1
    assert payload["total_events"] == 2
    assert payload["unique_people"] == 2
    assert payload["avg_events_per_completed_video"] == 2.0
