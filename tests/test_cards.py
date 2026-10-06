from exceptions.custom_exceptions import (CardUnavailableError, InvalidCardIDError,
                                          InvalidCardOperationError, NoCardsAvailableError)
from models.guest_card import GuestCard
import config
from tests.helpers import BackendCase


class CardTests(BackendCase):
    def setUp(self):
        super().setUp()
        self.cards = self.svc.cards

    def test_lowest_free_card_is_issued_first(self):
        self.assertEqual(self.cards.assign_card("NC-SI-000001").card_id, "001")
        self.assertEqual(self.cards.assign_card("NC-SI-000002").card_id, "002")

    def test_specific_card_and_unavailable(self):
        last_card_id = f"{config.CARD_COUNT:03d}"
        self.assertEqual(self.cards.assign_card("NC-SI-000001", str(config.CARD_COUNT)).card_id, last_card_id)
        with self.assertRaises(CardUnavailableError):
            self.cards.assign_card("NC-SI-000002", last_card_id)
        with self.assertRaises(InvalidCardIDError):
            self.cards.assign_card("NC-SI-000002", str(config.CARD_COUNT + 1))

    def test_life_cycle_and_holders(self):
        card_id = f"{config.CARD_COUNT:03d}"
        self.cards.assign_card("NC-SI-000001", card_id)
        self.assertEqual(self.cards.get_card_holder(card_id), "NC-SI-000001")
        self.cards.return_card(card_id)
        card = self.cards.get_card(card_id)
        self.assertEqual((card.status, card.current_holder, card.previous_holder),
                         (GuestCard.AVAILABLE, None, "NC-SI-000001"))
        self.assertEqual(self.cards.get_previous_holder(str(config.CARD_COUNT)), "NC-SI-000001")
        self.assertIn(card_id, [c.card_id for c in self.cards.get_available_cards()])

    def test_returned_cards_can_be_recycled_when_auto_recycle_is_disabled(self):
        card = self.cards.assign_card("NC-SI-000001", "001")
        self.cards.auto_recycle = False

        self.cards.return_card(card.card_id)

        self.assertEqual(self.cards.get_card(card.card_id).status, GuestCard.RETURNED)
        self.assertEqual(self.cards.recycle_returned_cards(), 1)
        self.assertEqual(self.cards.get_card(card.card_id).status, GuestCard.AVAILABLE)
        self.assertEqual(self.cards.recycle_returned_cards(), 0)

    def test_missing_and_unreturned(self):
        self.cards.assign_card("NC-SI-000001", "005")
        self.cards.mark_card_missing("5")
        self.assertEqual([c.card_id for c in self.cards.get_missing_cards()], ["005"])
        self.assertEqual([c.card_id for c in self.cards.get_unreturned_cards()], ["005"])
        self.cards.return_card("005")                       # found again
        self.assertEqual(self.cards.get_unreturned_cards(), [])

    def test_invalid_operations(self):
        with self.assertRaises(InvalidCardOperationError):
            self.cards.return_card("001")                   # never issued
        with self.assertRaises(InvalidCardOperationError):
            self.cards.mark_card_missing("001")

    def test_pool_runs_out(self):
        for n in range(config.CARD_COUNT):
            self.cards.assign_card(f"NC-SI-{n:06d}")
        with self.assertRaises(NoCardsAvailableError):
            self.cards.assign_card(f"NC-SI-{config.CARD_COUNT + 1:06d}")
        self.assertEqual(self.cards.stats()["available"], 0)

    def test_card_outside_the_pool(self):
        with self.assertRaises(InvalidCardIDError):
            self.cards.get_card(str(config.CARD_COUNT + 1))

    def test_cards_persist(self):
        self.cards.assign_card("NC-SI-000001", "012")
        self.restart()
        self.assertEqual(self.svc.cards.get_card_holder("012"), "NC-SI-000001")

    def test_existing_inventory_expands_without_losing_card_history(self):
        self.cards.assign_card("NC-SI-000001", "001")
        self.svc.storage.save_cards([card.to_dict() for card in self.cards.all_cards()[:20]])

        svc = self.restart()

        self.assertEqual(svc.cards.stats()["total"], config.CARD_COUNT)
        self.assertEqual(svc.cards.get_card_holder("001"), "NC-SI-000001")
        self.assertEqual(svc.cards.get_card(config.CARD_COUNT).status, GuestCard.AVAILABLE)

    def test_duplicate_and_invalid_saved_cards_are_skipped(self):
        records = self.svc.storage.load_cards()
        duplicate = dict(records[0], card_id="1", previous_holder="NC-NY-000999")
        invalid = dict(records[1], card_id="000")
        self.svc.storage.save_cards(records + [duplicate, invalid])

        svc = self.restart()

        self.assertEqual(svc.cards.get_card("001").previous_holder, records[0]["previous_holder"])
        self.assertTrue(any("2 unreadable guest card" in warning for warning in svc.warnings))
