import supervision as sv

tracker = sv.ByteTrack()


def track(detections):
    return tracker.update_with_detections(detections)