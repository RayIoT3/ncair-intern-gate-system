import tempfile
import unittest

from services.factory import build_services
from services.gate_contract import GateScreenService
from tests.helpers import FakeWeather


class GateContractTests(unittest.TestCase):
    def test_application_service_follows_the_gate_screen_contract(self):
        with tempfile.TemporaryDirectory() as data_dir:
            service = build_services(data_dir, gemini=None, weather=FakeWeather())
            intern_id = "NC-SI-000001"

            self.assertIsInstance(service, GateScreenService)
            roster = service.roster()
            self.assertEqual([row[1].casefold() for row in roster],
                             sorted(row[1].casefold() for row in roster))
            candidates = service.gate_candidates(intern_id)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0][0], intern_id)
            self.assertFalse(candidates[0][4])
            self.assertEqual(service.set_serial_number(intern_id, "9999").kind, "ok")
            serial_match = service.gate_candidates("09999")
            self.assertEqual(serial_match[0][0], intern_id)
            self.assertEqual(serial_match[0][3], "9999")

            checked_in = service.check_in(intern_id)
            self.assertEqual(checked_in.kind, "ok")
            self.assertEqual(service.recent(1)[0].direction, "in")

            checked_out = service.check_out(intern_id)
            self.assertEqual(checked_out.kind, "ok")
            self.assertEqual(service.recent(1)[0].direction, "out")
