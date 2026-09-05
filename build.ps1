# Builds the Electron + React + Kokonut UI + Motion application.
#
# Usage:
#   .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "Building Notification Tray..."
npm run build

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Build complete! Output in dist/"
