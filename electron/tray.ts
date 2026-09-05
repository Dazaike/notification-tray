import { app, Menu, nativeImage, screen, Tray } from "electron";
import { request } from "./core";
import { showPanelWindow, toggleCenterWindow } from "./windows";

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

  // Create with empty transparent 16x16 image initially
  const initialImg = nativeImage.createEmpty();
  tray = new Tray(initialImg);
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
      label: "Show panel",
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
    toggleCenterWindow();
  });

  refreshTrayIcon().catch(() => {});

  return tray;
}
