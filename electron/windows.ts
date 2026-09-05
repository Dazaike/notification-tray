import path from "node:path";
import { BrowserWindow, screen, type Display } from "electron";
import { request } from "./core";

export interface CoreMonitor {
  index: number;
  device: string;
  x: number;
  y: number;
  width: number;
  height: number;
  primary: boolean;
}

export interface AppSettings {
  version: string;
  position: "right" | "center" | "left";
  monitor: number;
  monitor_device: string;
  durations: Record<string, number>;
  accent_color: string;
  font_path: string;
  excluded_apps: Array<{ path: string; name: string }>;
  app_colors: Array<{ exe: string; color: string }>;
  dnd: boolean;
  suppress_focused_app: boolean;
  sound_enabled: boolean;
  custom_sound_path?: string;
  toast_alpha: number;
  toast_scale: number;
  gemini_enabled: boolean;
  animation_preset?: string;
  anim_incoming?: string;
  anim_outgoing?: string;
  anim_direction?: "auto" | "right" | "left" | "top" | "bottom";
  anim_duration?: number;
  anim_easing?: string;
  anim_distance?: number;
  anim_bounce?: number;
  anim_blur?: number;
  anim_scale?: number;
}

let overlayWin: BrowserWindow | null = null;
let centerWin: BrowserWindow | null = null;
let panelWin: BrowserWindow | null = null;

let currentSettings: AppSettings | null = null;
let currentMonitors: CoreMonitor[] = [];
let isQuitting = false;

export function setAppQuitting(quitting: boolean): void {
  isQuitting = quitting;
}

export function updateState(settings: AppSettings, monitors?: CoreMonitor[]): void {
  currentSettings = settings;
  if (monitors) {
    currentMonitors = monitors;
  }
  repositionWindows();
}

function resolveTargetDisplay(): Display {
  const all = screen.getAllDisplays();
  if (!currentSettings?.monitor_device || currentMonitors.length === 0) {
    return screen.getPrimaryDisplay();
  }

  const targetCoreMon = currentMonitors.find((m) => m.device === currentSettings?.monitor_device);
  if (!targetCoreMon) {
    return screen.getPrimaryDisplay();
  }

  for (const d of all) {
    const physicalPoint = screen.dipToScreenPoint({ x: d.bounds.x, y: d.bounds.y });
    if (physicalPoint.x === targetCoreMon.x && physicalPoint.y === targetCoreMon.y) {
      return d;
    }
  }

  return screen.getPrimaryDisplay();
}

function loadSurface(win: BrowserWindow, surface: "overlay" | "center" | "panel"): void {
  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    win.loadURL(`${devServerUrl}?surface=${surface}`);
  } else {
    const indexPath = path.join(__dirname, "../dist-ui/index.html");
    win.loadFile(indexPath, { search: `?surface=${surface}` });
  }
}

export function repositionWindows(): void {
  const target = resolveTargetDisplay();
  const workArea = target.workArea;

  if (overlayWin && !overlayWin.isDestroyed()) {
    overlayWin.setBounds({
      x: workArea.x,
      y: workArea.y,
      width: workArea.width,
      height: workArea.height,
    });
  }

  if (centerWin && !centerWin.isDestroyed()) {
    const width = 440;
    const height = Math.min(workArea.height - 48, 640);
    const margin = 24;
    const y = workArea.y + margin;
    let x = workArea.x + workArea.width - width - margin;
    if (currentSettings?.position === "left") {
      x = workArea.x + margin;
    }
    centerWin.setBounds({ x, y, width, height });
  }
}

export function createWindows(preloadPath: string): void {
  const target = resolveTargetDisplay();
  const workArea = target.workArea;

  // 1. Overlay window
  overlayWin = new BrowserWindow({
    x: workArea.x,
    y: workArea.y,
    width: workArea.width,
    height: workArea.height,
    transparent: true,
    frame: false,
    resizable: false,
    movable: false,
    focusable: false,
    skipTaskbar: true,
    hasShadow: false,
    thickFrame: false,
    type: "toolbar",
    roundedCorners: false,
    backgroundColor: "#00000000",
    show: false,
    paintWhenInitiallyHidden: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  overlayWin.setAlwaysOnTop(true, "screen-saver");
  overlayWin.setIgnoreMouseEvents(true, { forward: true });
  loadSurface(overlayWin, "overlay");
  overlayWin.show();

  // 2. Center window
  const centerWidth = 440;
  const centerHeight = Math.min(workArea.height - 48, 640);
  const margin = 24;
  const centerY = workArea.y + margin;
  let centerX = workArea.x + workArea.width - centerWidth - margin;
  if (currentSettings?.position === "left") {
    centerX = workArea.x + margin;
  }

  centerWin = new BrowserWindow({
    x: centerX,
    y: centerY,
    width: centerWidth,
    height: centerHeight,
    frame: false,
    movable: true,
    resizable: false,
    skipTaskbar: true,
    show: false,
    backgroundColor: "#00000000",
    backgroundMaterial: "mica",
    roundedCorners: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  centerWin.on("blur", () => {
    if (centerWin && !centerWin.isDestroyed() && centerWin.isVisible()) {
      centerWin.hide();
      request("markAllRead").catch(() => {});
    }
  });

  loadSurface(centerWin, "center");

  // 3. Panel window
  const panelWidth = 640;
  const panelHeight = 720;
  const panelX = Math.round(workArea.x + (workArea.width - panelWidth) / 2);
  const panelY = Math.round(workArea.y + (workArea.height - panelHeight) / 2);

  panelWin = new BrowserWindow({
    x: panelX,
    y: panelY,
    width: panelWidth,
    height: panelHeight,
    frame: false,
    movable: true,
    resizable: false,
    backgroundColor: "#00000000",
    backgroundMaterial: "mica",
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  panelWin.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      panelWin?.hide();
    }
  });

  loadSurface(panelWin, "panel");

  for (const w of [overlayWin, centerWin, panelWin]) {
    w?.webContents.on("console-message", (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        console.warn(`[Renderer Err] ${message} (${sourceId}:${line})`);
      }
    });
  }
  // Display change listeners
  screen.on("display-added", () => repositionWindows());
  screen.on("display-removed", () => repositionWindows());
  screen.on("display-metrics-changed", () => repositionWindows());
}

export function getOverlayWindow(): BrowserWindow | null {
  return overlayWin;
}

export function getCenterWindow(): BrowserWindow | null {
  return centerWin;
}

export function getPanelWindow(): BrowserWindow | null {
  return panelWin;
}

export function toggleCenterWindow(): void {
  if (!centerWin || centerWin.isDestroyed()) return;
  if (centerWin.isVisible()) {
    centerWin.hide();
    request("markAllRead").catch(() => {});
  } else {
    repositionWindows();
    centerWin.show();
    centerWin.focus();
  }
}

export function showPanelWindow(): void {
  if (!panelWin || panelWin.isDestroyed()) return;
  panelWin.show();
  panelWin.focus();
}

export function getAllWindows(): BrowserWindow[] {
  return [overlayWin, centerWin, panelWin].filter(
    (w): w is BrowserWindow => w !== null && !w.isDestroyed()
  );
}
