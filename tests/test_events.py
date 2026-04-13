from vision.events import EventEngine


class Tracks:
    def __init__(self, tracker_ids):
        self.tracker_id = tracker_ids


def test_event_engine_emits_customer_seated_once_after_threshold():
    engine = EventEngine()

    assert engine.update(Tracks([1]), frame_index=0, event_second=0.0) == []
    assert engine.update(Tracks([1]), frame_index=10, event_second=10.0) == []
    assert engine.update(Tracks([1]), frame_index=20, event_second=20.0) == []

    events = engine.update(Tracks([1]), frame_index=21, event_second=21.0)
    assert len(events) == 1
    assert events[0]["person_id"] == 1
    assert events[0]["event_type"] == "customer_seated"

    # No duplicate event while the same person remains active.
    assert engine.update(Tracks([1]), frame_index=22, event_second=22.0) == []
