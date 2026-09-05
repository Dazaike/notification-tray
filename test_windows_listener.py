"""Unit tests for Windows notification extraction and error resilience."""

import unittest
from unittest.mock import MagicMock, PropertyMock

import windows_listener


class WindowsListenerExtractionTests(unittest.TestCase):
    def test_extract_app_info_unpackaged_raises_oserror(self):
        # Simulates E_NOTIMPL on app_info attribute access
        notif = MagicMock()
        type(notif).app_info = PropertyMock(side_effect=OSError(-2147467263, "Not implemented"))

        app_name, aumid, app_info = windows_listener.extract_app_info(notif)
        self.assertEqual(app_name, "Windows")
        self.assertEqual(aumid, "")
        self.assertIsNone(app_info)

    def test_extract_app_info_normal_packaged_app(self):
        notif = MagicMock()
        disp = MagicMock()
        disp.display_name = "Discord"
        notif.app_info.display_info = disp
        notif.app_info.app_user_model_id = "com.squirrel.discord.discord"

        app_name, aumid, app_info = windows_listener.extract_app_info(notif)
        self.assertEqual(app_name, "Discord")
        self.assertEqual(aumid, "com.squirrel.discord.discord")
        self.assertIsNotNone(app_info)

    def test_extract_app_info_aumid_fallback_when_display_name_empty(self):
        notif = MagicMock()
        disp = MagicMock()
        disp.display_name = ""
        notif.app_info.display_info = disp
        notif.app_info.app_user_model_id = "com.automattic.beeper.desktop"

        app_name, aumid, app_info = windows_listener.extract_app_info(notif)
        self.assertEqual(app_name, "Desktop")
        self.assertEqual(aumid, "com.automattic.beeper.desktop")

    def test_format_notification_texts_empty(self):
        title, message = windows_listener.format_notification_texts([], app_name="Beeper")
        self.assertEqual(title, "Beeper")
        self.assertEqual(message, "")

    def test_format_notification_texts_single(self):
        title, message = windows_listener.format_notification_texts(["Alert message"], app_name="System")
        self.assertEqual(title, "Alert message")
        self.assertEqual(message, "Alert message")

    def test_format_notification_texts_multi(self):
        title, message = windows_listener.format_notification_texts(["Alice", "Hey there!", "Are you free?"], app_name="Chat")
        self.assertEqual(title, "Alice")
        self.assertEqual(message, "Hey there! — Are you free?")

    def test_extract_texts_generic_binding(self):
        notif = MagicMock()
        elem1 = MagicMock()
        elem1.text = "Notification Title"
        elem2 = MagicMock()
        elem2.text = "Notification Body"

        elements = MagicMock()
        elements.size = 2
        elements.get_at.side_effect = lambda i: [elem1, elem2][i]

        binding = MagicMock()
        binding.get_text_elements.return_value = elements
        notif.notification.visual.get_binding.return_value = binding

        texts = windows_listener.extract_texts(notif)
        self.assertEqual(texts, ["Notification Title", "Notification Body"])

    def test_extract_texts_fallback_to_bindings_list(self):
        notif = MagicMock()
        notif.notification.visual.get_binding.return_value = None

        elem = MagicMock()
        elem.text = "Fallback Text"
        elements = MagicMock()
        elements.size = 1
        elements.get_at.side_effect = lambda i: [elem][i]

        binding = MagicMock()
        binding.get_text_elements.return_value = elements

        bindings_list = MagicMock()
        bindings_list.size = 1
        bindings_list.get_at.return_value = binding
        notif.notification.visual.bindings = bindings_list

        texts = windows_listener.extract_texts(notif)
        self.assertEqual(texts, ["Fallback Text"])


if __name__ == "__main__":
    unittest.main()
