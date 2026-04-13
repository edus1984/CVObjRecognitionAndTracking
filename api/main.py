import logging
from contextlib import asynccontextmanager
from datetime import datetime
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

    return {
        "total_videos": int(total_videos),
        "completed_videos": int(completed_videos),
        "failed_videos": int(failed_videos),
        "total_events": int(total_events),
        "unique_people": int(unique_people),
        "avg_events_per_completed_video": (float(total_events) / float(completed_videos)) if completed_videos else 0.0,
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