from unittest import mock

import config
from exceptions.custom_exceptions import StorageError
from tests.helpers import BackendCase

A = "NC-SI-000001"


class AdapterTests(BackendCase):
    def test_check_in_and_out_results_match_what_the_gate_screen_shows(self):
        r = self.svc.check_in(A)
        self.assertEqual((r.kind, r.title, r.detail), ("ok", "Checked in", "Raymond Udoh \u00b7 hand over card #001"))
        r = self.svc.check_in(A)
        self.assertEqual((r.kind, r.title), ("wa", "Already inside"))
        r = self.svc.check_out(A)
        self.assertEqual((r.kind, r.detail), ("ok", "Raymond Udoh \u00b7 collect card #001"))
        self.assertEqual(self.svc.check_out(A).kind, "wa")
        self.assertEqual(self.svc.check_in("bad").kind, "er")
        self.assertEqual(self.svc.check_in("NC-NY-999999").title, "ID not found")

    def test_nothing_ever_raises_into_the_gui(self):
        with mock.patch.object(self.svc.gate, "check_in", side_effect=RuntimeError("bug")):
            r = self.svc.check_in(A)
        self.assertEqual((r.kind, r.title), ("er", "Unexpected error"))
        with mock.patch.object(self.svc.gate.storage, "save_cards", side_effect=StorageError("disk full")):
            r = self.svc.check_in(A)
        self.assertEqual((r.kind, r.title), ("er", "Storage problem"))
        self.assertFalse(self.svc.gate.is_intern_inside(A))

    def test_dashboard_numbers(self):
        self.svc.check_in(A)
        self.svc.check_in("NC-SI-000002")
        self.assertEqual(self.svc.stats(), {"inside": 2, "outside": 318, "free": config.CARD_COUNT - 2, "issued": 2,
                                            "total": 320, "cards": config.CARD_COUNT})
        self.assertEqual(self.svc.cards_in_use(), {1, 2})

    def test_recent_and_roster(self):
        self.svc.check_in(A)
        self.svc.check_out(A)
        self.svc.check_in("NC-SI-000002")
        rec = self.svc.recent(6)
        self.assertEqual([(m.direction, m.intern_id) for m in rec],
                         [("in", "NC-SI-000002"), ("out", A), ("in", A)])
        rows = self.svc.roster("", "in")
        self.assertEqual(rows[0][:3], ("NC-SI-000002", "Chigozie Nwofor", "SIWES"))
        self.assertEqual(rows[0][3], self.svc.interns.find_intern("NC-SI-000002").serial_number)
        self.assertEqual(rows[0][4:6], (True, "001"))
        self.assertEqual(rows[0][6], "08:04")
        all_rows = self.svc.roster("", "all")
        self.assertEqual(len(all_rows), 320)
        self.assertEqual([row[1].casefold() for row in all_rows],
                         sorted(row[1].casefold() for row in all_rows))
        self.assertEqual(len(self.svc.roster("nwofor", "all")), 1)
        row = next(row for row in all_rows if row[0] == "NC-SI-000101")
        self.assertEqual(row[5:], (0, "\u2014"))

    def test_gate_search_matches_names_ids_and_last_three_digits(self):
        extra_id = "NC-NY-123001"
        self.svc.register_intern(extra_id, "Amina Search", "Robotics")
        self.svc.check_in(A)

        matches = self.svc.gate_candidates(A)
        by_id = {row[0]: row for row in matches}
        self.assertIn(A, by_id)
        self.assertEqual(by_id[A][1], "Raymond Udoh")
        self.assertEqual(by_id[A][4:], (True, "001"))
        self.assertEqual(self.svc.set_serial_number(A, "9999").kind, "ok")
        serial_match = self.svc.gate_candidates("09999")
        self.assertEqual([row[0] for row in serial_match], [A])

    def test_extra_methods_for_future_screens(self):
        self.assertEqual(self.svc.register_intern("NC-NY-500001", "Test Person", "Robotics").kind, "ok")
        self.assertEqual(self.svc.register_intern("NC-NY-500001", "Test Person", "Robotics").kind, "er")
        self.svc.check_in(A)
        self.assertEqual(self.svc.check_out_card_not_returned(A).kind, "wa")
        self.assertEqual(self.svc.mark_card_missing("1").kind, "wa")
        self.assertEqual(self.svc.return_card("1").kind, "ok")
        self.assertEqual(self.svc.return_card("1").kind, "er")
        self.assertEqual(self.svc.card_report()[0][:2], ("001", "AVAILABLE"))
        self.assertEqual(self.svc.card_report()[0][2:4], (A, "Raymond Udoh"))

    def test_card_cannot_be_returned_or_marked_missing_while_holder_is_inside(self):
        self.svc.check_in(A)

        returned = self.svc.return_card("001")
        marked_missing = self.svc.mark_card_missing("001")

        self.assertEqual((returned.kind, returned.title), ("wa", "Intern still inside"))
        self.assertEqual((marked_missing.kind, marked_missing.title),
                         ("wa", "Intern still inside"))
        self.assertEqual(self.svc.cards.get_card("001").status, "ASSIGNED")
        self.assertTrue(self.svc.gate.is_intern_inside(A))

        self.svc.check_out_card_not_returned(A)
        self.assertEqual(self.svc.return_card("001").kind, "ok")
