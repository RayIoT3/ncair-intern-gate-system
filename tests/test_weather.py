import unittest

from api.weather_service import WeatherService
from exceptions.custom_exceptions import ExternalAPIError


class WeatherTests(unittest.TestCase):
    def test_parses_the_api_response(self):
        w = WeatherService(fetcher=lambda: {"current": {"temperature_2m": 30.6, "weather_code": 2}})
        r = w.fetch()
        self.assertEqual((r.ok, r.text), (True, "31\u00b0C  Partly cloudy"))

    def test_bad_responses_raise_a_controlled_error(self):
        for data in ({}, {"current": {}}, {"current": {"temperature_2m": "hot", "weather_code": 1}}, None):
            with self.assertRaises(ExternalAPIError):
                WeatherService(fetcher=lambda d=data: d).fetch()

    def test_failure_shows_unavailable_and_never_raises(self):
        def down():
            raise ExternalAPIError("offline")
        w = WeatherService(fetcher=down)
        w._refresh()
        report = w.get()
        self.assertEqual((report.ok, report.text), (False, "Weather unavailable"))

    def test_get_returns_immediately_then_has_data(self):
        w = WeatherService(fetcher=lambda: {"current": {"temperature_2m": 25, "weather_code": 0}})
        self.assertTrue(w.get().loading)                # first call: placeholder while a thread fetches
        w._refresh()
        self.assertEqual(w.get().text, "25\u00b0C  Clear sky")
