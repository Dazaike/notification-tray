"""Normalize deep-link launch URIs from mirrored Windows toasts."""

import re
# https://discord.com/channels/<guild>/<channel>[/<message>]
_DISCORD_WEB_RE = re.compile(
    r"^https?://(?:www\.)?discord(?:app)?\.com/channels/([^/?#]+)/(\d+)(?:/(\d+))?",
    re.I,
)


def normalize_launch_url(url: str) -> str:
    """Convert web Discord URLs and common variants into protocol URIs."""
    if not url:
        return ""

    url = url.strip()
    if url.lower().startswith("type=click") or url.lower().startswith("type=reply"):
        return ""
    match = _DISCORD_WEB_RE.match(url)
    if match:
        guild, channel, message = match.groups()
        base = f"discord://-/channels/{guild}/{channel}"
        return f"{base}/{message}" if message else base

    # discord:///channels/... -> discord://-/channels/... (Discord's canonical form)
    if url.lower().startswith("discord:///channels/"):
        return "discord://-/channels/" + url[len("discord:///channels/"):]

    return url
