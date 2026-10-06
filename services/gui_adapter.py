"""Bridge between the GUI and the backend.

The GUI screens call a handful of methods (is_valid_id, check_in, check_out, recent, stats,
cards_in_use, roster, set_serial_number, ask, memo). This class provides them, turning controlled
errors into the GateResult the Gate screen already knows how to show, so no exception reaches it.
The extra methods at the bottom are ready for screens the GUI does not have yet.
"""
import logging
from datetime import datetime
from typing import List

from exceptions.custom_exceptions import GateError
from models.guest_card import GuestCard
from services.gate_contract import GateCandidate, GateResult, Movement
from validation import validators as v

log = logging.getLogger("gate")


class GUIService:
    def __init__(self, gate, interns, cards, queries, weather, storage, clock=datetime.now):
        self.gate, self.interns, self.cards = gate, interns, cards
        self.queries, self.weather_service, self.storage = queries, weather, storage
        self.clock = clock

    @property
    def warnings(self):
        return list(self.storage.warnings)

    def _safe(self, action):
        """Run `action() -> GateResult`; convert any failure into a result the GUI can show."""
        try:
            return action()
        except GateError as e:
            return GateResult(e.kind, e.title, str(e))
        except Exception:
            log.exception("Unexpected error in a gate operation")
            return GateResult("er", "Unexpected error", "Something went wrong and was logged. Please try again.")

    # ---- Gate screen -----------------------------------------------------------------
    def is_valid_id(self, text):
        return v.is_valid_intern_id(text)

    def check_in(self, text: str) -> GateResult:
        def run():
            entry = self.gate.check_in(text)
            name = self.interns.get(entry.intern_id).name
            return GateResult("ok", "Checked in", f"{name} \u00b7 hand over card #{entry.card_id}")
        return self._safe(run)

    def check_out(self, text: str) -> GateResult:
        def run():
            entry = self.gate.check_out(text)
            name = self.interns.get(entry.intern_id).name
            if entry.card_id is None:
                return GateResult("ok", "Checked out", name)
            return GateResult("ok", "Checked out", f"{name} \u00b7 collect card #{entry.card_id}")
        return self._safe(run)

    def gate_candidates(self, query: str = "") -> List[GateCandidate]:
        """Return (id, name, programme, roster number, inside, card) rows for gate selection."""
        rows = []
        for intern in self.interns.search_gate(query):
            card = self.cards.card_held_by(intern.intern_id)
            rows.append((intern.intern_id, intern.name, intern.programme, intern.serial_number,
                         intern.is_inside, card.card_id if card else None))
        return rows

    def recent(self, limit: int = 6) -> List[Movement]:
        rows = []
        for e in self.gate.recent_logs(limit):
            intern = self.interns.get(e.intern_id)
            rows.append(Movement("in" if e.action == "CHECK_IN" else "out",
                                 intern.name if intern else e.intern_id, e.intern_id, e.time_str))
        return rows

    # ---- Dashboard -------------------------------------------------------------------
    def stats(self):
        s, total = self.cards.stats(), len(self.interns.get_all_interns())
        inside = len(self.gate.get_inside_interns())
        return {"inside": inside, "outside": total - inside, "free": s["available"],
                "issued": s["issued"], "total": total, "cards": s["total"]}

    def cards_in_use(self):
        return {c.number for c in self.cards.all_cards() if c.is_issued}

    def weather(self):
        """WeatherReport(ok, text, note, loading). Returns immediately, never raises."""
        return self.weather_service.get()

    # ---- Interns screen --------------------------------------------------------------
    def roster(self, query="", status="all"):
        held = self.cards.holders_map()
        latest = self.gate.last_movement_map()
        today = self.clock().date()
        rows = []
        for i in self.interns.search(query, status):
            card = held.get(i.intern_id)
            last = latest.get(i.intern_id)
            since = "\u2014" if not last else (last.time_str if last.when.date() == today
                                               else last.when.strftime("%d %b"))
            rows.append((i.intern_id, i.name, i.programme, i.serial_number,
                         i.is_inside, card.card_id if card else 0, since))
        return sorted(rows, key=lambda row: (row[1].casefold(), row[0]))

    # ---- AI Report screen ------------------------------------------------------------
    def ask(self, text):
        return self.queries.ask(text)

    def memo(self):
        return self.queries.memo()

    # ---- ready for screens the GUI does not have yet ------------------------------------
    def check_out_card_not_returned(self, text):
        def run():
            entry = self.gate.check_out(text, card_returned=False)
            name = self.interns.get(entry.intern_id).name
            return GateResult("wa", "Checked out, card not returned",
                              f"{name} left with card #{entry.card_id}. It is flagged as unreturned.")
        return self._safe(run)

    def register_intern(self, intern_id, name, department, phone="", email="", serial_number=None):
        def run():
            i = self.interns.register_intern(intern_id, name, department, phone, email, serial_number)
            number = f" \u00b7 roster no. {i.serial_number}" if i.serial_number else ""
            return GateResult("ok", "Intern registered",
                              f"{i.name} \u00b7 {i.intern_id} ({i.programme}){number}")
        return self._safe(run)

    def set_serial_number(self, intern_id, serial_number):
        def run():
            i = self.interns.update_intern(intern_id, serial_number=serial_number)
            number = i.serial_number or "unassigned"
            return GateResult("ok", "Roster number updated", f"{i.name} \u00b7 roster no. {number}")
        return self._safe(run)

    def return_card(self, card_text):
        def run():
            card = self.cards.get_card(card_text)
            inside_holder = self._inside_holder(card)
            if inside_holder:
                return GateResult(
                    "wa",
                    "Intern still inside",
                    f"{inside_holder.name} is inside. Check them out at the Gate before "
                    f"returning card #{card.card_id}.",
                )
            c = self.cards.return_card(card_text)
            return GateResult("ok", "Card returned", f"Card #{c.card_id} is back in the pool.")
        return self._safe(run)

    def mark_card_missing(self, card_text):
        def run():
            card = self.cards.get_card(card_text)
            inside_holder = self._inside_holder(card)
            if inside_holder:
                return GateResult(
                    "wa",
                    "Intern still inside",
                    f"{inside_holder.name} is inside. Check them out at the Gate before "
                    f"changing the status of card #{card.card_id}.",
                )
            c = self.cards.mark_card_missing(card_text)
            return GateResult("wa", "Card marked missing", f"Card #{c.card_id} was last held by {c.current_holder}.")
        return self._safe(run)

    def _inside_holder(self, card):
        """Return the card's holder if they are still inside the building."""
        if not card.is_issued or not card.current_holder:
            return None
        holder = self.interns.get(card.current_holder)
        return holder if holder and holder.is_inside else None

    def card_report(self):
        """[(card_id, status, holder_id, holder_name, assigned_at)] for a guest-card management screen."""
        rows = []
        for c in self.cards.all_cards():
            who = self.interns.get(c.last_holder)
            rows.append((c.card_id, c.status, c.last_holder, who.name if who else "", c.assigned_at))
        return rows
