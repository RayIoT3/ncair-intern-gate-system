import json
import os
import random
from datetime import date
from unittest import mock

from exceptions.custom_exceptions import (DuplicateCheckInError, InternNotFoundError, InvalidInternIDError,
                                          NoCardsAvailableError, NotCheckedInError, StorageError)
from models.guest_card import GuestCard
from services.factory import build_services
import config
from tests.helpers import BackendCase

A, B = "NC-SI-000001", "NC-SI-000002"


class GateTests(BackendCase):
    def setUp(self):
        super().setUp()
        self.gate, self.cards, self.interns = self.svc.gate, self.svc.cards, self.svc.interns

    def test_normal_check_in_and_out(self):
        entry = self.gate.check_in(" nc-si-000001 ")
        self.assertEqual((entry.action, entry.card_id), ("CHECK_IN", "001"))
        self.assertTrue(self.gate.is_intern_inside(A))
        self.assertEqual([i.intern_id for i in self.gate.get_inside_interns()], [A])
        out = self.gate.check_out(A)
        self.assertEqual((out.action, out.card_id, out.card_returned), ("CHECK_OUT", "001", True))
        self.assertFalse(self.gate.is_intern_inside(A))
        self.assertEqual(self.cards.get_card("001").status, GuestCard.AVAILABLE)

    def test_duplicate_check_in(self):
        self.gate.check_in(A)
        with self.assertRaises(DuplicateCheckInError) as ctx:
            self.gate.check_in(A)
        self.assertIn("card #001", str(ctx.exception))
        self.assertEqual(len(self.gate.logs_for_date(self.clock().date())), 1)

    def test_check_out_when_not_inside(self):
        with self.assertRaises(NotCheckedInError):
            self.gate.check_out(A)

    def test_invalid_and_unknown_ids(self):
        with self.assertRaises(InvalidInternIDError):
            self.gate.check_in("ABC!!!!!123")
        with self.assertRaises(InternNotFoundError):
            self.gate.check_in("NC-NY-999999")
        self.assertEqual(self.gate.log_count(), 0)

    def test_no_cards_left_leaves_no_trace(self):
        svc = build_services(os.path.join(self.dir, "small"), clock=self.clock,
                             intern_count=4, card_count=3)
        people = svc.interns.get_all_interns()
        for i in people[:3]:
            svc.gate.check_in(i.intern_id)
        with self.assertRaises(NoCardsAvailableError):
            svc.gate.check_in(people[3].intern_id)
        self.assertFalse(people[3].is_inside)
        self.assertEqual(svc.gate.log_count(), 3)

    def test_card_not_returned_is_flagged_and_reused(self):
        self.gate.check_in(A)
        out = self.gate.check_out(A, card_returned=False)
        self.assertFalse(out.card_returned)
        self.assertEqual([c.card_id for c in self.cards.get_unreturned_cards()], ["001"])
        self.assertEqual(self.gate.attendance_summary()["cards_unreturned_after_leaving"], 1)
        self.assertEqual(self.gate.check_in(A).card_id, "001")        # they still have it, so no second card
        self.assertEqual(self.cards.stats()["issued"], 1)

    def test_data_survives_restart(self):
        self.gate.check_in(A)
        self.gate.check_in(B)
        self.gate.check_out(B)
        svc = self.restart()
        self.assertEqual([i.intern_id for i in svc.gate.get_inside_interns()], [A])
        self.assertEqual(svc.cards.get_card_holder("001"), A)
        self.assertEqual(svc.gate.log_count(), 3)
        self.assertEqual(svc.gate.recent_logs(1)[0].action, "CHECK_OUT")

    def test_missing_files_are_recreated(self):
        import os
        for name in ("interns.json", "cards.json", "gate_logs.json"):
            os.remove(f"{self.dir}/{name}")
        svc = self.restart()
        self.assertEqual(len(svc.interns.get_all_interns()), 320)
        self.assertEqual(svc.cards.stats()["total"], config.CARD_COUNT)
        self.assertEqual(svc.gate.log_count(), 0)

    def test_corrupted_file_is_quarantined_not_fatal(self):
        import os
        self.gate.check_in(A)
        with open(f"{self.dir}/gate_logs.json", "w") as f:
            f.write("{ this is not json")
        with open(f"{self.dir}/cards.json", "w") as f:
            f.write("[1, 2, 3]")                                      # valid JSON, wrong shape
        svc = self.restart()
        self.assertEqual(svc.gate.log_count(), 0)
        self.assertEqual(len(svc.cards.all_cards()), config.CARD_COUNT)
        self.assertEqual(len(svc.warnings), 3)                        # two corrupt files + inside-without-card note
        self.assertTrue([n for n in os.listdir(self.dir) if ".corrupt-" in n])

    def test_bad_records_are_skipped(self):
        path = f"{self.dir}/interns.json"
        with open(path) as f:
            data = json.load(f)
        data += [{"intern_id": "garbage"}, {"name": "no id"}]
        with open(path, "w") as f:
            json.dump(data, f)
        svc = self.restart()
        self.assertEqual(len(svc.interns.get_all_interns()), 320)
        self.assertTrue(any("2 unreadable intern" in w for w in svc.warnings))

    def test_failed_save_rolls_everything_back(self):
        with mock.patch.object(self.svc.gate.storage, "save_gate_logs", side_effect=StorageError("disk full")):
            with self.assertRaises(StorageError):
                self.gate.check_in(A)
        self.assertFalse(self.interns.find_intern(A).is_inside)
        self.assertEqual(self.cards.get_card("001").status, GuestCard.AVAILABLE)
        self.assertEqual(self.gate.log_count(), 0)
        self.gate.check_in(A)                                         # and it works again afterwards
        self.assertTrue(self.gate.is_intern_inside(A))

    def test_summary(self):
        self.gate.check_in(A)
        self.gate.check_in("NC-NY-000101")
        s = self.gate.attendance_summary()
        self.assertEqual((s["check_ins"], s["inside_now"], s["cards_issued"]), (2, 2, 2))
        self.assertEqual((s["inside_nysc"], s["inside_siwes"]), (1, 1))
        self.assertEqual(s["date"], self.clock().date().isoformat())

    def test_morning_rush(self):
        """Hundreds of attempts: cards run out gracefully, nothing is issued twice, disk matches memory."""
        rng = random.Random(1)
        people = [i.intern_id for i in self.interns.get_all_interns()]
        refused = ok = 0
        for _ in range(400):
            iid = rng.choice(people)
            try:
                if rng.random() < 0.7:
                    self.gate.check_in(iid)
                else:
                    self.gate.check_out(iid, card_returned=rng.random() < 0.9)
                ok += 1
            except (DuplicateCheckInError, NotCheckedInError, NoCardsAvailableError):
                refused += 1
        self.assertGreater(refused, 0)
        held = [c.current_holder for c in self.cards.all_cards() if c.status == GuestCard.ASSIGNED]
        self.assertEqual(len(held), len(set(held)))
        inside = {i.intern_id for i in self.gate.get_inside_interns()}
        self.assertTrue(inside <= set(held))
        svc = self.restart()
        self.assertEqual({i.intern_id for i in svc.gate.get_inside_interns()}, inside)
        self.assertEqual(svc.gate.log_count(), ok)
