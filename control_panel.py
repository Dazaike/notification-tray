"""Control panel UI for sending and configuring notifications."""

import os
import tkinter as tk
from tkinter import filedialog, ttk

import config
import gemini_summarizer
from monitor_utils import (device_for_index, get_all_monitors, get_monitor_scale,
                           invalidate_monitor_cache)

_FONT = ("Segoe UI", 10)
_FONT_BOLD = ("Segoe UI", 13, "bold")
_PAD = 6   # outer section padding
_IPAD = 4  # inner widget padding
def _lf(parent, text):
    """Compact LabelFrame helper."""
    return tk.LabelFrame(parent, text=text, fg=config.FG_COLOR, bg=config.BG_COLOR,
                         labelanchor="nw", font=_FONT, relief="flat", bd=1,
                         highlightbackground=config.BORDER, highlightthickness=1)


def _btn(parent, text, command, accent=False):
    bg = config.ACCENT if accent else config.BORDER
    fg = config.BG_COLOR if accent else config.FG_COLOR
    hover_bg = config.mix_hex(bg, config.FG_COLOR, 0.12)
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    relief="flat", activebackground=config.MUTED, font=_FONT,
                    cursor="hand2")
    btn.bind("<Enter>", lambda e, b=btn, c=hover_bg: b.configure(bg=c))
    btn.bind("<Leave>", lambda e, b=btn, c=bg: b.configure(bg=c))
    return btn


def _rb(parent, text, value, variable, command):
    return tk.Radiobutton(parent, text=text, value=value, variable=variable,
                          command=command, bg=config.BORDER, fg=config.FG_COLOR,
                          selectcolor=config.ACCENT, activebackground=config.MUTED,
                          activeforeground=config.FG_COLOR, indicatoron=False,
                          relief="flat", font=_FONT, padx=8, pady=2, cursor="hand2")
def _entry(parent, textvariable, width=10):
    return tk.Entry(parent, textvariable=textvariable, bg=config.BORDER,
                    fg=config.FG_COLOR, insertbackground=config.FG_COLOR,
                    relief="flat", width=width, font=_FONT)


def _label(parent, text, **kw):
    return tk.Label(parent, text=text, fg=config.FG_COLOR, bg=config.BG_COLOR,
                    font=_FONT, **kw)


def _listbox(parent, height=3):
    return tk.Listbox(parent, bg=config.BORDER, fg=config.FG_COLOR,
                      relief="flat", height=height, selectbackground=config.ACCENT,
                      font=_FONT)


class ControlPanel:
    def __init__(self, manager):
        self.manager = manager

        self.ctrl = tk.Toplevel(manager.root)
        self.ctrl.title("Notification Tray")
        self.ctrl.configure(bg=config.BG_COLOR)
        self.ctrl.geometry(f"{config.PANEL_WIDTH}x{config.PANEL_HEIGHT}")
        self.position_var = tk.StringVar(value=manager.position)
        self.monitor_var = tk.IntVar(value=manager.monitor)
        self.duration_vars = {kind: tk.DoubleVar(value=manager.duration_for(kind) / 1000) for kind in config.ICONS}
        self.duration_labels = {}
        self.alpha_var = tk.DoubleVar(value=manager.toast_alpha)
        self.sound_var = tk.BooleanVar(value=manager.sound_enabled)
        self.accent_var = tk.StringVar(value=manager.accent_color)
        self.start_on_login_var = tk.BooleanVar(value=manager.start_on_login)
        self.suppress_focused_var = tk.BooleanVar(value=manager.suppress_focused_app)
        self.font_path_var = tk.StringVar(value=manager.font_path)
        self.gemini_enabled_var = tk.BooleanVar(value=manager.gemini_enabled)
        self.gemini_key_var = tk.StringVar(value=gemini_summarizer.get_stored_api_key())

        self._build_ui()
        self.ctrl.withdraw()

    # ------------------------------------------------------------------
    def _build_ui(self):
        P = _PAD

        style = ttk.Style(self.ctrl)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Nexus.Horizontal.TScale", background=config.BG_COLOR,
                        troughcolor=config.BORDER, sliderthickness=14)

        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        header.pack(fill="x", padx=P + 2, pady=(P + 2, 2))
        tk.Label(header, text="Notification Tray", fg=config.FG_COLOR, bg=config.BG_COLOR,
                 font=_FONT_BOLD).pack(side="left")
        tk.Label(header, text=f"v{config.__version__}", fg=config.SUBTEXT_COLOR, bg=config.BG_COLOR,
                 font=_FONT).pack(side="left", padx=(6, 0))
        _btn(header, "Clear all", self.manager.clear_all).pack(side="right")

        # ── Row 1: Position | Monitor ────────────────────────────────────
        row1 = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row1.pack(fill="x", padx=P, pady=2)

        pos_frame = _lf(row1, "Position")
        pos_frame.pack(side="left", fill="both", expand=True, padx=(0, 3))
        for label, value in (("Right", "right"), ("Center", "center"), ("Left", "left")):
            _rb(pos_frame, label, value, self.position_var, self._on_position_change
                ).pack(side="left", padx=4, pady=2)

        mon_frame = _lf(row1, "Monitor")
        mon_frame.pack(side="left", fill="both", expand=True, padx=(3, 0))
        # get_all_monitors() always returns at least one entry, and index 0 is
        # always the primary — label them so a wrong pick is obvious.
        for i, mon in enumerate(get_all_monitors()):
            label = f"{i + 1} · {mon.width}×{mon.height}" + (" (Primary)" if mon.primary else "")
            _rb(mon_frame, label, i, self.monitor_var, self._on_monitor_change
                ).pack(side="left", padx=4, pady=2)

        # ── Row 2: Durations | Color, Opacity, Sound ────────────────────
        row2 = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row2.pack(fill="x", padx=P, pady=2)

        dur_frame = _lf(row2, "Durations")
        dur_frame.pack(side="left", fill="both", expand=True, padx=(0, 3))
        for kind in ("info", "success", "warning", "error"):
            krow = tk.Frame(dur_frame, bg=config.BG_COLOR)
            krow.pack(fill="x", padx=_IPAD, pady=1)
            sec = self.duration_vars[kind].get()
            lbl = _label(krow, f"{kind.capitalize()}  {sec:.1f}s", width=12, anchor="w")
            lbl.pack(side="left")
            self.duration_labels[kind] = lbl
            ttk.Scale(krow, from_=2, to=15, orient="horizontal",
                      variable=self.duration_vars[kind], style="Nexus.Horizontal.TScale",
                      command=lambda val, k=kind: self._on_kind_duration_change(k, val)
                      ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        right_col = tk.Frame(row2, bg=config.BG_COLOR)
        right_col.pack(side="left", fill="both", expand=True, padx=(3, 0))

        col_frame = _lf(right_col, "Notification color")
        col_frame.pack(fill="x", pady=(0, 2))
        crow = tk.Frame(col_frame, bg=config.BG_COLOR)
        crow.pack(padx=_IPAD, pady=2)
        _label(crow, "#").pack(side="left")
        self.accent_entry = _entry(crow, self.accent_var, width=9)
        self.accent_entry.pack(side="left", padx=4)
        self.accent_swatch = tk.Frame(crow, bg=self.manager.accent_color,
                                      width=config.scale(22), height=config.scale(18),
                                      highlightbackground=config.BORDER, highlightthickness=1)
        self.accent_swatch.pack(side="left", padx=2)
        _btn(crow, "Apply", self._on_apply_accent).pack(side="left", padx=(4, 0))

        alpha_frame = _lf(right_col, "Opacity")
        alpha_frame.pack(fill="x", pady=2)
        arow = tk.Frame(alpha_frame, bg=config.BG_COLOR)
        arow.pack(fill="x", padx=_IPAD, pady=2)
        self.alpha_label = _label(arow, f"{self.alpha_var.get():.0%}", width=5)
        self.alpha_label.pack(side="left")
        ttk.Scale(arow, from_=config.MIN_TOAST_ALPHA, to=1.0, orient="horizontal",
                  variable=self.alpha_var, style="Nexus.Horizontal.TScale",
                  command=self._on_alpha_change
                  ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        sound_frame = _lf(right_col, "Sound")
        sound_frame.pack(fill="x", pady=(2, 0))
        tk.Checkbutton(sound_frame, text="Play sound on notification",
                       variable=self.sound_var,
                       command=self._on_sound_toggle,
                       indicatoron=False, relief="flat", bg=config.BORDER,
                       selectcolor=config.ACCENT, padx=8, pady=2,
                       activebackground=config.MUTED, activeforeground=config.FG_COLOR,
                       cursor="hand2", font=_FONT).pack(anchor="w", padx=_IPAD, pady=2)

        # ── Row 2b: Font ───────────────────────────────────────────────
        row2b = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row2b.pack(fill="x", padx=P, pady=2)
        font_frame = _lf(row2b, "Notification font")
        font_frame.pack(fill="x")
        frow = tk.Frame(font_frame, bg=config.BG_COLOR)
        frow.pack(fill="x", padx=_IPAD, pady=(2, 4))
        self.font_label = _label(frow, self._font_text(), anchor="w")
        self.font_label.pack(side="left", fill="x", expand=True)
        _btn(frow, "Browse...", self._on_browse_font).pack(side="left", padx=(4, 0))
        _btn(frow, "Reset", self._on_reset_font).pack(side="left", padx=(4, 0))

        # ── Row 2c: Gemini summaries ────────────────────────────────────
        row2c = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row2c.pack(fill="x", padx=P, pady=2)
        gemini_frame = _lf(row2c, "Gemini summaries")
        gemini_frame.pack(fill="x")
        gemini_toggle_row = tk.Frame(gemini_frame, bg=config.BG_COLOR)
        gemini_toggle_row.pack(fill="x", padx=_IPAD, pady=(2, 0))
        tk.Checkbutton(gemini_toggle_row, text="Summarize messages over 20 words",
                       variable=self.gemini_enabled_var,
                       command=self._on_gemini_enabled_change,
                       indicatoron=False, relief="flat", bg=config.BORDER,
                       selectcolor=config.ACCENT, padx=8, pady=2,
                       activebackground=config.MUTED, activeforeground=config.FG_COLOR,
                       cursor="hand2", font=_FONT).pack(side="left")
        gemini_key_row = tk.Frame(gemini_frame, bg=config.BG_COLOR)
        gemini_key_row.pack(fill="x", padx=_IPAD, pady=(2, 4))
        _label(gemini_key_row, "API key:").pack(side="left")
        self.gemini_key_entry = _entry(gemini_key_row, self.gemini_key_var, width=28)
        self.gemini_key_entry.configure(show="*")
        self.gemini_key_entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        _btn(gemini_key_row, "Save key", self._on_save_gemini_key).pack(side="left")
        _btn(gemini_key_row, "Clear", self._on_clear_gemini_key).pack(side="left", padx=(4, 0))

        # ── Row 3: Startup (single compact line) ─────────────────────────
        row3 = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row3.pack(fill="x", padx=P, pady=2)
        startup_frame = _lf(row3, "Startup")
        startup_frame.pack(fill="x")
        tk.Checkbutton(startup_frame, text="Start with Windows",
                       variable=self.start_on_login_var,
                       command=self._on_start_on_login_change,
                       indicatoron=False, relief="flat", bg=config.BORDER,
                       selectcolor=config.ACCENT, padx=8, pady=2,
                       activebackground=config.MUTED, activeforeground=config.FG_COLOR,
                       cursor="hand2", font=_FONT).pack(side="left", padx=_IPAD, pady=2)
        tk.Checkbutton(startup_frame, text="Don't notify for the app I'm focused on",
                       variable=self.suppress_focused_var,
                       command=self._on_suppress_focused_change,
                       indicatoron=False, relief="flat", bg=config.BORDER,
                       selectcolor=config.ACCENT, padx=8, pady=2,
                       activebackground=config.MUTED, activeforeground=config.FG_COLOR,
                       cursor="hand2", font=_FONT).pack(side="left", padx=_IPAD, pady=2)

        # ── Row 4: Excluded apps | Per-app colors ────────────────────────
        row4 = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row4.pack(fill="x", padx=P, pady=2)

        excl_frame = _lf(row4, "Excluded apps")
        excl_frame.pack(side="left", fill="both", expand=True, padx=(0, 3))
        self.exclusions_list = _listbox(excl_frame, height=3)
        self.exclusions_list.pack(fill="x", padx=_IPAD, pady=(4, 2))
        eb = tk.Frame(excl_frame, bg=config.BG_COLOR)
        eb.pack(fill="x", padx=_IPAD, pady=(0, 4))
        _btn(eb, "Add app...", self._add_excluded_app).pack(side="left")
        _btn(eb, "Remove", self._remove_excluded_app).pack(side="left", padx=(4, 0))
        self._refresh_exclusions()

        ac_frame = _lf(row4, "Per-app colors")
        ac_frame.pack(side="left", fill="both", expand=True, padx=(3, 0))
        self.app_colors_list = _listbox(ac_frame, height=3)
        self.app_colors_list.pack(fill="x", padx=_IPAD, pady=(4, 2))

        acr = tk.Frame(ac_frame, bg=config.BG_COLOR)
        acr.pack(fill="x", padx=_IPAD, pady=(0, 2))
        _label(acr, "EXE:").pack(side="left")
        self._ac_exe_var = tk.StringVar()
        _entry(acr, self._ac_exe_var, width=11).pack(side="left", padx=(2, 6))
        _label(acr, "#").pack(side="left")
        self._ac_color_var = tk.StringVar()
        _entry(acr, self._ac_color_var, width=7).pack(side="left", padx=2)
        self._ac_swatch = tk.Frame(acr, bg=config.BORDER, width=config.scale(16), height=config.scale(16),
                                   highlightbackground=config.BORDER, highlightthickness=1)
        self._ac_swatch.pack(side="left", padx=2)
        self._ac_color_var.trace_add("write", self._on_ac_color_change)

        acb = tk.Frame(ac_frame, bg=config.BG_COLOR)
        acb.pack(fill="x", padx=_IPAD, pady=(0, 4))
        _btn(acb, "Add", self._add_app_color).pack(side="left")
        _btn(acb, "Remove", self._remove_app_color).pack(side="left", padx=(4, 0))
        self._refresh_app_colors()

        # ── Row 5: Demo + status + Save ──────────────────────────────────
        row5 = tk.Frame(self.ctrl, bg=config.BG_COLOR)
        row5.pack(fill="x", padx=P, pady=(4, P))
        _btn(row5, "Demo burst", self._demo_burst, accent=True).pack(side="left")
        self.save_label = tk.Label(row5, text="", fg=config.MUTED, bg=config.BG_COLOR, font=_FONT)
        self.save_label.pack(side="left", padx=8)
        _btn(row5, "Save settings", self._on_save_settings, accent=True).pack(side="right")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _demo_burst(self):
        samples = [
            ("Beeper", "New message from Sarah: See you tomorrow!", "Sarah", "info"),
            ("GitHub", "Build #1042 passed all 58 tests successfully", "CI / CD Pipeline", "success"),
            ("Windows Security", "Threat definitions updated", "Security Intelligence", "warning"),
            ("Spotify", "Playback paused: network connection lost", "Spotify Music", "error"),
        ]
        for i, (app, msg, title, kind) in enumerate(samples):
            self.ctrl.after(i * 450, lambda a=app, m=msg, t=title, k=kind: self.manager.notify(
                m, title=t, kind=k, app_name=a))
    def _add_excluded_app(self):
        path = filedialog.askopenfilename(
            title="Select application",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if not path:
            return
        self.manager.add_excluded_app(path)
        self._refresh_exclusions()

    def _remove_excluded_app(self):
        selection = self.exclusions_list.curselection()
        if not selection:
            return
        self.manager.remove_excluded_app(selection[0])
        self._refresh_exclusions()

    def _refresh_exclusions(self):
        self.exclusions_list.delete(0, tk.END)
        for entry in self.manager.excluded_apps:
            self.exclusions_list.insert(tk.END, entry["name"])

    def _on_ac_color_change(self, *_):
        raw = self._ac_color_var.get().strip()
        color = f"#{raw}" if raw and not raw.startswith("#") else raw
        try:
            if len(color) == 7:
                int(color[1:], 16)
                self._ac_swatch.configure(bg=color)
                return
        except ValueError:
            pass
        self._ac_swatch.configure(bg=config.BORDER)

    def _add_app_color(self):
        exe = self._ac_exe_var.get().strip()
        color = self._ac_color_var.get().strip()
        if not exe or not color:
            return
        hex_color = f"#{color}" if not color.startswith("#") else color
        if len(hex_color) != 7:
            return
        try:
            int(hex_color[1:], 16)
        except ValueError:
            return
        self.manager.add_app_color(exe, hex_color)
        self._ac_exe_var.set("")
        self._ac_color_var.set("")
        self._refresh_app_colors()

    def _remove_app_color(self):
        selection = self.app_colors_list.curselection()
        if not selection:
            return
        self.manager.remove_app_color(selection[0])
        self._refresh_app_colors()

    def _refresh_app_colors(self):
        self.app_colors_list.delete(0, tk.END)
        for entry in self.manager.app_colors:
            self.app_colors_list.insert(tk.END, f"{entry['exe']}  {entry['color']}")

    def _on_position_change(self):
        self.manager.position = self.position_var.get()
        self.manager._restack()

    def _on_monitor_change(self):
        self.manager.monitor = self.monitor_var.get()
        invalidate_monitor_cache()
        self.manager.monitor_device = device_for_index(self.manager.monitor)
        config.apply_scale(get_monitor_scale(self.manager.monitor))
        self.manager.clear_all()
        self.manager._restack()

    def _on_kind_duration_change(self, kind, val):
        sec = float(val)
        self.manager.set_duration(kind, int(sec * 1000))
        if kind in self.duration_labels:
            self.duration_labels[kind].configure(text=f"{kind.capitalize()}  {sec:.1f}s")

    def _on_alpha_change(self, val):
        alpha = float(val)
        self.manager.set_toast_alpha(alpha)
        self.alpha_label.configure(text=f"{alpha:.0%}")

    def _on_sound_toggle(self):
        self.manager.toggle_sound()
    def _on_apply_accent(self):
        if self.manager.set_accent_color(self.accent_var.get()):
            self.accent_var.set(self.manager.accent_color)
            self.accent_swatch.configure(bg=self.manager.accent_color)
            self.save_label.configure(text="Color applied", fg=config.MUTED)
        else:
            self.save_label.configure(text="Invalid hex color", fg="#dd6974")

    def _on_gemini_enabled_change(self):
        self.manager.set_gemini_enabled(self.gemini_enabled_var.get())
        self.save_label.configure(
            text="Gemini summaries enabled" if self.gemini_enabled_var.get() else "Gemini summaries disabled",
            fg=config.MUTED,
        )

    def _on_save_gemini_key(self):
        if self.manager.save_gemini_api_key(self.gemini_key_var.get()):
            self.save_label.configure(text="Gemini API key saved securely", fg=config.MUTED)
        else:
            self.save_label.configure(text="Couldn't save Gemini API key", fg="#dd6974")

    def _on_clear_gemini_key(self):
        if self.manager.save_gemini_api_key(""):
            self.gemini_key_var.set("")
            self.save_label.configure(text="Gemini API key cleared", fg=config.MUTED)
        else:
            self.save_label.configure(text="Couldn't clear Gemini API key", fg="#dd6974")

    def _font_text(self):
        path = self.font_path_var.get()
        return os.path.basename(path) if path else "Default (Segoe UI)"

    def _on_browse_font(self):
        path = filedialog.askopenfilename(
            title="Select a font",
            filetypes=[("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*")],
        )
        if not path:
            return
        if self.manager.set_font_path(path):
            self.font_path_var.set(path)
            self.font_label.configure(text=self._font_text())
            self.save_label.configure(text="Font applied", fg=config.MUTED)
            self._demo_burst()
        else:
            self.save_label.configure(text="Couldn't load that font", fg="#dd6974")

    def _on_reset_font(self):
        self.manager.set_font_path("")
        self.font_path_var.set("")
        self.font_label.configure(text=self._font_text())
        self.save_label.configure(text="Font reset", fg=config.MUTED)

    def _on_start_on_login_change(self):
        self.manager.set_start_on_login(self.start_on_login_var.get())
        self.manager.save_settings()

    def _on_suppress_focused_change(self):
        self.manager.suppress_focused_app = self.suppress_focused_var.get()
        self.manager.save_settings()

    def _on_save_settings(self):
        self._collect_settings()
        self.manager.save_settings()
        self.save_label.configure(text="Saved", fg=config.MUTED)

    def _collect_settings(self):
        self.manager.position = self.position_var.get()
        self.manager.monitor = self.monitor_var.get()
        self.manager.monitor_device = device_for_index(self.manager.monitor)

    def _on_close(self):
        self._collect_settings()
        self.manager.save_settings()
        self.ctrl.withdraw()

    def show(self):
        self.ctrl.deiconify()
