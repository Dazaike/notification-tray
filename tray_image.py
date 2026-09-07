"""Tray icon image generation using Pillow."""

import base64
import io
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_ICON_CACHE = None


def _get_base_icon() -> Image.Image:
    global _ICON_CACHE
    if _ICON_CACHE is not None:
        return _ICON_CACHE.copy()

    # Locate icon.png in various deployment locations
    search_dirs = [
        Path(__file__).resolve().parent / "resources",
        Path(getattr(sys, "_MEIPASS", "")) / "resources" if getattr(sys, "_MEIPASS", "") else None,
        Path(__file__).resolve().parent / "build",
        Path(__file__).resolve().parent,
    ]

    for d in search_dirs:
        if d and (d / "icon.png").exists():
            try:
                im = Image.open(d / "icon.png").convert("RGBA")
                _ICON_CACHE = im
                return im.copy()
            except Exception:
                pass

    # Fallback to generated icon if asset not found
    canvas_size = 128
    fallback = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fallback)
    draw.pieslice([24, 20, 104, 100], 180, 360, fill="#ffffff")
    draw.rectangle([24, 60, 104, 88], fill="#ffffff")
    draw.polygon([(24, 88), (104, 88), (92, 104), (36, 104)], fill="#ffffff")
    draw.ellipse([56, 104, 72, 120], fill="#ffffff")
    draw.rectangle([60, 8, 68, 24], fill="#ffffff")
    _ICON_CACHE = fallback
    return fallback.copy()


def render_tray_png(unread: int = 0, accent: str = "#4f98a3", size: int = 16) -> str:
    """Return a base64 `data:image/png;base64,...` URL of the tray bell icon.

    Renders the app icon resized to `size` px square with unread badge counter for crisp rendering
    at any DPI scale factor.
    """
    target_size = max(1, int(size)) if size else 16
    canvas_size = max(128, target_size * 2)

    base = _get_base_icon()
    image = base.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)

    if unread > 0:
        draw = ImageDraw.Draw(image)
        badge_color = "#dd6974"
        badge_radius = int(canvas_size * 0.28)
        bx1 = canvas_size - badge_radius * 2
        by1 = 0
        bx2 = canvas_size
        by2 = badge_radius * 2
        draw.ellipse([bx1, by1, bx2, by2], fill=badge_color)
        text = str(unread) if unread <= 9 else "9+"
        draw.text(
            ((bx1 + bx2) / 2, (by1 + by2) / 2),
            text,
            fill="#ffffff",
            anchor="mm",
            font=ImageFont.load_default(),
        )

    if target_size != canvas_size:
        image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
