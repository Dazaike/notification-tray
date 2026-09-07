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
  tray_click_action?: "center" | "panel";
  monitor: number;
  monitor_device: string;
  /** When true, toast overlays are created on every connected display. */
  multi_monitor?: boolean;
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

interface OverlayEntry {
  displayId: number;
  win: BrowserWindow;
}

let overlays: OverlayEntry[] = [];
let centerWin: BrowserWindow | null = null;
let panelWin: BrowserWindow | null = null;
let cachedPreloadPath = "";

let lastReadyData: unknown = null;

export function setReadyData(data: unknown): void {
  lastReadyData = data;
}

export function getCurrentSettings(): AppSettings | null {
  return currentSettings;
}

let currentSettings: AppSettings | null = null;
let currentMonitors: CoreMonitor[] = [];
let isQuitting = false;

export function setAppQuitting(quitting: boolean): void {
  isQuitting = quitting;
}

export function updateState(settings: AppSettings, monitors?: CoreMonitor[]): void {
  const prevMulti = Boolean(currentSettings?.multi_monitor);
  currentSettings = settings;
  if (monitors) {
    currentMonitors = monitors;
  }
  // Multi-monitor toggle or monitor target change needs overlay resync.
  if (cachedPreloadPath && (prevMulti !== Boolean(settings.multi_monitor) || overlays.length > 0)) {
    syncOverlayWindows();
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

function resolveOverlayDisplays(): Display[] {
  if (currentSettings?.multi_monitor) {
    return screen.getAllDisplays();
  }
  return [resolveTargetDisplay()];
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

function wireRendererLifecycle(win: BrowserWindow): void {
  win.webContents.on("did-finish-load", () => {
    if (lastReadyData) {
      win.webContents.send("core-event", "ready", lastReadyData);
    }
    if (currentSettings) {
      win.webContents.send("core-event", "settings", currentSettings);
    }
  });
  win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    if (level >= 2) {
      console.warn(`[Renderer Err] ${message} (${sourceId}:${line})`);
    }
  });
}

function createOverlayWindow(display: Display, preloadPath: string): BrowserWindow {
  const workArea = display.workArea;
  const win = new BrowserWindow({
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

  win.setAlwaysOnTop(true, "screen-saver");
  win.setIgnoreMouseEvents(true, { forward: true });
  wireRendererLifecycle(win);
  loadSurface(win, "overlay");
  win.showInactive();
  return win;
}

/** Create/destroy/reposition toast overlays to match multi_monitor + display layout. */
export function syncOverlayWindows(): void {
  if (!cachedPreloadPath) return;

  const wanted = resolveOverlayDisplays();
  const wantedIds = new Set(wanted.map((d) => d.id));

  // Drop overlays for disconnected / deselected displays.
  const kept: OverlayEntry[] = [];
  for (const entry of overlays) {
    if (!wantedIds.has(entry.displayId) || entry.win.isDestroyed()) {
      if (!entry.win.isDestroyed()) {
        entry.win.destroy();
      }
      continue;
    }
    kept.push(entry);
  }
  overlays = kept;

  const existingIds = new Set(overlays.map((e) => e.displayId));
  for (const display of wanted) {
    if (existingIds.has(display.id)) continue;
    const win = createOverlayWindow(display, cachedPreloadPath);
    overlays.push({ displayId: display.id, win });
  }

  // Reposition surviving overlays onto current work areas.
  for (const entry of overlays) {
    const display = wanted.find((d) => d.id === entry.displayId);
    if (!display || entry.win.isDestroyed()) continue;
    const workArea = display.workArea;
    entry.win.setBounds({
      x: workArea.x,
      y: workArea.y,
      width: workArea.width,
      height: workArea.height,
    });
  }
}

export function repositionWindows(): void {
  const target = resolveTargetDisplay();
  const workArea = target.workArea;

  syncOverlayWindows();

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

  if (panelWin && !panelWin.isDestroyed() && panelWin.isVisible()) {
    // Keep panel on the selected monitor when it is already open.
    const panelBounds = panelWin.getBounds();
    const panelX = Math.round(workArea.x + (workArea.width - panelBounds.width) / 2);
    const panelY = Math.round(workArea.y + (workArea.height - panelBounds.height) / 2);
    panelWin.setBounds({
      x: panelX,
      y: panelY,
      width: panelBounds.width,
      height: panelBounds.height,
    });
  }
}

export function createWindows(preloadPath: string): void {
  cachedPreloadPath = preloadPath;
  const target = resolveTargetDisplay();
  const workArea = target.workArea;

  // 1. Overlay window(s) — one per display when multi_monitor is on
  syncOverlayWindows();

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
    icon: path.join(__dirname, "../resources/icon.png"),
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

  wireRendererLifecycle(centerWin);
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
    icon: path.join(__dirname, "../resources/icon.png"),
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

  wireRendererLifecycle(panelWin);
  loadSurface(panelWin, "panel");

  // Display change listeners — recreate overlays when layout changes
  screen.removeAllListeners("display-added");
  screen.removeAllListeners("display-removed");
  screen.removeAllListeners("display-metrics-changed");
  screen.on("display-added", () => repositionWindows());
  screen.on("display-removed", () => repositionWindows());
  screen.on("display-metrics-changed", () => repositionWindows());
}

/** First overlay (compat). Prefer getOverlayWindows for multi-monitor. */
export function getOverlayWindow(): BrowserWindow | null {
  const live = overlays.find((e) => !e.win.isDestroyed());
  return live?.win ?? null;
}

export function getOverlayWindows(): BrowserWindow[] {
  return overlays.map((e) => e.win).filter((w) => !w.isDestroyed());
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

export function togglePanelWindow(): void {
  if (!panelWin || panelWin.isDestroyed()) return;
  if (panelWin.isVisible() && !panelWin.isMinimized()) {
    panelWin.hide();
  } else {
    repositionWindows();
    panelWin.show();
    panelWin.focus();
  }
}

export function handleTrayClick(): void {
  const action = currentSettings?.tray_click_action ?? "center";
  if (action === "panel") {
    togglePanelWindow();
  } else {
    toggleCenterWindow();
  }
}

export function getAllWindows(): BrowserWindow[] {
  return [...getOverlayWindows(), centerWin, panelWin].filter(
    (w): w is BrowserWindow => w !== null && !w.isDestroyed()
  );
}

/** Force click-through on every toast overlay (after activate / clear). */
export function setAllOverlaysIgnoreMouse(ignore: boolean): void {
  for (const win of getOverlayWindows()) {
    win.setIgnoreMouseEvents(ignore, { forward: true });
  }
}

/** Relay dismiss/activate so mirrored toasts stay in sync across monitors. */
export function broadcastOverlaySync(
  sender: Electron.WebContents,
  payload: { type: "dismiss" | "activate"; key: string }
): void {
  for (const win of getOverlayWindows()) {
    if (win.isDestroyed() || win.webContents.id === sender.id) continue;
    win.webContents.send("core-event", "overlay-sync", payload);
  }
}
