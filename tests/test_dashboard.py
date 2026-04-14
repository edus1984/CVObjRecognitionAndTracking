from io import BytesIO


def test_fetch_uploaded_videos_returns_empty_on_request_failure(monkeypatch):
    import dashboard.app as dashboard_app

    def raise_error(*_args, **_kwargs):
        raise dashboard_app.requests.RequestException("down")

    monkeypatch.setattr(dashboard_app.requests, "get", raise_error)

    items, pagination = dashboard_app.fetch_uploaded_videos_page()
    assert items == []
    assert pagination["total"] == 0


def test_upload_video_file_success(monkeypatch):
    import dashboard.app as dashboard_app

    class Response:
        ok = True

    monkeypatch.setattr(dashboard_app.requests, "post", lambda *_args, **_kwargs: Response())

    fake_file = BytesIO(b"video")
    fake_file.name = "20260324T150520_C0104_SouthEast28.mp4"

    ok, message = dashboard_app.upload_video_file(fake_file)
    assert ok is True
    assert "processed" in message


def test_fetch_kpis_returns_default_on_invalid_response(monkeypatch):
    import dashboard.app as dashboard_app

    class Response:
        ok = True

        @staticmethod
        def json():
            return []

    monkeypatch.setattr(dashboard_app.requests, "get", lambda *_args, **_kwargs: Response())
    payload = dashboard_app.fetch_kpis()
    assert payload["total_videos"] == 0
    assert payload["total_events"] == 0
    assert payload["total_track_detections"] == 0


def test_fetch_events_timeline_returns_default_on_request_failure(monkeypatch):
    import dashboard.app as dashboard_app

    def raise_error(*_args, **_kwargs):
        raise dashboard_app.requests.RequestException("down")

    monkeypatch.setattr(dashboard_app.requests, "get", raise_error)

    payload = dashboard_app.fetch_events_timeline()
    assert payload["points"] == []
    assert payload["range"]["unit"] == "hours"


def test_fetch_people_by_hour_returns_default_on_invalid_payload(monkeypatch):
    import dashboard.app as dashboard_app

    class Response:
        ok = True

        @staticmethod
        def json():
            return []

    monkeypatch.setattr(dashboard_app.requests, "get", lambda *_args, **_kwargs: Response())

    payload = dashboard_app.fetch_people_by_hour()
    assert payload["points"] == []
    assert payload["range"]["unit"] == "hours"


def test_resolve_video_path_uses_bound_boxes_when_enabled(monkeypatch, tmp_path):
    import dashboard.app as dashboard_app

    # Create temporary video files
    orig_file = tmp_path / "source.mp4"
    orig_file.touch()
    bbox_file = tmp_path / "source_bbox.mp4"
    bbox_file.touch()

    # Mock the current working directory behavior
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    video = {
        "file_path": str(orig_file),
        "bound_boxes_file_path": str(bbox_file),
    }

    # When show_bound_boxes=False, should return original
    resolved = dashboard_app.resolve_video_path(video, show_bound_boxes=False)
    assert resolved is not None
    assert str(orig_file) in resolved or "source.mp4" in resolved

    # When show_bound_boxes=True, should return bound_boxes
    resolved = dashboard_app.resolve_video_path(video, show_bound_boxes=True)
    assert resolved is not None
    assert "source_bbox.mp4" in resolved or str(bbox_file) in resolved


def test_resolve_video_path_returns_none_when_bound_boxes_missing(tmp_path):
    import dashboard.app as dashboard_app

    orig_file = tmp_path / "source.mp4"
    orig_file.touch()

    video = {
        "file_path": str(orig_file),
        "bound_boxes_file_path": str(tmp_path / "missing_bbox.mp4"),
    }

    assert dashboard_app.resolve_video_path(video, show_bound_boxes=True) is None


def test_reprocess_video_success(monkeypatch):
    import dashboard.app as dashboard_app

    class Response:
        ok = True

    monkeypatch.setattr(dashboard_app.requests, "post", lambda *_args, **_kwargs: Response())

    ok, message = dashboard_app.reprocess_video(12)
    assert ok is True
    assert "reprocessed" in message.lower()


def test_reprocess_video_error_payload(monkeypatch):
    import dashboard.app as dashboard_app

    class Response:
        ok = False

        @staticmethod
        def json():
            return {"detail": "Video not found"}

    monkeypatch.setattr(dashboard_app.requests, "post", lambda *_args, **_kwargs: Response())

    ok, message = dashboard_app.reprocess_video(999)
    assert ok is False
    assert "Video not found" in message
