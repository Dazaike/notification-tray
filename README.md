# Windows Notification Tray (v2.0.14)

A modern, fluid Windows 11 notification tray built on **Electron**, **React 19**, **Tailwind CSS v4**, **Kokonut UI**, and **Motion**.

The UI runs on hardware-accelerated web surfaces with liquid-glass cards, card-stack peek effects, spring physics animations, and Windows 11 Mica material. All Windows-specific capture (WinRT Action Center listener), audio playback (MCI), activation (COM/deep links), and Gemini AI summarization are handled by a headless Python core service communicating via NDJSON over standard I/O.

## Architecture

```
Electron main (electron/main.ts)
├─ Tray (bell icon with dynamic unread badge)
├─ Child process (core_service.py / core.exe) ──NDJSON over stdio──► Python core
├─ Overlay: Transparent, click-through, always-on-top toast stack (?surface=overlay)
├─ Notification Center: Frameless Mica flyout history (?surface=center)
└─ Control Panel: Frameless Mica tabbed settings window (?surface=panel)
```

## Prerequisites

- Node.js 20+ (Node 24 recommended)
- Python 3.10+
- Windows 11 / Windows 10 (64-bit)

## Setup

Install Node and Python dependencies:

```bash
npm install
npm install --prefix ui
pip install -r requirements.txt
```

## Development

Run both the Vite dev server and the Electron shell:

```bash
npm run dev
```

Or run the Python headless core service standalone for headless testing:

```bash
python core_service.py
```

## Building a Standalone App

Build the UI, compile TypeScript, package the Python core with PyInstaller, and generate the Windows NSIS installer and unpacked executable with Electron Builder:

```powershell
.\build.ps1
```

Or via npm:

```bash
npm run build
```

This generates `dist/win-unpacked/notification-tray.exe` and an NSIS installer under `dist/`.

## Features

- **Liquid Glass Toasts** — Glassmorphic toast popups styled after modern Windows 11 surfaces with inset highlights and spring motion.
- **Card-Stack Grouping** — Grouped notifications from the same app/title stack with a visual peek layer and dynamic badge counter.
- **Countdown Progress Bar** — Accent-colored linear timer with frame-exact pause on hover and resume on mouse leave.
- **Click-Through Transparency** — Full click-through transparency for the overlay window so desktop clicks pass through smoothly.
- **Notification Center** — Frameless Mica drawer with sticky section headers, search filter, hold-to-clear button, and staggered animation.
- **Control Panel** — Tabbed interface (Appearance, Animations, Behaviour, Filters, AI) with spotlight cards, live accent color swatches, opacity sliders, and Demo Burst particle animations.
- **Directional Animations & Presets** — 16 incoming and 16 outgoing animation effects with 12 paired presets (Default, Smooth, Spring, Pop, Glass, Material, Elastic, 3D Flip, Liquid, Minimal, Dynamic, Compact) and granular physics tuning (duration, distance, bounce, blur, scale, easing).
- **Customizable Notification Sounds** — Built-in native MCI playback supporting custom `.mp3`, `.wav`, `.wma`, `.m4a` audio files with in-app audio browsing, testing, and reset to defaults.
- **Draggable Frameless Windows** — Native drag-and-move support on settings and notification center header bars.
- **Gemini AI Summaries** — Optional AI summarization for notifications over 20 words. API keys are stored in the Windows Credential Manager.
- **Deep Links & App Activation** — Clicking a notification activates the source app via COM, native toast activation, or Beeper/protocol deep links.
- **Tray Icon Click Action** — Configurable tray click behavior: open either the Notification Center or the Settings Panel directly on click.
- **Instant Settings Sync** — Immediate state hydration on app startup across all window surfaces with robust fallback resolution.
