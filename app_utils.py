"""Helpers for identifying an application from its .exe path."""

import time
from pathlib import Path

_FG_CACHE = ("", 0.0)
# AUMID -> process filename stem(s) for focusing an already-running app.
_AUMID_EXE_STEMS = {
    "anysphere.cursor": ("cursor",),
    "com.squirrel.discord.discord": ("discord",),
    "org.equicord.equibop": ("equibop",),
    "microsoft.windowscommunicationsapps_8wekyb3d8bbwe": ("hxoutlook", "olk", "outlook"),
}


def find_exe_for_app(app_name: str):
    """Best-effort: find the executable path of a running or installed app.
    Used as an icon fallback for win32 apps that don't expose a logo via toast API."""
    if not app_name:
        return None
    target = app_name.strip().lower()

    # 1. Check known AUMID stems
    for aumid_key, stems in _AUMID_EXE_STEMS.items():
        if target in aumid_key or any(target == s or s in target for s in stems):
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
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        for proc in wmi.InstancesOf("Win32_Process"):
            path = proc.ExecutablePath
            if not path:
                continue
            stem = Path(path).stem.lower()
            if stem and (stem == target or stem in target or target in stem):
                return path
            display = get_exe_display_name(path).lower()
            if display and (display == target or display in target or target in display):
                return path
    except Exception:
        pass

    # 3. Check Windows App Paths in Registry
    try:
        import winreg
        for hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for ext in ("", ".exe"):
                try:
                    with winreg.OpenKey(hkey, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{target}{ext}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and Path(val).is_file():
                            return val
                except OSError:
                    pass
    except Exception:
        pass

    return None


def extract_exe_icon(exe_path: str, size: int = 48):
    """Best-effort: extract the embedded icon from an .exe as a PIL Image,
    resized to (size, size). Returns None on failure."""
    try:
        import win32gui
        import win32ui
        from PIL import Image

        large, small = win32gui.ExtractIconEx(exe_path, 0, 1)
        handles = (large or []) + (small or [])
        if not handles:
            return None
        hicon = handles[0]

        info = win32gui.GetIconInfo(hicon)
        hbm_mask, hbm_color = info[3], info[4]

        bmp = win32ui.CreateBitmapFromHandle(hbm_color)
        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)
        w, h = bmpinfo["bmWidth"], bmpinfo["bmHeight"]
        img = Image.frombuffer("RGBA", (w, h), bmpstr, "raw", "BGRA", 0, 1)

        if img.getextrema()[3] == (0, 0):
            img.putalpha(255)

        for handle in handles:
            win32gui.DestroyIcon(handle)
        win32gui.DeleteObject(hbm_mask)
        win32gui.DeleteObject(hbm_color)

        return img.resize((size, size), Image.LANCZOS)
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
