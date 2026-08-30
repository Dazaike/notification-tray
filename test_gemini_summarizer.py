"""Regression coverage for Gemini notification summarization."""

import io
import json
import queue
import unittest
from unittest.mock import MagicMock, patch

import gemini_summarizer
import manager


class GeminiSummarizerTests(unittest.TestCase):
    def test_word_threshold_is_strictly_above_twenty(self) -> None:
        self.assertFalse(gemini_summarizer.should_summarize("word " * 20))
        self.assertTrue(gemini_summarizer.should_summarize("word " * 21))

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True)
    @patch("gemini_summarizer.request.urlopen")
    def test_successful_request_uses_generate_content_and_returns_stripped_text(self, mock_urlopen) -> None:
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(
            b'{"candidates": [{"content": {"parts": [{"text": "  Approve $250 by 3 PM tomorrow.  "}]}}]}'
        )
        mock_urlopen.return_value = response

        summary = gemini_summarizer.summarize("Alex needs a travel expense approved before tomorrow afternoon.")

        self.assertEqual(summary, "Approve $250 by 3 PM tomorrow.")
        api_request = mock_urlopen.call_args.args[0]
        self.assertEqual(
            api_request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        )
        self.assertEqual(api_request.get_header("X-goog-api-key"), "test-key")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], gemini_summarizer.TIMEOUT_SECONDS)
        payload = json.loads(api_request.data.decode("utf-8"))
        self.assertEqual(payload["contents"][0]["parts"][0]["text"].split(": ", 1)[1],
                         "Alex needs a travel expense approved before tomorrow afternoon.")
        self.assertEqual(payload["generationConfig"], {
            "thinkingConfig": {"thinkingLevel": "low", "includeThoughts": False},
            "maxOutputTokens": 512,
        })

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True)
    @patch("gemini_summarizer.request.urlopen")
    def test_generate_content_response_returns_summary(self, mock_urlopen) -> None:
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(
            b'{"candidates": [{"content": {"parts": [{"text": "Approve $250 by 3 PM tomorrow."}]}}]}'
        )
        mock_urlopen.return_value = response

        self.assertEqual(
            gemini_summarizer.summarize("Alex needs a travel expense approved before tomorrow afternoon."),
            "Approve $250 by 3 PM tomorrow.",
        )

    @patch("gemini_summarizer.win32cred.CredWrite")
    def test_save_key_uses_windows_credential_manager(self, mock_credential_write) -> None:
        self.assertTrue(gemini_summarizer.save_api_key(" saved-key "))

        credential = mock_credential_write.call_args.args[0]
        self.assertEqual(credential["TargetName"], "NotificationTray/GeminiApiKey")
        self.assertEqual(credential["CredentialBlob"], "saved-key")
        self.assertEqual(credential["Type"], gemini_summarizer.win32cred.CRED_TYPE_GENERIC)


    @patch("gemini_summarizer.win32cred.CredRead")
    def test_stored_api_key_removes_windows_credential_null_padding(self, mock_credential_read) -> None:
        mock_credential_read.return_value = {"CredentialBlob": "A\x00I\x00z\x00a\x00"}

        self.assertEqual(gemini_summarizer.get_stored_api_key(), "AIza")
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_key_returns_none_without_request(self) -> None:
        with patch("gemini_summarizer._get_stored_api_key", return_value=""), \
                patch("gemini_summarizer.request.urlopen") as mock_urlopen:
            self.assertFalse(gemini_summarizer.is_configured())
            self.assertIsNone(gemini_summarizer.summarize("A message"))
            mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True)
    @patch("gemini_summarizer.request.urlopen", side_effect=TimeoutError("timeout"))
    def test_network_failure_returns_none(self, mock_urlopen) -> None:
        self.assertIsNone(gemini_summarizer.summarize("A message"))
        mock_urlopen.assert_called_once()

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True)
    @patch("gemini_summarizer.request.urlopen")
    def test_malformed_response_and_blank_output_return_none(self, mock_urlopen) -> None:
        malformed_response = MagicMock()
        malformed_response.__enter__.return_value = io.BytesIO(b"not json")
        mock_urlopen.return_value = malformed_response
        self.assertIsNone(gemini_summarizer.summarize("A message"))

        blank_response = MagicMock()
        blank_response.__enter__.return_value = io.BytesIO(b'{"output_text": "  "}')
        mock_urlopen.return_value = blank_response
        self.assertIsNone(gemini_summarizer.summarize("A message"))


class _ImmediateThread:
    def __init__(self, *, target, args, daemon) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


class NotificationManagerSummaryDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notification_manager = manager.NotificationManager.__new__(manager.NotificationManager)
        self.notification_manager.queue = queue.Queue()
        self.message = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty one"
        self.notification_manager.gemini_enabled = True
        self.metadata = {
            "title": "Expense approval",
            "kind": "warning",
            "aumid": "contoso.app",
            "icon_path": "C:/icon.ico",
            "app_name": "Contoso",
            "launch_url": "contoso://expense/250",
            "toast_tag": "expense-250",
        }

    @patch("manager.threading.Thread", _ImmediateThread)
    @patch("manager.gemini_summarizer.summarize", return_value="Approve $250 by 3 PM tomorrow.")
    @patch("manager.gemini_summarizer.should_summarize", return_value=True)
    @patch("manager.gemini_summarizer.is_configured", return_value=True)
    def test_qualifying_notification_waits_for_summary_then_enqueues_it(
        self, _configured, _qualifies, _summarize
    ) -> None:
        self.notification_manager.notify(self.message, **self.metadata)

        self.assertEqual(
            self.notification_manager.queue.get_nowait(),
            ("Approve $250 by 3 PM tomorrow.", *self.metadata.values()),
        )

    @patch("manager.threading.Thread", _ImmediateThread)
    @patch("manager.gemini_summarizer.summarize", return_value=None)
    @patch("manager.gemini_summarizer.should_summarize", return_value=True)
    @patch("manager.gemini_summarizer.is_configured", return_value=True)
    def test_failed_summary_enqueues_original_body(self, _configured, _qualifies, _summarize) -> None:
        self.notification_manager.notify(self.message, **self.metadata)

        self.assertEqual(
            self.notification_manager.queue.get_nowait(),
            (self.message, *self.metadata.values()),
        )

    @patch("manager.gemini_summarizer.is_configured", return_value=False)
    def test_unconfigured_api_enqueues_original_body_immediately(self, _configured) -> None:
        self.notification_manager.notify(self.message, **self.metadata)

        self.assertEqual(
            self.notification_manager.queue.get_nowait(),
            (self.message, *self.metadata.values()),
        )

    @patch("manager.gemini_summarizer.is_configured")
    def test_disabled_summaries_enqueue_original_body_immediately(self, mock_configured) -> None:
        self.notification_manager.gemini_enabled = False
        self.notification_manager.notify(self.message, **self.metadata)

        self.assertEqual(
            self.notification_manager.queue.get_nowait(),
            (self.message, *self.metadata.values()),
        )
        mock_configured.assert_not_called()

    @patch("manager.gemini_summarizer.is_configured")
    def test_short_notification_bypasses_api_key_lookup(self, mock_configured) -> None:
        short_message = "word " * 20
        self.notification_manager.notify(short_message, **self.metadata)

        self.assertEqual(
            self.notification_manager.queue.get_nowait(),
            (short_message, *self.metadata.values()),
        )
        mock_configured.assert_not_called()


if __name__ == "__main__":
    unittest.main()
