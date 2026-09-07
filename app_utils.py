"""Helpers for identifying an application from its .exe path."""

import time
from pathlib import Path

_FG_CACHE = ("", 0.0)
# AUMID -> process filename stem(s) for focusing an already-running app.
_AUMID_EXE_STEMS = {
    "anysphere.cursor": ("cursor",),
    "com.automattic.beeper.desktop": ("beeper",),
    "com.squirrel.discord.discord": ("discord",),
    "org.equicord.equibop": ("equibop",),
    "microsoft.windowscommunicationsapps_8wekyb3d8bbwe": ("hxoutlook", "olk", "outlook"),
}


def find_exe_for_app(app_name: str, aumid: str = ""):
    """Best-effort: find the executable path of a running or installed app.
    Used as an icon fallback for win32 apps that don't expose a logo via toast API."""
    if not app_name and not aumid:
        return None
    target = (app_name or "").strip().lower()
    aumid_target = (aumid or "").strip().lower()

    # 1. Check known AUMID stems
    for aumid_key, stems in _AUMID_EXE_STEMS.items():
        matched = False
        if aumid_target and (aumid_target in aumid_key or aumid_key in aumid_target):
            matched = True
        elif target and (target in aumid_key or any(target == s or s in target for s in stems)):
            matched = True
        if matched:
            for stem in stems:
                # Check running processes first
                try:
                    import win32com.client
                    wmi = win32com.client.GetObject("winmgmts:")
                    for proc in wmi.InstancesOf("Win32_Process"):
                        path = proc.ExecutablePath
                        if path and Path(path).stem.lower() == stem:
                            return path
                except Exception:
                    pass

    # 2. Check running processes via WMI
    targets_to_check = [t for t in (target, aumid_target.split(".")[-1] if aumid_target else "") if t]
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        for proc in wmi.InstancesOf("Win32_Process"):
            path = proc.ExecutablePath
            if not path:
                continue
            stem = Path(path).stem.lower()
            for t in targets_to_check:
                if stem and (stem == t or stem in t or t in stem):
                    return path
            display = get_exe_display_name(path).lower()
            for t in targets_to_check:
                if display and (display == t or display in t or t in display):
                    return path
    except Exception:
        pass

    # 3. Check Windows App Paths in Registry
    try:
        import winreg
        for t in targets_to_check:
            for hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for ext in ("", ".exe"):
                    try:
                        with winreg.OpenKey(hkey, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{t}{ext}") as key:
                            val, _ = winreg.QueryValueEx(key, "")
                            if val and Path(val).is_file():
                                return val
                    except OSError:
                        pass
    except Exception:
        pass

    return None


def adapt_icon_for_dark_theme(im):
    """If an icon is dark monochrome on a transparent background, adapt its colors
    (invert/brighten) so it is crisp and clearly visible on dark theme backgrounds."""
    if im is None:
        return None
    try:
        from PIL import Image

        if im.mode != "RGBA":
            im = im.convert("RGBA")

        alpha_extrema = im.getextrema()[3]
        # If fully opaque, icon has its own background plate/canvas
        if alpha_extrema[0] >= 250:
            return im

        pixels = list(im.getdata())
        visible = [px for px in pixels if px[3] > 32]
        if not visible:
            return im

        max_lum = max(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in visible)
        max_sat = max(max(r, g, b) - min(r, g, b) for r, g, b, a in visible)

        # If brightest pixel is dark mid-gray/black and color saturation is low,
        # it is a dark monochrome silhouette designed for light backgrounds.
        if max_lum < 140 and max_sat < 40:
            new_pixels = []
            for r, g, b, a in pixels:
                if a <= 8:
                    new_pixels.append((0, 0, 0, 0))
                else:
                    new_pixels.append((255 - r, 255 - g, 255 - b, a))
            adapted = Image.new("RGBA", im.size)
            adapted.putdata(new_pixels)
            return adapted
        return im
    except Exception:
        return im

def prepare_icon_for_cache(im, size: int = 128):
    """Normalize an icon to a square RGBA PNG-ready image at `size` px.

    Pads non-square sources, downscales with LANCZOS when larger, and leaves
    smaller sources alone (caller should re-fetch those when possible).
    Applies dark-theme contrast adaptation last.
    """
    if im is None:
        return None
    try:
        from PIL import Image

        im = im.convert("RGBA")
        w, h = im.size
        if w != h:
            side = max(w, h)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
            im = canvas
        if im.size[0] > size:
            im = im.resize((size, size), Image.Resampling.LANCZOS)
        elif im.size[0] < size and im.size[0] >= size * 0.75:
            # Near-target sources (e.g. 100–127) snap cleanly; tiny sources
            # stay as-is so callers can detect undersize and re-fetch.
            im = im.resize((size, size), Image.Resampling.LANCZOS)
        return adapt_icon_for_dark_theme(im)
    except Exception:
        return adapt_icon_for_dark_theme(im) if im is not None else None



def extract_exe_icon(exe_path: str, size: int = 128):
    """Best-effort: extract the embedded icon from an .exe as a PIL Image,
    resized to (size, size). Returns None on failure."""
    try:
        import ctypes
        from ctypes import wintypes
        import win32gui
        import win32ui
        from PIL import Image

        user32 = ctypes.windll.user32
        hicons = (wintypes.HICON * 1)()
        icon_ids = (wintypes.UINT * 1)()
        hicon = None

        # Try PrivateExtractIconsW first to get the highest resolution icon available (e.g. 256x256)
        for target_dim in (256, 128, 64, size):
            try:
                res = user32.PrivateExtractIconsW(exe_path, 0, target_dim, target_dim, hicons, icon_ids, 1, 0)
                if res > 0 and hicons[0]:
                    hicon = hicons[0]
                    break
            except Exception:
                pass

        handles_to_destroy = []
        if hicon:
            handles_to_destroy.append(hicon)
        else:
            large, small = win32gui.ExtractIconEx(exe_path, 0, 1)
            handles = (large or []) + (small or [])
            if not handles:
                return None
            hicon = handles[0]
            handles_to_destroy.extend(handles)

        info = win32gui.GetIconInfo(hicon)
        hbm_mask, hbm_color = info[3], info[4]

        bmp = win32ui.CreateBitmapFromHandle(hbm_color)
        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)
        w, h = bmpinfo["bmWidth"], bmpinfo["bmHeight"]
        img = Image.frombuffer("RGBA", (w, h), bmpstr, "raw", "BGRA", 0, 1)

        if img.getextrema()[3] == (0, 0):
            img.putalpha(255)

        for handle in handles_to_destroy:
            try:
                user32.DestroyIcon(handle)
            except Exception:
                try:
                    win32gui.DestroyIcon(handle)
                except Exception:
                    pass
        try:
            win32gui.DeleteObject(hbm_mask)
            win32gui.DeleteObject(hbm_color)
        except Exception:
            pass

        resized = img.resize((size, size), Image.LANCZOS)
        return adapt_icon_for_dark_theme(resized)
    except Exception:
        return None


def get_foreground_exe_stem() -> str:
    """Best-effort: lowercase filename stem of the foreground window's
    process .exe, used to detect when the user is already looking at the
    app that's sending a notification. Returns "" on failure. Memoized with 250ms TTL."""
    global _FG_CACHE
    now = time.monotonic()
    if now - _FG_CACHE[1] < 0.25:
        return _FG_CACHE[0]
    try:
        import win32gui
        import win32process
        import win32api
        import win32con

        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            path = win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
        stem = Path(path).stem.lower()
        _FG_CACHE = (stem, now)
        return stem
    except Exception:
        _FG_CACHE = ("", now)
        return ""

def get_exe_display_name(path: str) -> str:
    """Best-effort human-readable name for an .exe, used to match it
    against the app name reported by Windows notifications."""
    try:
        import win32api

        info = win32api.GetFileVersionInfo(path, "\\")
        lang, codepage = win32api.GetFileVersionInfo(path, "\\VarFileInfo\\Translation")[0]
        str_info = "\\StringFileInfo\\%04X%04X\\%s"

        for key in ("FileDescription", "ProductName"):
            try:
                value = win32api.GetFileVersionInfo(path, str_info % (lang, codepage, key))
                if value:
                    return value.strip()
            except Exception:
                continue
    except Exception:
        pass

    return Path(path).stem


def _exe_stems_for_app(aumid: str = "", app_name: str = "") -> set[str]:
    stems: set[str] = set()
    key = (aumid or "").strip().lower()
    if key in _AUMID_EXE_STEMS:
        stems.update(_AUMID_EXE_STEMS[key])
    if app_name:
        name = app_name.strip().lower()
        stems.add(name.replace(" ", ""))
        if " " in name:
            stems.add(name.split()[0])
    return {s for s in stems if s}


def _flash_window(hwnd) -> None:
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        info = FLASHWINFO(
            ctypes.sizeof(FLASHWINFO),
            hwnd,
            0x00000003 | 0x0000000C,  # FLASHW_ALL | FLASHW_TIMERNOFG
            2,
            0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def _force_foreground(hwnd) -> bool:
    try:
        import ctypes
        import win32con
        import win32gui
        import win32process

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        _flash_window(hwnd)
        fg = win32gui.GetForegroundWindow()
        if fg == hwnd:
            return True
        fg_thread = win32process.GetWindowThreadProcessId(fg)[0]
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
        if fg_thread != target_thread:
            win32process.AttachThreadInput(fg_thread, target_thread, True)
        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        finally:
            if fg_thread != target_thread:
                win32process.AttachThreadInput(fg_thread, target_thread, False)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        try:
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def focus_running_app(aumid: str = "", app_name: str = "", source_hwnd=None) -> bool:
    """Bring an already-running app's main window to the foreground.

    Used when a toast has no deep link (or COM activation is unavailable) and
    ``shell:AppsFolder`` would spawn a duplicate window — e.g. Cursor agent-done
    notifications.
    """
    stems = _exe_stems_for_app(aumid, app_name)
    if not stems:
        return False
    try:
        import ctypes
        import win32api
        import win32con
        import win32gui
        import win32process
    except ImportError:
        return False

    if source_hwnd:
        try:
            _, pid = win32process.GetWindowThreadProcessId(int(source_hwnd))
            ctypes.windll.user32.AllowSetForegroundWindow(pid)
        except Exception:
            pass

    candidates: list[tuple[int, int]] = []

    def _pid_exe_stem(pid: int) -> str:
        try:
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                path = win32process.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
            return Path(path).stem.lower()
        except Exception:
            return ""

    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        stem = _pid_exe_stem(pid)
        if stem not in stems:
            display = ""
            try:
                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                try:
                    path = win32process.GetModuleFileNameEx(handle, 0)
                    display = get_exe_display_name(path).lower()
                finally:
                    win32api.CloseHandle(handle)
            except Exception:
                pass
            if not any(s in stem or s in display for s in stems):
                return True
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return True
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            area = max(0, right - left) * max(0, bottom - top)
        except Exception:
            area = 0
        if area < 200 * 200:
            return True
        candidates.append((area, hwnd))
        return True

    win32gui.EnumWindows(enum_handler, None)
    if not candidates:
        return False
    candidates.sort(reverse=True)
    return _force_foreground(candidates[0][1])


def is_app_running(aumid: str = "", app_name: str = "") -> bool:
    """Return True if a process matching the app appears to be running."""
    stems = _exe_stems_for_app(aumid, app_name)
    if not stems:
        return False
    try:
        import win32com.client

        wmi = win32com.client.GetObject("winmgmts:")
        for proc in wmi.InstancesOf("Win32_Process"):
            path = proc.ExecutablePath
            if not path:
                continue
            stem = Path(path).stem.lower()
            if stem in stems:
                return True
            display = get_exe_display_name(path).lower()
            if any(s in stem or s in display for s in stems):
                return True
    except Exception:
        pass
    return False
