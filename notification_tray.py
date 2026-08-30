"""Entry point for the notification tray application."""

import sys

import win32api
import win32event
from winerror import ERROR_ALREADY_EXISTS
import config
from control_panel import ControlPanel
from manager import NotificationManager
from notification_center import NotificationCenter
from tray_icon import setup_tray
import windows_listener

# Held for the lifetime of the process; releasing/GC'ing it would let a
# second instance acquire the lock. Module-level so it isn't collected.
_instance_mutex = None


def _acquire_single_instance() -> bool:
    """Return True if this is the only running instance. A second launch
    (e.g. Startup shortcut racing a manual double-click) used to spawn a
    duplicate process that fought the first one over the shared config
    file and tray/notification-listener registration — that's what made
    the app appear to randomly stop working."""
    global _instance_mutex
    _instance_mutex = win32event.CreateMutex(None, False, "Local\\NotificationTraySingleInstance")
    return win32api.GetLastError() != ERROR_ALREADY_EXISTS


def main():
    config.enable_dpi_awareness()
    if not _acquire_single_instance():
        print("[notification_tray] already running; exiting")
        sys.exit(0)
    manager = NotificationManager()

    control_panel = ControlPanel(manager)
    notification_center = NotificationCenter(manager)

    tray_icon = setup_tray(manager, control_panel, notification_center)
    tray_icon.run_detached()

    windows_listener.start(manager)
    manager.run()


if __name__ == "__main__":
    main()
