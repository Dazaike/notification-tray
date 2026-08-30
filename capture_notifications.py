"""Capture activation payloads from Windows 11 Action Center toasts.

Run while notifications arrive (or while some are already in Action Center):

    python capture_notifications.py

Output is printed to the console and appended to ~/.notif_tray_capture.jsonl

Notes:
- UserNotificationListener can read title/body but NOT launch/actions directly.
- ToastNotificationManager.history (per AUMID) exposes the full toast XML.
- We cannot hook native *clicks* — only capture data when a toast appears.
- Apps like Discord/Equibop may omit deep links from XML and route clicks
  in-process via Electron; the log will show whether that is the case.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from toast_history import best_launch_target, find_toast_info

CAPTURE_PATH = Path.home() / ".notif_tray_capture.jsonl"
POLL_INTERVAL_SEC = 0.5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(record: dict) -> None:
    line = json.dumps(record, ensure_ascii=False)
    print(line)
    with open(CAPTURE_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _record_from_notification(user_notification, event: str) -> dict:
    app_name = ""
    aumid = ""
    try:
        if user_notification.app_info:
            app_name = user_notification.app_info.display_info.display_name or ""
            aumid = user_notification.app_info.app_user_model_id or ""
    except Exception:
        pass

    xml_text, activation, toast_tag, toast_group = find_toast_info(user_notification)
    target = best_launch_target(activation)

    texts = []
    try:
        from winsdk.windows.ui.notifications import KnownNotificationBindings

        binding = user_notification.notification.visual.get_binding(
            KnownNotificationBindings.toast_generic
        )
        if binding is not None:
            elements = binding.get_text_elements()
            texts = [elements.get_at(i).text for i in range(elements.size)]
    except Exception:
        pass

    return {
        "time": _now(),
        "event": event,
        "notification_id": int(user_notification.id),
        "app_name": app_name,
        "aumid": aumid,
        "texts": texts,
        "launch": activation.get("launch", ""),
        "launch_activation_type": activation.get("launch_activation_type", ""),
        "toast_tag": toast_tag,
        "toast_group": toast_group,
        "actions": activation.get("actions", []),
        "best_target": target,
        "raw_xml": xml_text,
    }


async def _dump_existing(listener) -> None:
    from winsdk.windows.ui.notifications import NotificationKinds

    notes = await listener.get_notifications_async(NotificationKinds.TOAST)
    print(f"Found {len(notes)} toast(s) already in Action Center.")
    for note in notes:
        _log(_record_from_notification(note, "existing"))


async def main() -> None:
    try:
        from winsdk.windows.ui.notifications import NotificationKinds, UserNotificationChangedKind
        from winsdk.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
    except ImportError:
        print("winsdk is required: pip install winsdk")
        return

    listener = UserNotificationListener.current
    status = await listener.request_access_async()
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        print(f"Notification access not granted ({status}).")
        print("Enable it in Settings > Privacy & security > Notifications.")
        return

    print(f"Logging to {CAPTURE_PATH}")
    print("Trigger a notification, then check the log. Ctrl+C to stop.\n")

    await _dump_existing(listener)

    seen: set[int] = set()
    initial = await listener.get_notifications_async(NotificationKinds.TOAST)
    for note in initial:
        seen.add(int(note.id))

    cache: dict[int, dict] = {}

    def on_changed(sender, args):
        note_id = int(args.user_notification_id)
        if args.change_kind == UserNotificationChangedKind.ADDED:
            try:
                note = sender.get_notification(note_id)
            except Exception:
                return
            if note is None or note_id in seen:
                return
            seen.add(note_id)
            record = _record_from_notification(note, "added")
            cache[note_id] = record
            _log(record)
        elif args.change_kind == UserNotificationChangedKind.REMOVED and note_id in cache:
            record = dict(cache.pop(note_id))
            record["time"] = _now()
            record["event"] = "removed"
            record["note"] = (
                "Removed from Action Center (clicked or dismissed). "
                "Windows does not tell us which."
            )
            _log(record)

    token = None
    try:
        token = listener.add_notification_changed(on_changed)
    except OSError as exc:
        print(f"NotificationChanged hook unavailable ({exc}); using polling only.")

    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SEC)
            notes = await listener.get_notifications_async(NotificationKinds.TOAST)
            for note in notes:
                note_id = int(note.id)
                if note_id in seen:
                    continue
                seen.add(note_id)
                record = _record_from_notification(note, "added")
                cache[note_id] = record
                _log(record)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if token is not None:
            listener.remove_notification_changed(token)


if __name__ == "__main__":
    asyncio.run(main())
