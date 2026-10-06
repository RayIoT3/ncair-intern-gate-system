"""Everything about intern records: register, find, search, update. Saved through FileStorage."""

import config
from exceptions.custom_exceptions import (DuplicateInternError, DuplicateSerialNumberError,
                                          GateError, InternNotFoundError, StorageError,
                                          ValidationError)
from models.intern import Intern
from services import seed_data
from validation import validators as v


class InternService:
    """Validate, search, and persist the intern roster."""

    UPDATABLE = ("name", "department", "phone", "email", "serial_number")

    def __init__(self, storage, seed_count=config.INTERN_COUNT):
        self.storage = storage
        self._interns = {}
        records = storage.load_interns()
        if records is None:                                    # first run, or file was corrupt
            records = seed_data.generate_interns(seed_count)
            self._load(records)
            self._assign_initial_serial_numbers()
            self.persist()
        else:
            self._load(records)
            if self._assign_initial_serial_numbers():
                self.persist()

    def _load(self, records):
        """Load valid records and report entries that need correction."""
        skipped, invalid_serials = 0, 0
        for record in records:
            try:
                intern = Intern.from_dict(record)
                intern.intern_id = v.validate_intern_id(intern.intern_id)
                if intern.intern_id in self._interns:
                    # IDs are canonicalized first, so differently formatted duplicates are caught too.
                    raise ValueError(f"duplicate intern ID {intern.intern_id}")
                try:
                    intern.serial_number = v.validate_serial_number(intern.serial_number)
                    if intern.serial_number and any(
                            existing.serial_number == intern.serial_number
                            for existing in self._interns.values()):
                        raise DuplicateSerialNumberError(intern.serial_number)
                except (GateError, ValueError):
                    intern.serial_number = None
                    invalid_serials += 1
                self._interns[intern.intern_id] = intern
            except (KeyError, TypeError, ValueError, GateError):
                skipped += 1
        if skipped:
            self.storage.warn(f"{skipped} unreadable intern record(s) were skipped.")
        if invalid_serials:
            self.storage.warn(
                f"{invalid_serials} invalid or duplicate roster number(s) were cleared.")

    def _assign_initial_serial_numbers(self):
        """Assign alphabetical roster numbers once, without renumbering existing records."""
        if not self._interns or any(i.serial_number for i in self._interns.values()):
            return False
        interns_by_name = sorted(
            self._interns.values(),
            key=lambda intern: (intern.name.casefold(), intern.intern_id),
        )
        for number, intern in enumerate(interns_by_name, start=1):
            intern.serial_number = str(number)
        return True

    def persist(self):
        """Write the current roster to storage."""
        self.storage.save_interns([i.to_dict() for i in self._interns.values()])

    # ---- queries -------------------------------------------------------------
    def get(self, intern_id):
        """Lookup without validation or exceptions; returns None if unknown."""
        return self._interns.get(intern_id)

    def find_intern(self, intern_id):
        """Validate an ID and return its intern, or raise a domain-specific error."""
        iid = v.validate_intern_id(intern_id)
        intern = self._interns.get(iid)
        if intern is None:
            raise InternNotFoundError(f"No registered intern has {iid}.")
        return intern

    def get_all_interns(self):
        """Return the current roster as a list."""
        return list(self._interns.values())

    def search(self, query="", status="all"):
        """status: 'all' | 'in' | 'out' (the GUI's filter names)."""
        q = query.strip().lower()
        if q.isdigit():
            serial = q.lstrip("0") or "0"
            serial_matches = [
                intern for intern in self._interns.values()
                if intern.serial_number == serial
            ]
            if serial_matches:
                return [
                    intern for intern in serial_matches
                    if status == "all" or (status == "in") == intern.is_inside
                ]
        matching_interns = []
        for intern in self._interns.values():
            if status == "in" and not intern.is_inside:
                continue
            if status == "out" and intern.is_inside:
                continue
            searchable_text = (
                intern.name + intern.intern_id + (intern.serial_number or "")
            ).lower()
            if q and q not in searchable_text:
                continue
            matching_interns.append(intern)
        return matching_interns

    def search_gate(self, query=""):
        """Find by exact roster number, name, full ID, or the last three ID digits."""
        q = " ".join(query.split()).casefold()
        if not q:
            return []

        if q.isdigit():
            serial = q.lstrip("0") or "0"
            serial_matches = [i for i in self._interns.values() if i.serial_number == serial]
            if serial_matches:
                return serial_matches
        if q.isdigit() and len(q) < 3:
            return []
        # Three digits mean a suffix lookup; longer numeric queries use normal full-ID matching.
        suffix_search = q.isdigit() and len(q) == 3
        matches = [
            intern for intern in self._interns.values()
            if (
                intern.intern_id.casefold().endswith(q)
                if suffix_search
                else q in intern.intern_id.casefold() or q in intern.name.casefold()
            )
        ]
        return sorted(matches, key=lambda intern: (
            0 if q in (intern.intern_id.casefold(), intern.name.casefold()) else
            1 if intern.name.casefold().startswith(q) else
            2 if intern.intern_id.casefold().startswith(q) else 3,
            intern.name.casefold(), intern.intern_id))

    # ---- changes -------------------------------------------------------------
    def register_intern(self, intern_id, name, department, phone="", email="", serial_number=None):
        """Validate and save a new intern, undoing the in-memory insert if saving fails."""
        canonical_id = v.validate_intern_id(intern_id)
        if canonical_id in self._interns:
            existing_name = self._interns[canonical_id].name
            raise DuplicateInternError(
                f"{canonical_id} is already registered to {existing_name}."
            )

        serial = v.validate_serial_number(serial_number)
        self._ensure_serial_available(serial)
        intern = Intern(
            canonical_id,
            v.validate_name(name),
            v.validate_department(department),
            v.validate_phone(phone),
            v.validate_email(email),
            serial_number=serial,
        )
        self._interns[canonical_id] = intern
        try:
            self.persist()
        except StorageError:
            del self._interns[canonical_id]
            raise
        return intern

    def update_intern(self, intern_id, **fields):
        """Validate and save selected fields, restoring the prior record if saving fails."""
        intern = self.find_intern(intern_id)
        checks = {"name": v.validate_name, "department": v.validate_department,
                  "phone": v.validate_phone, "email": v.validate_email,
                  "serial_number": v.validate_serial_number}
        for key in fields:
            if key not in self.UPDATABLE:
                raise ValidationError(f"'{key}' cannot be updated.")
        updated = {key: checks[key](value) for key, value in fields.items()}
        if "serial_number" in updated:
            self._ensure_serial_available(updated["serial_number"], exclude=intern.intern_id)
        snapshot = intern.snapshot()
        for key, value in updated.items():
            setattr(intern, key, value)
        try:
            self.persist()
        except StorageError:
            intern.restore(snapshot)
            raise
        return intern

    def _ensure_serial_available(self, serial_number, exclude=None):
        """Reject a roster number already assigned to a different intern."""
        if serial_number is None:
            return
        duplicate = next(
            (
                intern for intern in self._interns.values()
                if intern.intern_id != exclude and intern.serial_number == serial_number
            ),
            None,
        )
        if duplicate:
            raise DuplicateSerialNumberError(
                f"Roster number {serial_number} is already assigned to {duplicate.name}.")
