"""Regression coverage for monitor ordering and device-name resolution.

Toasts were rendering off-screen because get_all_monitors() returned displays in
raw EnumDisplayMonitors order, which is undefined: index 1 (the shipped default)
resolved to a non-primary display at x=-1920. Index 0 must always be the primary.
"""

import unittest

import monitor_utils
from monitor_utils import (MonitorRect, device_for_index, get_all_monitors,
                           get_monitor_rect, invalidate_monitor_cache,
                           resolve_monitor_index)


# The real layout on the reporting machine, deliberately scrambled: the primary
# is enumerated last and the leftmost display first.
_SCRAMBLED = [
    MonitorRect(-1920, 0, 1920, 1080, 131073, r"\\.\DISPLAY1", False),
    MonitorRect(1920, 65, 1600, 900, 65695, r"\\.\DISPLAY3", False),
    MonitorRect(0, 0, 1920, 1080, 65693, r"\\.\DISPLAY2", True),
]


class MonitorOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._real_win32 = monitor_utils._from_win32
        self._real_screeninfo = monitor_utils._from_screeninfo
        monitor_utils._from_win32 = lambda: list(_SCRAMBLED)
        monitor_utils._from_screeninfo = lambda: list(_SCRAMBLED)
        invalidate_monitor_cache()

    def tearDown(self) -> None:
        monitor_utils._from_win32 = self._real_win32
        monitor_utils._from_screeninfo = self._real_screeninfo
        invalidate_monitor_cache()

    def test_primary_sorts_first_then_left_to_right(self):
        devices = [m.device for m in get_all_monitors()]
        self.assertEqual(devices, [r"\\.\DISPLAY2", r"\\.\DISPLAY1", r"\\.\DISPLAY3"])

    def test_index_zero_is_the_primary_display(self):
        self.assertEqual(get_monitor_rect(0).x, 0)
        self.assertTrue(get_monitor_rect(0).primary)

    def test_out_of_range_index_falls_back_to_primary(self):
        # Previously clamped to len-1, parking toasts on the far display.
        self.assertEqual(get_monitor_rect(7).x, 0)
        self.assertEqual(get_monitor_rect(-3).x, 0)

    def test_device_round_trips_through_index(self):
        self.assertEqual(device_for_index(0), r"\\.\DISPLAY2")
        self.assertEqual(resolve_monitor_index(r"\\.\DISPLAY3"), 2)
        self.assertEqual(resolve_monitor_index(r"\\.\DISPLAY1"), 1)

    def test_unknown_or_empty_device_resolves_to_primary(self):
        self.assertEqual(resolve_monitor_index(r"\\.\DISPLAY9"), 0)
        self.assertEqual(resolve_monitor_index(""), 0)

    def test_right_edge_placement_lands_on_the_primary(self):
        # The exact arithmetic _restack() performs for position == "right".
        rect = get_monitor_rect(0)
        self.assertEqual(rect.x + rect.width - 400 - 24, 1496)


if __name__ == "__main__":
    unittest.main()
