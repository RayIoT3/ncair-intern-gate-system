"""Guest card inventory and life cycle. Saved through FileStorage."""
from datetime import datetime

import config
from exceptions.custom_exceptions import (CardNotFoundError, CardUnavailableError, GateError,
                                          NoCardsAvailableError, StorageError)
from models.guest_card import GuestCard
from validation import validators as v


class CardService:
    """Manage guest-card records and enforce their life cycle."""

    def __init__(self, storage, card_count=config.CARD_COUNT, clock=datetime.now,
                 auto_recycle=config.AUTO_RECYCLE_CARDS):
        self.storage = storage
        self.clock = clock
        self.auto_recycle = auto_recycle
        self._cards = {}
        records = storage.load_cards()
        skipped = 0
        for record in records or []:
            try:
                card = GuestCard.from_dict(record)
                card.card_id = v.validate_card_id(card.card_id, 999)
                if card.card_id in self._cards:
                    # Keep the first valid record instead of silently replacing its history.
                    raise ValueError(f"duplicate card ID {card.card_id}")
                self._cards[card.card_id] = card
            except (KeyError, TypeError, ValueError, GateError):
                skipped += 1
        if skipped:
            storage.warn(f"{skipped} unreadable guest card record(s) were skipped.")
        if not self._cards:
            self._cards = {f"{n:03d}": GuestCard(f"{n:03d}") for n in range(1, card_count + 1)}
            self.persist()
        else:
            # Grow older inventories to the configured size without replacing saved card history.
            added = 0
            for n in range(1, card_count + 1):
                card_id = f"{n:03d}"
                if card_id not in self._cards:
                    self._cards[card_id] = GuestCard(card_id)
                    added += 1
            if added:
                self.persist()

    def _stamp(self):
        """Return the current time in the format used by persisted card records."""
        return self.clock().isoformat(timespec="seconds")

    def _sorted(self) -> list[GuestCard]:
        """Return cards in numeric order, regardless of their insertion order."""
        return sorted(self._cards.values(), key=lambda c: c.number)

    def persist(self):
        """Write the current card inventory to storage."""
        self.storage.save_cards([c.to_dict() for c in self._sorted()])

    def _commit(self, card, snapshot):
        """Save one changed card, restoring it if the write fails."""
        try:
            self.persist()
        except StorageError:
            card.restore(snapshot)
            raise

    # ---- lookups ---------------------------------------------------------------
    @property
    def max_card(self):
        """The highest card number present in the saved inventory."""
        return max((c.number for c in self._cards.values()), default=0)

    def get_card(self, card_id):
        cid = v.validate_card_id(card_id, self.max_card)
        card = self._cards.get(cid)
        if card is None:
            raise CardNotFoundError(f"Card {cid} does not exist.")
        return card

    def all_cards(self):
        return self._sorted()

    def get_card_holder(self, card_id):
        """Intern ID currently holding the card, or None."""
        return self.get_card(card_id).current_holder

    def get_previous_holder(self, card_id):
        return self.get_card(card_id).previous_holder

    def get_available_cards(self):
        return [c for c in self._sorted() if c.status == GuestCard.AVAILABLE]

    def get_unreturned_cards(self):
        """Cards not back in the pool: ASSIGNED (still out) or MISSING."""
        return [c for c in self._sorted() if c.is_issued]

    def get_missing_cards(self):
        return [c for c in self._sorted() if c.status == GuestCard.MISSING]

    def card_held_by(self, intern_id):
        return next((c for c in self._sorted() if c.status == GuestCard.ASSIGNED
                     and c.current_holder == intern_id), None)

    def holders_map(self):
        return {c.current_holder: c for c in self._cards.values() if c.status == GuestCard.ASSIGNED}

    def stats(self):
        """Return counts by status and totals used by the dashboard."""
        counts_by_status = {status: 0 for status in GuestCard.STATUSES}
        for card in self._cards.values():
            counts_by_status[card.status] += 1
        return {
            "total": len(self._cards),
            "available": counts_by_status[GuestCard.AVAILABLE],
            "assigned": counts_by_status[GuestCard.ASSIGNED],
            "missing": counts_by_status[GuestCard.MISSING],
            "returned": counts_by_status[GuestCard.RETURNED],
            "issued": counts_by_status[GuestCard.ASSIGNED] + counts_by_status[GuestCard.MISSING],
        }

    # ---- life cycle ------------------------------------------------------------
    def pick_card(self, card_id=None):
        """The card that would be issued next (lowest free one, or the one asked for). No changes made."""
        if card_id is not None and str(card_id).strip():
            card = self.get_card(card_id)
            if card.status != GuestCard.AVAILABLE:
                raise CardUnavailableError(f"Card {card.card_id} is {card.status.lower()}.")
            return card
        for card in self._sorted():
            if card.status == GuestCard.AVAILABLE:
                return card
        raise NoCardsAvailableError(f"All {len(self._cards)} guest cards are issued.")

    def assign_card(self, intern_id, card_id=None, persist=True):
        """Assign the requested card, or the lowest-numbered available card."""
        card = self.pick_card(card_id)
        snapshot = card.snapshot()
        card.assign(intern_id, self._stamp())
        if persist:
            self._commit(card, snapshot)
        return card

    def return_card(self, card_id, persist=True):
        """Return an issued card and optionally make it immediately available again."""
        card = self.get_card(card_id)
        snapshot = card.snapshot()
        card.return_card(self._stamp())
        if self.auto_recycle:
            card.recycle()
        if persist:
            self._commit(card, snapshot)
        return card

    def mark_card_missing(self, card_id, persist=True):
        """Mark a currently assigned card missing and optionally save the change."""
        card = self.get_card(card_id)
        snapshot = card.snapshot()
        card.mark_missing()
        if persist:
            self._commit(card, snapshot)
        return card

    def recycle_returned_cards(self):
        """For auto_recycle=False: put every RETURNED card back into the pool. Returns how many."""
        cards = [c for c in self._cards.values() if c.status == GuestCard.RETURNED]
        for c in cards:
            c.recycle()
        if cards:
            self.persist()
        return len(cards)
