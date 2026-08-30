"""Renders text (including color emoji) to Tk PhotoImages.

Tk's text rendering on Windows can't draw color emoji glyphs - they show
up as empty boxes. Segoe UI Emoji (a color bitmap font) renders emoji
correctly via Pillow's embedded_color support, so we pre-render text to
images for display on canvases/labels.

Regular (non-emoji) text is drawn with a separate, user-configurable font
(see set_custom_font_path). Each character is drawn with the first font in
a fallback chain that actually contains its glyph - the same approach
"""

import struct
import unicodedata
import tkinter as tk
from collections import OrderedDict
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = ImageTk = None

# Segoe UI Emoji is the preferred color-emoji font on Windows 10/11.
# Segoe UI Symbol is an older fallback that still covers many symbols.
_EMOJI_FONT_PATHS = [
    "C:/Windows/Fonts/seguiemj.ttf",
    "C:/Windows/Fonts/seguisym.ttf",
]
_font_cache = {}
_CUSTOM_FONT_PATH = None
_text_font_cache = {}
_fallback_font_cache = {}
_cmap_cache = {}
_font_meta = {}
_char_font_cache = {}
_char_width_cache = {}
_render_cache = OrderedDict()
_RENDER_CACHE_MAX = 256
# Windows fonts tried after the custom / primary text font (Chromium-style).
# Covers Latin, symbols, math, CJK, Indic, Canadian Aboriginal, Lao/Thai, etc.
_SYSTEM_FONT_PATHS = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/SegoeUIVar.ttf",
    "C:/Windows/Fonts/cambria.ttc",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/seguihis.ttf",
    "C:/Windows/Fonts/Nirmala.ttf",
    "C:/Windows/Fonts/gadugi.ttf",
    "C:/Windows/Fonts/ebrima.ttf",
    "C:/Windows/Fonts/LeelawUI.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/YuGothR.ttc",
    "C:/Windows/Fonts/arial.ttf",
]

# Unicode blocks where Cambria is preferred over the primary text font.
_CAMBRIA_BLOCKS = (
    (0x1D400, 0x1D7FF),   # mathematical alphanumeric
    (0x2100, 0x214F),     # letterlike symbols
    (0xFF01, 0xFF5E),     # fullwidth ASCII variants
)

# Script-specific fonts tried before the generic chain (CSS unicode-range style).
# Segoe UI's cmap often maps these blocks to empty/.notdef glyphs.
_SCRIPT_FONT_PATHS = (
    ((0x0E00, 0x0E7F), "C:/Windows/Fonts/LeelawUI.ttf"),       # Thai
    ((0x0E80, 0x0EFF), "C:/Windows/Fonts/LeelawUI.ttf"),       # Lao
    ((0x0900, 0x097F), "C:/Windows/Fonts/Nirmala.ttf"),       # Devanagari
    ((0x0980, 0x09FF), "C:/Windows/Fonts/Nirmala.ttf"),         # Bengali
    ((0x0A80, 0x0AFF), "C:/Windows/Fonts/Nirmala.ttf"),         # Gujarati
    ((0x0B80, 0x0BFF), "C:/Windows/Fonts/Nirmala.ttf"),         # Tamil
    ((0x1400, 0x167F), "C:/Windows/Fonts/gadugi.ttf"),          # Canadian Aboriginal
    ((0x3040, 0x309F), "C:/Windows/Fonts/msgothic.ttc"),        # Hiragana
    ((0x30A0, 0x30FF), "C:/Windows/Fonts/msgothic.ttc"),        # Katakana
    ((0x4E00, 0x9FFF), "C:/Windows/Fonts/msyh.ttc"),            # CJK unified
    ((0xAC00, 0xD7AF), "C:/Windows/Fonts/malgun.ttf"),          # Hangul
    ((0x0600, 0x06FF), "C:/Windows/Fonts/segoeui.ttf"),         # Arabic (Segoe UI)
    ((0x0400, 0x04FF), "C:/Windows/Fonts/segoeui.ttf"),         # Cyrillic
    ((0x0370, 0x03FF), "C:/Windows/Fonts/segoeui.ttf"),         # Greek
)

# True color emoji / pictographs - prefer the emoji font for these.
_EMOJI_RANGES = (
    (0x200D, 0x200D),      # zero-width joiner
    (0xFE0F, 0xFE0F),      # variation selector-16
    (0x1F000, 0x1FAFF),    # mahjong through symbols & pictographs extended-A
)


def _is_emoji_char(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def set_custom_font_path(path):
    """Set (or clear, with a falsy path) the font file used for normal text."""
    global _CUSTOM_FONT_PATH
    path = path or None
    if path == _CUSTOM_FONT_PATH:
        return
    _CUSTOM_FONT_PATH = path
    _text_font_cache.clear()
    _char_font_cache.clear()
    _char_width_cache.clear()
    _render_cache.clear()


def get_custom_font_path():
    return _CUSTOM_FONT_PATH


def font_file_is_loadable(path):
    """Return True if Pillow can load `path` as a font."""
    if ImageFont is None or not path:
        return False
    try:
        ImageFont.truetype(path, 13)
        return True
    except Exception:
        return False

_CONTROL_TRANSLATION = {
    ord(ch): " "
    for ch in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
              "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
}


def normalize_text(value):
    """Return text safe for Pillow/Tk rendering."""
    if value is None:
        return ""
    text = str(value).translate(_CONTROL_TRANSLATION)
    try:
        text = text.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    text = text.replace("\ufffd", "")
    kept = []
    for ch in text:
        cat = unicodedata.category(ch)
        # Invisible formatting (Discord tag chars, bidi isolates, ZWJ/ZWNJ).
        if cat == "Cf":
            continue
        # Private-use / unassigned codepoints almost always render as tofu.
        if cat in ("Co", "Cn", "Cs"):
            continue
        kept.append(ch)
    return "".join(kept)


def _read_u16(data, off):
    return struct.unpack_from(">H", data, off)[0]


def _read_u32(data, off):
    return struct.unpack_from(">I", data, off)[0]


def _table_offset(data, table_dir, tag):
    num_tables = _read_u16(data, table_dir + 4)
    for i in range(num_tables):
        rec = table_dir + 12 + i * 16
        if data[rec:rec + 4] == tag.encode("ascii"):
            return _read_u32(data, rec + 8)
    return None


def _font_table_dir(data, index=0):
    if data[:4] == b"ttcf":
        count = _read_u32(data, 8)
        if index >= count:
            index = 0
        return _read_u32(data, 12 + index * 4)
    return 0


def _cmap_codepoints(data, cmap_off):
    """Parse Unicode cmap subtables (format 4 and 12)."""
    num_sub = _read_u16(data, cmap_off + 2)
    codepoints = set()
    for i in range(num_sub):
        rec = cmap_off + 4 + i * 8
        platform = _read_u16(data, rec)
        encoding = _read_u16(data, rec + 2)
        sub_off = cmap_off + _read_u32(data, rec + 4)
        if platform == 3 and encoding in (1, 10):
            fmt = _read_u16(data, sub_off)
            if fmt == 4:
                seg_count = _read_u16(data, sub_off + 6) // 2
                end_codes = sub_off + 14
                start_codes = end_codes + 2 + seg_count * 2
                id_delta = start_codes + seg_count * 2
                id_range = id_delta + seg_count * 2
                for j in range(seg_count):
                    start = _read_u16(data, start_codes + j * 2)
                    end = _read_u16(data, end_codes + j * 2)
                    delta = struct.unpack_from(">h", data, id_delta + j * 2)[0]
                    range_off = _read_u16(data, id_range + j * 2)
                    if start == 0xFFFF:
                        continue
                    if range_off:
                        ro = id_range + j * 2 + range_off
                        for cp in range(start, end + 1):
                            gidx = _read_u16(data, ro + (cp - start) * 2)
                            if gidx:
                                codepoints.add(cp)
                    else:
                        for cp in range(start, end + 1):
                            if (cp + delta) & 0xFFFF:
                                codepoints.add(cp)
            elif fmt == 12:
                ngroups = _read_u32(data, sub_off + 12)
                groups = sub_off + 16
                for j in range(ngroups):
                    grec = groups + j * 12
                    start = _read_u32(data, grec)
                    end = _read_u32(data, grec + 4)
                    codepoints.update(range(start, end + 1))
    return codepoints


def _font_cmap(path, index=0):
    key = (path, index)
    if key not in _cmap_cache:
        try:
            data = Path(path).read_bytes()
            table_dir = _font_table_dir(data, index)
            cmap_off = _table_offset(data, table_dir, "cmap")
            _cmap_cache[key] = _cmap_codepoints(data, cmap_off) if cmap_off else set()
        except Exception:
            _cmap_cache[key] = set()
    return _cmap_cache[key]


def _register_font(font, path, index=0):
    if font is not None:
        _font_meta[id(font)] = (path, index)


def _font_has_glyph(font, ch):
    """Return True if `font` has a real glyph for `ch` (not .notdef tofu)."""
    if font is None:
        return False
    cat = unicodedata.category(ch)
    if cat[0] in "ZsZlZp":
        return True
    meta = _font_meta.get(id(font))
    if not meta:
        return True
    path, index = meta
    return ord(ch) in _font_cmap(path, index)


def _load_truetype(path, size, index=0):
    """Load and cache a TrueType/OpenType font face."""
    if ImageFont is None:
        return None
    key = (path, size, index)
    if key not in _fallback_font_cache:
        try:
            font = ImageFont.truetype(path, size, index=index)
            _register_font(font, path, index)
            _fallback_font_cache[key] = font
        except Exception:
            _fallback_font_cache[key] = None
    return _fallback_font_cache[key]


def _get_emoji_font(size):
    if ImageFont is None:
        return None
    if size not in _font_cache:
        font = None
        for path in _EMOJI_FONT_PATHS:
            font = _load_truetype(path, size, 0)
            if font is not None:
                break
        _font_cache[size] = font
    return _font_cache[size]


def _get_default_text_font(size):
    return _load_truetype(_SYSTEM_FONT_PATHS[0], size, 0)


def _get_text_font(size):
    if ImageFont is None:
        return None
    if not _CUSTOM_FONT_PATH:
        return _get_default_text_font(size) or _get_emoji_font(size)
    key = (_CUSTOM_FONT_PATH, size)
    if key not in _text_font_cache:
        try:
            font = ImageFont.truetype(_CUSTOM_FONT_PATH, size)
            _register_font(font, _CUSTOM_FONT_PATH, 0)
            _text_font_cache[key] = font
        except Exception:
            _text_font_cache[key] = _get_default_text_font(size) or _get_emoji_font(size)
    return _text_font_cache[key]


def _get_cambria_font(size):
    return _load_truetype(_SYSTEM_FONT_PATHS[2], size, 0)


def _is_cambria_char(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CAMBRIA_BLOCKS)


def _script_font_path(ch):
    cp = ord(ch)
    for (lo, hi), path in _SCRIPT_FONT_PATHS:
        if lo <= cp <= hi:
            return path
    return None


def _font_chain(size, ch):
    """Yield fonts to try for `ch`, in priority order."""
    seen = set()

    def _yield_font(font):
        if font is not None and id(font) not in seen:
            seen.add(id(font))
            yield font

    if _is_emoji_char(ch):
        yield from _yield_font(_get_emoji_font(size))

    if _is_cambria_char(ch):
        yield from _yield_font(_get_cambria_font(size))

    script_path = _script_font_path(ch)
    if script_path:
        yield from _yield_font(_load_truetype(script_path, size, 0))

    yield from _yield_font(_get_text_font(size))
    yield from _yield_font(_get_default_text_font(size))

    for path in _SYSTEM_FONT_PATHS[1:]:
        yield from _yield_font(_load_truetype(path, size, 0))

    if not _is_emoji_char(ch):
        yield from _yield_font(_get_emoji_font(size))


def _resolve_char_font(size, ch):
    """Pick the first font in the chain that covers `ch`."""
    for font in _font_chain(size, ch):
        if _font_has_glyph(font, ch):
            return font
    return _get_text_font(size) or _get_default_text_font(size)


def _char_font(size, ch):
    key = (size, ch)
    font = _char_font_cache.get(key, False)
    if font is False:
        font = _resolve_char_font(size, ch)
        _char_font_cache[key] = font
    return font


def _hex_to_rgb(color, alpha=255):
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def _resolve_char_width(size, ch):
    font = _char_font(size, ch)
    if font is None:
        return 0.0
    try:
        return font.getlength(ch)
    except Exception:
        return 0.0


def _char_width(size, ch):
    key = (size, ch)
    w = _char_width_cache.get(key, False)
    if w is False:
        w = _resolve_char_width(size, ch)
        _char_width_cache[key] = w
    return w

def _text_length(text, size):
    return sum(_char_width(size, ch) for ch in text)


def _draw_char(draw, x, y, ch, size, fill):
    font = _char_font(size, ch)
    if font is None or not _font_has_glyph(font, ch):
        return x
    use_color = _is_emoji_char(ch) and font is _get_emoji_font(size)
    for embedded_color in (use_color, False):
        try:
            draw.text((x, y), ch, font=font, embedded_color=embedded_color, fill=fill)
            break
        except Exception:
            continue
    try:
        return x + font.getlength(ch)
    except Exception:
        return x


def wrap_lines(text, size, max_width):
    """Word-wrap text (preserving existing newlines) to fit max_width px."""
    text = normalize_text(text)
    have_font = _get_emoji_font(size) is not None or _get_text_font(size) is not None
    lines = []
    space_w = _char_width(size, " ")
    for raw in text.split("\n"):
        if not have_font or max_width <= 0:
            lines.append(raw)
            continue
        words = raw.split(" ")
        cur_words = []
        cur_w = 0.0
        for word in words:
            word_w = sum(_char_width(size, c) for c in word)
            test_w = word_w if not cur_words else (cur_w + space_w + word_w)
            if not cur_words or test_w <= max_width:
                cur_words.append(word)
                cur_w = test_w
            else:
                lines.append(" ".join(cur_words))
                cur_words = [word]
                cur_w = word_w
        lines.append(" ".join(cur_words))
    return lines or [""]


def ellipsize(text, size, max_width):
    text = normalize_text(text)
    if _get_text_font(size) is None and _get_emoji_font(size) is None:
        return text
    try:
        if _text_length(text, size) <= max_width:
            return text
        ellipsis_w = _char_width(size, "…")
        acc = 0.0
        for i, ch in enumerate(text):
            ch_w = _char_width(size, ch)
            if acc + ch_w + ellipsis_w > max_width:
                return text[:i] + "…"
            acc += ch_w
        return text + "…"
    except Exception:
        return text


def render(lines, size, fg, bg, line_height, width):
    """Render lines of text (possibly containing emoji) to a PhotoImage."""
    if Image is None:
        return None
    if _get_text_font(size) is None and _get_emoji_font(size) is None:
        return None

    safe_lines = [normalize_text(line) for line in lines]
    width = max(1, int(width))
    line_height = int(line_height)
    key = (tuple(safe_lines), size, fg, bg, line_height, width)
    if key in _render_cache:
        _render_cache.move_to_end(key)
        return _render_cache[key]

    height = max(1, len(safe_lines)) * line_height

    try:
        img = Image.new("RGBA", (width, height), _hex_to_rgb(bg))
        draw = ImageDraw.Draw(img)
        fill = _hex_to_rgb(fg)
        for i, line in enumerate(safe_lines):
            y = i * line_height + max(0, (line_height - size) // 2)
            x = 0.0
            for ch in line:
                x = _draw_char(draw, x, y, ch, size, fill)
        photo = ImageTk.PhotoImage(img)
        _render_cache[key] = photo
        while len(_render_cache) > _RENDER_CACHE_MAX:
            _render_cache.popitem(last=False)
        return photo
    except Exception:
        return None
