from io import BytesIO


def test_fetch_uploaded_videos_returns_empty_on_request_failure(monkeypatch):
    import dashboard.app as dashboard_app

    def raise_error(*_args, **_kwargs):
        raise dashboard_app.requests.RequestException("down")

    monkeypatch.setattr(dashboard_app.requests, "get", raise_error)

    assert dashboard_app.fetch_uploaded_videos() == []


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
