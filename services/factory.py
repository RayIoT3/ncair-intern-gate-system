"""Builds the whole backend in one call. main.py and the tests both use it."""
from datetime import datetime
from pathlib import Path

import config
from ai.gemini_service import AdminQueryService, GeminiClient
from api.weather_service import WeatherService
from services.card_service import CardService
from services.gate_service import GateService
from services.gui_adapter import GUIService
from services.intern_service import InternService
from storage.file_storage import FileStorage, setup_logging


def build_services(data_dir=config.DATA_DIR, clock=datetime.now, gemini=None, weather=None,
                   intern_count=config.INTERN_COUNT, card_count=config.CARD_COUNT, configure_logging=False):
    storage = FileStorage(data_dir)
    if configure_logging:
        setup_logging(Path(data_dir) / config.ERROR_LOG_FILE)
    interns = InternService(storage, seed_count=intern_count)
    cards = CardService(storage, card_count=card_count, clock=clock)
    gate = GateService(interns, cards, storage, clock=clock)
    queries = AdminQueryService(gate, interns, cards, gemini or GeminiClient())
    return GUIService(
        gate,
        interns,
        cards,
        queries,
        weather or WeatherService(),
        storage,
        clock=clock,
    )
