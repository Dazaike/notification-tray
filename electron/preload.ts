import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

const urlParams = new URLSearchParams(window.location.search);
const surface = (urlParams.get("surface") || "overlay") as "overlay" | "center" | "panel";

contextBridge.exposeInMainWorld("tray", {
  surface,
  request<T = unknown>(op: string, args?: Record<string, unknown>): Promise<T> {
    return ipcRenderer.invoke("core", op, args);
  },
  on<T = unknown>(event: string, cb: (data: T) => void): () => void {
    const handler = (_e: IpcRendererEvent, name: string, data: unknown) => {
      if (name === event || event === "*") {
        cb(data as T);
      }
    };
    ipcRenderer.on("core-event", handler);
    return () => {
      ipcRenderer.removeListener("core-event", handler);
    };
  },
  setIgnoreMouse(ignore: boolean): void {
    ipcRenderer.send("set-ignore-mouse", ignore);
  },
  hideSelf(): void {
    ipcRenderer.send("hide-self");
  },
  pickFile(kind: "exe" | "font" | "audio"): Promise<string | null> {
    return ipcRenderer.invoke("pick-file", kind);
  },
  loginItem: {
    get(): Promise<boolean> {
      return ipcRenderer.invoke("login-item:get");
    },
    set(v: boolean): Promise<void> {
      return ipcRenderer.invoke("login-item:set", v);
    },
  },
});
