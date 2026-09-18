# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v2.0.15] - 2026-09-18

### Fixed
- Toast overlay windows occasionally sinking behind other windows and staying
  there until the app was manually restarted. Windows can silently evict a
  topmost layered window from the topmost z-order band (other topmost apps,
  UAC prompts, fullscreen toggles, screen lock/unlock, GPU/Explorer resets)
  without firing any Electron event, and the overlay's `setAlwaysOnTop` /
  `showInactive()` were previously only ever called once at window creation
  (`electron/windows.ts`). Added `reassertOverlaysOnTop()`, which re-applies
  `setAlwaysOnTop(true, "screen-saver")` and raises (`moveTop()`) every live
  overlay window, and wired it into the core `"toast"` event (fires right
  before a notification renders) plus `powerMonitor` `resume` /
  `unlock-screen` as a safety net (`electron/main.ts`).

## [v2.0.14] - prior release

No changelog history was tracked prior to v2.0.15; see `git log` for commit
history before this point.

[v2.0.15]: https://github.com/Dazaike/notification-tray/compare/v2.0.14...v2.0.15
