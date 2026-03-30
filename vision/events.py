import time

class EventEngine:

    def __init__(self):
        self.active = {}

    def update(self, tracks):
        events = []

        for track in tracks:
            person_id = track.tracker_id

            if person_id not in self.active:
                self.active[person_id] = time.time()

            if time.time() - self.active[person_id] > 20:
                events.append({
                    "person_id": person_id,
                    "event": "customer_seated"
                })

        return events