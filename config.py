"""All user-tunable constants for the notification tray."""

import ctypes
import sys
from pathlib import Path

__version__ = "1.2.1"


def enable_dpi_awareness() -> None:
    """Per-monitor DPI awareness. Must run before the first tk.Tk()."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
def resource_path(name: str) -> Path:
    """Absolute path to a bundled data file, in-tree or inside a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).resolve().parent)
    else:
        base = Path(__file__).resolve().parent
    return base / name


# Appearance
NOTIF_WIDTH = 400
NOTIF_HEIGHT = 92
NOTIF_GAP = 10
MARGIN = 24
DURATION_MS = 5000
ANIM_DURATION_MS = 260
ANIM_FRAME_MS = 16
COUNTDOWN_TICK_MS = 50
MIN_TOAST_ALPHA = 0.6
SOUND_COOLDOWN_MS = 1500
CORNER_RADIUS = 16
ICON_DIAMETER = 38
ICON_RADIUS = 9
SHADOW_OFFSET = 5

# Grouping / stacked-peek effect
PEEK_OFFSET = 6      # px each peek layer is shifted down+right
PEEK_MAX = 2         # number of peek layers drawn behind the main card
GROUP_WINDOW_SEC = 30  # merge into an existing toast if it's still alive
BADGE_COLOR = "#dd6974"
BADGE_TEXT_COLOR = "#ffffff"

# Multi-line grouped messages
LINE_HEIGHT = 18
MAX_GROUP_LINES = 6

# App icon cache
ICON_CACHE_DIR = Path.home() / ".notif_tray_icons"

# Final opacity for the toast window once it's fully faded in. Slightly
# below 1.0 so the Windows 11 Mica backdrop can blend through the card
# (DWM only shows the backdrop where the layered window isn't fully opaque).
TOAST_ALPHA = 0.94

# Sound played when a new notification arrives (set to "" to disable)
_SOUND_FILE = resource_path("fears-to-fathom-notification.mp3")
NOTIFICATION_SOUND = str(_SOUND_FILE) if _SOUND_FILE.exists() else ""

# Defaults (overridden at runtime via control panel)
DEFAULT_POSITION = "right"   # "right" | "center" | "left"
DEFAULT_MONITOR = 0          # 0-indexed; index 0 is always the primary display

# Custom text font for notification title/message. Empty string means
# "use the built-in default" (Segoe UI Emoji). Set to the absolute path of
# any .ttf/.otf/.ttc file to render notification text in that font - the
# font does not need to be installed system-wide.
DEFAULT_FONT_PATH = ""

# Colors (Modern dark glass / slate-zinc theme)
BG_COLOR = "#121214"
CARD_COLOR = "#1c1c20"
CARD_HIGHLIGHT = "#2c2c32"
FG_COLOR = "#f4f4f6"
SUBTEXT_COLOR = "#a1a1aa"
HEADER_COLOR = "#71717a"
ACCENT = "#4f98a3"
MUTED = "#71717a"
BORDER = "#2e2e34"
SHADOW_COLOR = "#08080a"
PROGRESS_TRACK = "#28282e"
HOVER_BG = "#2a2a30"
ICONS = {"info": "ℹ", "success": "✓", "warning": "⚠", "error": "✕"}

# Default user-configurable accent color
DEFAULT_ACCENT = ACCENT

def mix_hex(c1: str, c2: str, t: float) -> str:
    """Blend two #rrggbb colors; t=0 -> c1, t=1 -> c2."""
    c1, c2 = c1.lstrip("#"), c2.lstrip("#")
    r1, g1, b1 = (int(c1[i:i + 2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (int(c2[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def icon_bg_for(accent: str) -> str:
    """A subtle tinted background for the icon badge, derived from the accent."""
    return mix_hex(accent, BG_COLOR, 0.82)


# Window key color used for shape-masking (must not appear elsewhere in the UI)
TRANSPARENT_KEY = "#0d0d0d"

# History / Notification Center
HISTORY_LIMIT = 200
CENTER_WIDTH = 440

# Layout design literals (96 DPI base)
CARD_PAD = 14           # toast.py _build_ui `pad`
ACCENT_BAR_W = 3        # toast.py _build_ui `bar_w`
TITLE_Y = 24            # toast.py module constant
MSG_Y = 44              # toast.py: message start Y
BOTTOM_PAD = 14         # toast.py module constant
BADGE_RADIUS = 9
BADGE_OFFSET = 20
PROGRESS_INSET = 14
PROGRESS_WIDTH = 2
PROGRESS_HEIGHT = 2
TEXT_TO_PROGRESS_GAP = 14
PROGRESS_BOTTOM_INSET = 12
TEXT_SIZE = 12          # Pillow size used for toast message
MSG_SIZE = 12           # Pillow size used for toast body message
TITLE_SIZE = 13         # Pillow size used for toast title
APP_HEADER_SIZE = 10    # Pillow size used for app name / header
ICON_GLYPH_SIZE = 16    # Tk point size for the fallback kind glyph — NOT scaled
CENTER_ICON_SIZE = 36
CENTER_TEXT_SIZE = 12
CENTER_HEADER_SIZE = 11
CENTER_MAX_HEIGHT = 640
PANEL_WIDTH = 580
PANEL_HEIGHT = 600

SCALE = 1.0
_SCALED_NAMES = (
    "NOTIF_WIDTH", "NOTIF_HEIGHT", "NOTIF_GAP", "MARGIN", "CORNER_RADIUS",
    "ICON_DIAMETER", "ICON_RADIUS", "SHADOW_OFFSET", "PEEK_OFFSET", "LINE_HEIGHT",
    "CENTER_WIDTH", "CARD_PAD", "ACCENT_BAR_W", "TITLE_Y", "MSG_Y", "BOTTOM_PAD",
    "BADGE_RADIUS", "BADGE_OFFSET", "PROGRESS_INSET", "PROGRESS_WIDTH", "PROGRESS_HEIGHT",
    "TEXT_TO_PROGRESS_GAP", "PROGRESS_BOTTOM_INSET",
    "TEXT_SIZE", "MSG_SIZE", "TITLE_SIZE", "APP_HEADER_SIZE",
    "CENTER_ICON_SIZE", "CENTER_TEXT_SIZE", "CENTER_HEADER_SIZE",
    "CENTER_MAX_HEIGHT", "PANEL_WIDTH", "PANEL_HEIGHT",
)
_BASE_METRICS = {name: globals()[name] for name in _SCALED_NAMES}


def apply_scale(factor: float) -> None:
    """Rescale every pixel metric from its 96-DPI base. Idempotent."""
    global SCALE
    SCALE = max(0.5, min(4.0, float(factor) or 1.0))
    for name, base in _BASE_METRICS.items():
        globals()[name] = max(1, int(round(base * SCALE)))


def scale(px: int) -> int:
    return max(1, int(round(px * SCALE)))


# Persisted settings file
CONFIG_PATH = Path.home() / ".notif_tray_config.json"
