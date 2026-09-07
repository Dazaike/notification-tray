import path from "node:path";
import { pathToFileURL } from "node:url";
import { app, BrowserWindow, dialog, ipcMain, net, protocol } from "electron";
import { onCoreEvent, request, startCore, stopCore } from "./core";
import { createTray, refreshTrayIcon, updateUnreadCount } from "./tray";
import {
  broadcastOverlaySync,
  createWindows,
  getAllWindows,
  getOverlayWindows,
  handleTrayClick,
  setAllOverlaysIgnoreMouse,
  setAppQuitting,
  setReadyData,
  showPanelWindow,
  toggleCenterWindow,
  togglePanelWindow,
  updateState,
  type AppSettings,
  type CoreMonitor,
} from "./windows";


const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: "res",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      bypassCSP: true,
    },
  },
]);

app.on("second-instance", () => {
  handleTrayClick();
});

app.on("window-all-closed", () => {
  // Never quit on window-all-closed: this is a tray app.
});

async function shutdownApp(): Promise<void> {
  setAppQuitting(true);
  try {
    await stopCore();
  } catch (err) {
    console.error("[main.ts] Error stopping core:", err);
  }
  app.quit();
}

app.whenReady().then(async () => {
  protocol.handle("res", (req) => {
    try {
      const parsed = new URL(req.url);
      let filePath = decodeURIComponent(parsed.pathname);
      if (process.platform === "win32") {
        if (parsed.host) {
          if (/^[a-zA-Z]:?$/.test(parsed.host)) {
            filePath = `${parsed.host.replace(/:$/, "")}:${filePath}`;
          } else {
            filePath = `//${parsed.host}${filePath}`;
          }
        } else if (filePath.startsWith("/") && /^\/[a-zA-Z]:/.test(filePath)) {
          filePath = filePath.slice(1);
        }
      }
      return net.fetch(pathToFileURL(filePath).toString(), { bypassCustomProtocolHandlers: true });
    } catch (err) {
      console.error("[main.ts] Error resolving res:// URL:", req.url, err);
      return new Response("Not Found", { status: 404 });
    }
  });

  // Setup IPC handlers
  ipcMain.handle("core", async (_event, op: string, args: Record<string, unknown> = {}) => {
    if (op === "activate" || op === "clearHistory" || op === "dismissHistory") {
      setAllOverlaysIgnoreMouse(true);
    }
    return request(op, args);
  });

  // Per-window click-through so hovering a toast on one monitor does not
  // steal mouse input from the other overlays.
  ipcMain.on("set-ignore-mouse", (event, ignore: boolean) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (win && !win.isDestroyed() && getOverlayWindows().includes(win)) {
      win.setIgnoreMouseEvents(Boolean(ignore), { forward: true });
    }
  });

  ipcMain.on("overlay-sync", (event, payload: { type: "dismiss" | "activate"; key: string }) => {
    if (!payload || (payload.type !== "dismiss" && payload.type !== "activate") || !payload.key) {
      return;
    }
    broadcastOverlaySync(event.sender, payload);
  });


  ipcMain.on("hide-self", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (win && !win.isDestroyed()) {
      win.hide();
    }
  });
  ipcMain.on("show-panel", () => {
    showPanelWindow();
  });

  ipcMain.on("toggle-panel", () => {
    togglePanelWindow();
  });

  ipcMain.on("toggle-center", () => {
    toggleCenterWindow();
  });


  ipcMain.handle("pick-file", async (_event, kind: "exe" | "font" | "audio") => {
    const filters =
      kind === "exe"
        ? [{ name: "Applications", extensions: ["exe"] }]
        : kind === "font"
        ? [{ name: "Fonts", extensions: ["ttf", "otf", "woff2"] }]
        : [{ name: "Audio Files", extensions: ["mp3", "wav", "wma", "aac", "m4a", "ogg"] }];
    const res = await dialog.showOpenDialog({
      properties: ["openFile"],
      filters,
    });

    if (res.canceled || res.filePaths.length === 0) {
      return null;
    }
    return res.filePaths[0];
  });

  ipcMain.handle("login-item:get", () => {
    return app.getLoginItemSettings().openAtLogin;
  });

  ipcMain.handle("login-item:set", (_event, enabled: boolean) => {
    app.setLoginItemSettings({
      openAtLogin: enabled,
      path: process.execPath,
      args: ["--hidden"],
    });
  });

  // Broadcast all core events to all windows
  onCoreEvent("*", (eventName, data) => {
    for (const win of getAllWindows()) {
      if (!win.isDestroyed()) {
        win.webContents.send("core-event", eventName, data);
      }
    }
  });
  onCoreEvent("ready", (data: unknown) => {
    setReadyData(data);
  });


  onCoreEvent("unread", (data: unknown) => {
    if (data && typeof data === "object" && "count" in data) {
      const countVal = data.count;
      if (typeof countVal === "number") {
        updateUnreadCount(countVal);
      }
    }
  });

  onCoreEvent("settings", (data: unknown) => {
    if (data && typeof data === "object") {
      updateState(data as AppSettings);
      refreshTrayIcon().catch(() => {});
    }
  });

  // Start Python core service and await ready event
  const preloadPath = path.join(__dirname, "preload.js");
  try {
    const rawReady = await startCore();
    if (rawReady && typeof rawReady === "object") {
      setReadyData(rawReady);
      const readyObj = rawReady as {
        settings?: AppSettings;
        monitors?: CoreMonitor[];
        unread?: number;
      };
      if (readyObj.settings) {
        updateState(readyObj.settings, readyObj.monitors);
      }
      if (typeof readyObj.unread === "number") {
        updateUnreadCount(readyObj.unread);
      }
    }

    createWindows(preloadPath);
    createTray(() => {
      shutdownApp().catch(() => app.quit());
    });
  } catch (err) {
    console.error("[main.ts] Failed to start core or create windows:", err);
  }
});
