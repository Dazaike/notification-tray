"""Regression coverage for Beeper renderer-log deep-link capture."""

import tempfile
import unittest
from pathlib import Path

import beeper_deeplink


_VALID_LINE = (
    "[sendNotification] threadID=thread-123 sourceThreadID=source-123 "
    "accountID=account/example platform.name=bridge-whatsapp"
)
_EXPECTED_DEEPLINK = (
    "beeper://select-thread/whatsapp/thread-123?accountID=account%2Fexample"
)


class BeeperDeeplinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_thread = beeper_deeplink._LOG_THREAD
        with beeper_deeplink._LOCK:
            beeper_deeplink._RECENT.clear()
            beeper_deeplink._LOG_THREAD = None
        beeper_deeplink._LOG_STOP.clear()

    def tearDown(self) -> None:
        with beeper_deeplink._LOCK:
            beeper_deeplink._RECENT.clear()
            beeper_deeplink._LOG_THREAD = self._old_thread
        beeper_deeplink._LOG_STOP.clear()

    def test_live_line_records_its_deeplink(self) -> None:
        entry = beeper_deeplink._process_log_line(_VALID_LINE)

        self.assertIsNotNone(entry)
        self.assertEqual(entry.deeplink, _EXPECTED_DEEPLINK)
        self.assertEqual(beeper_deeplink._RECENT[0].deeplink, _EXPECTED_DEEPLINK)

    def test_history_seed_records_the_deeplink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "renderer-1.log"
            log_path.write_text(f"{_VALID_LINE}\n", encoding="utf-8")
            beeper_deeplink._seed_recent_from_log(log_path)

        self.assertEqual(beeper_deeplink._RECENT[0].deeplink, _EXPECTED_DEEPLINK)

    def test_malformed_line_records_nothing(self) -> None:
        entry = beeper_deeplink._process_log_line("[sendNotification] broken")

        self.assertIsNone(entry)
        self.assertEqual(list(beeper_deeplink._RECENT), [])


if __name__ == "__main__":
    unittest.main()
