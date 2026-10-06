"""One gate movement: who, what, when, and which card was involved."""
from datetime import datetime

from models.base import Record


class GateLog(Record):
    CHECK_IN, CHECK_OUT = "CHECK_IN", "CHECK_OUT"

    def __init__(self, intern_id, action, timestamp, card_id=None, card_returned=None):
        if action not in (self.CHECK_IN, self.CHECK_OUT):
            raise ValueError(f"unknown action {action!r}")
        datetime.fromisoformat(timestamp)              # raises ValueError if malformed
        self.intern_id = intern_id
        self.action = action
        self.timestamp = timestamp                     # ISO, e.g. 2026-09-30T08:13:05
        self.card_id = card_id
        self.card_returned = card_returned             # only meaningful for CHECK_OUT

    @property
    def when(self):
        return datetime.fromisoformat(self.timestamp)

    @property
    def time_str(self):
        return self.when.strftime("%H:%M")

    def to_dict(self):
        return {"intern_id": self.intern_id, "action": self.action, "timestamp": self.timestamp,
                "card_id": self.card_id, "card_returned": self.card_returned}

    @classmethod
    def from_dict(cls, d):
        return cls(d["intern_id"], d["action"], d["timestamp"], d.get("card_id"), d.get("card_returned"))
