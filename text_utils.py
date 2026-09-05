"""Text normalization utilities for notification tray."""

import unicodedata

_CONTROL_TRANSLATION = {
    ord(ch): " "
    for ch in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
              "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
}


def normalize_text(value) -> str:
    """Return text safe for rendering (strips C0 controls, lone surrogates, and Cf/Co/Cn/Cs)."""
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
