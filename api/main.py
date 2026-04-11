import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
import shutil

from db.database import get_db, init_db
from db.models import Video
from vision.pipeline import process_video
from vision.video_metadata import parse_video_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEOS_DIR = Path("videos")

app = FastAPI()


@app.on_event("startup")
def startup():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("API startup completed: videos directory and metadata tables are ready")

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
def list_videos(db=Depends(get_db)):
    rows = db.query(Video).order_by(Video.uploaded_at.desc()).all()
    return [
        {
            "id": row.id,
            "original_filename": row.original_filename,
            "stored_filename": row.stored_filename,
            "file_path": row.file_path,
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
        for row in rows
    ]