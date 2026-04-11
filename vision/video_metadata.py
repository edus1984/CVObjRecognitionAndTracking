import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


VIDEO_NAME_PATTERN = re.compile(
    r"^(?P<capture_dt>\d{8}T\d{6})_"
    r"(?P<camera_id>C\d+)_"
    r"(?P<location>[A-Za-z]+?)"
    r"(?P<sector>\d+)"
    r"\.(?P<extension>[A-Za-z0-9]+)$"
)


@dataclass(frozen=True)
class VideoNameMetadata:
    original_filename: str
    capture_started_at: datetime
    camera_id: str
    location_name: str
    sector_number: int
    extension: str


def parse_video_filename(filename: str) -> VideoNameMetadata:
    base_name = Path(filename).name
    match = VIDEO_NAME_PATTERN.match(base_name)
    if not match:
        raise ValueError(
            "Invalid video filename format. Expected "
            "[datetime]_[cameraID]_[location][sector].[ext], e.g. "
            "20260324T150520_C0104_SouthEast28.mp4"
        )

    capture_started_at = datetime.strptime(match.group("capture_dt"), "%Y%m%dT%H%M%S")

    return VideoNameMetadata(
        original_filename=base_name,
        capture_started_at=capture_started_at,
        camera_id=match.group("camera_id"),
        location_name=match.group("location"),
        sector_number=int(match.group("sector")),
        extension=match.group("extension").lower(),
    )
