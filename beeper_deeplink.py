"""Capture Beeper deep links from renderer logs when toasts fire.

Beeper's Windows toast XML does not include a protocol URL — only an Electron
reply tag. When a notification is sent, Beeper logs:

  [sendNotification] threadID=... accountID=... platform.name=bridge-...

We tail that log and build the same deep link Beeper uses internally:

  beeper://select-thread/<platform>/<threadID>?accountID=<accountID>
"""

from __future__ import annotations

import os
import re
import threading
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass
from pathlib import Path

BEEPER_AUMID = "com.automattic.beeper.desktop"
DEEPLINK_SCHEME = "beeper://"
_LOG_LINE_RE = re.compile(
    r"\[sendNotification\][^\r\n]*?\b"
    r"threadID=(?P<thread_id>\S+)[^\r\n]*?\b"
    r"accountID=(?P<account_id>\S+)[^\r\n]*?\b"
    r"platform\.name=(?P<platform_name>\S+)"
)

_LOCK = threading.Lock()
_RECENT: deque["_CapturedNotification"] = deque(maxlen=64)
_LOG_THREAD: threading.Thread | None = None
_LOG_STOP = threading.Event()


@dataclass(frozen=True)
class _CapturedNotification:
    thread_id: str
    account_id: str
    platform_name: str
    deeplink: str
    captured_at: float


def is_beeper_aumid(aumid: str, app_name: str = "") -> bool:
    aumid = (aumid or "").strip().lower()
    if aumid == BEEPER_AUMID:
        return True
    return (app_name or "").strip().lower() == "beeper"


def is_beeper_deeplink(url: str) -> bool:
    return (url or "").strip().lower().startswith(DEEPLINK_SCHEME)


def make_deeplink(platform_name: str, thread_id: str, account_id: str) -> str:
    platform_slug = (platform_name or "").removeprefix("bridge-").strip()
    thread_id = (thread_id or "").strip()
    account_id = (account_id or "").strip()
    if not platform_slug or not thread_id or not account_id:
        return ""
    query = urllib.parse.urlencode({"accountID": account_id})
    return f"{DEEPLINK_SCHEME}select-thread/{platform_slug}/{thread_id}?{query}"


def _beeper_logs_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "BeeperTexts" / "logs" / "renderer"
    return Path.home() / "AppData" / "Roaming" / "BeeperTexts" / "logs" / "renderer"


def _latest_renderer_log() -> Path | None:
    log_dir = _beeper_logs_dir()
    if not log_dir.is_dir():
        return None
    candidates = sorted(log_dir.glob("renderer-*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _append_recent(entry: _CapturedNotification) -> None:
    with _LOCK:
        _RECENT.appendleft(entry)


def _record_from_match(match: re.Match[str]) -> _CapturedNotification | None:
    thread_id = match.group("thread_id")
    account_id = match.group("account_id")
    platform_name = match.group("platform_name")
    deeplink = make_deeplink(platform_name, thread_id, account_id)
    if not deeplink:
        return None
    entry = _CapturedNotification(
        thread_id=thread_id,
        account_id=account_id,
        platform_name=platform_name,
        deeplink=deeplink,
        captured_at=time.time(),
    )
    _append_recent(entry)
    return entry


def _process_log_line(line: str) -> _CapturedNotification | None:
    match = _LOG_LINE_RE.search(line)
    return _record_from_match(match) if match else None

def _tail_log(path: Path | None) -> None:
    position = path.stat().st_size if path and path.is_file() else 0
    while not _LOG_STOP.is_set():
        if path is None or not path.is_file():
            time.sleep(2.0)
            path = _latest_renderer_log()
            position = path.stat().st_size if path and path.is_file() else 0
            continue
        try:
            size = path.stat().st_size
            if size < position:
                position = 0
            if size == position:
                newer = _latest_renderer_log()
                if newer and newer != path:
                    path = newer
                    position = 0
                time.sleep(0.25)
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(position)
                chunk = handle.read()
                position = handle.tell()
        except OSError:
            time.sleep(1.0)
            continue
        for line in chunk.splitlines():
            _process_log_line(line)


def _seed_recent_from_log(path: Path, max_lines: int = 400) -> None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-max_lines:]
    except OSError:
        return
    for line in lines:
        _process_log_line(line)


def ensure_log_watcher() -> None:
    global _LOG_THREAD
    with _LOCK:
        if _LOG_THREAD and _LOG_THREAD.is_alive():
            return
        log_path = _latest_renderer_log()
        _LOG_STOP.clear()
        thread = threading.Thread(
            target=_tail_log,
            args=(log_path,),
            name="beeper-log-tail",
            daemon=True,
        )
        _LOG_THREAD = thread

    if log_path:
        _seed_recent_from_log(log_path)

    with _LOCK:
        if _LOG_THREAD is thread and not thread.is_alive():
            thread.start()




def capture_recent_deeplink(max_age_sec: float = 12.0) -> str:
    """Return the newest Beeper deep link logged within the last few seconds."""
    ensure_log_watcher()
    cutoff = time.time() - max(0.5, max_age_sec)
    with _LOCK:
        for entry in _RECENT:
            if entry.captured_at >= cutoff:
                return entry.deeplink
    return ""


def parse_send_notification_line(line: str) -> str:
    match = _LOG_LINE_RE.search(line or "")
    if not match:
        return ""
    return make_deeplink(
        match.group("platform_name"),
        match.group("thread_id"),
        match.group("account_id"),
    )
