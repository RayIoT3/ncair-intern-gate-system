"""Live weather for the dashboard (Open-Meteo: free, no API key).

`get()` never blocks and never raises: it returns the last known report at once and refreshes
in a background thread. If the request fails the report says "Weather unavailable" and the rest
of the application carries on.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

import config
from exceptions.custom_exceptions import ExternalAPIError

log = logging.getLogger("gate")

WMO = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
       80: "Rain showers", 81: "Rain showers", 82: "Violent showers", 95: "Thunderstorm",
       96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}


@dataclass
class WeatherReport:
    ok: bool
    text: str                    # e.g. "31°C  Partly cloudy"
    note: str                    # small grey line under it
    loading: bool = False
    temperature_c: float = None
    condition: str = ""


class WeatherService:
    def __init__(self, lat=config.WEATHER_LAT, lon=config.WEATHER_LON, city=config.WEATHER_CITY,
                 timeout=config.WEATHER_TIMEOUT, ttl=config.WEATHER_TTL, fetcher=None):
        self.lat, self.lon, self.city, self.timeout, self.ttl = lat, lon, city, timeout, ttl
        self._fetcher = fetcher              # returns the raw API dict; replaced by a fake in tests
        self._report, self._stamp, self._busy = None, 0.0, False
        self._lock = threading.Lock()

    def _download(self):
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}"
               "&current=temperature_2m,weather_code")
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise ExternalAPIError(f"Weather request failed: {e}") from e

    def fetch(self):
        """One synchronous lookup. Raises ExternalAPIError on any failure."""
        data = (self._fetcher or self._download)()
        try:
            current = data["current"]
            temp, code = float(current["temperature_2m"]), int(current["weather_code"])
        except (KeyError, TypeError, ValueError) as e:
            raise ExternalAPIError(f"Unexpected weather response: {e}") from e
        condition = WMO.get(code, "Mixed conditions")
        return WeatherReport(True, f"{round(temp)}\u00b0C  {condition}", f"Live data \u00b7 {self.city}",
                             temperature_c=temp, condition=condition)

    def _refresh(self):
        try:
            report, delay = self.fetch(), 0
        except ExternalAPIError as e:
            log.warning("%s", e)
            report = WeatherReport(False, "Weather unavailable",
                                   "Live weather could not be loaded. The gate keeps working.")
            delay = self.ttl - 60                # try again in about a minute
        with self._lock:
            self._report, self._stamp, self._busy = report, time.time() - delay, False

    def get(self):
        with self._lock:
            stale = self._report is None or time.time() - self._stamp > self.ttl
            start = stale and not self._busy
            if start:
                self._busy = True
            report = self._report
        if start:
            threading.Thread(target=self._refresh, daemon=True).start()
        return report or WeatherReport(False, "Loading weather\u2026", "Fetching live data.", loading=True)
