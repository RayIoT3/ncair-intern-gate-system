import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from ai.gemini_service import GeminiClient
from services.factory import build_services


class FakeClock:
    """Advances one minute per call so every movement has its own timestamp."""
    def __init__(self, start=datetime(2026, 9, 30, 8, 0, 0)):
        self.now = start

    def __call__(self):
        self.now += timedelta(minutes=1)
        return self.now


class FakeWeather:
    def get(self):
        raise AssertionError("weather should not be called in this test")


class BackendCase(unittest.TestCase):
    """Fresh temp data folder and a fully wired backend for each test (no Gemini key, no network)."""
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.clock = FakeClock()
        self.svc = self.build()

    def build(self, **kw):
        kw.setdefault("gemini", GeminiClient(api_key=""))
        kw.setdefault("weather", FakeWeather())
        return build_services(self.dir, clock=self.clock, **kw)

    def restart(self, **kw):
        """Simulate closing and reopening the app."""
        self.svc = self.build(**kw)
        return self.svc
