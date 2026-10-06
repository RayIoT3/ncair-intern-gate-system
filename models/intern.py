"""Intern model. `programme` (NYSC / SIWES) is derived from the ID, so it can never disagree with it."""
from models.base import Record


class Intern(Record):
    INSIDE, OUTSIDE = "INSIDE", "OUTSIDE"

    def __init__(self, intern_id, name, department, phone="", email="", status=OUTSIDE,
                 serial_number=None):
        self.intern_id = intern_id
        self.name = name
        self.department = department
        self.phone = phone
        self.email = email
        self.status = status if status in (self.INSIDE, self.OUTSIDE) else self.OUTSIDE
        self.serial_number = serial_number

    @property
    def programme(self):
        return "NYSC" if "-NY-" in self.intern_id else "SIWES"

    @property
    def is_inside(self):
        return self.status == self.INSIDE

    def mark_inside(self):
        self.status = self.INSIDE

    def mark_outside(self):
        self.status = self.OUTSIDE

    def to_dict(self):
        return {"intern_id": self.intern_id, "name": self.name, "programme": self.programme,
                "department": self.department, "phone": self.phone, "email": self.email,
                "status": self.status, "serial_number": self.serial_number}

    @classmethod
    def from_dict(cls, d):
        return cls(d["intern_id"], d["name"], d["department"], d.get("phone", ""),
                   d.get("email", ""), d.get("status", cls.OUTSIDE), d.get("serial_number"))

    def __repr__(self):
        return f"Intern({self.intern_id!r}, {self.name!r}, {self.status})"
