import unittest
from pathlib import Path
import tempfile
import config
from manager import NotificationManager


class TestAnimationSettings(unittest.TestCase):
    def setUp(self):
        self._orig_config_path = config.CONFIG_PATH
        self._tmp_dir = tempfile.TemporaryDirectory()
        config.CONFIG_PATH = Path(self._tmp_dir.name) / "test_config.json"

    def tearDown(self):
        config.CONFIG_PATH = self._orig_config_path
        self._tmp_dir.cleanup()

    def test_default_animation_settings(self):
        mgr = NotificationManager()
        settings = mgr.to_settings_dict()

        self.assertEqual(settings["animation_preset"], "default")
        self.assertEqual(settings["anim_incoming"], "soft-slide")
        self.assertEqual(settings["anim_outgoing"], "slide-away")
        self.assertEqual(settings["anim_direction"], "auto")
        self.assertEqual(settings["anim_duration"], 350)
        self.assertEqual(settings["anim_easing"], "spring")
        self.assertEqual(settings["anim_distance"], 400)
        self.assertAlmostEqual(settings["anim_bounce"], 0.3)
        self.assertEqual(settings["anim_blur"], 12)
        self.assertAlmostEqual(settings["anim_scale"], 0.9)

    def test_set_animation_setting_bounds_and_values(self):
        mgr = NotificationManager()

        # Preset & Effects
        self.assertTrue(mgr.set_animation_setting("animation_preset", "glass"))
        self.assertEqual(mgr.animation_preset, "glass")

        self.assertTrue(mgr.set_animation_setting("anim_incoming", "blur-in"))
        self.assertEqual(mgr.anim_incoming, "blur-in")

        self.assertTrue(mgr.set_animation_setting("anim_outgoing", "blur-away"))
        self.assertEqual(mgr.anim_outgoing, "blur-away")

        self.assertTrue(mgr.set_animation_setting("anim_direction", "top"))
        self.assertEqual(mgr.anim_direction, "top")

        self.assertTrue(mgr.set_animation_setting("anim_easing", "ease-out"))
        self.assertEqual(mgr.anim_easing, "ease-out")

        # Clamping
        mgr.set_animation_setting("anim_duration", 10)  # clamped to min 50
        self.assertEqual(mgr.anim_duration, 50)
        mgr.set_animation_setting("anim_duration", 5000)  # clamped to max 3000
        self.assertEqual(mgr.anim_duration, 3000)

        mgr.set_animation_setting("anim_distance", 5)  # clamped to min 10
        self.assertEqual(mgr.anim_distance, 10)
        mgr.set_animation_setting("anim_distance", 3000)  # clamped to max 2000
        self.assertEqual(mgr.anim_distance, 2000)

        mgr.set_animation_setting("anim_bounce", -0.5)  # clamped to 0.0
        self.assertEqual(mgr.anim_bounce, 0.0)
        mgr.set_animation_setting("anim_bounce", 1.8)  # clamped to 1.0
        self.assertEqual(mgr.anim_bounce, 1.0)

        mgr.set_animation_setting("anim_blur", -5)  # clamped to 0
        self.assertEqual(mgr.anim_blur, 0)
        mgr.set_animation_setting("anim_blur", 90)  # clamped to 50
        self.assertEqual(mgr.anim_blur, 50)

        mgr.set_animation_setting("anim_scale", 0.01)  # clamped to 0.1
        self.assertAlmostEqual(mgr.anim_scale, 0.1)
        mgr.set_animation_setting("anim_scale", 4.0)  # clamped to 2.0
        self.assertAlmostEqual(mgr.anim_scale, 2.0)

        # Unknown setting
        self.assertFalse(mgr.set_animation_setting("invalid_setting", 123))

    def test_settings_dict_reflects_changes(self):
        mgr = NotificationManager()
        mgr.set_animation_setting("animation_preset", "spring")
        mgr.set_animation_setting("anim_incoming", "spring")
        mgr.set_animation_setting("anim_outgoing", "accelerate")
        mgr.set_animation_setting("anim_duration", 420)

        d = mgr.to_settings_dict()
        self.assertEqual(d["animation_preset"], "spring")
        self.assertEqual(d["anim_incoming"], "spring")
        self.assertEqual(d["anim_outgoing"], "accelerate")
        self.assertEqual(d["anim_duration"], 420)

    def test_custom_sound_path_setting(self):
        mgr = NotificationManager()
        self.assertEqual(mgr.custom_sound_path, "")
        # Invalid file non-existent
        self.assertFalse(mgr.set_custom_sound_path("C:/nonexistent/file.mp3"))
        # Reset to empty is valid
        self.assertTrue(mgr.set_custom_sound_path(""))
        self.assertEqual(mgr.custom_sound_path, "")
        # Test with an actual file (e.g. fears-to-fathom-notification.mp3)
        actual_file = str(Path(__file__).resolve().parent / "fears-to-fathom-notification.mp3")
        self.assertTrue(mgr.set_custom_sound_path(actual_file))
        self.assertEqual(mgr.custom_sound_path, actual_file)
        self.assertEqual(mgr.to_settings_dict()["custom_sound_path"], actual_file)

    def test_sound_cooldown_config_present(self):
        self.assertTrue(hasattr(config, "SOUND_COOLDOWN_MS"))
        self.assertGreater(config.SOUND_COOLDOWN_MS, 0)

    def test_tray_click_action_setting(self):
        mgr = NotificationManager()
        self.assertEqual(mgr.tray_click_action, "center")
        self.assertEqual(mgr.to_settings_dict()["tray_click_action"], "center")

        self.assertTrue(mgr.set_tray_click_action("panel"))
        self.assertEqual(mgr.tray_click_action, "panel")
        self.assertEqual(mgr.to_settings_dict()["tray_click_action"], "panel")

        # Persistence test
        mgr2 = NotificationManager()
        self.assertEqual(mgr2.tray_click_action, "panel")

        self.assertTrue(mgr2.set_tray_click_action("center"))
        self.assertEqual(mgr2.tray_click_action, "center")

        # Normalization of settings -> panel
        self.assertTrue(mgr2.set_tray_click_action("settings"))
        self.assertEqual(mgr2.tray_click_action, "panel")


if __name__ == "__main__":
    unittest.main()
