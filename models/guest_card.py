"""Guest card model and its life cycle:

    AVAILABLE -> ASSIGNED -> RETURNED -> AVAILABLE      (normal day)
                 ASSIGNED -> MISSING  -> RETURNED       (card lost, later found)

`current_holder` is kept while a card is ASSIGNED or MISSING; on return it moves to
`previous_holder`, so "who last had card 023?" always has an answer.
"""
from exceptions.custom_exceptions import CardUnavailableError, InvalidCardOperationError
from models.base import Record


class GuestCard(Record):
    AVAILABLE, ASSIGNED, RETURNED, MISSING = "AVAILABLE", "ASSIGNED", "RETURNED", "MISSING"
    STATUSES = (AVAILABLE, ASSIGNED, RETURNED, MISSING)

    def __init__(self, card_id, status=AVAILABLE, current_holder=None, previous_holder=None,
                 assigned_at=None, returned_at=None):
        if status not in self.STATUSES:
            raise ValueError(f"unknown card status {status!r}")
        self.card_id = card_id            # "047"
        self.status = status
        self.current_holder = current_holder
        self.previous_holder = previous_holder
        self.assigned_at = assigned_at    # ISO timestamps
        self.returned_at = returned_at

    @property
    def number(self):
        return int(self.card_id)

    @property
    def is_issued(self):
        return self.status in (self.ASSIGNED, self.MISSING)

    @property
    def last_holder(self):
        return self.current_holder or self.previous_holder

    def assign(self, intern_id, when):
        if self.status != self.AVAILABLE:
            raise CardUnavailableError(f"Card {self.card_id} is {self.status.lower()}.")
        self.status, self.current_holder, self.assigned_at, self.returned_at = \
            self.ASSIGNED, intern_id, when, None

    def return_card(self, when):
        if not self.is_issued:
            raise InvalidCardOperationError(f"Card {self.card_id} is not currently issued.")
        self.previous_holder, self.current_holder = self.current_holder, None
        self.status, self.returned_at = self.RETURNED, when

    def recycle(self):
        if self.status != self.RETURNED:
            raise InvalidCardOperationError(f"Card {self.card_id} has not been returned.")
        self.status = self.AVAILABLE

    def mark_missing(self):
        if self.status != self.ASSIGNED:
            raise InvalidCardOperationError(f"Only an issued card can be marked missing; card {self.card_id} is {self.status.lower()}.")
        self.status = self.MISSING

    def to_dict(self):
        return {"card_id": self.card_id, "status": self.status, "current_holder": self.current_holder,
                "previous_holder": self.previous_holder, "assigned_at": self.assigned_at,
                "returned_at": self.returned_at}

    @classmethod
    def from_dict(cls, d):
        return cls(d["card_id"], d.get("status", cls.AVAILABLE), d.get("current_holder"),
                   d.get("previous_holder"), d.get("assigned_at"), d.get("returned_at"))

    def __repr__(self):
        return f"GuestCard({self.card_id!r}, {self.status})"
