"""Tray icon image generation using Pillow."""

import base64
import io
from PIL import Image, ImageDraw, ImageFont


def render_tray_png(unread: int = 0, accent: str = "#4f98a3", size: int = 16) -> str:
    """Return a base64 `data:image/png;base64,...` URL of the tray bell icon.

    Draws at 64x64 canvas then resizes to `size` px square for crisp rendering
    at any DPI scale factor.
    """
    canvas_size = 64
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    accent = accent or "#4f98a3"

    # Bell body
    draw.pieslice([12, 10, 52, 50], 180, 360, fill=accent)
    draw.rectangle([12, 30, 52, 44], fill=accent)
    draw.polygon([(12, 44), (52, 44), (46, 52), (18, 52)], fill=accent)

    # Clapper
    draw.ellipse([28, 52, 36, 60], fill=accent)

    # Top knob
    draw.rectangle([30, 4, 34, 12], fill=accent)

    if unread > 0:
        badge = "#dd6974"
        draw.ellipse([34, 0, 64, 30], fill=badge)
        text = str(unread) if unread <= 9 else "9+"
        draw.text((49, 15), text, fill="#ffffff", anchor="mm", font=ImageFont.load_default())

    target_size = max(1, int(size)) if size else 16
    if target_size != canvas_size:
        image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
