# NCAIR / NITDA Intern Gate System: Project Overview

**Group 23 · 5 active members** · Python 3 · CustomTkinter desktop app · JSON storage · Gemini + Open-Meteo APIs

This is the shared map of the codebase. Each member also has a personal document in `docs/members/` that goes deep on their own layer. Read this one first, then your own.

---

## 1. What the system does

Security officers at the NCAIR E-Government Facility used to flip through a paper book to find an intern's ID, tick it, and hand over a guest card. This application replaces that book:

- Finds an intern by roster number, name, full ID, or the last three ID digits.
- Checks them in or out, blocks duplicate check-ins, and hands out or collects a guest card.
- Tracks who is inside, which cards are out, and which cards are unreturned or missing.
- Saves everything to JSON files, so data survives closing the app.
- Shows a live dashboard (occupancy, card pool, weather) and answers plain-English admin questions with Gemini, falling back to local rules when the AI is unavailable.

## 2. How to run it

```bash
pip install -r requirements.txt          # customtkinter, pillow
python main.py                           # first run creates 320 interns and 400 cards in ./data
python -m unittest discover -s tests     # 70 tests (66 backend + 4 window-layout tests that need Tk)
```

Optional Gemini key (without one, the app answers from the same records using plain templates):

```bash
set GEMINI_API_KEY=your-key              # Windows
export GEMINI_API_KEY=your-key           # macOS / Linux
```

## 3. Architecture in one picture

```text
main.py
 └─ services/factory.py              builds every object once and wires them together
     ├─ gui/app.py + gui/*_screen.py        what the officer sees and clicks
     │    └─ services/gui_adapter.py        translates clicks into service calls, turns errors into messages
     │         ├─ services/gate_service.py     check-in / check-out engine
     │         ├─ services/intern_service.py   roster: register, find, search, update
     │         ├─ services/card_service.py     guest-card inventory and life cycle
     │         ├─ ai/gemini_service.py         admin questions and daily memo
     │         └─ api/weather_service.py       dashboard weather (background thread)
     ├─ models/        Intern, GuestCard, GateLog (plain objects with to_dict / from_dict)
     ├─ validation/    regex rules and input normalisation
     ├─ exceptions/    every controlled error, with a GUI-friendly kind and title
     └─ storage/       atomic JSON load / save, corrupt-file recovery, log file
```

The rule that holds the design together: **the window displays, the services decide, storage saves.** No screen reads a JSON file or decides whether a gate action is allowed.

## 4. Who owns what

| Member | Role in the proposal | Primary files | Tests that cover it |
|---|---|---|---|
| **Raymond Udoh** | Lead, core integration, intern management | `main.py`, `config.py`, `services/factory.py`, `services/gate_service.py`, `services/gui_adapter.py`, `services/gate_contract.py`, `services/intern_service.py`, `services/seed_data.py`, `models/intern.py`, `models/base.py` | `test_gate.py`, `test_interns.py`, `test_gui_adapter.py`, `test_gate_contract.py`, `test_config.py` |
| **Chigozie Nwofor** | GUI, external API, system testing | `gui/` (all files), `api/weather_service.py`, `tests/helpers.py` | `test_weather.py`, `test_responsive_layout.py`, plus the end-to-end `test_morning_rush` |
| **Isaac Erameh** | Validation, exceptions, file persistence | `validation/validators.py`, `exceptions/custom_exceptions.py`, `storage/file_storage.py`, `models/gate_log.py` | `test_validation.py` and the persistence tests inside `test_gate.py` |
| **Jessie Nyiyongo** | AI integration | `ai/gemini_service.py` | `test_ai.py` |
| **Abdurrahman Ibrahim** | Guest-card lifecycle | `models/guest_card.py`, `services/card_service.py` | `test_cards.py` |

Some files are shared on purpose: `tests/helpers.py` is the common test harness, and `gui_adapter.py` is where Raymond's engine meets Chigozie's screens and Isaac's exceptions.

## 5. Agreed data shapes

| Record | Fields |
|---|---|
| Intern | `intern_id`, `serial_number` (optional printed roster number), `name`, `programme` (derived from the ID), `department`, `phone`, `email`, `status` (`INSIDE` / `OUTSIDE`) |
| Guest card | `card_id` (e.g. `"047"`), `status`, `current_holder`, `previous_holder`, `assigned_at`, `returned_at` |
| Gate log | `intern_id`, `action` (`CHECK_IN` / `CHECK_OUT`), `timestamp` (ISO), `card_id`, `card_returned` |

Card statuses: `AVAILABLE → ASSIGNED → RETURNED → AVAILABLE`, or `ASSIGNED → MISSING → RETURNED`.

ID formats: NYSC `NC-NY-######`, SIWES `NC-SI-######`, enforced by one regular expression in `validation/validators.py`.

## 6. The life of one check-in

1. The officer types a roster number, name, ID, or the last three digits. `GateScreen` calls `service.gate_candidates(query)`, which calls `InternService.search_gate()`.
2. The officer selects the intern. The screen enables only the action that matches the intern's current inside/outside status.
3. The screen calls `GUIService.check_in(id)`. The adapter wraps the call in `_safe()` so no exception can reach the window.
4. `GateService.check_in()` validates the ID, finds the intern, rejects a duplicate, and picks a card (reusing one still assigned to this intern).
5. It takes snapshots of the intern and card, then updates both and appends a `GateLog` entry.
6. `_persist_all()` saves cards, interns, and logs through `FileStorage` (each write is atomic).
7. If any save fails, the snapshots are restored in memory and the restored state is written back, then the error is re-raised. The adapter turns it into a red "Storage problem" message.
8. On success the adapter returns `GateResult("ok", "Checked in", "Name · hand over card #001")` and the screen refreshes "Recent activity".

## 7. Design ideas worth naming in a presentation

| Idea | Where | Why it matters |
|---|---|---|
| Layered architecture | whole project | Each part can be changed or tested without touching the others |
| Dependency injection | `factory.py`, every service takes `storage` / `clock` | Tests swap in a fake clock, fake weather, and fake AI transport |
| Never raise into the GUI | `GUIService._safe`, `AdminQueryService.ask`, `WeatherService.get` | A failure becomes a message, not a crash |
| Atomic write + rollback | `FileStorage.save_records`, `GateService._rollback` | Disk and memory never disagree after a failed save |
| Fallback chains | Gemini → keyword rules → plain template | The AI feature degrades gracefully instead of failing |
| Deterministic seed | `seed_data.generate_interns(seed=23)` | Every machine gets the same 320 interns |
| Derived, not stored, facts | `Intern.programme` comes from the ID | The programme can never disagree with the ID |

## 8. Decisions the group agreed (from the README)

1. **Card pool = 400** (`config.CARD_COUNT`): 320 interns plus 20% spare, computed as `ceil(320 / 0.8)`.
2. **Card reuse:** an intern who left without returning a card gets the same card back on the next check-in.
3. **"Unreturned"** means a card that is not back in the pool: still out, held by someone who has left, or `MISSING`.
4. **Check-out button** means "card returned". `GUIService.check_out_card_not_returned()` exists and is ready for a second button.
5. **One log file** (`gate_logs.json`) holds all movements; rotate per month if it ever runs long.

## 9. Tests at a glance

| File | Tests | What it proves |
|---|---|---|
| `test_gate.py` | 13 | Check-in/out, duplicates, no cards left, restart persistence, corrupt files, rollback, 400-attempt morning rush |
| `test_interns.py` | 12 | Seed data, search ranking, registration, roster numbers, bad saved records |
| `test_cards.py` | 10 | Card life cycle, pool exhaustion, missing/unreturned, persistence |
| `test_ai.py` | 13 | Keyword routing, local answers, Gemini success and every failure path, invented data rejected |
| `test_gui_adapter.py` | 6 | Results match what the Gate screen shows; nothing raises into the GUI |
| `test_validation.py` | 6 | ID, card, name, phone, email, roster-number rules |
| `test_weather.py` | 4 | Parsing, bad responses, failure never raises, non-blocking `get()` |
| `test_responsive_layout.py` | 4 | Window sizing on small and high-DPI screens (needs Tk) |
| `test_gate_contract.py` | 1 | The real service satisfies the Gate screen's interface |
| `test_config.py` | 1 | Card pool keeps the 20% reserve |

No test touches the real network or the real `data/` folder: each test builds a fresh backend in a temporary directory.
