"""NotificationManager — owns the hidden root window, the queue, and active toasts."""

import json
import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
import config
import emoji_render
import gemini_summarizer
import beeper_deeplink
import launch_utils
import sound
import startup
import toast_activate
from app_utils import focus_running_app, get_exe_display_name, get_foreground_exe_stem, is_app_running
from monitor_utils import get_monitor_rect, get_monitor_scale
from toast import Toast


class NotificationManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.queue = queue.Queue()
        self.active = []
        self.history = []
        self.lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._persist_job = None
        self._animating = set()
        self._anim_job = None
        self._countdown_job = None
        self.position = config.DEFAULT_POSITION
        self.monitor = config.DEFAULT_MONITOR
        self.durations = {kind: config.DURATION_MS for kind in config.ICONS}
        self.accent_color = config.DEFAULT_ACCENT
        self.font_path = config.DEFAULT_FONT_PATH
        self.excluded_apps = []  # list of {"path": str, "name": str}
        self.app_colors = []    # list of {"exe": str, "color": str}
        self.dnd = False
        self.suppress_focused_app = True
        self.sound_enabled = True
        self._last_sound_ts = 0.0
        self.toast_alpha = config.TOAST_ALPHA
        self.unread_count = 0
        self.on_unread_change = None  # optional callback(count)
        self.gemini_enabled = True
        self.on_history_change = None  # optional callback()
        self._load_settings()
        config.apply_scale(get_monitor_scale(self.monitor))
        try:
            self.root.tk.call("tk", "scaling", 96.0 * config.SCALE / 72.0)
        except tk.TclError:
            pass
        emoji_render.set_custom_font_path(self.font_path)
        self.start_on_login = startup.is_enabled()

        self._poll_queue()
        self._tick_countdowns()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def notify(self, message: str, title: str = "", kind: str = "info", aumid: str = "", icon_path: str = "",
               app_name: str = "", launch_url: str = "", toast_tag: str = "") -> None:
        """Thread-safe. Can be called from any thread."""
        normalized = tuple(
            emoji_render.normalize_text(value)
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
            emoji_render.normalize_text(summary) if summary is not None else message,
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

    def run(self):
        self.root.mainloop()

    # ------------------------------------------------------------------
    # Queue / toast lifecycle
    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag = self.queue.get_nowait()
                try:
                    self._show_toast(message, title, kind, aumid, icon_path, app_name, launch_url, toast_tag)
                except Exception as exc:
                    print(f"[manager] dropped bad notification: {exc}")
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._poll_queue)

    def _show_toast(self, message, title, kind, aumid="", icon_path="", app_name="", launch_url="", toast_tag=""):
        if self.is_app_excluded(app_name, aumid):
            return

        suppressed = self.is_focus_suppressed(app_name, aumid)
        group_key = f"{aumid or app_name}\x1f{title or kind}".strip().lower()

        with self.lock:
            entry = {
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
        if self.sound_enabled and (now - self._last_sound_ts) * 1000 >= config.SOUND_COOLDOWN_MS:
            self._last_sound_ts = now
            sound.play_notification_sound()

        with self.lock:
            existing = None
            if config.GROUP_WINDOW_SEC > 0:
                for toast in self.active:
                    if toast.alive and toast.group_key == group_key and (time.monotonic() - toast.created_at) <= config.GROUP_WINDOW_SEC:
                        existing = toast
                        break

            if existing is not None:
                existing.group_count += 1
                existing.aumid = aumid
                existing.toast_tag = toast_tag or existing.toast_tag
                if icon_path:
                    existing.icon_path = icon_path
                if launch_url:
                    existing.launch_url = launch_url
                existing.history_entries.append(entry)
                existing.refresh(message, title, kind, existing.group_count, app_name=app_name)
                self._bump_unread()
                self._restack()
                if self.on_history_change:
                    self.on_history_change()
                self.save_history()
                return

        toast = Toast(self, message, title, kind, group_key=group_key, aumid=aumid, icon_path=icon_path,
                       app_name=app_name, launch_url=launch_url, toast_tag=toast_tag)
        toast.history_entries = [entry]
        self._place_off_screen(toast)

        with self.lock:
            self.active.append(toast)

        self._restack()
        toast.start_countdown(self.duration_for(kind))
        self._bump_unread()
        if self.on_history_change:
            self.on_history_change()
        self.save_history()
    # ------------------------------------------------------------------
    # Activation (click-through to source app)
    # ------------------------------------------------------------------
    def activate(self, toast):
        self.remove_history_entries(toast.history_entries)
        source_hwnd = None
        try:
            source_hwnd = toast.win.winfo_id()
        except tk.TclError:
            pass
        self._launch_app(
            toast.aumid,
            toast.launch_url,
            toast_tag=toast.toast_tag,
            title=toast.title,
            message=toast.message,
            app_name=toast.app_name,
            source_hwnd=source_hwnd,
        )
        toast.dismiss()

    def remove_history_entries(self, entries):
        with self.lock:
            for entry in entries:
                if entry in self.history:
                    self.history.remove(entry)
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
        self.mark_all_read()
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
    def _place_off_screen(self, toast):
        """Position a brand-new toast just outside the screen edge it will
        slide in from, so the entry animation is a straight slide rather
        than a diagonal move from a fixed off-screen point."""
        rect = get_monitor_rect(self.monitor)

        with self.lock:
            toasts = list(self.active)

        ty = rect.y + config.MARGIN
        for prev in toasts:
            if not prev.alive:
                continue
            ty += prev.card_height + config.NOTIF_GAP
        if self.position == "right":
            sx = rect.x + rect.width
            sy = ty
        elif self.position == "left":
            sx = rect.x - config.NOTIF_WIDTH - config.SHADOW_OFFSET
            sy = ty
        else:  # center
            sx = rect.x + (rect.width - config.NOTIF_WIDTH) // 2
            sy = rect.y - config.NOTIF_HEIGHT - config.SHADOW_OFFSET - config.MARGIN

        toast.win.geometry(f"+{sx}+{sy}")
        toast.cur_x, toast.cur_y = sx, sy

    def _restack(self):
        rect = get_monitor_rect(self.monitor)

        with self.lock:
            toasts = list(self.active)

        ty = rect.y + config.MARGIN
        for toast in toasts:
            if not toast.alive:
                continue
            if self.position == "right":
                tx = rect.x + rect.width - config.NOTIF_WIDTH - config.MARGIN
            elif self.position == "left":
                tx = rect.x + config.MARGIN
            else:  # center
                tx = rect.x + (rect.width - config.NOTIF_WIDTH) // 2

            toast.animate_to(tx, ty)
            ty += toast.card_height + config.NOTIF_GAP

    def remove(self, toast):
        with self.lock:
            if toast in self.active:
                self.active.remove(toast)
        self._restack()

    def clear_all(self, animate=True):
        with self.lock:
            toasts = list(self.active)
        for toast in toasts:
            toast.dismiss(animate=animate)

    # ------------------------------------------------------------------
    # Animation & countdown tickers
    # ------------------------------------------------------------------
    def register_animation(self, toast):
        self._animating.add(toast)
        if self._anim_job is None:
            self._anim_job = self.root.after(config.ANIM_FRAME_MS, self._tick_animations)

    def unregister_animation(self, toast):
        self._animating.discard(toast)

    def _tick_animations(self):
        self._anim_job = None
        now = time.monotonic()
        for toast in list(self._animating):
            anim = toast.anim
            if anim is None:
                self._animating.discard(toast)
                continue
            t = 1.0 if anim["dur"] <= 0 else min(1.0, (now - anim["t0"]) / anim["dur"])
            if toast.apply_frame(t):
                self._animating.discard(toast)
        if self._animating:
            self._anim_job = self.root.after(config.ANIM_FRAME_MS, self._tick_animations)

    def _tick_countdowns(self):
        with self.lock:
            toasts = list(self.active)
        for toast in toasts:
            if toast.tick_countdown():
                toast.dismiss()
        self._countdown_job = self.root.after(config.COUNTDOWN_TICK_MS, self._tick_countdowns)
    # ------------------------------------------------------------------
    # Appearance / startup
    # ------------------------------------------------------------------
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
        return True

    def set_font_path(self, path: str) -> bool:
        """Set the font file used for notification text. Pass "" to reset to default."""
        path = (path or "").strip()
        if path and not emoji_render.font_file_is_loadable(path):
            return False
        self.font_path = path
        emoji_render.set_custom_font_path(path)
        self.save_settings()
        return True

    def set_start_on_login(self, enabled: bool) -> None:
        try:
            startup.set_enabled(enabled)
            self.start_on_login = enabled
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Do Not Disturb
    # ------------------------------------------------------------------
    def toggle_dnd(self):
        self.dnd = not self.dnd
        self.save_settings()
        return self.dnd

    # ------------------------------------------------------------------
    # Focused-app suppression
    # ------------------------------------------------------------------
    def toggle_suppress_focused_app(self):
        self.suppress_focused_app = not self.suppress_focused_app
        self.save_settings()
        return self.suppress_focused_app

    def is_focus_suppressed(self, app_name: str, aumid: str = "") -> bool:
        if not self.suppress_focused_app:
            return False
        fg_stem = get_foreground_exe_stem()
        if not fg_stem:
            return False
        haystack = f"{app_name} {aumid}".lower()
        return fg_stem in haystack

    # ------------------------------------------------------------------
    # App exclusions
    # ------------------------------------------------------------------
    def add_excluded_app(self, path: str):
        name = get_exe_display_name(path)
        for entry in self.excluded_apps:
            if entry["path"] == path:
                return
        self.excluded_apps.append({"path": path, "name": name})
        self.save_settings()

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
                return
        self.app_colors.append({"exe": exe, "color": color})
        self.save_settings()

    def remove_app_color(self, index: int):
        if 0 <= index < len(self.app_colors):
            del self.app_colors[index]
            self.save_settings()

    def remove_excluded_app(self, index: int):
        if 0 <= index < len(self.excluded_apps):
            del self.excluded_apps[index]
            self.save_settings()

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

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
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
        self.monitor = data.get("monitor", self.monitor)
        stored = data.get("durations")
        if isinstance(stored, dict):
            for kind in config.ICONS:
                if isinstance(stored.get(kind), (int, float)):
                    self.durations[kind] = max(1000, min(60000, int(stored[kind])))
        elif isinstance(data.get("duration_ms"), (int, float)):
            legacy = max(1000, min(60000, int(data["duration_ms"])))
            self.durations = {kind: legacy for kind in config.ICONS}
        self.accent_color = data.get("accent_color", self.accent_color)
        self.font_path = data.get("font_path", self.font_path)
        self.excluded_apps = data.get("excluded_apps", self.excluded_apps)
        self.app_colors = data.get("app_colors", self.app_colors)
        self.dnd = data.get("dnd", self.dnd)
        self.suppress_focused_app = data.get("suppress_focused_app", self.suppress_focused_app)
        self.sound_enabled = bool(data.get("sound_enabled", self.sound_enabled))
        self.gemini_enabled = bool(data.get("gemini_enabled", self.gemini_enabled))
        try:
            self.toast_alpha = float(data.get("toast_alpha", self.toast_alpha))
            self.toast_alpha = max(config.MIN_TOAST_ALPHA, min(1.0, self.toast_alpha))
        except (ValueError, TypeError):
            self.toast_alpha = config.TOAST_ALPHA
        self.history = data.get("history", self.history)

        if self.position not in ("right", "center", "left"):
            self.position = config.DEFAULT_POSITION
        if not isinstance(self.monitor, int) or self.monitor < 0:
            self.monitor = config.DEFAULT_MONITOR
        if not isinstance(self.history, list):
            self.history = []
        self.history = self.history[-config.HISTORY_LIMIT:]

    def duration_for(self, kind: str) -> int:
        return int(self.durations.get(kind if kind in config.ICONS else "info", config.DURATION_MS))

    def set_duration(self, kind: str, duration_ms: int) -> None:
        if kind in config.ICONS:
            self.durations[kind] = max(1000, min(60000, int(duration_ms)))
            self.save_settings()

    def toggle_sound(self) -> bool:
        self.sound_enabled = not self.sound_enabled
        self.save_settings()
        return self.sound_enabled

    def set_toast_alpha(self, value: float) -> None:
        self.toast_alpha = max(config.MIN_TOAST_ALPHA, min(1.0, float(value)))
        with self.lock:
            toasts = [t for t in self.active if t.alive]
        for toast in toasts:
            toast.animate_to(toast.cur_x, toast.cur_y)
        self.save_settings()


    def set_gemini_enabled(self, enabled: bool) -> None:
        self.gemini_enabled = bool(enabled)
        self.save_settings()

    def save_gemini_api_key(self, api_key: str) -> bool:
        return gemini_summarizer.save_api_key(api_key)
    def save_settings(self):
        """Persist settings immediately (user actions, quit, explicit Save)."""
        self._persist_now()

    def save_history(self):
        """Debounced persist for notification history churn.

        Every mirrored toast used to rewrite the full config JSON synchronously
        on the Tk main thread; under a burst of notifications that stalls the
        event loop and makes the tray menu feel frozen.
        """
        if self._persist_job is not None:
            self.root.after_cancel(self._persist_job)
        self._persist_job = self.root.after(400, self._persist_debounced)

    def flush_persist(self):
        """Write any pending debounced state now (e.g. on quit)."""
        if self._persist_job is not None:
            self.root.after_cancel(self._persist_job)
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
                "durations": dict(self.durations),
                "accent_color": self.accent_color,
                "font_path": self.font_path,
                "excluded_apps": list(self.excluded_apps),
                "app_colors": list(self.app_colors),
                "dnd": self.dnd,
                "suppress_focused_app": self.suppress_focused_app,
                "sound_enabled": self.sound_enabled,
                "toast_alpha": self.toast_alpha,
                "history": list(self.history),
                "gemini_enabled": self.gemini_enabled,
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
        self.clear_all(animate=False)
        self.flush_persist()
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass
