"""Windows 11 DWM backdrop helpers (Mica) for Tkinter windows."""

import ctypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2       # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Mica Alt — for flyouts/toasts/transient surfaces
DWMSBT_TABBEDWINDOW = 4     # Mica Alt (tabbed)


def apply_mica(win, transient: bool = True, dark: bool = True) -> bool:
    """Apply the Windows 11 Mica backdrop to a Tkinter Toplevel.

    Best-effort: silently does nothing on Windows 10 / older Windows 11
    builds that don't support DWMWA_SYSTEMBACKDROP_TYPE, or on non-Windows
    platforms. Returns True if the backdrop was applied.
    """
    try:
        win.update_idletasks()
        hwnd = win.winfo_id()
        try:
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
        except Exception:
            pass
        dwmapi = ctypes.windll.dwmapi
        if dark:
            value = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                          ctypes.byref(value), ctypes.sizeof(value))

        backdrop = DWMSBT_TRANSIENTWINDOW if transient else DWMSBT_MAINWINDOW
        value = ctypes.c_int(backdrop)
        result = dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                                               ctypes.byref(value), ctypes.sizeof(value))
        return result == 0
    except Exception:
        return False
