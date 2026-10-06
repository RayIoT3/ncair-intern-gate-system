from exceptions.custom_exceptions import (DuplicateInternError, DuplicateSerialNumberError,
                                          InternNotFoundError, InvalidInternIDError,
                                          ValidationError)
from tests.helpers import BackendCase


class InternTests(BackendCase):
    def test_seed_has_300_plus_unique_interns_and_the_team(self):
        interns = self.svc.interns.get_all_interns()
        self.assertGreaterEqual(len(interns), 300)
        self.assertEqual(len({i.intern_id for i in interns}), len(interns))
        self.assertEqual(interns[0].name, "Raymond Udoh")
        self.assertEqual({i.programme for i in interns}, {"NYSC", "SIWES"})
        alphabetic = sorted(interns, key=lambda i: (i.name.casefold(), i.intern_id))
        self.assertEqual([i.serial_number for i in alphabetic],
                         [str(number) for number in range(1, len(interns) + 1)])

    def test_seed_is_identical_on_every_machine(self):
        from services.seed_data import generate_interns
        self.assertEqual(generate_interns(), generate_interns())

    def test_seed_team_matches_active_members_in_project_overview(self):
        from services.seed_data import TEAM
        self.assertEqual(
            [name for name, _ in TEAM],
            [
                "Raymond Udoh",
                "Chigozie Nwofor",
                "Isaac Erameh",
                "Jessie Nyiyongo",
                "Abdurrahman Ibrahim",
            ],
        )
        self.assertEqual(len({intern_id for _, intern_id in TEAM}), len(TEAM))

    def test_find_and_errors(self):
        self.assertEqual(self.svc.interns.find_intern("nc-si-000002").name, "Chigozie Nwofor")
        with self.assertRaises(InternNotFoundError):
            self.svc.interns.find_intern("NC-NY-999999")
        with self.assertRaises(InvalidInternIDError):
            self.svc.interns.find_intern("bad")

    def test_register_duplicate_and_persistence(self):
        i = self.svc.interns.register_intern("NC-NY-500001", "Test Person", "Robotics", "08012345678")
        self.assertEqual(i.programme, "NYSC")
        with self.assertRaises(DuplicateInternError):
            self.svc.interns.register_intern("NC-NY-500001", "Someone Else", "Robotics")
        with self.assertRaises(ValidationError):
            self.svc.interns.register_intern("NC-NY-500002", "X", "Robotics")
        self.restart()
        self.assertEqual(self.svc.interns.find_intern("NC-NY-500001").name, "Test Person")

    def test_duplicate_saved_intern_ids_are_skipped(self):
        records = self.svc.storage.load_interns()
        duplicate = dict(records[0], name="Duplicate Name")
        self.svc.storage.save_interns(records + [duplicate])

        svc = self.restart()

        self.assertEqual(svc.interns.find_intern(records[0]["intern_id"]).name, records[0]["name"])
        self.assertTrue(any("1 unreadable intern" in warning for warning in svc.warnings))

    def test_duplicate_saved_roster_numbers_are_cleared_without_dropping_interns(self):
        records = self.svc.storage.load_interns()
        records[0]["serial_number"] = "12"
        records[1]["serial_number"] = "12"
        self.svc.storage.save_interns(records)

        svc = self.restart()

        people = svc.interns.get_all_interns()
        self.assertEqual((people[0].serial_number, people[1].serial_number), ("12", None))
        self.assertEqual(len(people), len(records))
        self.assertTrue(any("duplicate roster number" in warning for warning in svc.warnings))

    def test_existing_unassigned_roster_is_numbered_once_in_alphabetical_order(self):
        records = self.svc.storage.load_interns()
        for record in records:
            record.pop("serial_number", None)
        self.svc.storage.save_interns(records)

        svc = self.restart()

        ordered = sorted(svc.interns.get_all_interns(),
                         key=lambda i: (i.name.casefold(), i.intern_id))
        self.assertEqual([i.serial_number for i in ordered],
                         [str(number) for number in range(1, len(ordered) + 1)])
        self.assertEqual(svc.interns.search_gate("001"), [ordered[0]])
        assigned = ordered[0].serial_number
        svc.interns.update_intern(ordered[0].intern_id, name="Zzz Renamed")
        self.restart()
        self.assertEqual(svc.interns.find_intern(ordered[0].intern_id).serial_number, assigned)

    def test_update_and_search(self):
        self.svc.interns.update_intern("NC-SI-000003", department="Cybersecurity", phone="08099998888")
        self.restart()
        self.assertEqual(self.svc.interns.find_intern("NC-SI-000003").department, "Cybersecurity")
        with self.assertRaises(ValidationError):
            self.svc.interns.update_intern("NC-SI-000003", status="INSIDE")
        self.assertEqual([i.name for i in self.svc.interns.search("erameh")], ["Isaac Erameh"])
        self.assertEqual(self.svc.interns.search("", "in"), [])

    def test_roster_numbers_can_be_assigned_searched_and_persisted(self):
        intern = self.svc.interns.find_intern("NC-SI-000003")
        self.svc.interns.update_intern(intern.intern_id, serial_number="9001")
        added = self.svc.interns.register_intern(
            "NC-NY-500001", "Test Person", "Robotics", serial_number="9002")
        self.assertEqual(self.svc.interns.search_gate("9001"), [intern])
        self.restart()
        self.assertEqual(self.svc.interns.find_intern(intern.intern_id).serial_number, "9001")
        self.assertEqual(self.svc.interns.find_intern(added.intern_id).serial_number, "9002")
        self.assertEqual(self.svc.interns.search("9001"), [self.svc.interns.find_intern(intern.intern_id)])

    def test_roster_numbers_are_unique_and_validated(self):
        first = self.svc.interns.find_intern("NC-SI-000001")
        second = self.svc.interns.find_intern("NC-SI-000002")
        second_serial = second.serial_number
        self.svc.interns.update_intern(first.intern_id, serial_number="9001")
        with self.assertRaises(DuplicateSerialNumberError):
            self.svc.interns.update_intern(second.intern_id, serial_number="09001")
        with self.assertRaises(DuplicateSerialNumberError):
            self.svc.interns.register_intern(
                "NC-NY-500001", "Test Person", "Robotics", serial_number="9001")
        with self.assertRaises(ValidationError):
            self.svc.interns.update_intern(second.intern_id, serial_number="one")
        self.assertEqual(second.serial_number, second_serial)

    def test_exact_roster_number_takes_precedence_over_id_suffix_search(self):
        intern = self.svc.interns.find_intern("NC-SI-000001")
        self.svc.interns.update_intern(intern.intern_id, serial_number="9001")
        self.assertEqual([match.intern_id for match in self.svc.interns.search_gate("09001")],
                         [intern.intern_id])

    def test_gate_search_matches_and_ranks_candidates(self):
        self.svc.interns.register_intern("NC-NY-123999", "Amina Search", "Robotics")
        matches = self.svc.interns.search_gate("999")
        ids = [i.intern_id for i in matches]
        self.assertIn("NC-NY-123999", ids)
        self.assertTrue(all(intern.intern_id.endswith("999") for intern in matches))
        self.assertEqual([i.intern_id for i in self.svc.interns.search_gate("amina search")],
                         ["NC-NY-123999"])
        self.assertEqual([i.intern_id for i in self.svc.interns.search_gate("nc-si-000001")],
                         ["NC-SI-000001"])
        self.assertEqual(self.svc.interns.search_gate("00"), [])
        self.assertEqual(self.svc.interns.search_gate(""), [])
