class EventEngine:

    def __init__(self):
        self.active = {}
        self.emitted = set()

    def update(self, tracks, frame_index, event_second):
        events = []
        current_ids = set()

        track_ids = self._extract_track_ids(tracks)

        for person_id in track_ids:
            current_ids.add(person_id)

            if person_id not in self.active:
                self.active[person_id] = event_second

            elapsed = event_second - self.active[person_id]
            if elapsed > 20 and person_id not in self.emitted:
                events.append({
                    "person_id": person_id,
                    "event_type": "customer_seated",
                    "event_second": float(event_second),
                    "frame_index": int(frame_index),
                })
                self.emitted.add(person_id)

        inactive_ids = set(self.active.keys()) - current_ids
        for person_id in inactive_ids:
            self.active.pop(person_id, None)
            self.emitted.discard(person_id)

        return events

    @staticmethod
    def _extract_track_ids(tracks):
        if tracks is None:
            return []

        tracker_id = getattr(tracks, "tracker_id", None)
        if tracker_id is not None:
            return [int(track_id) for track_id in tracker_id if track_id is not None and int(track_id) >= 0]

        ids = []
        for track in tracks:
            if isinstance(track, (list, tuple)) and len(track) > 1:
                try:
                    ids.append(int(track[1]))
                except (TypeError, ValueError):
                    continue
        return ids