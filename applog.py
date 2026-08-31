"""Single rotating log file so failures in the windowless build are visible.

The shipped executable is built with `console=False` (see NotificationTray.spec),
which means stdout is thrown away: every `print` in a background thread or an
exception handler vanished silently. Anything worth diagnosing goes here instead.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path.home() / ".notif_tray.log"

_log = None


def get_logger():
    """Process-wide logger writing to ~/.notif_tray.log (512 KB, 1 backup)."""
    global _log
    if _log is not None:
        return _log

    log = logging.getLogger("notif_tray")
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=1,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    except OSError:
        # A read-only or locked home directory must not take the app down.
        log.addHandler(logging.NullHandler())
    _log = log
    return _log
