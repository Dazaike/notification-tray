"""Manage a Startup-folder shortcut so the app can launch at login."""

import os
import sys
from pathlib import Path

_SHORTCUT_NAME = "NotificationTray.lnk"


def _shortcut_path() -> Path:
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup / _SHORTCUT_NAME


def _target():
    """Return (target_path, arguments, working_dir) for the current run mode."""
    if getattr(sys, "frozen", False):
        target = sys.executable
        return target, "", str(Path(target).parent)

    script = str(Path(__file__).resolve().parent / "notification_tray.py")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = str(pythonw) if pythonw.exists() else sys.executable
    return target, f'"{script}"', str(Path(__file__).resolve().parent)


def is_enabled() -> bool:
    return _shortcut_path().exists()


def enable() -> None:
    import win32com.client

    target, args, workdir = _target()
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(_shortcut_path()))
    shortcut.TargetPath = target
    shortcut.Arguments = args
    shortcut.WorkingDirectory = workdir
    shortcut.Description = "Notification Tray"
    shortcut.Save()


def disable() -> None:
    path = _shortcut_path()
    if path.exists():
        path.unlink()


def set_enabled(enabled: bool) -> None:
    if enabled:
        enable()
    else:
        disable()
