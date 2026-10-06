"""The core gate engine: check-in, check-out and who is inside.

Flow for a check-in:  validate ID -> find intern -> reject duplicate -> pick a card ->
mark inside -> write the log entry -> save intern, card and log files.
If saving fails half-way, every object is rolled back so memory and disk agree.
No GUI code lives here: the GUI (or the AI) calls these methods.
"""
import logging
from datetime import datetime

from exceptions.custom_exceptions import DuplicateCheckInError, NotCheckedInError, StorageError
from models.gate_log import GateLog
from models.guest_card import GuestCard

log = logging.getLogger("gate")


class GateService:
    """Apply gate movements and keep intern, card, and log records in sync."""

    def __init__(self, interns, cards, storage, clock=datetime.now):
        self.interns = interns
        self.cards = cards
        self.storage = storage
        self.clock = clock
        self._logs = []
        records = storage.load_gate_logs()
        skipped = 0
        for record in records or []:
            try:
                self._logs.append(GateLog.from_dict(record))
            except (KeyError, TypeError, ValueError):
                skipped += 1
        if skipped:
            storage.warn(f"{skipped} unreadable gate log entr{'y' if skipped == 1 else 'ies'} skipped.")
        self._logs.sort(key=lambda entry: entry.timestamp)
        if records is None:  # Create the empty log file on first run.
            self._save_logs()
        self._audit()

    def _audit(self):
        """Report inconsistent saved state without blocking application startup."""
        card_holders = self.cards.holders_map()
        for intern in self.get_inside_interns():
            if intern.intern_id not in card_holders:
                self.storage.warn(
                    f"{intern.name} ({intern.intern_id}) is marked inside but holds no guest card."
                )

    def _stamp(self):
        """Return the current time in the format used by persisted gate logs."""
        return self.clock().isoformat(timespec="seconds")

    def _save_logs(self):
        self.storage.save_gate_logs([entry.to_dict() for entry in self._logs])

    def _persist_all(self):
        """Save every record changed by a gate movement."""
        self.cards.persist()
        self.interns.persist()
        self._save_logs()

    def _rollback(self, objects, snapshots, entry):
        """Restore in-memory records and try to write the restored state to disk."""
        for record, snapshot in zip(objects, snapshots):
            record.restore(snapshot)
        if entry in self._logs:
            self._logs.remove(entry)
        try:
            self._persist_all()
        except StorageError:
            log.error("Rollback could not be written to disk.")

    # ---- operations ------------------------------------------------------------
    def check_in(self, intern_id, card_id=None):
        """Check an intern in and hand them a guest card. Returns the GateLog entry."""
        intern = self.interns.find_intern(intern_id)
        if intern.is_inside:
            last_entry = self.last_log_for(intern.intern_id)
            held_card = self.cards.card_held_by(intern.intern_id)
            last_time = last_entry.time_str if last_entry else "an earlier time"
            card_detail = f" with card #{held_card.card_id}." if held_card else "."
            raise DuplicateCheckInError(
                f"{intern.name} checked in at {last_time}{card_detail}"
            )

        # Reuse a card that is still assigned to this intern from an earlier visit.
        card = self.cards.card_held_by(intern.intern_id)
        reusing_card = card is not None
        if not reusing_card:
            card = self.cards.pick_card(card_id)

        stamp = self._stamp()
        entry = GateLog(intern.intern_id, GateLog.CHECK_IN, stamp, card_id=card.card_id)
        changed_records = [intern, card]
        snapshots = [record.snapshot() for record in changed_records]
        try:
            if not reusing_card:
                card.assign(intern.intern_id, stamp)
            intern.mark_inside()
            self._logs.append(entry)
            self._persist_all()
        except Exception:
            # The movement spans multiple files; restore all records if any save fails.
            self._rollback(changed_records, snapshots, entry)
            raise
        return entry

    def check_out(self, intern_id, card_returned=True):
        """Check an intern out. With card_returned=False the card stays ASSIGNED and is
        reported as unreturned. Returns the GateLog entry."""
        intern = self.interns.find_intern(intern_id)
        if not intern.is_inside:
            raise NotCheckedInError(f"{intern.name} is not marked as inside.")
        card = self.cards.card_held_by(intern.intern_id)
        entry = GateLog(intern.intern_id, GateLog.CHECK_OUT, self._stamp(),
                        card_id=card.card_id if card else None,
                        card_returned=bool(card_returned) if card else None)
        changed_records = [intern] + ([card] if card else [])
        snapshots = [record.snapshot() for record in changed_records]
        try:
            # Only a card confirmed as returned goes back into the available pool.
            if card and card_returned:
                self.cards.return_card(card.card_id, persist=False)
            intern.mark_outside()
            self._logs.append(entry)
            self._persist_all()
        except Exception:
            self._rollback(changed_records, snapshots, entry)
            raise
        return entry

    # ---- queries ---------------------------------------------------------------
    def get_inside_interns(self):
        """Return the interns currently marked inside."""
        return [i for i in self.interns.get_all_interns() if i.is_inside]

    def is_intern_inside(self, intern_id):
        """Check the saved inside/outside status for one intern."""
        return self.interns.find_intern(intern_id).is_inside

    def recent_logs(self, limit=6):
        """Return the newest log entries first."""
        return self._logs[-limit:][::-1] if limit > 0 else []

    def last_log_for(self, intern_id):
        """Return the latest movement for one intern, or None if they have no history."""
        return next((e for e in reversed(self._logs) if e.intern_id == intern_id), None)

    def last_movement_map(self):
        """Map each intern ID to that intern's latest movement."""
        latest = {}
        for entry in self._logs:
            latest[entry.intern_id] = entry
        return latest

    def logs_for_date(self, day=None):
        """Return all movements on the requested date (today by default)."""
        day = day or self.clock().date()
        return [e for e in self._logs if e.when.date() == day]

    def log_count(self):
        """Return the number of movements currently stored."""
        return len(self._logs)

    def attendance_summary(self, day=None):
        """Plain-data facts for the daily memo and the AI (JSON friendly)."""
        day = day or self.clock().date()
        todays_movements = self.logs_for_date(day)
        check_ins = [
            movement for movement in todays_movements
            if movement.action == GateLog.CHECK_IN
        ]
        inside_interns = self.get_inside_interns()
        cards_not_returned_after_leaving = 0
        for card in self.cards.get_unreturned_cards():
            holder = self.interns.get(card.current_holder)
            holder_is_inside = holder is not None and holder.is_inside
            if card.status == GuestCard.ASSIGNED and not holder_is_inside:
                cards_not_returned_after_leaving += 1

        card_counts = self.cards.stats()
        return {
            "date": day.isoformat(),
            "check_ins": len(check_ins),
            "check_outs": len(todays_movements) - len(check_ins),
            "inside_now": len(inside_interns),
            "inside_nysc": sum(
                1 for intern in inside_interns if intern.programme == "NYSC"
            ),
            "inside_siwes": sum(
                1 for intern in inside_interns if intern.programme == "SIWES"
            ),
            "total_interns": len(self.interns.get_all_interns()),
            "cards_total": card_counts["total"],
            "cards_issued": card_counts["issued"],
            "cards_free": card_counts["available"],
            "cards_unreturned_after_leaving": cards_not_returned_after_leaving,
            "cards_missing": card_counts["missing"],
            "first_check_in": check_ins[0].time_str if check_ins else None,
            "last_movement": (
                todays_movements[-1].time_str if todays_movements else None
            ),
        }
