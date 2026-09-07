"""Unit tests for icon extraction, dark theme contrast adaptation, and executable resolution."""

import unittest
from PIL import Image

import app_utils


class IconContrastTests(unittest.TestCase):
    def test_dark_monochrome_transparent_icon_is_adapted(self):
        # Create a 48x48 image with dark gray monochrome pixels on transparent background (like Equibop)
        im = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        # Draw dark gray circle: (60, 60, 60, 255)
        for x in range(12, 36):
            for y in range(12, 36):
                im.putpixel((x, y), (60, 60, 60, 255))

        adapted = app_utils.adapt_icon_for_dark_theme(im)
        self.assertIsNotNone(adapted)
        # Verify the dark gray pixels were inverted to bright silver/white
        pixel = adapted.getpixel((20, 20))
        self.assertEqual(pixel, (195, 195, 195, 255))
        # Verify transparent pixels remain transparent
        bg = adapted.getpixel((0, 0))
        self.assertEqual(bg, (0, 0, 0, 0))

    def test_colored_transparent_icon_is_not_adapted(self):
        # Discord/Chrome style colored icon on transparent background
        im = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        for x in range(12, 36):
            for y in range(12, 36):
                im.putpixel((x, y), (88, 101, 242, 255)) # Discord blurple

        adapted = app_utils.adapt_icon_for_dark_theme(im)
        # Should remain unchanged because saturation is high
        pixel = adapted.getpixel((20, 20))
        self.assertEqual(pixel, (88, 101, 242, 255))

    def test_opaque_icon_is_not_adapted(self):
        # Fully opaque square icon (with its own plate/background)
        im = Image.new("RGBA", (48, 48), (40, 40, 40, 255))
        adapted = app_utils.adapt_icon_for_dark_theme(im)
        pixel = adapted.getpixel((20, 20))
        self.assertEqual(pixel, (40, 40, 40, 255))

    def test_bright_monochrome_transparent_icon_is_not_adapted(self):
        # White/bright icon on transparent background (like Cursor or Codex)
        im = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        for x in range(12, 36):
            for y in range(12, 36):
                im.putpixel((x, y), (240, 240, 240, 255))

        adapted = app_utils.adapt_icon_for_dark_theme(im)
        pixel = adapted.getpixel((20, 20))
        self.assertEqual(pixel, (240, 240, 240, 255))

    def test_prepare_icon_downscales_large_source(self):
        im = Image.new("RGBA", (256, 256), (10, 20, 30, 255))
        out = app_utils.prepare_icon_for_cache(im, 128)
        self.assertIsNotNone(out)
        self.assertEqual(out.size, (128, 128))
        self.assertEqual(out.getpixel((64, 64))[:3], (10, 20, 30))

    def test_prepare_icon_pads_non_square(self):
        im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        for x in range(200):
            for y in range(100):
                im.putpixel((x, y), (255, 0, 0, 255))
        out = app_utils.prepare_icon_for_cache(im, 128)
        self.assertEqual(out.size, (128, 128))
        # Transparent padding remains on the letterbox edges
        self.assertEqual(out.getpixel((64, 0))[3], 0)

    def test_prepare_icon_keeps_tiny_source_for_refetch(self):
        im = Image.new("RGBA", (48, 48), (1, 2, 3, 255))
        out = app_utils.prepare_icon_for_cache(im, 128)
        self.assertEqual(out.size, (48, 48))



    def test_find_exe_by_aumid_or_app_name(self):
        # Test known AUMID mapping for Equibop
        exe_by_name = app_utils.find_exe_for_app("equibop")
        exe_by_aumid = app_utils.find_exe_for_app("", aumid="org.equicord.equibop")
        if exe_by_name:
            self.assertTrue(exe_by_name.lower().endswith("equibop.exe"))
        if exe_by_aumid:
            self.assertTrue(exe_by_aumid.lower().endswith("equibop.exe"))


if __name__ == "__main__":
    unittest.main()
