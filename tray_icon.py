"""System tray integration using pystray + Pillow."""

import pystray
from PIL import Image, ImageDraw, ImageFont

import config


def create_icon_image(unread_count=0, accent=None) -> Image.Image:
    """Draw a simple bell icon as a 64x64 PIL image, with an optional
    unread-count badge in the corner."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    accent = accent or config.ACCENT

    # Bell body
    draw.pieslice([12, 10, 52, 50], 180, 360, fill=accent)
    draw.rectangle([12, 30, 52, 44], fill=accent)
    draw.polygon([(12, 44), (52, 44), (46, 52), (18, 52)], fill=accent)

    # Clapper
    draw.ellipse([28, 52, 36, 60], fill=accent)

    # Top knob
    draw.rectangle([30, 4, 34, 12], fill=accent)

    if unread_count > 0:
        badge = config.BADGE_COLOR
        draw.ellipse([34, 0, 64, 30], fill=badge)
        text = str(unread_count) if unread_count <= 9 else "9+"
        draw.text((49, 15), text, fill=config.BADGE_TEXT_COLOR, anchor="mm",
                  font=ImageFont.load_default())

    return image

def _ensure_self_icon_saved(accent=None) -> config.Path:
    config.ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    icon_file = config.ICON_CACHE_DIR / "notification_tray.png"
    img = create_icon_image(0, accent=accent)
    try:
        img.save(icon_file)
    except Exception:
        pass
    return icon_file


def _send_test_notification(manager):
    icon_file = _ensure_self_icon_saved(manager.accent_color)
    manager.notify(
        "This is a preview of the restyled modern notification card.",
        title="Notification Tray",
        kind="info",
        app_name="Notification Tray",
        icon_path=str(icon_file),
    )


def setup_tray(manager, control_panel, notification_center) -> pystray.Icon:
    _ensure_self_icon_saved(manager.accent_color)
    icon = pystray.Icon("NotifTray", create_icon_image(accent=manager.accent_color), "Notification Tray")

    # pystray runs the tray icon (and its right-click menu) on its own
    # background thread, separate from the thread running Tk's mainloop.
    # Tkinter/Tcl is not thread-safe, so menu callbacks that touch widgets
    # directly (deiconify, geometry, destroy, ...) race the mainloop thread.
    # That race intermittently wedges Tcl's event loop entirely (the app
    # "just stops working") or blocks the pystray thread on a Tcl call that
    # never resolves (the right-click menu becomes unresponsive). Marshal
    # every callback onto the main thread via root.after(0, ...) instead.
    def _on_main(func):
        return lambda: manager.root.after(0, func)

    icon.menu = pystray.Menu(
        pystray.MenuItem("Notification Center", _on_main(notification_center.toggle), default=True),
        pystray.MenuItem("Show panel", _on_main(control_panel.show)),
        pystray.MenuItem("Send test notification", lambda: _send_test_notification(manager)),
        pystray.MenuItem("Do Not Disturb", lambda: _toggle_dnd(manager, icon),
                         checked=lambda item: manager.dnd),
        pystray.MenuItem("Quit", lambda: _quit(manager, icon)),
    )
    def on_unread_change(count):
        icon.icon = create_icon_image(count, accent=manager.accent_color)

    manager.on_unread_change = on_unread_change
    return icon


def _toggle_dnd(manager, icon):
    manager.toggle_dnd()
    icon.update_menu()


def _quit(manager, icon):
    def shutdown():
        manager.shutdown()

    manager.root.after(0, shutdown)
    icon.stop()
