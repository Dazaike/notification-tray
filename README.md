# Windows Notification Tray

A custom iOS-style notification tray for Windows. Renders animated, stacked
toast popups on a chosen monitor (right, center, or left), with a control
panel for sending notifications and configuring behavior.

## Setup

```bash
pip install -r requirements.txt
```

## Gemini notification summaries

Use **Gemini summaries** in the control panel to enable or disable summaries,
and enter or replace the Google AI Studio API key. The key is stored in Windows
Credential Manager, not `~/.notif_tray_config.json`; it is masked in the panel.

`GEMINI_API_KEY` remains supported for launch-time configuration and takes
precedence over the saved key. Qualifying notifications wait up to 60 seconds
for a one-sentence Gemini 3.5 Flash-Lite summary. If no key is available or the
request fails, the original body is displayed instead.

## Run

```bash
python notification_tray.py
```

This opens the control panel and adds a bell icon to the system tray.
Closing the control panel minimizes it to the tray; use the tray menu to
show it again, send a test notification, or quit.

## Usage

- **Send notification** — type a message next to a kind (info/success/
  warning/error) and click Send.
- **Position** — choose which edge of the monitor toasts slide in from.
- **Monitor** — choose which monitor toasts appear on (unavailable monitors
  are disabled).
- **Duration** — how long a toast stays before sliding out (2-15s).
- **Demo burst** — fires 5 staggered notifications to preview stacking.
- **History** — the last 20 notifications, most recent first.

Settings (position, monitor, duration) are saved to
`~/.notif_tray_config.json` and restored on the next launch.

## Native notifications

A background thread ([windows_listener.py](windows_listener.py)) mirrors new
Windows toast notifications (Action Center) into the tray. The first run may
prompt for "notification access" in Windows Settings — if denied, mirroring
is silently skipped.

## Building a standalone app

Package everything into a single windowless `.exe` with PyInstaller:

```powershell
.\build.ps1
```

This produces `dist\NotificationTray.exe` — no Python install required to
run it.

## Running in the background at login

```powershell
.\install_startup.ps1            # add a Startup shortcut (run after build.ps1)
.\install_startup.ps1 -Uninstall # remove it
```

After this, the app launches automatically on login with no console window —
only the tray icon and toast popups are visible. Use the tray menu's "Quit"
to exit.

## Integration from Python

```python
from manager import NotificationManager

mgr = NotificationManager()
mgr.notify("Deployment succeeded", title="CI/CD", kind="success")
mgr.notify("CPU at 95%", title="System", kind="warning")
```

`notify()` is thread-safe and can be called from any thread.
