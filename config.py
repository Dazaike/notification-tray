"""All user-tunable constants for the notification tray."""

import sys
from pathlib import Path

__version__ = "2.0.13"
KINDS = ("info", "success", "warning", "error")
DURATION_MS = 5000
MIN_TOAST_ALPHA = 0.6
TOAST_ALPHA = 0.94
DEFAULT_TOAST_SCALE = 1.0
MIN_TOAST_SCALE = 0.5
MAX_TOAST_SCALE = 1.5
GROUP_WINDOW_SEC = 30
SOUND_COOLDOWN_MS = 1500
HISTORY_LIMIT = 200
DEFAULT_POSITION = "right"
DEFAULT_TRAY_CLICK_ACTION = "center"
DEFAULT_MONITOR = 0
DEFAULT_FONT_PATH = ""
DEFAULT_ACCENT = "#4f98a3"
ICON_CACHE_DIR = Path.home() / ".notif_tray_icons"
CONFIG_PATH = Path.home() / ".notif_tray_config.json"
DEFAULT_CUSTOM_SOUND_PATH = ""
DEFAULT_ANIMATION_PRESET = "default"
DEFAULT_ANIM_INCOMING = "soft-slide"
DEFAULT_ANIM_OUTGOING = "slide-away"
DEFAULT_ANIM_DIRECTION = "auto"
DEFAULT_ANIM_DURATION = 350
DEFAULT_ANIM_EASING = "spring"
DEFAULT_ANIM_DISTANCE = 400
DEFAULT_ANIM_BOUNCE = 0.3
DEFAULT_ANIM_BLUR = 12
DEFAULT_ANIM_SCALE = 0.9


def resource_path(name: str) -> Path:
    """Absolute path to a bundled data file, in-tree or inside a PyInstaller/Electron bundle."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / name)
        candidates.append(exe_dir.parent / name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            candidates.append(mp / name)
            candidates.append(mp.parent / name)
    candidates.append(Path(__file__).resolve().parent / name)
    candidates.append(Path.cwd() / name)

    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]

_SOUND_FILE = resource_path("fears-to-fathom-notification.mp3")
NOTIFICATION_SOUND = str(_SOUND_FILE) if _SOUND_FILE.exists() else ""
