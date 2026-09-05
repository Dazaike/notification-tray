"""NotificationManager — owns notification capture, history, persistence, and activation."""

import json
import os
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import applog
import config
import text_utils
import gemini_summarizer
import beeper_deeplink
import launch_utils
import sound
import toast_activate
from app_utils import focus_running_app, get_exe_display_name, get_foreground_exe_stem, is_app_running
from monitor_utils import device_for_index, get_monitor_rect, resolve_monitor_index


class NotificationManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.history = []
        self.lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._persist_job = None
        self._shutdown_event = threading.Event()

        self.position = config.DEFAULT_POSITION
        self.monitor = config.DEFAULT_MONITOR
        self.monitor_device = ""
        self.durations = {kind: config.DURATION_MS for kind in config.KINDS}
        self.accent_color = config.DEFAULT_ACCENT
        self.font_path = config.DEFAULT_FONT_PATH
        self.excluded_apps = []  # list of {"path": str, "name": str}
        self.app_colors = []    # list of {"exe": str, "color": str}
        self.dnd = False
        self.suppress_focused_app = True
        self.sound_enabled = True
        self._last_sound_ts = 0.0
        self.custom_sound_path = config.DEFAULT_CUSTOM_SOUND_PATH
        self.toast_alpha = config.TOAST_ALPHA
        self.toast_scale = config.DEFAULT_TOAST_SCALE
        self.unread_count = 0
        self.gemini_enabled = True
        self.animation_preset = config.DEFAULT_ANIMATION_PRESET
        self.anim_incoming = config.DEFAULT_ANIM_INCOMING
        self.anim_outgoing = config.DEFAULT_ANIM_OUTGOING
        self.anim_direction = config.DEFAULT_ANIM_DIRECTION
        self.anim_duration = config.DEFAULT_ANIM_DURATION
        self.anim_easing = config.DEFAULT_ANIM_EASING
        self.anim_distance = config.DEFAULT_ANIM_DISTANCE
        self.anim_bounce = config.DEFAULT_ANIM_BOUNCE
        self.anim_blur = config.DEFAULT_ANIM_BLUR
        self.anim_scale = config.DEFAULT_ANIM_SCALE

        # Callbacks bound by core service
        self.on_toast = None           # callback(entry: dict)
        self.on_history_change = None  # callback()
        self.on_unread_change = None   # callback(count: int)
        self.on_settings_change = None # callback()

        self._load_settings()

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        applog.get_logger().info("NotificationManager initialized, monitor index=%s device=%s",
                                 self.monitor, self.monitor_device)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def notify(self, message: str, title: str = "", kind: str = "info", aumid: str = "", icon_path: str = "",
               app_name: str = "", launch_url: str = "", toast_tag: str = "") -> None:
        """Thread-safe. Can be called from any thread."""
        normalized = tuple(
            text_utils.normalize_text(value)
            for value in (message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag)
        )
        if (self.gemini_enabled and gemini_summarizer.should_summarize(normalized[0])
                and gemini_summarizer.is_configured()):
            threading.Thread(
                target=self._summarize_and_enqueue,
                args=normalized,
                daemon=True,
            ).start()
            return
        self._enqueue(*normalized)

    def _summarize_and_enqueue(self, message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag):
        summary = gemini_summarizer.summarize(message)
        self._enqueue(
            text_utils.normalize_text(summary) if summary is not None else message,
            title,
            kind,
            aumid,
            icon_path,
            app_name,
            launch_url,
            toast_tag,
        )

    def _enqueue(self, message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag):
        self.queue.put((message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag))

    # ------------------------------------------------------------------
    # Queue / worker loop
    # ------------------------------------------------------------------
    def _worker_loop(self):
        while not self._shutdown_event.is_set():
            try:
                item = self.queue.get()
                if item is None or self._shutdown_event.is_set():
                    break
                message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag = item
                try:
                    self._show_toast(message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag)
                except Exception:
                    applog.get_logger().exception("dropped bad notification")
            except Exception:
                applog.get_logger().exception("worker error in notification queue")

    def _show_toast(self, message, title, kind, aumid="", icon_path="", app_name="", launch_url="", toast_tag=""):
        if self.is_app_excluded(app_name, aumid):
            return

        suppressed = self.is_focus_suppressed(app_name, aumid)
        group_key = f"{aumid or app_name}\x1f{title or kind}".strip().lower()
        entry_id = uuid.uuid4().hex

        with self.lock:
            entry = {
                "id": entry_id,
                "group_key": group_key,
                "message": message,
                "title": title,
                "kind": kind,
                "aumid": aumid,
                "icon_path": icon_path,
                "app_name": app_name,
                "launch_url": launch_url,
                "toast_tag": toast_tag,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "ts": time.time(),
                "read": False,
            }
            self.history.append(entry)
            if len(self.history) > config.HISTORY_LIMIT:
                self.history = self.history[-config.HISTORY_LIMIT:]

        if suppressed:
            self._bump_unread()
            if self.on_history_change:
                self.on_history_change()
            self.save_history()
            return

        if self.dnd:
            self._bump_unread()
            if self.on_history_change:
                self.on_history_change()
            self.save_history()
            return

        now = time.monotonic()
        cooldown_ms = getattr(config, "SOUND_COOLDOWN_MS", 1500)
        if self.sound_enabled and (now - self._last_sound_ts) * 1000 >= cooldown_ms:
            self._last_sound_ts = now
            sound.play_notification_sound(self.custom_sound_path)

        if self.on_toast:
            self.on_toast(entry)
        self._bump_unread()
        if self.on_history_change:
            self.on_history_change()
        self.save_history()

    # ------------------------------------------------------------------
    # Activation (click-through to source app)
    # ------------------------------------------------------------------
    def activate(self, entry_ids: list[str]) -> None:
        """Remove the given history entries and launch the source app."""
        if not entry_ids:
            return
        target_ids = set(entry_ids)
        matching_entries = []
        with self.lock:
            for entry in self.history:
                if entry.get("id") in target_ids:
                    matching_entries.append(entry)
        if not matching_entries:
            return
        newest = matching_entries[-1]
        self.remove_history_entries(matching_entries)
        self._launch_app(
            newest.get("aumid", ""),
            newest.get("launch_url", ""),
            toast_tag=newest.get("toast_tag", ""),
            title=newest.get("title", ""),
            message=newest.get("message", ""),
            app_name=newest.get("app_name", ""),
            source_hwnd=None,
        )

    def remove_history_entries(self, entries_or_ids):
        with self.lock:
            ids_to_remove = {
                item if isinstance(item, str) else item.get("id")
                for item in entries_or_ids
            }
            self.history = [e for e in self.history if e.get("id") not in ids_to_remove]
        if self.on_history_change:
            self.on_history_change()
        self.save_history()

    def _launch_app(self, aumid, launch_url="", toast_tag="", title="", message="", app_name="", source_hwnd=None):
        if beeper_deeplink.is_beeper_aumid(aumid, app_name):
            url = launch_url
            if not beeper_deeplink.is_beeper_deeplink(url):
                url = beeper_deeplink.capture_recent_deeplink(max_age_sec=30)
            if url:
                try:
                    os.startfile(url)
                    return
                except OSError:
                    pass

        if toast_tag and aumid and not beeper_deeplink.is_beeper_aumid(aumid, app_name):
            if toast_activate.activate_native_toast(aumid, toast_tag):
                return

        launch_url = launch_utils.normalize_launch_url(launch_url)
        if launch_url:
            try:
                os.startfile(launch_url)
                return
            except OSError:
                pass
        if focus_running_app(aumid, app_name, source_hwnd=source_hwnd):
            return
        if is_app_running(aumid, app_name):
            return
        if not aumid:
            return
        try:
            os.startfile(f"shell:AppsFolder\\{aumid}")
        except OSError:
            pass

    def _bump_unread(self):
        self.unread_count += 1
        if self.on_unread_change:
            self.on_unread_change(self.unread_count)

    def clear_history(self):
        with self.lock:
            self.history = []
        self.unread_count = 0
        if self.on_unread_change:
            self.on_unread_change(self.unread_count)
        if self.on_history_change:
            self.on_history_change()
        self.save_history()

    def mark_all_read(self):
        with self.lock:
            for entry in self.history:
                entry["read"] = True
        self.unread_count = 0
        if self.on_unread_change:
            self.on_unread_change(self.unread_count)
        self.save_history()

    # ------------------------------------------------------------------
    # Appearance / Settings Setters
    # ------------------------------------------------------------------
    def set_position(self, pos: str) -> bool:
        if pos in ("right", "center", "left"):
            self.position = pos
            self.save_settings()
            if self.on_settings_change:
                self.on_settings_change()
            return True
        return False

    def set_monitor(self, index: int, device: str = "") -> None:
        self.monitor = int(index)
        if device:
            self.monitor_device = device
        else:
            self.monitor_device = device_for_index(self.monitor)
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def duration_for(self, kind: str) -> int:
        return int(self.durations.get(kind if kind in config.KINDS else "info", config.DURATION_MS))

    def set_duration(self, kind: str, duration_ms: int) -> None:
        if kind in config.KINDS:
            self.durations[kind] = max(1000, min(60000, int(duration_ms)))
            self.save_settings()
            if self.on_settings_change:
                self.on_settings_change()

    def set_accent_color(self, hex_color: str) -> bool:
        hex_color = hex_color.strip()
        if not hex_color.startswith("#"):
            hex_color = f"#{hex_color}"
        if len(hex_color) != 7:
            return False
        try:
            int(hex_color[1:], 16)
        except ValueError:
            return False
        self.accent_color = hex_color
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()
        return True

    def set_font_path(self, path: str) -> bool:
        """Set the font file used for notification text. Pass "" to reset to default."""
        path = (path or "").strip()
        if path:
            p = Path(path)
            if not (p.is_file() and p.suffix.lower() in (".ttf", ".otf", ".woff2")):
                return False
        self.font_path = path
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()
        return True

    def set_toast_alpha(self, value: float) -> None:
        self.toast_alpha = max(config.MIN_TOAST_ALPHA, min(1.0, float(value)))
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def set_toast_scale(self, value: float) -> None:
        self.toast_scale = max(config.MIN_TOAST_SCALE, min(config.MAX_TOAST_SCALE, float(value)))
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def set_sound_enabled(self, enabled: bool) -> None:
        self.sound_enabled = bool(enabled)
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def toggle_sound(self) -> bool:
        self.set_sound_enabled(not self.sound_enabled)
        return self.sound_enabled

    def set_custom_sound_path(self, path: str) -> bool:
        path = (path or "").strip()
        if path:
            p = Path(path)
            if not (p.is_file() and p.suffix.lower() in (".mp3", ".wav", ".wma", ".aac", ".m4a", ".ogg")):
                return False
        self.custom_sound_path = path
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()
        return True

    def set_dnd(self, enabled: bool) -> None:
        self.dnd = bool(enabled)
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def toggle_dnd(self) -> bool:
        self.set_dnd(not self.dnd)
        return self.dnd

    def set_suppress_focused_app(self, enabled: bool) -> None:
        self.suppress_focused_app = bool(enabled)
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def set_animation_setting(self, key: str, value) -> bool:
        if key == "animation_preset":
            self.animation_preset = str(value)
        elif key == "anim_incoming":
            self.anim_incoming = str(value)
        elif key == "anim_outgoing":
            self.anim_outgoing = str(value)
        elif key == "anim_direction":
            self.anim_direction = str(value)
        elif key == "anim_duration":
            self.anim_duration = max(50, min(3000, int(value)))
        elif key == "anim_easing":
            self.anim_easing = str(value)
        elif key == "anim_distance":
            self.anim_distance = max(10, min(2000, int(value)))
        elif key == "anim_bounce":
            self.anim_bounce = max(0.0, min(1.0, float(value)))
        elif key == "anim_blur":
            self.anim_blur = max(0, min(50, int(value)))
        elif key == "anim_scale":
            self.anim_scale = max(0.1, min(2.0, float(value)))
        else:
            return False
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()
        return True

    def toggle_suppress_focused_app(self) -> bool:
        self.set_suppress_focused_app(not self.suppress_focused_app)
        return self.suppress_focused_app

    def is_focus_suppressed(self, app_name: str, aumid: str = "") -> bool:
        if not self.suppress_focused_app:
            return False
        fg_stem = get_foreground_exe_stem()
        if not fg_stem:
            return False
        haystack = f"{app_name} {aumid}".lower()
        return fg_stem in haystack

    def set_gemini_enabled(self, enabled: bool) -> None:
        self.gemini_enabled = bool(enabled)
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def save_gemini_api_key(self, api_key: str) -> bool:
        return gemini_summarizer.save_api_key(api_key)

    # ------------------------------------------------------------------
    # App exclusions & custom colors
    # ------------------------------------------------------------------
    def add_excluded_app(self, path: str):
        name = get_exe_display_name(path)
        for entry in self.excluded_apps:
            if entry["path"] == path:
                return
        self.excluded_apps.append({"path": path, "name": name})
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def remove_excluded_app(self, index: int):
        if 0 <= index < len(self.excluded_apps):
            del self.excluded_apps[index]
            self.save_settings()
            if self.on_settings_change:
                self.on_settings_change()

    def is_app_excluded(self, app_name: str, aumid: str = "") -> bool:
        haystack = f"{app_name} {aumid}".lower()
        for entry in self.excluded_apps:
            name = entry["name"].lower()
            if name and name in haystack:
                return True
            stem = Path(entry["path"]).stem.lower()
            if stem and stem in haystack:
                return True
        return False

    def get_accent_for_app(self, app_name: str) -> str:
        """Return a per-app accent color if one is configured, else the global accent."""
        if app_name:
            needle = app_name.lower()
            for entry in self.app_colors:
                stem = Path(entry["exe"]).stem.lower()
                if stem and (stem in needle or needle in stem):
                    return entry["color"]
        return self.accent_color

    def add_app_color(self, exe: str, color: str):
        color = color.strip()
        if not color.startswith("#"):
            color = f"#{color}"
        for entry in self.app_colors:
            if entry["exe"].lower() == exe.lower():
                entry["color"] = color
                self.save_settings()
                if self.on_settings_change:
                    self.on_settings_change()
                return
        self.app_colors.append({"exe": exe, "color": color})
        self.save_settings()
        if self.on_settings_change:
            self.on_settings_change()

    def remove_app_color(self, index: int):
        if 0 <= index < len(self.app_colors):
            del self.app_colors[index]
            self.save_settings()
            if self.on_settings_change:
                self.on_settings_change()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def to_settings_dict(self) -> dict:
        with self.lock:
            return {
                "version": config.__version__,
                "position": self.position,
                "monitor": self.monitor,
                "monitor_device": self.monitor_device,
                "durations": dict(self.durations),
                "accent_color": self.accent_color,
                "font_path": self.font_path,
                "excluded_apps": list(self.excluded_apps),
                "app_colors": list(self.app_colors),
                "dnd": self.dnd,
                "suppress_focused_app": self.suppress_focused_app,
                "sound_enabled": self.sound_enabled,
                "toast_alpha": self.toast_alpha,
                "custom_sound_path": self.custom_sound_path,
                "toast_scale": self.toast_scale,
                "gemini_enabled": self.gemini_enabled,
                "animation_preset": self.animation_preset,
                "anim_incoming": self.anim_incoming,
                "anim_outgoing": self.anim_outgoing,
                "anim_direction": self.anim_direction,
                "anim_duration": self.anim_duration,
                "anim_easing": self.anim_easing,
                "anim_distance": self.anim_distance,
                "anim_bounce": self.anim_bounce,
                "anim_blur": self.anim_blur,
                "anim_scale": self.anim_scale,
            }

    def _load_settings(self):
        if not config.CONFIG_PATH.exists():
            return
        try:
            with open(config.CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            try:
                config.CONFIG_PATH.replace(config.CONFIG_PATH.with_suffix(".json.corrupt"))
            except OSError:
                pass
            return
        except OSError:
            return

        self.position = data.get("position", self.position)
        stored_device = data.get("monitor_device")
        if isinstance(stored_device, str) and stored_device:
            self.monitor_device = stored_device
            self.monitor = resolve_monitor_index(stored_device)
        else:
            self.monitor = config.DEFAULT_MONITOR
            self.monitor_device = device_for_index(self.monitor)

        stored = data.get("durations")
        if isinstance(stored, dict):
            for kind in config.KINDS:
                if isinstance(stored.get(kind), (int, float)):
                    self.durations[kind] = max(1000, min(60000, int(stored[kind])))
        elif isinstance(data.get("duration_ms"), (int, float)):
            legacy = max(1000, min(60000, int(data["duration_ms"])))
            self.durations = {kind: legacy for kind in config.KINDS}

        self.accent_color = data.get("accent_color", self.accent_color)
        self.font_path = data.get("font_path", self.font_path)
        self.excluded_apps = data.get("excluded_apps", self.excluded_apps)
        self.app_colors = data.get("app_colors", self.app_colors)
        self.dnd = data.get("dnd", self.dnd)
        self.suppress_focused_app = data.get("suppress_focused_app", self.suppress_focused_app)
        self.sound_enabled = bool(data.get("sound_enabled", self.sound_enabled))
        self.gemini_enabled = bool(data.get("gemini_enabled", self.gemini_enabled))
        self.custom_sound_path = data.get("custom_sound_path", self.custom_sound_path)
        try:
            self.toast_alpha = float(data.get("toast_alpha", self.toast_alpha))
            self.toast_alpha = max(config.MIN_TOAST_ALPHA, min(1.0, self.toast_alpha))
        except (ValueError, TypeError):
            self.toast_alpha = config.TOAST_ALPHA
        try:
            self.toast_scale = float(data.get("toast_scale", self.toast_scale))
            self.toast_scale = max(
                config.MIN_TOAST_SCALE, min(config.MAX_TOAST_SCALE, self.toast_scale)
            )
        except (ValueError, TypeError):
            self.toast_scale = config.DEFAULT_TOAST_SCALE

        self.animation_preset = data.get("animation_preset", self.animation_preset)
        self.anim_incoming = data.get("anim_incoming", self.anim_incoming)
        self.anim_outgoing = data.get("anim_outgoing", self.anim_outgoing)
        self.anim_direction = data.get("anim_direction", self.anim_direction)
        try:
            self.anim_duration = max(50, min(3000, int(data.get("anim_duration", self.anim_duration))))
        except (ValueError, TypeError):
            self.anim_duration = config.DEFAULT_ANIM_DURATION
        self.anim_easing = data.get("anim_easing", self.anim_easing)
        try:
            self.anim_distance = max(10, min(2000, int(data.get("anim_distance", self.anim_distance))))
        except (ValueError, TypeError):
            self.anim_distance = config.DEFAULT_ANIM_DISTANCE
        try:
            self.anim_bounce = max(0.0, min(1.0, float(data.get("anim_bounce", self.anim_bounce))))
        except (ValueError, TypeError):
            self.anim_bounce = config.DEFAULT_ANIM_BOUNCE
        try:
            self.anim_blur = max(0, min(50, int(data.get("anim_blur", self.anim_blur))))
        except (ValueError, TypeError):
            self.anim_blur = config.DEFAULT_ANIM_BLUR
        try:
            self.anim_scale = max(0.1, min(2.0, float(data.get("anim_scale", self.anim_scale))))
        except (ValueError, TypeError):
            self.anim_scale = config.DEFAULT_ANIM_SCALE
        raw_history = data.get("history", self.history)
        if not isinstance(raw_history, list):
            raw_history = []

        # Backfill id and group_key on existing history entries
        for entry in raw_history:
            if isinstance(entry, dict):
                if not entry.get("id"):
                    entry["id"] = uuid.uuid4().hex
                if not entry.get("group_key"):
                    aumid = entry.get("aumid", "")
                    app_name = entry.get("app_name", "")
                    title = entry.get("title", "")
                    kind = entry.get("kind", "")
                    entry["group_key"] = f"{aumid or app_name}\x1f{title or kind}".strip().lower()

        self.history = raw_history[-config.HISTORY_LIMIT:]
        self.unread_count = sum(1 for e in self.history if not e.get("read", False))

        if self.position not in ("right", "center", "left"):
            self.position = config.DEFAULT_POSITION

    def save_settings(self):
        """Persist settings immediately (user actions, quit, explicit Save)."""
        self._persist_now()

    def save_history(self):
        """Debounced persist for notification history churn."""
        if self._persist_job is not None:
            self._persist_job.cancel()
        self._persist_job = threading.Timer(0.4, self._persist_debounced)
        self._persist_job.daemon = True
        self._persist_job.start()

    def flush_persist(self):
        """Write any pending debounced state now (e.g. on quit)."""
        if self._persist_job is not None:
            self._persist_job.cancel()
            self._persist_job = None
        self._persist_now()

    def _persist_debounced(self):
        self._persist_job = None
        self._persist_now()

    def _persist_now(self):
        with self.lock:
            data = {
                "version": config.__version__,
                "position": self.position,
                "monitor": self.monitor,
                "monitor_device": self.monitor_device,
                "durations": dict(self.durations),
                "accent_color": self.accent_color,
                "font_path": self.font_path,
                "excluded_apps": list(self.excluded_apps),
                "app_colors": list(self.app_colors),
                "dnd": self.dnd,
                "suppress_focused_app": self.suppress_focused_app,
                "sound_enabled": self.sound_enabled,
                "toast_alpha": self.toast_alpha,
                "toast_scale": self.toast_scale,
                "custom_sound_path": self.custom_sound_path,
                "history": list(self.history),
                "gemini_enabled": self.gemini_enabled,
                "animation_preset": self.animation_preset,
                "anim_incoming": self.anim_incoming,
                "anim_outgoing": self.anim_outgoing,
                "anim_direction": self.anim_direction,
                "anim_duration": self.anim_duration,
                "anim_easing": self.anim_easing,
                "anim_distance": self.anim_distance,
                "anim_bounce": self.anim_bounce,
                "anim_blur": self.anim_blur,
                "anim_scale": self.anim_scale,
            }
        with self._save_lock:
            tmp = config.CONFIG_PATH.with_name(config.CONFIG_PATH.name + ".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, config.CONFIG_PATH)
            except OSError:
                pass

    def shutdown(self):
        self._shutdown_event.set()
        self.flush_persist()
        try:
            self.queue.put_nowait(None)
        except Exception:
            pass
