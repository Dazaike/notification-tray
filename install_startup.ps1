# Adds (or removes with -Uninstall) a shortcut to NotificationTray.exe in the
# current user's Startup folder, so it launches automatically at login.
#
# Usage:
#   .\install_startup.ps1            # install
#   .\install_startup.ps1 -Uninstall # remove

param(
    [switch]$Uninstall
)

$exePath = Join-Path $PSScriptRoot "dist\NotificationTray.exe"
$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "NotificationTray.lnk"

if ($Uninstall) {
    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-Host "Removed startup shortcut: $shortcutPath"
    } else {
        Write-Host "No startup shortcut found."
    }
    exit 0
}

if (-not (Test-Path $exePath)) {
    Write-Error "NotificationTray.exe not found at $exePath. Run build.ps1 first."
    exit 1
}

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path $exePath
$shortcut.Description = "Notification Tray"
$shortcut.Save()

Write-Host "Installed startup shortcut: $shortcutPath -> $exePath"
Write-Host "It will launch automatically on next login. To start it now, run:"
Write-Host "  & `"$exePath`""
