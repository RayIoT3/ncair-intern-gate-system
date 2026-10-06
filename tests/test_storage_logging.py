import logging
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest import mock

from storage.file_storage import setup_logging


class StorageLoggingTests(unittest.TestCase):
    def test_logging_uses_a_bounded_rotating_file(self):
        logger = logging.getLogger("gate")
        with tempfile.TemporaryDirectory() as data_dir:
            with mock.patch.object(logger, "handlers", []):
                configured_logger = setup_logging(
                    Path(data_dir) / "gate_errors.log",
                    max_bytes=1024,
                    backup_count=2,
                )
                try:
                    self.assertEqual(len(configured_logger.handlers), 1)
                    handler = configured_logger.handlers[0]
                    self.assertIsInstance(handler, RotatingFileHandler)
                    self.assertEqual(handler.maxBytes, 1024)
                    self.assertEqual(handler.backupCount, 2)
                finally:
                    for handler in configured_logger.handlers:
                        handler.close()


if __name__ == "__main__":
    unittest.main()
