"""Shared helper for rendering app icons as squircle PhotoImages with vector fallbacks."""

import os
from collections import OrderedDict

import config

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk
except ImportError:  # pragma: no cover - PIL is a hard dependency, but be safe
    Image = ImageChops = ImageDraw = ImageFont = ImageTk = None

_icon_cache = OrderedDict()
_ICON_CACHE_MAX = 128


def _create_rounded_mask(size: int, radius: int) -> Image.Image:
    """Create an antialiased rounded-rectangle mask using 4x supersampling."""
    factor = 4
    ss_size = size * factor
    ss_radius = radius * factor
    mask = Image.new("L", (ss_size, ss_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, ss_size - 1, ss_size - 1), radius=ss_radius, fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def make_rounded_icon(icon_path: str, size: int, radius: int = 9, border_color: str = "#ffffff18"):
    """Load icon_path, resize to (size, size), and clip to a smooth squircle.
    Returns a PhotoImage, or None if unavailable."""
    if not (icon_path and Image and ImageTk):
        return None
    try:
        mtime = os.stat(icon_path).st_mtime_ns
        key = ("rounded", icon_path, size, radius, mtime)
        if key in _icon_cache:
            _icon_cache.move_to_end(key)
            return _icon_cache[key]

        img = Image.open(icon_path).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = _create_rounded_mask(size, radius)
        alpha = ImageChops.multiply(img.getchannel("A"), mask)
        img.putalpha(alpha)

        # Optional subtle 1px border stroke around the icon
        if border_color:
            border_img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
            b_draw = ImageDraw.Draw(border_img)
            r, g, b = (int(border_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            a = 32 if len(border_color.lstrip("#")) < 8 else int(border_color.lstrip("#")[6:8], 16)
            b_draw.rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=radius * 4,
                                     outline=(r, g, b, a), width=4)
            border_img = border_img.resize((size, size), Image.LANCZOS)
            img = Image.alpha_composite(img, border_img)

        photo = ImageTk.PhotoImage(img)
        _icon_cache[key] = photo
        while len(_icon_cache) > _ICON_CACHE_MAX:
            _icon_cache.popitem(last=False)
        return photo
    except Exception:
        return None


def make_circular_icon(icon_path: str, d: int):
    """Backward compatibility helper."""
    return make_rounded_icon(icon_path, d, radius=d // 2)


def make_fallback_icon(kind: str, size: int, accent: str, radius: int = 9):
    """Generate an antialiased vector squircle fallback icon with tinted background."""
    if not (Image and ImageTk):
        return None
    key = ("fallback", kind, size, accent, radius)
    if key in _icon_cache:
        _icon_cache.move_to_end(key)
        return _icon_cache[key]

    try:
        factor = 4
        ss_size = size * factor
        ss_radius = radius * factor

        # 4x supersampled image for ultra-smooth antialiasing
        img = Image.new("RGBA", (ss_size, ss_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        bg_hex = config.icon_bg_for(accent).lstrip("#")
        bg_r, bg_g, bg_b = (int(bg_hex[i:i + 2], 16) for i in (0, 2, 4))
        draw.rounded_rectangle((0, 0, ss_size - 1, ss_size - 1), radius=ss_radius, fill=(bg_r, bg_g, bg_b, 255))

        # Subtle 1px border
        acc_hex = accent.lstrip("#")
        acc_r, acc_g, acc_b = (int(acc_hex[i:i + 2], 16) for i in (0, 2, 4))
        draw.rounded_rectangle((0, 0, ss_size - 1, ss_size - 1), radius=ss_radius,
                               outline=(acc_r, acc_g, acc_b, 60), width=factor)

        # Draw antialiased geometric vector symbol centered
        mid = ss_size / 2.0
        if kind == "success":
            # Checkmark: two smooth connected line segments
            points = [
                (mid - factor * 3.5, mid),
                (mid - factor * 0.8, mid + factor * 2.8),
                (mid + factor * 3.6, mid - factor * 2.8),
            ]
            draw.line(points, fill=(acc_r, acc_g, acc_b, 255), width=int(factor * 1.8), joint="curve")
        elif kind == "warning":
            # Warning triangle / exclamation mark
            draw.line([(mid, mid - factor * 3.2), (mid, mid + factor * 0.8)],
                      fill=(acc_r, acc_g, acc_b, 255), width=int(factor * 1.8))
            draw.ellipse([mid - factor * 0.9, mid + factor * 2.2, mid + factor * 0.9, mid + factor * 4.0],
                         fill=(acc_r, acc_g, acc_b, 255))
        elif kind == "error":
            # Clean cross ✕
            s = factor * 3.0
            draw.line([(mid - s, mid - s), (mid + s, mid + s)], fill=(acc_r, acc_g, acc_b, 255), width=int(factor * 1.8))
            draw.line([(mid - s, mid + s), (mid + s, mid - s)], fill=(acc_r, acc_g, acc_b, 255), width=int(factor * 1.8))
        else:  # info
            # Info "i"
            draw.ellipse([mid - factor * 0.9, mid - factor * 3.8, mid + factor * 0.9, mid - factor * 2.0],
                         fill=(acc_r, acc_g, acc_b, 255))
            draw.line([(mid, mid - factor * 0.8), (mid, mid + factor * 3.2)],
                      fill=(acc_r, acc_g, acc_b, 255), width=int(factor * 1.8))

        final_img = img.resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(final_img)
        _icon_cache[key] = photo
        while len(_icon_cache) > _ICON_CACHE_MAX:
            _icon_cache.popitem(last=False)
        return photo
    except Exception:
        return None
