"""A persistent, scrollable history panel — like Windows' Action Center."""

import tkinter as tk

import config
import emoji_render
from dwm_utils import apply_mica
from icon_utils import make_fallback_icon, make_rounded_icon

class NotificationCenter:
    def __init__(self, manager):
        self.manager = manager
        self.visible = False
        self._dirty = True
        self._icon_photos = []

        self.win = tk.Toplevel(manager.root)
        self.win.withdraw()
        self.win.title("Notification Center")
        self.win.configure(bg=config.BG_COLOR)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        apply_mica(self.win, transient=False, dark=True)
        try:
            self.win.attributes("-alpha", manager.toast_alpha)
        except tk.TclError:
            pass

        self.manager.on_history_change = self._on_history_change
        self._build_ui()

    def _on_history_change(self):
        self._dirty = True
        if self.visible:
            self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        header = tk.Frame(self.win, bg=config.CARD_COLOR)
        header.pack(fill="x")

        title = tk.Label(header, text="Notifications", fg=config.FG_COLOR, bg=config.CARD_COLOR,
                          font=("Segoe UI", 16, "bold"))
        title.pack(side="left", padx=12, pady=10)

        clear_btn = tk.Button(header, text="Clear all", command=self._clear_all,
                               bg=config.BORDER, fg=config.FG_COLOR, relief="flat",
                               activebackground=config.MUTED, cursor="hand2")
        clear_btn.pack(side="right", padx=12, pady=10)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        search_entry = tk.Entry(header, textvariable=self.search_var, bg=config.BG_COLOR,
                                fg=config.FG_COLOR, insertbackground=config.FG_COLOR,
                                relief="flat", font=("Segoe UI", 10))
        search_entry.pack(side="right", padx=(0, 10), pady=10, ipady=2)

        body = tk.Frame(self.win, bg=config.BG_COLOR)
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, bg=config.BG_COLOR, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(body, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.list_frame = tk.Frame(self.canvas, bg=config.BG_COLOR)
        self._list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")

        self.list_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.empty_label = tk.Label(self.list_frame, text="No notifications yet",
                                     fg=config.MUTED, bg=config.BG_COLOR,
                                     font=("Segoe UI", 13))
        self._icon_photos = []

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._list_window, width=event.width)

    def _on_scroll(self, event):
        if not self.visible:
            return
        self.canvas.yview_scroll(int(-event.delta / 40), "units")

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def refresh(self):
        for child in self.list_frame.winfo_children():
            if child is not self.empty_label:
                child.destroy()
        self._icon_photos = []

        history = list(reversed(self.manager.history))

        needle = self.search_var.get().strip().lower()
        if needle:
            history = [
                e for e in history
                if needle in f"{e.get('title', '')} {e.get('message', '')} {e.get('app_name', '')}".lower()
            ]

        if not history:
            self.empty_label.pack(fill="x", pady=20)
            return
        self.empty_label.pack_forget()

        # Group consecutive-by-app runs visually with a header per app,
        # mirroring the toast grouping logic (same title == same group).
        last_title = None
        for entry in history:
            title = entry.get("title") or entry.get("kind", "").capitalize()
            if title != last_title:
                self._add_section_header(title)
                last_title = title
            self._add_item(entry)

    def _add_section_header(self, title):
        photo = emoji_render.render([title], config.CENTER_HEADER_SIZE, config.MUTED, config.BG_COLOR,
                                     config.LINE_HEIGHT, config.CENTER_WIDTH - config.scale(24))
        if photo is not None:
            self._icon_photos.append(photo)
            label = tk.Label(self.list_frame, image=photo, bg=config.BG_COLOR, anchor="w")
        else:
            label = tk.Label(self.list_frame, text=title, fg=config.MUTED, bg=config.BG_COLOR,
                              font=("Segoe UI", 11, "bold"), anchor="w")
        label.pack(fill="x", padx=12, pady=(10, 2))

    def _add_item(self, entry):
        kind = entry.get("kind", "info")
        accent = self.manager.accent_color
        is_unread = entry.get("read", True) is False
        row_bg = config.icon_bg_for(accent) if is_unread else config.CARD_COLOR
        msg_fg = config.FG_COLOR if is_unread else config.SUBTEXT_COLOR
        icon_bg = config.icon_bg_for(accent)

        row = tk.Frame(self.list_frame, bg=row_bg)
        row.pack(fill="x", padx=10, pady=3)

        icon_wrap = tk.Frame(row, bg=row_bg, width=config.CENTER_ICON_SIZE, height=config.CENTER_ICON_SIZE)
        icon_wrap.pack(side="left", padx=8, pady=8)
        icon_wrap.pack_propagate(False)

        photo = make_rounded_icon(entry.get("icon_path", ""), config.CENTER_ICON_SIZE, radius=config.ICON_RADIUS)
        if photo is None:
            photo = make_fallback_icon(kind, config.CENTER_ICON_SIZE, accent, radius=config.ICON_RADIUS)

        if photo is not None:
            self._icon_photos.append(photo)
            icon_label = tk.Label(icon_wrap, image=photo, bg=row_bg, bd=0)
            icon_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            icon_label = tk.Label(icon_wrap, text=config.ICONS.get(kind, "ℹ"), fg=accent,
                                   bg=row_bg, font=("Segoe UI", 13, "bold"))
            icon_label.place(relx=0.5, rely=0.5, anchor="center")
        text_col = tk.Frame(row, bg=row_bg)
        text_col.pack(side="left", fill="x", expand=True, pady=8)

        msg_w = config.CENTER_WIDTH - config.scale(130)
        msg_lines = emoji_render.wrap_lines(entry.get("message", ""), config.CENTER_TEXT_SIZE, msg_w)
        msg_photo = emoji_render.render(msg_lines, config.CENTER_TEXT_SIZE, msg_fg, row_bg,
                                         config.LINE_HEIGHT, msg_w)
        if msg_photo is not None:
            self._icon_photos.append(msg_photo)
            msg = tk.Label(text_col, image=msg_photo, bg=row_bg, anchor="w")
        else:
            msg = tk.Label(text_col, text=entry.get("message", ""), fg=msg_fg,
                            bg=row_bg, font=("Segoe UI", 12), anchor="w",
                            justify="left", wraplength=msg_w)
        msg.pack(fill="x")

        dismiss_btn = tk.Label(row, text="✕", fg=config.MUTED, bg=row_bg, cursor="hand2",
                               font=("Segoe UI", 10))
        dismiss_btn.pack(side="right", padx=(4, 10))
        dismiss_btn.bind("<Button-1>", lambda e, entry=entry: self._dismiss(entry))
        dismiss_btn.bind("<Enter>", lambda e, b=dismiss_btn: b.config(fg=config.FG_COLOR))
        dismiss_btn.bind("<Leave>", lambda e, b=dismiss_btn: b.config(fg=config.MUTED))

        time_label = tk.Label(row, text=entry.get("timestamp", ""), fg=config.MUTED,
                               bg=row_bg, font=("Segoe UI", 11), anchor="ne")
        time_label.pack(side="right", padx=(0, 4))

        for widget in (row, icon_wrap, icon_label, text_col, msg, time_label):
            widget.bind("<Button-1>", lambda e, entry=entry: self._activate(entry))
            widget.bind("<Enter>", lambda e: self.win.config(cursor="hand2"))
            widget.bind("<Leave>", lambda e: self.win.config(cursor=""))

    def _dismiss(self, entry):
        self.manager.remove_history_entries([entry])
        self.refresh()
        self._dirty = False
    def _activate(self, entry):
        self.manager.remove_history_entries([entry])
        source_hwnd = None
        try:
            source_hwnd = self.win.winfo_id()
        except tk.TclError:
            pass
        self.manager._launch_app(
            entry.get("aumid", ""),
            entry.get("launch_url", ""),
            toast_tag=entry.get("toast_tag", ""),
            title=entry.get("title", ""),
            message=entry.get("message", ""),
            app_name=entry.get("app_name", ""),
            source_hwnd=source_hwnd,
        )
        self.refresh()

    def _clear_all(self):
        self.manager.clear_history()
        self.refresh()
        self._dirty = False

    def _on_focus_out(self, event):
        if event.widget == self.win:
            try:
                focused = self.win.focus_get()
                if focused is None or not str(focused).startswith(str(self.win)):
                    self.hide()
            except Exception:
                self.hide()

    # ------------------------------------------------------------------
    # Show / hide
    # ------------------------------------------------------------------
    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        if self._dirty:
            self.refresh()
            self._dirty = False

        rect = self.manager._monitor_rect()

        width = config.CENTER_WIDTH
        height = min(rect.height - config.MARGIN * 2, config.CENTER_MAX_HEIGHT)

        if self.manager.position == "left":
            x = rect.x + config.MARGIN
        else:
            x = rect.x + rect.width - width - config.MARGIN
        y = rect.y + config.MARGIN

        self.win.geometry(f"{width}x{height}+{x}+{y}")
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.win.bind("<Escape>", lambda e: self.hide())
        self.win.bind("<FocusOut>", self._on_focus_out)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.visible = True

    def hide(self):
        self.canvas.unbind("<MouseWheel>")
        try:
            self.win.unbind("<Escape>")
            self.win.unbind("<FocusOut>")
        except tk.TclError:
            pass
        self.manager.mark_all_read()
        self.win.withdraw()
        self.visible = False
