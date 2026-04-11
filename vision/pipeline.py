import cv2
import logging
from datetime import datetime, timedelta, timezone

from db.models import Event, Video
from vision.events import EventEngine

logger = logging.getLogger(__name__)


def _count_tracks(tracks):
    tracker_id = getattr(tracks, "tracker_id", None)
    if tracker_id is not None:
        return len(tracker_id)
    try:
        return len(tracks)
    except TypeError:
        return 0


def process_video(path, db, video_id, capture_started_at):
    from vision.detector import detect
    from vision.tracker import track

    logger.info("Starting processing for video_id=%s path=%s", video_id, path)
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    safe_fps = fps if fps > 0 else 30.0
    frame_index = 0
    event_engine = EventEngine()
    events_to_store = []
    latest_tracks = []

    video = db.query(Video).filter(Video.id == video_id).first()
    if video is None:
        cap.release()
        raise ValueError(f"Video {video_id} not found in database")

    video.status = "processing"
    db.commit()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detections = detect(frame)
            tracks = track(detections)
            latest_tracks = tracks

            event_second = frame_index / safe_fps
            generated_events = event_engine.update(tracks, frame_index=frame_index, event_second=event_second)
            for generated_event in generated_events:
                absolute_ts = capture_started_at + timedelta(seconds=generated_event["event_second"])
                events_to_store.append(
                    Event(
                        video_id=video_id,
                        person_id=generated_event["person_id"],
                        event_type=generated_event["event_type"],
                        frame_index=generated_event["frame_index"],
                        event_second=generated_event["event_second"],
                        event_timestamp=absolute_ts,
                    )
                )

            frame_index += 1
            if frame_index % 100 == 0:
                logger.info(
                    "Progress video_id=%s frames=%s generated_events=%s",
                    video_id,
                    frame_index,
                    len(events_to_store),
                )

        if events_to_store:
            db.add_all(events_to_store)

        video.total_frames = frame_index
        video.fps = float(fps)
        video.duration_seconds = (frame_index / safe_fps) if frame_index else 0.0
        video.events_count = len(events_to_store)
        video.status = "completed"
        video.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

        logger.info(
            "Completed video_id=%s frames=%s tracks=%s events=%s",
            video_id,
            frame_index,
            _count_tracks(latest_tracks),
            len(events_to_store),
        )

        return {
            "video_id": video_id,
            "frames": frame_index,
            "events": len(events_to_store),
            "fps": float(fps),
        }
    except Exception:
        logger.exception("Failed processing video_id=%s", video_id)
        video.status = "failed"
        video.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        raise
    finally:
        cap.release()