"""JSON file storage: one agreed format for the whole project (a list of record dicts per file).

* Writes are atomic (temp file, then rename) so a crash cannot leave half a file.
* A missing file is reported as None so the caller can create it from defaults.
* A corrupted file is moved aside to `<name>.corrupt-<time>` (never deleted), a warning is
  recorded, and None is returned so the app starts from defaults instead of crashing.
* OS-level failures (disk full, permissions) raise StorageError.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

import config
from exceptions.custom_exceptions import StorageError

log = logging.getLogger("gate")


def setup_logging(log_path, max_bytes=1_048_576, backup_count=3):
    """Write gate logs to a rotating file (falls back to stderr if it cannot be opened)."""
    logger = logging.getLogger("gate")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class FileStorage:
    def __init__(self, data_dir=config.DATA_DIR):
        self.data_dir = Path(data_dir)
        self.warnings = []          # human-readable notes the GUI can show at start-up
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Cannot create the data folder {self.data_dir}: {e}") from e

    def warn(self, message):
        log.warning(message)
        self.warnings.append(message)

    # ---- generic ---------------------------------------------------------
    def load_records(self, name):
        path = self.data_dir / name
        if not path.exists():
            log.info("%s not found; it will be created.", name)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._quarantine(path)
            return None
        except OSError as e:
            raise StorageError(f"Cannot read {name}: {e}") from e
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            self._quarantine(path)
            return None
        return data

    def save_records(self, name, records):
        path = self.data_dir / name
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except (OSError, TypeError, ValueError) as e:
            log.error("Could not save %s: %s", name, e)
            raise StorageError(f"Could not save {name}: {e}") from e

    def _quarantine(self, path):
        backup = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            path.replace(backup)
            note = f"{path.name} was corrupted. It was moved to {backup.name} and rebuilt from defaults."
        except OSError:
            note = f"{path.name} was corrupted and could not be moved aside. It was rebuilt from defaults."
        self.warn(note)

    # ---- named helpers used by the services ------------------------------
    def load_interns(self):
        return self.load_records(config.INTERNS_FILE)

    def save_interns(self, records):
        self.save_records(config.INTERNS_FILE, records)

    def load_cards(self):
        return self.load_records(config.CARDS_FILE)

    def save_cards(self, records):
        self.save_records(config.CARDS_FILE, records)

    def load_gate_logs(self):
        return self.load_records(config.LOGS_FILE)

    def save_gate_logs(self, records):
        self.save_records(config.LOGS_FILE, records)
