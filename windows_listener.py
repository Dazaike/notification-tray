"""Mirrors native Windows toast notifications into the custom tray.

Uses the WinRT UserNotificationListener API to read notifications from the
Windows Action Center and forward new ones to a NotificationManager.

The first time this runs, Windows will prompt the user to grant
"notification access" (Settings > Privacy & security > Notifications). If
access is denied or the listener crashes, it restarts automatically after a
short backoff so a transient failure does not stop native mirroring.
"""

import asyncio
import re
import threading
import time
from pathlib import Path

import applog
import config
from app_utils import extract_exe_icon, find_exe_for_app
import beeper_deeplink
from toast_history import best_launch_target, find_toast_info

POLL_INTERVAL_SEC = 0.25
_ICON_MISSES = set()

# Map well-known app names to a toast "kind" so they pick up the matching
# accent color. Anything not listed here falls back to "info".
_KIND_HINTS = {
    "error": ("error", "failed", "failure", "crash"),
    "warning": ("warning", "low battery", "update available"),
    "success": ("success", "complete", "completed", "done", "finished"),
}


def _guess_kind(title, message):
    text = f"{title} {message}".lower()
    for kind, keywords in _KIND_HINTS.items():
        if any(keyword in text for keyword in keywords):
            return kind
    return "info"


def start(manager):
    """Start mirroring native Windows notifications in a background thread.

    Returns the thread object. Safe to call even if winsdk isn't installed
    or notification access is denied — it will just log and exit quietly.
    """
    thread = threading.Thread(target=_run, args=(manager,), daemon=True)
    thread.start()
    return thread


def _run(manager):
    """Keep the native notification mirror alive.

    _listen returns None on a clean permanent shutdown (winsdk missing) or
    after a transient exit (access denied, internal error). Transient exits
    are retried with a short backoff so a momentary failure does not stop
    native mirroring for the rest of the session.
    """
    while True:
        try:
            result = asyncio.run(_listen(manager))
            if result == "permanent":
                return
            applog.get_logger().warning("listener exited; restarting in 5s")
        except Exception:  # pragma: no cover - best-effort background mirror
            applog.get_logger().exception("listener crashed; restarting in 5s")
        time.sleep(5)


async def _get_app_icon(app_info, aumid, app_name=""):
    """Best-effort fetch of the source app's logo/icon, cached to disk.
    Returns a file path, or "" if unavailable."""
    if not aumid or aumid in _ICON_MISSES:
        return ""

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", aumid)
    cache_path = config.ICON_CACHE_DIR / f"{safe}.png"
    if cache_path.exists():
        return str(cache_path)

    if app_info:
        try:
            from winsdk.windows.foundation import Size
            from winsdk.windows.storage.streams import DataReader

            logo_ref = app_info.display_info.get_logo(Size(48, 48))
            if logo_ref is not None:
                stream = await logo_ref.open_read_async()
                size = stream.size
                if size:
                    reader = DataReader(stream)
                    await reader.load_async(size)
                    buf = bytearray(size)
                    reader.read_bytes(buf)
                    data = bytes(buf)

                    config.ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    with open(cache_path, "wb") as f:
                        f.write(data)
                    return str(cache_path)
        except Exception:
            pass

    # Fall back to extracting the icon from the source app's .exe — many
    # win32 apps don't expose a logo via the toast API. WMI lookups and
    # icon extraction are blocking, so run them off the event loop.
    def _extract():
        exe_path = find_exe_for_app(app_name)
        if not exe_path:
            return None
        return extract_exe_icon(exe_path, 48)

    try:
        loop = asyncio.get_running_loop()
        # Cap the WMI / icon-extraction fallback so a stuck query can't
        # hang the listener indefinitely.
        img = await asyncio.wait_for(loop.run_in_executor(None, _extract), timeout=5.0)
        if img is None:
            _ICON_MISSES.add(aumid)
            return ""
        config.ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cache_path)
        return str(cache_path)
    except Exception:
        _ICON_MISSES.add(aumid)
        return ""


async def _listen(manager):
    """Mirror native Windows notifications.

    Returns "permanent" if winsdk is missing (no point retrying), otherwise
    returns None so the caller will restart us after a backoff.
    """
    try:
        from winsdk.windows.ui.notifications import KnownNotificationBindings, NotificationKinds
        from winsdk.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
    except ImportError:
        applog.get_logger().warning("winsdk not installed; native mirroring disabled")
        return "permanent"

    listener = UserNotificationListener.current
    status = await listener.request_access_async()
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        applog.get_logger().warning("notification access not granted (%s); retrying later", status)
        return None

    binding_id = KnownNotificationBindings.toast_generic

    # Don't replay everything already sitting in Action Center — only mirror
    # notifications that arrive from this point on.
    seen = set()
    initial = await listener.get_notifications_async(NotificationKinds.TOAST)
    for n in initial:
        seen.add(n.id)

    while True:
        try:
            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception:
            await asyncio.sleep(POLL_INTERVAL_SEC)
            continue
        current_ids = set()
        for n in notifications:
            try:
                current_ids.add(n.id)
                if n.id in seen:
                    continue
                seen.add(n.id)

                try:
                    binding = n.notification.visual.get_binding(binding_id)
                    texts = [t.text for t in binding.get_text_elements()]
                except Exception:
                    texts = []

                app_name = n.app_info.display_info.display_name if n.app_info else "Windows"
                aumid = n.app_info.app_user_model_id if n.app_info else ""
                title = texts[0] if texts else app_name
                message = " — ".join(texts[1:]) if len(texts) > 1 else (texts[0] if texts else "")

                if not title and not message:
                    continue

                if manager.is_app_excluded(app_name, aumid):
                    continue

                launch_url = ""
                toast_tag = ""
                try:
                    _xml, activation, toast_tag, _group = find_toast_info(n)
                    launch_url = best_launch_target(activation).get("value", "")
                    if beeper_deeplink.is_beeper_aumid(aumid, app_name):
                        deeplink = beeper_deeplink.capture_recent_deeplink()
                        if deeplink:
                            launch_url = deeplink
                except Exception:
                    applog.get_logger().exception("activation read error")

                kind = _guess_kind(title, message)
                icon_path = await _get_app_icon(n.app_info, aumid, app_name)
                manager.notify(message or title, title=title if message else app_name, kind=kind,
                               aumid=aumid, icon_path=icon_path, app_name=app_name, launch_url=launch_url,
                               toast_tag=toast_tag)
            except Exception:
                applog.get_logger().exception("skipped bad notification")

        seen &= current_ids

        await asyncio.sleep(POLL_INTERVAL_SEC)
