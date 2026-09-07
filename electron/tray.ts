import path from "node:path";
import { app, Menu, nativeImage, screen, Tray } from "electron";
import { request } from "./core";
import { handleTrayClick, showPanelWindow, toggleCenterWindow } from "./windows";

let tray: Tray | null = null;
let lastUnread = 0;
let onQuitCallback: (() => void) | null = null;

export async function refreshTrayIcon(): Promise<void> {
  if (!tray || tray.isDestroyed()) return;
  try {
    const scale = screen.getPrimaryDisplay().scaleFactor;
    const size = Math.round(16 * scale);
    const res = await request<{ dataUrl: string }>("trayIcon", { size });
    if (res && res.dataUrl) {
      const img = nativeImage.createFromDataURL(res.dataUrl);
      tray.setImage(img);
    }
  } catch (err) {
    console.error("[tray.ts] Failed to update tray icon:", err);
  }
}

export function updateUnreadCount(count: number): void {
  lastUnread = count;
  refreshTrayIcon().catch(() => {});
}

export function createTray(onQuit: () => void): Tray {
  onQuitCallback = onQuit;

  const defaultIconPath = path.join(__dirname, "../resources/icon.png");
  const initialImg = nativeImage.createFromPath(defaultIconPath);
  tray = new Tray(initialImg.isEmpty() ? nativeImage.createEmpty() : initialImg);
  tray.setToolTip("Notification Tray");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Notification Center",
      type: "normal",
      click: () => {
        toggleCenterWindow();
      },
    },
    {
      label: "Settings",
      type: "normal",
      click: () => {
        showPanelWindow();
      },
    },
    {
      label: "Send test notification",
      type: "normal",
      click: () => {
        request("notify", {
          message: "This is a preview of the restyled modern notification card.",
          title: "Notification Tray",
          kind: "info",
          app_name: "Notification Tray",
          icon_path: path.join(__dirname, "../resources/icon.png"),
        }).catch((err) => console.error("[tray] Send test notification error:", err));
      },
    },
    {
      label: "Clear all",
      type: "normal",
      click: () => {
        request("clearHistory").catch((err) => console.error("[tray] Clear all error:", err));
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      type: "normal",
      click: () => {
        if (onQuitCallback) {
          onQuitCallback();
        } else {
          app.quit();
        }
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  tray.on("click", () => {
    handleTrayClick();
  });

  tray.on("double-click", () => {
    handleTrayClick();
  });

  refreshTrayIcon().catch(() => {});

  return tray;
}
