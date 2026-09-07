"""Core service — NDJSON stdio server orchestrating NotificationManager."""

import json
import sys
import threading
from pathlib import Path

import config
import gemini_summarizer
import tray_image
import windows_listener
from manager import NotificationManager
from monitor_utils import get_all_monitors, invalidate_monitor_cache

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_stdout_lock = threading.Lock()


def send_frame(frame: dict) -> None:
    line = json.dumps(frame, separators=(",", ":"), ensure_ascii=False)
    with _stdout_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def send_event(name: str, data: any) -> None:
    send_frame({"t": "ev", "name": name, "data": data})


def send_response(req_id: int, ok: bool, data: any = None, error: str = "") -> None:
    frame = {"t": "res", "id": req_id, "ok": ok, "data": data}
    if error:
        frame["error"] = error
    send_frame(frame)


def get_monitors_payload() -> list[dict]:
    invalidate_monitor_cache()
    raw = get_all_monitors()
    result = []
    for i, m in enumerate(raw):
        result.append({
            "index": i,
            "device": m.device,
            "x": m.x,
            "y": m.y,
            "width": m.width,
            "height": m.height,
            "primary": bool(m.primary),
        })
    return result


def validate_font(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_file() and p.suffix.lower() in (".ttf", ".otf", ".woff2")


def main() -> None:
    manager = NotificationManager()

    manager.on_toast = lambda entry: send_event("toast", entry)
    manager.on_history_change = lambda: send_event("history", {"history": manager.history})
    manager.on_unread_change = lambda count: send_event("unread", {"count": count})
    manager.on_settings_change = lambda: send_event("settings", manager.to_settings_dict())

    windows_listener.start(manager)

    # Emit ready event once after init
    send_event("ready", {
        "version": config.__version__,
        "settings": manager.to_settings_dict(),
        "history": manager.history,
        "unread": manager.unread_count,
        "monitors": get_monitors_payload(),
    })

    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            break

        if not line:  # EOF
            break

        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception as exc:
            sys.stderr.write(f"Malformed JSON: {exc}\n")
            sys.stderr.flush()
            continue

        if not isinstance(req, dict) or req.get("t") != "req":
            continue

        req_id = req.get("id", 0)
        op = req.get("op", "")
        args = req.get("args") or {}

        try:
            if op == "activate":
                ids = args.get("ids") or []
                manager.activate(ids)
                send_response(req_id, True, None)

            elif op == "dismissHistory":
                ids = args.get("ids") or []
                manager.remove_history_entries(ids)
                send_response(req_id, True, None)

            elif op == "clearHistory":
                manager.clear_history()
                send_response(req_id, True, None)

            elif op == "markAllRead":
                manager.mark_all_read()
                send_response(req_id, True, None)

            elif op == "setSetting":
                key = args.get("key", "")
                value = args.get("value")
                ok = False
                if key == "position":
                    ok = manager.set_position(value)
                elif key == "tray_click_action":
                    ok = manager.set_tray_click_action(value)
                elif key == "monitor":
                    manager.set_monitor(value)
                    ok = True
                elif key == "monitor_device":
                    manager.set_monitor(manager.monitor, value)
                    ok = True
                elif key == "multi_monitor":
                    manager.set_multi_monitor(bool(value))
                    ok = True

                elif key.startswith("duration."):
                    kind = key.split(".", 1)[1]
                    manager.set_duration(kind, value)
                    ok = True
                elif key == "accent_color":
                    ok = manager.set_accent_color(value)
                elif key == "font_path":
                    ok = manager.set_font_path(value)
                elif key == "toast_alpha":
                    manager.set_toast_alpha(value)
                    ok = True
                elif key == "toast_scale":
                    manager.set_toast_scale(value)
                    ok = True
                elif key == "sound_enabled":
                    manager.set_sound_enabled(value)
                    ok = True
                elif key == "dnd":
                    manager.set_dnd(value)
                    ok = True
                elif key == "suppress_focused_app":
                    manager.set_suppress_focused_app(value)
                    ok = True
                elif key == "gemini_enabled":
                    manager.set_gemini_enabled(value)
                    ok = True
                elif key == "custom_sound_path":
                    ok = manager.set_custom_sound_path(value)
                elif key == "animation_preset" or key.startswith("anim_"):
                    ok = manager.set_animation_setting(key, value)
                send_response(req_id, True, {"ok": ok})

            elif op == "addExcludedApp":
                path = args.get("path", "")
                manager.add_excluded_app(path)
                send_response(req_id, True, None)

            elif op == "removeExcludedApp":
                index = args.get("index", -1)
                manager.remove_excluded_app(index)
                send_response(req_id, True, None)

            elif op == "addAppColor":
                exe = args.get("exe", "")
                color = args.get("color", "")
                manager.add_app_color(exe, color)
                send_response(req_id, True, None)

            elif op == "removeAppColor":
                index = args.get("index", -1)
                manager.remove_app_color(index)
                send_response(req_id, True, None)

            elif op == "saveGeminiKey":
                key = args.get("key", "")
                ok = manager.save_gemini_api_key(key)
                send_response(req_id, True, {"ok": ok})

            elif op == "geminiKeyPresent":
                present = gemini_summarizer.is_configured()
                send_response(req_id, True, {"present": present})

            elif op == "notify":
                message = args.get("message", "")
                title = args.get("title", "")
                kind = args.get("kind", "info")
                app_name = args.get("app_name", "")
                manager.notify(message, title=title, kind=kind, app_name=app_name)
                send_response(req_id, True, None)
            elif op == "testSound":
                path = args.get("path") or manager.custom_sound_path
                sound.play_notification_sound(path)
                send_response(req_id, True, None)


            elif op == "monitors":
                payload = get_monitors_payload()
                send_response(req_id, True, {"monitors": payload})
            elif op == "getState":
                send_response(req_id, True, {
                    "version": config.__version__,
                    "settings": manager.to_settings_dict(),
                    "history": manager.history,
                    "unread": manager.unread_count,
                    "monitors": get_monitors_payload(),
                })

            elif op == "getSettings":
                send_response(req_id, True, {
                    "settings": manager.to_settings_dict(),
                    "monitors": get_monitors_payload(),
                })

            elif op == "getHistory":
                send_response(req_id, True, {
                    "history": manager.history,
                    "unread": manager.unread_count,
                })

            elif op == "trayIcon":
                size = args.get("size", 16)
                data_url = tray_image.render_tray_png(manager.unread_count, manager.accent_color, size)
                send_response(req_id, True, {"dataUrl": data_url})

            elif op == "validateFont":
                path = args.get("path", "")
                ok = validate_font(path)
                send_response(req_id, True, {"ok": ok})

            elif op == "shutdown":
                send_response(req_id, True, None)
                manager.shutdown()
                break

            else:
                send_response(req_id, False, None, f"unknown op: {op}")

        except Exception as exc:
            sys.stderr.write(f"Error handling op {op}: {exc}\n")
            sys.stderr.flush()
            send_response(req_id, False, None, str(exc))

    manager.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
