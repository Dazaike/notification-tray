# Builds a single-file, windowless executable for the Notification Tray.
#
# Usage:
#   .\build.ps1
#
# Output: dist\NotificationTray.exe

$ErrorActionPreference = "Stop"

pip install -q -r requirements.txt
pip install -q pyinstaller

python -m PyInstaller `
    --noconfirm `
    --noconsole `
    --onefile `
    --name NotificationTray `
    --add-data "fears-to-fathom-notification.mp3;." `
    --collect-all winsdk `
    --collect-all pystray `
    --collect-all PIL `
    notification_tray.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Build complete: dist\NotificationTray.exe"
