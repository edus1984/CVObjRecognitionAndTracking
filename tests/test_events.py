from vision.events import EventEngine


class Tracks:
    def __init__(self, tracker_ids):
        self.tracker_id = tracker_ids


def test_event_engine_emits_customer_seated_once_after_threshold():
    engine = EventEngine()

    assert engine.update(Tracks([1]), frame_index=0, event_second=0.0) == []
    assert engine.update(Tracks([1]), frame_index=1, event_second=1.0) == []
    assert engine.update(Tracks([1]), frame_index=2, event_second=2.0) == []

    events = engine.update(Tracks([1]), frame_index=3, event_second=3.0)
    assert len(events) == 1
    assert events[0]["person_id"] == 1
    assert events[0]["event_type"] == "customer_seated"

    # No duplicate event while the same person remains active.
    assert engine.update(Tracks([1]), frame_index=4, event_second=4.0) == []
