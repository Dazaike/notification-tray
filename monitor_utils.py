"""Monitor detection, isolated from the rest of the codebase."""

import sys
import threading
import time
from dataclasses import dataclass


# Cache monitor layout so every toast notification doesn't re-query the
# display stack (screeninfo can be slow or hang on some systems).
_MONITOR_CACHE = None
_MONITOR_CACHE_TIME = 0.0
_MONITOR_CACHE_TTL = 2.0  # seconds


@dataclass
class MonitorRect:
    x: int
    y: int
    width: int
    height: int
    handle: int = 0
    device: str = ""
    primary: bool = False


def _from_screeninfo():
    """Query screeninfo with a short timeout to avoid blocking the UI.

    Uses a bare daemon thread rather than ThreadPoolExecutor: a
    ThreadPoolExecutor (even via `with`, even after future.result() times
    out) joins its worker on shutdown, and is itself joined again at
    interpreter exit. If screeninfo ever hangs (sleep/wake, display change,
    RDP), that join blocks forever — freezing the whole UI thread (every
    toast calls this) and later vetoing process shutdown. A daemon thread
    can simply be abandoned when it doesn't finish in time.
    """
    try:
        from screeninfo import get_monitors
    except Exception:
        return []

    result = {}

    def worker():
        try:
            result["monitors"] = get_monitors()
        except Exception:
            result["monitors"] = []

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=2.0)
    if thread.is_alive():
        return []  # screeninfo is hung; abandon it and fall back

    raw = result.get("monitors") or []
    return [MonitorRect(m.x, m.y, m.width, m.height) for m in raw]


def _from_win32():
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        monitors = []

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(wintypes.RECT),
            ctypes.c_double,
        )

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", ctypes.c_wchar * 32),
            ]

        MONITORINFOF_PRIMARY = 0x1

        def callback(hmonitor, hdc, rect, data):
            r = rect.contents
            device = ""
            primary = False
            # EnumDisplayMonitors hands back handles in an arbitrary order and
            # tells us nothing about identity, so ask for the stable device
            # name (\\.\DISPLAYn) and the primary flag here.
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if ctypes.windll.user32.GetMonitorInfoW(int(hmonitor), ctypes.byref(info)):
                device = info.szDevice
                primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            monitors.append(MonitorRect(r.left, r.top, r.right - r.left, r.bottom - r.top,
                                        int(hmonitor), device, primary))
            return 1

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(callback), 0)
        return monitors
    except Exception:
        return []




def invalidate_monitor_cache():
    """Drop the cached layout (e.g. after the user picks a different monitor)."""
    global _MONITOR_CACHE, _MONITOR_CACHE_TIME
    _MONITOR_CACHE = None
    _MONITOR_CACHE_TIME = 0.0


def get_all_monitors():
    """Return a list of MonitorRect for every detected monitor.

    Falls back through Win32 EnumDisplayMonitors -> screeninfo -> hardcoded
    1920x1080 fallback so this always returns at least one entry.

    Results are cached briefly; this is called on every toast restack, so
    we avoid repeatedly querying the (sometimes slow) display APIs.

    On Windows we prefer the Win32 API directly: screeninfo can hang for
    seconds on sleep/wake or display changes, and the old code joined that
    lookup for up to 2 s on whatever thread called us — usually Tk's main
    loop — which froze every toast and made the tray menu feel dead.
    """
    global _MONITOR_CACHE, _MONITOR_CACHE_TIME

    now = time.monotonic()
    if _MONITOR_CACHE is not None and now - _MONITOR_CACHE_TIME < _MONITOR_CACHE_TTL:
        return _MONITOR_CACHE

    if sys.platform == "win32":
        monitors = _from_win32()
        if not monitors:
            monitors = _from_screeninfo()
    else:
        monitors = _from_screeninfo()
    if not monitors:
        monitors = [MonitorRect(0, 0, 1920, 1080)]

    # EnumDisplayMonitors order is explicitly undefined, so a bare index is
    # not a stable way to name a display. Sort primary-first, then
    # left-to-right, so index 0 is always the display the user is looking at.
    monitors.sort(key=lambda m: (not m.primary, m.x, m.y))

    _MONITOR_CACHE = monitors
    _MONITOR_CACHE_TIME = now
    return monitors


def get_monitor_rect(index: int) -> MonitorRect:
    """Return the MonitorRect for `index`, clamping out-of-range indices."""
    monitors = get_all_monitors()
    if index < 0:
        index = 0
    if index >= len(monitors):
        # Primary, not the last monitor: falling back to the far end of the
        # desktop is how a stale index parks toasts on an unwatched screen.
        index = 0
    return monitors[index]


def device_for_index(index: int) -> str:
    r"""Stable device name (e.g. \\.\DISPLAY2) for a monitor index, or ""."""
    return get_monitor_rect(index).device


def resolve_monitor_index(device: str) -> int:
    """Index of the monitor with this device name; 0 (primary) when unknown."""
    if not device:
        return 0
    for i, mon in enumerate(get_all_monitors()):
        if mon.device == device:
            return i
    return 0


def get_monitor_scale(index: int) -> float:
    """Effective scale factor (1.0 == 96 DPI) of monitor `index`."""
    if sys.platform != "win32":
        return 1.0
    rect = get_monitor_rect(index)
    try:
        import ctypes
        if rect.handle:
            dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
            if ctypes.windll.shcore.GetDpiForMonitor(rect.handle, 0,
                                                    ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                return dpi_x.value / 96.0
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0
