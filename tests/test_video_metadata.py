from datetime import datetime

import pytest

from vision.video_metadata import parse_video_filename


def test_parse_video_filename_valid_name():
    metadata = parse_video_filename("20260324T150520_C0104_SouthEast28.mp4")

    assert metadata.capture_started_at == datetime(2026, 3, 24, 15, 5, 20)
    assert metadata.camera_id == "C0104"
    assert metadata.location_name == "SouthEast"
    assert metadata.sector_number == 28
    assert metadata.extension == "mp4"


def test_parse_video_filename_accepts_non_mp4_extension():
    metadata = parse_video_filename("20260324T150520_C0104_SouthEast28.dav")

    assert metadata.extension == "dav"


@pytest.mark.parametrize(
    "filename",
    [
        "bad-name.mp4",
        "20260324T150520_C0104_SouthEast.mp4",
        "20260324T150520__SouthEast28.mp4",
    ],
)
def test_parse_video_filename_rejects_invalid_names(filename):
    with pytest.raises(ValueError):
        parse_video_filename(filename)
