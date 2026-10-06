"""Central settings. Change values here, not inside the modules."""
import math
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INTERNS_FILE = "interns.json"
CARDS_FILE = "cards.json"
LOGS_FILE = "gate_logs.json"
ERROR_LOG_FILE = "gate_errors.log"

INTERN_COUNT = 320          # baseline records generated on first run (proposal: 300+)
CARD_RESERVE_RATE = 0.20    # keep 20% of the card pool available after the baseline is checked in
# Solve for a pool where checking in every baseline intern still leaves the reserve.
CARD_COUNT = math.ceil(INTERN_COUNT / (1 - CARD_RESERVE_RATE))
AUTO_RECYCLE_CARDS = True   # a returned card goes straight back into the pool

# Gemini: set the key in your environment, never in the code:
#   Windows (cmd):   set GEMINI_API_KEY=your-key
#   macOS / Linux:   export GEMINI_API_KEY=your-key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TIMEOUT = 8          # seconds; on failure the local rule-based answer is used

WEATHER_CITY = "Abuja"
WEATHER_LAT, WEATHER_LON = 9.0765, 7.3986
WEATHER_TIMEOUT = 4         # seconds
WEATHER_TTL = 600           # seconds between refreshes
