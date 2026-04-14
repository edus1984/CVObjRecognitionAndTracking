import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
import shutil
from sqlalchemy import func

from db.database import get_db, init_db
from db.models import Event, Video
from vision.pipeline import process_video
from vision.video_metadata import parse_video_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = PROJECT_ROOT / "videos"
BOUND_BOXES_DIR = VIDEOS_DIR / "bound_boxes"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    BOUND_BOXES_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("API startup completed: videos directory and metadata tables are ready")
    yield


app = FastAPI(lifespan=lifespan)


_UNIT_SECONDS = {
    "minutes": 60,
    "hours": 60 * 60,
    "days": 24 * 60 * 60,
}

_ALLOWED_INTERVALS = {
    "minutes": {1, 5, 10},
    "hours": {1, 2, 6},
    "days": {1, 7},
}


def _serialize_video(row):
    return {
        "id": row.id,
        "original_filename": row.original_filename,
        "stored_filename": row.stored_filename,
        "file_path": row.file_path,
        "bound_boxes_file_path": str(BOUND_BOXES_DIR / row.stored_filename),
        "camera_id": row.camera_id,
        "location_name": row.location_name,
        "sector_number": row.sector_number,
        "capture_started_at": row.capture_started_at.isoformat(),
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        "status": row.status,
        "total_frames": row.total_frames,
        "duration_seconds": row.duration_seconds,
        "events_count": row.events_count,
    }


def _resolve_existing_video_path(file_path: str, stored_filename: str) -> Path | None:
    candidate = Path(file_path)
    candidates = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.append(PROJECT_ROOT / candidate)
        candidates.append(Path.cwd() / candidate)

    # Legacy rows may have stale/incorrect file_path; prefer canonical upload location too.
    candidates.append(VIDEOS_DIR / stored_filename)

    for path in candidates:
        if path.exists():
            return path

    return None


def _validate_time_controls(range_unit: str, range_value: int, interval: int) -> tuple[str, int, int]:
    if range_unit not in _UNIT_SECONDS:
        raise HTTPException(status_code=400, detail="range_unit must be one of: minutes, hours, days")
    if range_value <= 0:
        raise HTTPException(status_code=400, detail="range_value must be greater than zero")
    if interval not in _ALLOWED_INTERVALS[range_unit]:
        allowed = sorted(_ALLOWED_INTERVALS[range_unit])
        raise HTTPException(status_code=400, detail=f"interval must be one of {allowed} for unit '{range_unit}'")
    return range_unit, range_value, interval


def _time_window_start(range_unit: str, range_value: int, now: datetime) -> datetime:
    if range_unit == "minutes":
        return now - timedelta(minutes=range_value)
    if range_unit == "hours":
        return now - timedelta(hours=range_value)
    return now - timedelta(days=range_value)


def _bucket_floor(ts: datetime, range_unit: str, interval: int) -> datetime:
    epoch = datetime(1970, 1, 1)
    step_seconds = _UNIT_SECONDS[range_unit] * interval
    elapsed = int((ts - epoch).total_seconds())
    bucket_seconds = elapsed - (elapsed % step_seconds)
    return epoch + timedelta(seconds=bucket_seconds)


def _timeline_label(ts: datetime, range_unit: str) -> str:
    if range_unit == "minutes":
        return ts.strftime("%m-%d %H:%M")
    if range_unit == "hours":
        return ts.strftime("%m-%d %H:00")
    return ts.strftime("%Y-%m-%d")


def _hour_bucket_label(start_hour: int, width: int) -> str:
    end_hour = min(23, start_hour + width - 1)
    return f"{start_hour:02d}:00-{end_hour:02d}:59"

@app.post("/upload")
async def upload(file: UploadFile, db=Depends(get_db)):
    try:
        metadata = parse_video_filename(file.filename)
    except ValueError as exc:
        logger.warning("Rejected filename=%s reason=%s", file.filename, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = VIDEOS_DIR / metadata.original_filename

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    video = Video(
        original_filename=metadata.original_filename,
        stored_filename=path.name,
        file_path=str(path),
        capture_started_at=metadata.capture_started_at,
        camera_id=metadata.camera_id,
        location_name=metadata.location_name,
        sector_number=metadata.sector_number,
        status="uploaded",
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    logger.info("Stored upload metadata video_id=%s filename=%s", video.id, metadata.original_filename)

    result = process_video(
        path=str(path),
        db=db,
        video_id=video.id,
        capture_started_at=metadata.capture_started_at,
    )

    return {"status": "processed", "video": result}


@app.get("/videos")
def list_videos(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    camera_id: str | None = None,
    status: str | None = None,
    capture_from: str | None = None,
    capture_to: str | None = None,
    db=Depends(get_db),
):
    query = db.query(Video)

    if camera_id:
        query = query.filter(Video.camera_id == camera_id)
    if status:
        query = query.filter(Video.status == status)

    try:
        if capture_from:
            query = query.filter(Video.capture_started_at >= datetime.fromisoformat(capture_from))
        if capture_to:
            query = query.filter(Video.capture_started_at <= datetime.fromisoformat(capture_to))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="capture_from and capture_to must be ISO datetime strings") from exc

    total = query.count()
    rows = query.order_by(Video.uploaded_at.desc()).offset(skip).limit(limit).all()

    return {
        "items": [_serialize_video(row) for row in rows],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "returned": len(rows),
            "total": total,
        },
    }


@app.get("/kpis")
def get_kpis(db=Depends(get_db)):
    total_videos = db.query(func.count(Video.id)).scalar() or 0
    completed_videos = db.query(func.count(Video.id)).filter(Video.status == "completed").scalar() or 0
    failed_videos = db.query(func.count(Video.id)).filter(Video.status == "failed").scalar() or 0
    total_events = db.query(func.count(Event.id)).scalar() or 0
    unique_people = db.query(func.count(func.distinct(Event.person_id))).scalar() or 0
    total_track_detections = db.query(Event.video_id, Event.person_id).distinct().count()

    return {
        "total_videos": int(total_videos),
        "completed_videos": int(completed_videos),
        "failed_videos": int(failed_videos),
        "total_events": int(total_events),
        "unique_people": int(unique_people),
        "total_track_detections": int(total_track_detections),
        "avg_events_per_completed_video": (float(total_events) / float(completed_videos)) if completed_videos else 0.0,
    }


@app.get("/kpis/events-timeline")
def get_events_timeline(
    range_unit: str = Query(default="hours"),
    range_value: int = Query(default=24, ge=1),
    interval: int = Query(default=1, ge=1),
    db=Depends(get_db),
):
    range_unit, range_value, interval = _validate_time_controls(range_unit, range_value, interval)
    now = datetime.now().replace(microsecond=0)
    start = _time_window_start(range_unit, range_value, now)

    rows = (
        db.query(Event.event_timestamp)
        .filter(Event.event_timestamp >= start)
        .filter(Event.event_timestamp <= now)
        .all()
    )

    counts = {}
    for (event_timestamp,) in rows:
        bucket = _bucket_floor(event_timestamp, range_unit, interval)
        counts[bucket] = counts.get(bucket, 0) + 1

    points = []
    step = timedelta(seconds=_UNIT_SECONDS[range_unit] * interval)
    cursor = _bucket_floor(start, range_unit, interval)
    last_bucket = _bucket_floor(now, range_unit, interval)
    while cursor <= last_bucket:
        points.append(
            {
                "bucket_start": cursor.isoformat(),
                "label": _timeline_label(cursor, range_unit),
                "events": int(counts.get(cursor, 0)),
            }
        )
        cursor += step

    return {
        "range": {
            "unit": range_unit,
            "value": int(range_value),
            "interval": int(interval),
            "start": start.isoformat(),
            "end": now.isoformat(),
        },
        "points": points,
    }


@app.get("/kpis/people-by-hour")
def get_unique_people_by_hour(
    range_unit: str = Query(default="hours"),
    range_value: int = Query(default=24, ge=1),
    interval: int = Query(default=1, ge=1),
    db=Depends(get_db),
):
    range_unit, range_value, interval = _validate_time_controls(range_unit, range_value, interval)
    now = datetime.now().replace(microsecond=0)
    start = _time_window_start(range_unit, range_value, now)

    hour_width = interval if range_unit == "hours" else 1
    rows = (
        db.query(Event.person_id, Event.event_timestamp)
        .filter(Event.event_timestamp >= start)
        .filter(Event.event_timestamp <= now)
        .all()
    )

    people_by_hour = {h: set() for h in range(0, 24, hour_width)}
    for person_id, event_timestamp in rows:
        bucket = (event_timestamp.hour // hour_width) * hour_width
        people_by_hour[bucket].add(person_id)

    points = [
        {
            "label": _hour_bucket_label(hour_start, hour_width),
            "unique_people": len(people_by_hour[hour_start]),
        }
        for hour_start in sorted(people_by_hour)
        if people_by_hour[hour_start]
    ]

    return {
        "range": {
            "unit": range_unit,
            "value": int(range_value),
            "interval": int(interval),
            "start": start.isoformat(),
            "end": now.isoformat(),
        },
        "points": points,
    }


@app.post("/videos/{video_id}/reprocess")
def reprocess_video(video_id: int, db=Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    resolved_video_path = _resolve_existing_video_path(video.file_path, video.stored_filename)
    if resolved_video_path is None:
        raise HTTPException(status_code=404, detail="Original video file not found on disk")

    logger.info("Reprocessing video_id=%s path=%s", video_id, resolved_video_path)

    # Keep event store consistent by replacing previous detections/events.
    db.query(Event).filter(Event.video_id == video_id).delete(synchronize_session=False)
    video.events_count = 0
    video.status = "uploaded"
    db.commit()

    result = process_video(
        path=str(resolved_video_path),
        db=db,
        video_id=video.id,
        capture_started_at=video.capture_started_at,
    )

    db.refresh(video)
    return {
        "status": "reprocessed",
        "video": result,
        "item": _serialize_video(video),
    }