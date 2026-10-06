# NCAIR / NITDA Intern Gate System (Group 23)

Desktop gate and attendance system for NYSC / SIWES interns: ID validation, guest-card
management, JSON persistence, Gemini-assisted admin questions and live weather.

## Run

    pip install -r requirements.txt
    python main.py            # real data in ./data (created on first run: 320 interns, 400 cards)
    python -m unittest discover -s tests

Optional Gemini (without a key the app answers from the same records with plain templates):

    Windows:      set GEMINI_API_KEY=your-key
    macOS/Linux:  export GEMINI_API_KEY=your-key

## How the application is organized

The program is split into layers so that the window displays information while the
services enforce the rules and storage handles files:

```text
main.py
  -> services/factory.py             builds and connects the application services
  -> gui/app.py and gui/*_screen.py   display screens and collect user input
       -> services/gui_adapter.py     translates screen requests into service calls
            -> services/*_service.py enforces intern, card, and gate rules
                 -> models/           represents interns, guest cards, and gate logs
                 -> validation/       checks and normalizes input
                 -> storage/           loads and saves JSON records
            -> ai/gemini_service.py   answers questions using facts from services
            -> api/weather_service.py loads dashboard weather independently
```

`services/factory.py` is the composition root: it creates each dependency once and
passes it to the services that need it. The screens do not read JSON files or decide
whether a gate action is allowed.

### Example: checking an intern in

1. The guard types a roster number, name, full ID, or the last three ID digits.
   `InternService.search_gate()` finds candidates; an exact roster-number match takes
   priority over an ID suffix.
2. `GateScreen` displays the candidates. Selecting one enables only the action that
   matches the intern's current inside/outside status.
3. The screen calls `GUIService.check_in()`. The adapter calls `GateService`, which
   validates and finds the intern, rejects a duplicate check-in, and chooses a guest
   card. A card still assigned to that intern from a previous visit is reused.
4. `GateService` takes snapshots, updates the intern, card, and movement log, then
   saves all three records. If any save fails, it restores the snapshots and tries to
   save the restored state.
5. The adapter turns expected `GateError` exceptions into a result the screen can
   display. Unexpected errors are logged and shown as a safe, general error message.

### Data and error handling

- `Intern`, `GuestCard`, and `GateLog` are the domain models. Each can convert to and
  from a plain dictionary, which is the format used in the JSON files.
- `validation/validators.py` is the shared entry point for normalizing and checking
  IDs, card numbers, names, contact details, and roster numbers. Domain services call
  these validators before changing records.
- `FileStorage` writes through a temporary file and replaces the old file only after
  the complete JSON has been written. Missing files are initialized; unreadable or
  malformed files are moved aside with a `.corrupt-<timestamp>` suffix and reported
  to the user. File-system failures raise `StorageError`.
- Gate operations span multiple files, so they keep snapshots and roll back in-memory
  changes if persistence fails. Individual intern and card updates also restore their
  previous state if their save fails.
- The GUI adapter catches expected domain errors separately from unexpected errors.
  The Gemini service falls back to local keyword rules and templates. Weather refresh
  runs in a background thread, so an unavailable weather service does not stop gate
  operations.

## Presenting the project

A concise explanation for an instructor:

1. **Problem:** staff need to find interns quickly, record arrivals and departures,
   and track reusable guest cards.
2. **Design:** the GUI, business rules, data models, and file storage are separate,
   so each part has a clear responsibility.
3. **Demonstration:** search by a printed roster number, select the intern, check them
   in, and show the updated inside status, card assignment, and recent activity.
4. **Reliability:** explain input validation, duplicate-action checks, JSON recovery,
   atomic saves, and rollback if any part of a gate movement cannot be saved.
5. **Testing:** run `python -m unittest discover -s tests` to exercise service rules,
   storage behavior, validation, AI fallbacks, and external-service handling.

When tracing code during the presentation, start at `main.py`, follow
`services/factory.py` to see how dependencies are connected, then trace one screen
action through `services/gui_adapter.py` to its domain service. Avoid starting with a
widget's layout code when explaining a business rule.

| Member | Role in the proposal | Primary files |
|---|---|---|
| **Raymond Udoh** | Lead, core integration, intern management | `main.py`, `config.py`, `services/factory.py`, `services/gate_service.py`, `services/gui_adapter.py`, `services/gate_contract.py`, `services/intern_service.py`, `services/seed_data.py`, `models/intern.py`, `models/base.py` |
| **Chigozie Nwofor** | GUI, external API, system testing | `gui/`, `api/weather_service.py`, `tests/helpers.py` |
| **Isaac Erameh** | Validation, exceptions, file persistence | `validation/validators.py`, `exceptions/custom_exceptions.py`, `storage/file_storage.py`, `models/gate_log.py` |
| **Jessie Nyiyongo** | AI integration | `ai/gemini_service.py` |
| **Abdurrahman Ibrahim** | Guest-card lifecycle | `models/guest_card.py`, `services/card_service.py` |

## Agreed data shapes (change them here first, then tell everyone)

- Intern: `intern_id, serial_number (optional printed roster number), name, programme (derived from ID), department, phone, email, status (INSIDE/OUTSIDE)`
- Guest card: `card_id ("047"), status, current_holder, previous_holder, assigned_at, returned_at`
- Gate log: `intern_id, action (CHECK_IN/CHECK_OUT), timestamp (ISO), card_id, card_returned`
- Card statuses: `AVAILABLE -> ASSIGNED -> RETURNED -> AVAILABLE`, or `ASSIGNED -> MISSING`

## Decisions the group should confirm

1. **Card pool = 400** (`config.CARD_COUNT`), sized for 320 interns plus 20% spare capacity (80 cards), IDs shown as 001-400. Existing card records and history are preserved; missing cards are added on startup to reach the configured pool size.
2. **Card reuse:** an intern who left without returning their card gets that same card back on the next check-in instead of a second one.
3. **"Unreturned"** means a card that is not back in the pool: still out, held by someone who has left, or MISSING.
4. **Card not returned at check-out** keeps the card ASSIGNED and flags it; nothing becomes MISSING until someone marks it. The Gate screen has separate check-out actions for a returned card and a card the intern keeps.
5. **Team intern IDs** in `services/seed_data.py` are still placeholders because the project overview lists member names but not their real intern IDs. Confirm those IDs before changing the seed records. Existing `data/` files are preserved and should not be deleted without a backup.
6. **One log file** (`gate_logs.json`) holds all movements; fine for this project, rotate it per month if it ever runs for long.

## Intern and guest-card management

At the gate, search by printed roster number, intern name, full ID, or the last three ID digits.
Roster numbers are optional and must be assigned to interns on the Interns page; exact roster-number
matches take precedence over ID suffix matches. Select the matching intern from the results before
acting; the app shows their roster number and whether they are inside, then offers the appropriate
check-in or check-out action. When a query matches multiple interns, choose the correct person.
The application uses the saved roster and gate records in `data/`.
`services/gate_contract.py` documents the typed interface used by the gate screen.

On first load, if no roster numbers are present, existing interns are assigned unique numbers starting
at 1 in alphabetical name order and the mapping is saved. Numbers stay fixed after that; they are not
renumbered when names or the roster change. The Interns page includes a registration dialog for intern
ID, optional roster number, name, department, and optional phone/email. Select an existing intern and
use "Set roster no." to assign, change, or clear their printed number. Roster numbers must be unique;
blank numbers remain unassigned.
The Cards page lists card status and holder, lets staff record a return, and confirms before marking an
issued card missing. On the Gate screen, "Check out" means the card was returned; use
"Check out · card not returned" when the intern leaves with the guest card. That card remains issued
and appears in unreturned-card reports.
AI questions run in a background thread so a slow Gemini response does not freeze the window.

The interface uses shared font-size tokens in `gui/theme.py`, CustomTkinter's display scaling, and
responsive layouts that switch navigation and tables to compact arrangements on narrower windows.
On Windows, CustomTkinter detects the monitor's DPI scale automatically; the app also sizes its
starting window to fit the available screen at that scale. Do not force a fixed widget or window
scaling value in the entry point. To run a GitHub copy on another computer, install the packages
from `requirements.txt` and start it with `python main.py`; the saved `data/` files are local to
each copy and are not required to launch the application.
The dashboard clock uses the computer's local time; weather is fetched separately from Open-Meteo.
