import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";
import path from "node:path";
import { app } from "electron";

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
}

interface CoreEventFrame {
  t: "ev";
  name: string;
  data: unknown;
}

interface CoreResponseFrame {
  t: "res";
  id: number;
  ok: boolean;
  data?: unknown;
  error?: string;
}

type CoreFrame = CoreEventFrame | CoreResponseFrame;

let child: ChildProcessWithoutNullStreams | null = null;
let nextId = 1;
const pending = new Map<number, PendingRequest>();
const emitter = new EventEmitter();
let isQuitting = false;
let restartAttempts = 0;
const MAX_RESTART_ATTEMPTS = 5;

function getLaunchTarget(): { exePath: string; args: string[]; cwd: string } {
  if (app.isPackaged) {
    const exePath = path.join(process.resourcesPath, "core", "core.exe");
    return {
      exePath,
      args: [],
      cwd: path.dirname(exePath),
    };
  }
  const rootDir = path.resolve(__dirname, "..");
  return {
    exePath: "python",
    args: ["core_service.py"],
    cwd: rootDir,
  };
}

export function startCore(): Promise<unknown> {
  const { promise, resolve: resolveReady, reject: rejectReady } = Promise.withResolvers<unknown>();
  const { exePath, args, cwd } = getLaunchTarget();

  child = spawn(exePath, args, {
    cwd,
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  });

  let buffer = "";

  child.stdout.on("data", (chunk: Buffer) => {
    buffer += chunk.toString("utf-8");
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      try {
        const msg = JSON.parse(line) as CoreFrame;
        if (msg.t === "res") {
          const p = pending.get(msg.id);
          if (p) {
            pending.delete(msg.id);
            if (msg.ok) {
              p.resolve(msg.data);
            } else {
              p.reject(new Error(msg.error || "Request failed"));
            }
          }
        } else if (msg.t === "ev") {
          emitter.emit(msg.name, msg.data);
          emitter.emit("*", msg.name, msg.data);
          if (msg.name === "ready") {
            resolveReady(msg.data);
          }
        }
      } catch (err) {
        console.error("[core.ts] Error parsing NDJSON frame:", line, err);
      }
    }
  });

  child.stderr.on("data", (chunk: Buffer) => {
    process.stderr.write(`[core-err] ${chunk.toString("utf-8")}`);
  });

  child.on("error", (err) => {
    console.error("[core.ts] Failed to start core process:", err);
    rejectReady(err);
  });

  child.on("exit", (code, signal) => {
    console.log(`[core.ts] Core process exited (code=${code}, signal=${signal})`);
    for (const [id, req] of pending.entries()) {
      req.reject(new Error(`Core process exited before response (id=${id})`));
    }
    pending.clear();
    child = null;

    if (!isQuitting && restartAttempts < MAX_RESTART_ATTEMPTS) {
      restartAttempts++;
      console.warn(`[core.ts] Restarting core (attempt ${restartAttempts}/${MAX_RESTART_ATTEMPTS}) in 1s...`);
      setTimeout(() => {
        startCore().catch((e) => console.error("[core.ts] Restart failed:", e));
      }, 1000);
    }
  });

  return promise;
}

export function request<T = unknown>(op: string, args: Record<string, unknown> = {}): Promise<T> {
  const { promise, resolve, reject } = Promise.withResolvers<T>();
  if (!child || !child.stdin || child.killed) {
    reject(new Error("Core process is not running"));
    return promise;
  }
  const id = nextId++;
  pending.set(id, {
    resolve: (val) => resolve(val as T),
    reject,
  });
  const frame = JSON.stringify({ t: "req", id, op, args }) + "\n";
  child.stdin.write(frame, "utf-8");
  return promise;
}

export function onCoreEvent(event: string, handler: (...args: unknown[]) => void): () => void {
  emitter.on(event, handler);
  return () => {
    emitter.off(event, handler);
  };
}

export async function stopCore(): Promise<void> {
  isQuitting = true;
  if (child && child.stdin && !child.killed) {
    try {
      await request("shutdown", {});
    } catch {
      child.kill();
    }
  }
}
