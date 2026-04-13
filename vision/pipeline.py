import cv2
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db.models import Event, Video
from vision.events import EventEngine

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOUND_BOXES_DIR = PROJECT_ROOT / "videos" / "bound_boxes"


def _count_tracks(tracks):
    tracker_id = getattr(tracks, "tracker_id", None)
    if tracker_id is not None:
        return len(tracker_id)
    try:
        return len(tracks)
    except TypeError:
        return 0


def _tracked_pairs(tracks):
    xyxy = getattr(tracks, "xyxy", None)
    tracker_id = getattr(tracks, "tracker_id", None)
    if xyxy is None or tracker_id is None:
        return []
    return zip(xyxy, tracker_id)


def _draw_bound_boxes(frame, tracks):
    for box, person_id in _tracked_pairs(tracks):
        x1, y1, x2, y2 = [int(v) for v in box]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 220, 80), 2)
        cv2.putText(
            frame,
            f"person_id={int(person_id)}",
            (x1, max(16, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (80, 220, 80),
            2,
            cv2.LINE_AA,
        )


def _bound_boxes_output_path(input_path):
    source_path = Path(input_path)
    BOUND_BOXES_DIR.mkdir(parents=True, exist_ok=True)
    return BOUND_BOXES_DIR / source_path.name


def _decode_fourcc(value):
    if value is None:
        return None
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return None
    if int_value <= 0:
        return None

    chars = [chr((int_value >> (8 * i)) & 0xFF) for i in range(4)]
    code = "".join(chars).strip()
    if len(code) != 4:
        return None
    if any((ord(c) < 32 or ord(c) > 126) for c in code):
        return None
    return code


def _create_video_writer(output_path, fps, frame_width, frame_height):
    """Create a video writer enforcing H.264-compatible codecs only."""
    codecs = ["avc1", "H264", "X264"]

    for codec_code in codecs:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec_code)
            writer = cv2.VideoWriter(
                str(output_path),
                fourcc,
                fps,
                (frame_width, frame_height),
            )
            if writer.isOpened():
                logger.info("Video writer opened with codec %s at %s", codec_code, output_path)
                return writer
        except Exception as e:
            logger.debug("Codec %s failed: %s", codec_code, e)
            continue

    raise RuntimeError(
        f"Could not create H.264 video writer for {output_path}; install FFmpeg/OpenH264 support in OpenCV"
    )


def process_video(path, db, video_id, capture_started_at):
    from vision.detector import detect
    from vision.tracker import track

    logger.info("Starting processing for video_id=%s path=%s", video_id, path)
    cap = cv2.VideoCapture(path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    safe_fps = fps if fps > 0 else 30.0
    source_codec = _decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))
    frame_index = 0
    event_engine = EventEngine()
    events_to_store = []
    latest_tracks = []
    writer = None
    bound_boxes_path = _bound_boxes_output_path(path)

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

            if writer is None:
                height, width = frame.shape[:2]
                writer = _create_video_writer(bound_boxes_path, safe_fps, width, height)
                logger.info(
                    "Created bound-boxes video writer at %s (source codec=%s, output enforced to H.264)",
                    bound_boxes_path,
                    source_codec or "unknown",
                )

            annotated_frame = frame.copy()
            _draw_bound_boxes(annotated_frame, tracks)
            writer.write(annotated_frame)

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
                    "Progress video_id=%s frames=%s/%s generated_events=%s",
                    video_id,
                    frame_index,
                    total_frames,
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
            "Completed video_id=%s frames=%s tracks=%s events=%s bound_boxes_path=%s",
            video_id,
            frame_index,
            _count_tracks(latest_tracks),
            len(events_to_store),
            bound_boxes_path,
        )

        return {
            "video_id": video_id,
            "frames": frame_index,
            "events": len(events_to_store),
            "fps": float(fps),
            "bound_boxes_file_path": str(bound_boxes_path),
        }
    except Exception:
        logger.exception("Failed processing video_id=%s", video_id)
        video.status = "failed"
        video.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        raise
    finally:
        cap.release()
        if writer is not None:
            writer.release()
            logger.info("Released bound-boxes video writer")