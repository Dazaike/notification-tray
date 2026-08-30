"""A single toast notification window."""

import sys
import time
import tkinter as tk
from tkinter import ttk
import config
import emoji_render
from icon_utils import make_fallback_icon, make_rounded_icon

def _pick_font():
    if sys.platform == "win32":
        return ("Segoe UI", 13)
    return ("Helvetica", 13)




def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def _rounded_rect_points(x1, y1, x2, y2, r):
    """Return point list for a smoothed rounded-rectangle polygon."""
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class Toast:
    def __init__(self, manager, message, title="", kind="info", group_key=None, aumid="", icon_path="", app_name="", launch_url="", toast_tag=""):
        self.manager = manager
        self.message = message
        self.title = title
        self.kind = kind if kind in config.ICONS else "info"
        self.group_key = group_key
        self.group_count = 1
        self.messages = [message]
        self.aumid = aumid
        self.icon_path = icon_path
        self.app_name = app_name
        self.launch_url = launch_url
        self.toast_tag = toast_tag
        self.history_entries = []
        self.alive = True
        self.paused = False
        self._remaining_ms = manager.duration_for(self.kind)
        self._duration_ms = self._remaining_ms
        self.created_at = time.monotonic()
        self._deadline = None
        self.cur_x = 10000
        self.cur_y = 10000
        self.cur_alpha = 0.0
        self.anim = None
        self._progress_y = 0
        self._progress_x0 = 0
        self._embedded = []
        self._icon_photo = None
        self._header_photo = None
        self._title_photo = None
        self._msg_photo = None
        self.card_height = config.NOTIF_HEIGHT

        # Reserve room for the shadow plus the deepest peek layer.
        extra = config.SHADOW_OFFSET + config.PEEK_MAX * config.PEEK_OFFSET
        self.total_width = config.NOTIF_WIDTH + extra
        self.total_height = config.NOTIF_HEIGHT + extra

        self.win = tk.Toplevel(manager.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=config.TRANSPARENT_KEY)
        try:
            self.win.attributes("-transparentcolor", config.TRANSPARENT_KEY)
        except tk.TclError:
            pass
        try:
            self.win.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self.win, width=self.total_width, height=self.total_height,
                                 bg=config.TRANSPARENT_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._build_ui()
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", lambda e: self.dismiss())

        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        # Start off-screen; manager will call animate_to() for the real position.
        self.win.geometry(f"{self.total_width}x{self.total_height}+10000+10000")
        self.win.update_idletasks()

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------
    def _on_click(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for item in items:
            if "dismiss" in self.canvas.gettags(item):
                return
        self.manager.activate(self)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _build_ui(self):
        canvas = self.canvas

        for widget in self._embedded:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._embedded = []

        canvas.delete("all")

        font = _pick_font()
        accent = self.manager.get_accent_for_app(self.app_name)

        pad = config.CARD_PAD
        d = config.ICON_DIAMETER
        w = config.NOTIF_WIDTH
        r = config.CORNER_RADIUS
        off = config.SHADOW_OFFSET

        # Text block layout:
        text_x = pad + d + config.scale(12)
        text_w = w - text_x - pad - config.scale(24)

        # Header / app name
        app_display = (self.app_name or self.title or self.kind).strip().upper()
        if len(app_display) > 28:
            app_display = app_display[:27] + "…"

        # Title text
        title_text = self.title or self.kind.capitalize()
        title_text = emoji_render.ellipsize(title_text, config.TITLE_SIZE, text_w)

        # Message lines wrapped
        lines = []
        for msg in self.messages:
            lines.extend(emoji_render.wrap_lines(msg or "", config.MSG_SIZE, text_w))
        truncated = len(lines) > config.MAX_GROUP_LINES
        shown_lines = lines[:config.MAX_GROUP_LINES]
        line_count = max(1, len(shown_lines) + (1 if truncated else 0))

        # Dynamic card height calculation. The bottom two terms reserve
        # whitespace below the message and around the floating progress track.
        header_h = config.APP_HEADER_SIZE + config.scale(4)
        title_h = config.TITLE_SIZE + config.scale(6)
        msg_h = line_count * config.LINE_HEIGHT
        content_h = (
            pad + header_h + config.scale(2) + title_h + config.scale(2) + msg_h
            + config.TEXT_TO_PROGRESS_GAP + config.PROGRESS_BOTTOM_INSET
        )
        min_h = max(config.NOTIF_HEIGHT, pad * 2 + d + config.scale(8))
        h = max(content_h, min_h)
        self.card_height = h

        extra = config.SHADOW_OFFSET + config.PEEK_MAX * config.PEEK_OFFSET
        self.total_width = w + extra
        self.total_height = h + extra
        canvas.config(width=self.total_width, height=self.total_height)
        self.win.geometry(f"{self.total_width}x{self.total_height}")

        # 1. Stacked "peek" cards behind the main card (if grouped)
        peek_count = min(self.group_count - 1, config.PEEK_MAX)
        for i in range(peek_count, 0, -1):
            shift = i * config.PEEK_OFFSET
            canvas.create_polygon(
                _rounded_rect_points(shift, shift, shift + w, shift + h, r),
                smooth=True, fill=config.CARD_COLOR, outline=config.BORDER, width=1)

        # 2. Soft Drop Shadow
        canvas.create_polygon(
            _rounded_rect_points(off, off, off + w, off + h, r),
            smooth=True, fill=config.SHADOW_COLOR, outline="")

        # 3. Main Card Surface
        canvas.create_polygon(
            _rounded_rect_points(0, 0, w, h, r),
            smooth=True, fill=config.CARD_COLOR, outline=config.BORDER, width=1, tags=("card",))

        # 4. Subtle top glass highlight
        canvas.create_line(r, 1, w - r, 1, fill=config.CARD_HIGHLIGHT, width=1, tags=("card",))

        # 5. App Icon (Squircle) / Vector fallback
        icon_x = pad
        icon_y = pad + config.scale(2)
        photo = make_rounded_icon(self.icon_path, d, radius=config.ICON_RADIUS)
        if photo is None:
            photo = make_fallback_icon(self.kind, d, accent, radius=config.ICON_RADIUS)

        if photo is not None:
            self._icon_photo = photo
            canvas.create_image(icon_x, icon_y, image=photo, anchor="nw", tags=("card",))

        # 6. Text Elements
        cur_y = pad

        # Header: App name + relative time
        header_photo = emoji_render.render([app_display], config.APP_HEADER_SIZE, config.HEADER_COLOR,
                                            config.CARD_COLOR, header_h, text_w)
        if header_photo is not None:
            self._header_photo = header_photo
            canvas.create_image(text_x, cur_y, image=header_photo, anchor="nw", tags=("card",))
        else:
            header_lbl = tk.Label(canvas, text=app_display, fg=config.HEADER_COLOR, bg=config.CARD_COLOR,
                                  font=(font[0], config.APP_HEADER_SIZE, "bold"), anchor="w")
            canvas.create_window(text_x, cur_y, window=header_lbl, anchor="nw", width=text_w)
            self._embedded.append(header_lbl)
            header_lbl.bind("<Button-1>", lambda e: self.manager.activate(self))

        cur_y += header_h + config.scale(2)

        # Title
        title_photo = emoji_render.render([title_text], config.TITLE_SIZE, config.FG_COLOR,
                                           config.CARD_COLOR, title_h, text_w)
        if title_photo is not None:
            self._title_photo = title_photo
            canvas.create_image(text_x, cur_y, image=title_photo, anchor="nw", tags=("card",))
        else:
            title_lbl = tk.Label(canvas, text=title_text, fg=config.FG_COLOR, bg=config.CARD_COLOR,
                                 font=(font[0], config.TITLE_SIZE, "bold"), anchor="w", justify="left")
            canvas.create_window(text_x, cur_y, window=title_lbl, anchor="nw", width=text_w)
            self._embedded.append(title_lbl)
            title_lbl.bind("<Button-1>", lambda e: self.manager.activate(self))

        cur_y += title_h + config.scale(2)

        # Message body
        display_lines = list(shown_lines)
        if truncated:
            remaining = len(lines) - len(shown_lines)
            display_lines.append(f"+{remaining} more")

        msg_photo = emoji_render.render(display_lines, config.MSG_SIZE, config.SUBTEXT_COLOR,
                                         config.CARD_COLOR, config.LINE_HEIGHT, text_w)
        if msg_photo is not None:
            self._msg_photo = msg_photo
            canvas.create_image(text_x, cur_y, image=msg_photo, anchor="nw", tags=("card",))
        else:
            msg_text = "\n".join(display_lines)
            msg_lbl = tk.Label(canvas, text=msg_text, fg=config.SUBTEXT_COLOR, bg=config.CARD_COLOR,
                               font=(font[0], config.MSG_SIZE), anchor="nw", justify="left",
                               wraplength=text_w)
            canvas.create_window(text_x, cur_y, window=msg_lbl, anchor="nw", width=text_w)
            self._embedded.append(msg_lbl)
            msg_lbl.bind("<Button-1>", lambda e: self.manager.activate(self))

        # 7. Dismiss Button (Top Right circular target)
        dismiss_cx = w - pad - config.scale(8)
        dismiss_cy = pad + config.scale(8)
        btn_r = config.scale(10)

        dismiss_bg = canvas.create_oval(
            dismiss_cx - btn_r, dismiss_cy - btn_r, dismiss_cx + btn_r, dismiss_cy + btn_r,
            fill="", outline="", tags=("dismiss_target", "dismiss")
        )
        arm = config.scale(4)
        stroke = config.scale(2)
        dismiss_lines = (
            canvas.create_line(
                dismiss_cx - arm, dismiss_cy - arm, dismiss_cx + arm, dismiss_cy + arm,
                fill=config.MUTED, width=stroke, capstyle="round", tags=("dismiss_target", "dismiss"),
            ),
            canvas.create_line(
                dismiss_cx - arm, dismiss_cy + arm, dismiss_cx + arm, dismiss_cy - arm,
                fill=config.MUTED, width=stroke, capstyle="round", tags=("dismiss_target", "dismiss"),
            ),
        )

        def _on_dismiss_enter(e):
            canvas.itemconfig(dismiss_bg, fill=config.HOVER_BG)
            for item in dismiss_lines:
                canvas.itemconfig(item, fill=config.FG_COLOR)
            self.win.config(cursor="hand2")

        def _on_dismiss_leave(e):
            canvas.itemconfig(dismiss_bg, fill="")
            for item in dismiss_lines:
                canvas.itemconfig(item, fill=config.MUTED)
            self.win.config(cursor="")

        canvas.tag_bind("dismiss_target", "<Button-1>", lambda e: self.dismiss())
        canvas.tag_bind("dismiss_target", "<Enter>", _on_dismiss_enter)
        canvas.tag_bind("dismiss_target", "<Leave>", _on_dismiss_leave)

        # 8. Group count badge (if grouped > 1)
        if self.group_count > 1:
            bx = dismiss_cx - btn_r - config.scale(16)
            by = dismiss_cy
            b_r = config.BADGE_RADIUS
            canvas.create_oval(bx - b_r, by - b_r, bx + b_r, by + b_r, fill=config.BADGE_COLOR, outline="")
            label = str(self.group_count) if self.group_count <= 99 else "99+"
            canvas.create_text(bx, by, text=label, fill=config.BADGE_TEXT_COLOR,
                               font=(font[0], 9, "bold"))

        # 9. Floating Progress Bar at bottom of card
        bar_y = h - config.PROGRESS_BOTTOM_INSET
        self._progress_y = bar_y
        x0 = pad + config.scale(2)
        x1 = w - pad - config.scale(2)
        self._progress_x0 = x0
        self._progress_max = max(1, x1 - x0)

        # Inset background track
        canvas.create_line(x0, bar_y, x1, bar_y, fill=config.PROGRESS_TRACK,
                           width=config.PROGRESS_HEIGHT, capstyle="round")
        # Inset progress fill
        self._progress_fill = canvas.create_line(x0, bar_y, x0 + self._progress_max, bar_y,
                                                 fill=accent, width=config.PROGRESS_HEIGHT, capstyle="round")
        self._update_progress()
    def refresh(self, message, title, kind, group_count, app_name=None):
        """Update an existing toast in place for a new grouped notification
        and restart its countdown, redrawing the stacked-peek effect."""
        self.message = message
        self.title = title
        self.kind = kind if kind in config.ICONS else "info"
        self.group_count = group_count
        if app_name:
            self.app_name = app_name
        self.messages.append(message)
        self._build_ui()
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", lambda e: self.dismiss())
        self.start_countdown(self.manager.duration_for(self.kind))

    # ------------------------------------------------------------------
    # Countdown
    # ------------------------------------------------------------------
    def start_countdown(self, duration_ms=None):
        self._duration_ms = self.manager.duration_for(self.kind) if duration_ms is None else duration_ms
        self._remaining_ms = self._duration_ms
        self._deadline = time.monotonic() + self._duration_ms / 1000.0
        self._update_progress()

    def tick_countdown(self):
        """Called by the manager ticker. Returns True when the toast has expired."""
        if not self.alive or self.paused or self._deadline is None:
            return False
        self._remaining_ms = max(0.0, (self._deadline - time.monotonic()) * 1000.0)
        self._update_progress()
        return self._remaining_ms <= 0

    def _update_progress(self):
        frac = max(self._remaining_ms, 0) / self._duration_ms if self._duration_ms else 0
        x0 = getattr(self, "_progress_x0", config.CARD_PAD + config.scale(2))
        x1 = x0 + self._progress_max * frac
        try:
            self.canvas.coords(self._progress_fill, x0, self._progress_y, x1, self._progress_y)
        except (tk.TclError, AttributeError):
            pass

    def _on_enter(self, event=None):
        self.paused = True
        self._deadline = None

    def _on_leave(self, event=None):
        self.paused = False
        self._deadline = time.monotonic() + self._remaining_ms / 1000.0

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def animate_to(self, tx, ty, alpha=None, duration_ms=None, on_done=None):
        """Record an animation target; the manager's ticker drives it."""
        if not self.alive and alpha is None:
            return
        target_alpha = self.manager.toast_alpha if alpha is None else alpha
        self.anim = {
            "x0": float(self.cur_x), "y0": float(self.cur_y), "a0": float(self.cur_alpha),
            "x1": float(tx), "y1": float(ty), "a1": float(target_alpha),
            "t0": time.monotonic(),
            "dur": (config.ANIM_DURATION_MS if duration_ms is None else duration_ms) / 1000.0,
            "on_done": on_done,
        }
        self.manager.register_animation(self)

    def apply_frame(self, t):
        """Interpolate to progress `t` in [0,1]. Returns True when finished."""
        a = self.anim
        if a is None:
            return True
        e = _ease_out_cubic(t)
        x = int(a["x0"] + (a["x1"] - a["x0"]) * e)
        y = int(a["y0"] + (a["y1"] - a["y0"]) * e)
        alpha = a["a0"] + (a["a1"] - a["a0"]) * e
        try:
            if x != self.cur_x or y != self.cur_y:
                self.win.geometry(f"+{x}+{y}")
                self.cur_x, self.cur_y = x, y
            if abs(alpha - self.cur_alpha) >= 0.01 or t >= 1.0:
                self.win.attributes("-alpha", alpha)
                self.cur_alpha = alpha
        except tk.TclError:
            self.anim = None
            return True
        if t < 1.0:
            return False
        done = a["on_done"]
        self.anim = None
        if done:
            done()
        return True

    # ------------------------------------------------------------------
    # Dismiss / slide-out
    # ------------------------------------------------------------------
    def dismiss(self, animate=True):
        if not self.alive:
            return
        self.alive = False
        if not animate:
            self._destroy()
            return
        self._slide_out()

    def _slide_out(self):
        position = self.manager.position
        if position == "left":
            tx = self.cur_x - config.NOTIF_WIDTH - config.MARGIN
            ty = self.cur_y
        elif position == "center":
            tx = self.cur_x
            ty = self.cur_y - config.NOTIF_HEIGHT - config.MARGIN
        else:  # right
            tx = self.cur_x + config.NOTIF_WIDTH + config.MARGIN
            ty = self.cur_y
        self.animate_to(tx, ty, alpha=0.0, on_done=self._destroy)

    def _destroy(self):
        self.manager.unregister_animation(self)
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.manager.remove(self)
