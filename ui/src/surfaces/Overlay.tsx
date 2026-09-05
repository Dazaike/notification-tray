import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  motion,
  AnimatePresence,
  LayoutGroup,
  useAnimate,
  useReducedMotion,
  type AnimationPlaybackControls,
} from "motion/react";
import { Info, Check, TriangleAlert, X } from "lucide-react";
import { LiquidGlassCard } from "@/components/kokonutui/liquid-glass-card";
import { CardStack } from "@/components/kokonutui/card-stack";
import { spring, cn } from "@/lib/utils";
import type { AppSettings, HistoryEntry, LiveToast, NotificationKind } from "@/types/tray";
import { getToastMotionProps } from "@/lib/animations";

const GROUP_WINDOW_MS = 30_000;
const MAX_GROUP_LINES = 6;

function getKindIcon(kind: NotificationKind) {
  switch (kind) {
    case "success":
      return <Check className="w-4 h-4 text-[var(--accent)]" />;
    case "warning":
      return <TriangleAlert className="w-4 h-4 text-[var(--accent)]" />;
    case "error":
      return <X className="w-4 h-4 text-[var(--accent)]" />;
    case "info":
    default:
      return <Info className="w-4 h-4 text-[var(--accent)]" />;
  }
}

function resolveAccent(appName: string, settings: AppSettings): string {
  if (appName && settings.app_colors) {
    const needle = appName.toLowerCase();
    for (const item of settings.app_colors) {
      const stem = item.exe
        ? item.exe.replace(/^.*[\\/]/, "").replace(/\.[^/.]+$/, "").toLowerCase()
        : "";
      if (stem && (stem.includes(needle) || needle.includes(stem))) {
        return item.color;
      }
    }
  }
  return settings.accent_color || "#4f98a3";
}

interface ToastCardProps {
  toast: LiveToast;
  settings: AppSettings;
  onDismiss: (key: string) => void;
  onActivate: (toast: LiveToast) => void;
  updateIgnoreMouse: (ignore: boolean) => void;
}

const ToastCard: React.FC<ToastCardProps> = ({
  toast,
  settings,
  onDismiss,
  onActivate,
  updateIgnoreMouse,
}) => {
  const shouldReduceMotion = useReducedMotion();
  const [scope, animate] = useAnimate();
  const animCtrl = useRef<AnimationPlaybackControls | null>(null);
  const [isExiting, setIsExiting] = useState(false);
  const [iconFailed, setIconFailed] = useState(false);

  useEffect(() => {
    setIconFailed(false);
  }, [toast.iconPath]);
  const durationMs = settings.durations?.[toast.kind] ?? 5000;
  // Cleanup on unmount ensures overlay window never remains non-transparent to clicks
  useEffect(() => {
    return () => {
      updateIgnoreMouse(true);
    };
  }, [updateIgnoreMouse]);


  // Countdown progress bar animation with frame-exact hover pause
  useEffect(() => {
    if (!scope.current) return;
    const anim = animate(
      scope.current,
      { scaleX: 0 },
      { duration: durationMs / 1000, ease: "linear" }
    );
    anim.then(() => {
      setIsExiting(true);
      updateIgnoreMouse(true);
      onDismiss(toast.key);
    });
    animCtrl.current = anim;

    return () => {
      anim.stop();
    };
  }, [durationMs, onDismiss, toast.key, animate, scope, updateIgnoreMouse]);

  const handleMouseEnter = useCallback(() => {
    if (isExiting) return;
    animCtrl.current?.pause();
    updateIgnoreMouse(false);
  }, [isExiting, updateIgnoreMouse]);

  const handleMouseLeave = useCallback(() => {
    animCtrl.current?.play();
    updateIgnoreMouse(true);
  }, [updateIgnoreMouse]);

  const handleCardClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExiting(true);
    updateIgnoreMouse(true);
    onActivate(toast);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsExiting(true);
    updateIgnoreMouse(true);
    onDismiss(toast.key);
  };

  const handleDismissClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExiting(true);
    updateIgnoreMouse(true);
    onDismiss(toast.key);
  };

  // Slide offset depending on screen position
  const motionProps = getToastMotionProps(settings, shouldReduceMotion);

  // Grouped message rendering: up to 6 lines, with +N more tail
  const shownMessages = toast.messages.slice(0, MAX_GROUP_LINES);
  const remainingCount = toast.messages.length - MAX_GROUP_LINES;

  const appDisplay = (toast.appName || "NOTIFICATION").toUpperCase().slice(0, 28);
  const titleDisplay = toast.title || (toast.kind.charAt(0).toUpperCase() + toast.kind.slice(1));
  const accent = resolveAccent(toast.appName, settings);

  return (
    <motion.div
      layout
      data-toast-card={isExiting ? undefined : "true"}
      initial={motionProps.initial}
      animate={motionProps.animate}
      exit={motionProps.exit}
      transition={motionProps.transition}
      className={cn(
        isExiting ? "pointer-events-none" : "pointer-events-auto",
        "select-none"
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleCardClick}
      onContextMenu={handleContextMenu}
      style={
        {
          ...motionProps.style,
          "--accent": accent,
          "--accent-soft": `color-mix(in srgb, ${accent} 18%, #121214)`,
        } as React.CSSProperties
      }
    >
      <CardStack count={toast.count}>
        <LiquidGlassCard
          glassOpacity={settings.toast_alpha}
          className="w-[400px] min-h-[92px] p-[14px] cursor-pointer"
        >
          <div className="flex items-start gap-3">
            {/* App / Kind Icon */}
            <div
              className={`shrink-0 w-[38px] h-[38px] rounded-icon overflow-hidden flex items-center justify-center ${
                toast.iconPath && !iconFailed
                  ? "bg-transparent"
                  : "bg-[var(--accent-soft)] border border-border/50"
              }`}
            >
              {toast.iconPath && !iconFailed ? (
                <img
                  src={`res:///${toast.iconPath.replace(/\\/g, "/")}`}
                  alt=""
                  className="w-full h-full object-contain rounded-icon"
                  onError={() => setIconFailed(true)}
                />
              ) : (
                getKindIcon(toast.kind)
              )}
            </div>

            {/* Content Column */}
            <div className="flex-1 min-w-0 flex flex-col justify-center">
              {/* Header: App Name */}
              <div className="text-[10px] font-semibold text-header uppercase tracking-wider truncate mb-0.5">
                {appDisplay}
              </div>

              {/* Title */}
              <div className="text-[13px] font-semibold text-fg truncate mb-1 leading-snug">
                {titleDisplay}
              </div>

              {/* Message lines */}
              <div className="text-[12px] text-subtext leading-[18px] break-words">
                {shownMessages.map((msg, i) => (
                  <div key={i} className="line-clamp-2">
                    {msg}
                  </div>
                ))}
                {remainingCount > 0 && (
                  <div className="text-[11px] text-muted italic mt-0.5">
                    +{remainingCount} more
                  </div>
                )}
              </div>
            </div>

            {/* Top right actions: Badge + Dismiss */}
            <div className="flex items-center gap-1.5 shrink-0 -mt-0.5 -mr-0.5">
              {toast.count > 1 && (
                <motion.span
                  key={`badge-${toast.count}`}
                  initial={{ scale: 1.25 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", visualDuration: 0.2, bounce: 0.3 }}
                  className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[11px] font-bold text-white bg-badge rounded-full shadow-sm"
                >
                  {toast.count > 99 ? "99+" : toast.count}
                </motion.span>
              )}

              <button
                type="button"
                onClick={handleDismissClick}
                className="w-5 h-5 flex items-center justify-center rounded-full text-muted hover:text-fg hover:bg-hover transition-colors outline-none cursor-pointer"
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* 2px Progress bar at bottom */}
          <div className="absolute inset-x-4 bottom-2 h-[2px] rounded-full bg-track overflow-hidden">
            <div
              ref={scope}
              style={{ transformOrigin: "left" }}
              className="h-full w-full bg-[var(--accent)]"
            />
          </div>
        </LiquidGlassCard>
      </CardStack>
    </motion.div>
  );
};

export const Overlay: React.FC = () => {
  const [toasts, setToasts] = useState<LiveToast[]>([]);
  const [settings, setSettings] = useState<AppSettings>({
    version: "2.0.12",
    position: "right",
    monitor: 0,
    monitor_device: "",
    durations: { info: 5000, success: 5000, warning: 5000, error: 5000 },
    accent_color: "#4f98a3",
    font_path: "",
    excluded_apps: [],
    app_colors: [],
    dnd: false,
    suppress_focused_app: true,
    sound_enabled: true,
    toast_alpha: 0.94,
    toast_scale: 1,
    gemini_enabled: true,
  });
  const isIgnoringMouseRef = useRef(true);
  const mousePosRef = useRef<{ x: number; y: number } | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const updateIgnoreMouse = useCallback((ignore: boolean) => {
    if (isIgnoringMouseRef.current !== ignore) {
      isIgnoringMouseRef.current = ignore;
      window.tray?.setIgnoreMouse(ignore);
    }
  }, []);

  // When no toasts exist, overlay must always be click-through
  useEffect(() => {
    if (toasts.length === 0) {
      updateIgnoreMouse(true);
    }
  }, [toasts.length, updateIgnoreMouse]);

  // Global pointer move tracking: whenever the pointer is over any toast card,
  // ensure clicks are captured; otherwise, clicks must pass through to underlying windows.
  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      mousePosRef.current = { x: e.clientX, y: e.clientY };
      const target = e.target as HTMLElement | null;
      const isOverCard = !!target?.closest?.("[data-toast-card]");
      updateIgnoreMouse(!isOverCard);
    };

    const handlePointerLeave = () => {
      updateIgnoreMouse(true);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerleave", handlePointerLeave, { passive: true });
    document.addEventListener("mouseleave", handlePointerLeave, { passive: true });

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", handlePointerLeave);
      document.removeEventListener("mouseleave", handlePointerLeave);
    };
  }, [updateIgnoreMouse]);


  // Fetch initial settings from core & subscribe to events
  useEffect(() => {
    if (!window.tray) return;

    window.tray
      .request<{ settings: AppSettings }>("monitors")
      .catch(() => {});

    const unsubSettings = window.tray.on<AppSettings>("settings", (newSettings) => {
      setSettings((prev) => ({ ...prev, ...newSettings }));
    });

    const unsubReady = window.tray.on<{ settings: AppSettings }>("ready", (data) => {
      if (data?.settings) {
        setSettings(data.settings);
      }
    });

    const unsubToast = window.tray.on<HistoryEntry>("toast", (entry) => {
      const now = Date.now();
      const accent = resolveAccent(entry.app_name, settingsRef.current);

      setToasts((prev) => {
        const existingIdx = prev.findIndex(
          (t) => t.groupKey === entry.group_key && now - t.createdAt <= GROUP_WINDOW_MS
        );

        if (existingIdx !== -1) {
          const updated = [...prev];
          const curr = updated[existingIdx];
          updated[existingIdx] = {
            ...curr,
            ids: [...curr.ids, entry.id],
            count: curr.count + 1,
            messages: [...curr.messages, entry.message],
            iconPath: entry.icon_path || curr.iconPath,
            title: entry.title || curr.title,
            appName: entry.app_name || curr.appName,
          };
          return updated;
        }

        const newToast: LiveToast = {
          key: entry.id,
          groupKey: entry.group_key,
          ids: [entry.id],
          count: 1,
          messages: [entry.message],
          title: entry.title,
          kind: entry.kind,
          appName: entry.app_name,
          iconPath: entry.icon_path,
          accent,
          createdAt: now,
        };

        return [newToast, ...prev];
      });
    });

    return () => {
      unsubSettings();
      unsubReady();
      unsubToast();
    };
  }, []);

  const handleDismiss = useCallback((key: string) => {
    updateIgnoreMouse(true);
    setToasts((prev) => prev.filter((t) => t.key !== key));
    setTimeout(() => {
      if (mousePosRef.current) {
        const el = document.elementFromPoint(mousePosRef.current.x, mousePosRef.current.y);
        if (el?.closest("[data-toast-card]")) {
          updateIgnoreMouse(false);
        }
      }
    }, 50);
  }, [updateIgnoreMouse]);

  const handleActivate = useCallback((toast: LiveToast) => {
    updateIgnoreMouse(true);
    window.tray?.request("activate", { ids: toast.ids }).catch(() => {});
    setToasts((prev) => prev.filter((t) => t.key !== toast.key));
    setTimeout(() => {
      if (mousePosRef.current) {
        const el = document.elementFromPoint(mousePosRef.current.x, mousePosRef.current.y);
        if (el?.closest("[data-toast-card]")) {
          updateIgnoreMouse(false);
        }
      }
    }, 50);
  }, [updateIgnoreMouse]);

  // Stack positioning
  const positionClass =
    settings.position === "left"
      ? "top-6 left-6"
      : settings.position === "center"
      ? "top-6 left-1/2 -translate-x-1/2"
      : "top-6 right-6";

  return (
    <div className="pointer-events-none h-screen w-screen relative overflow-hidden">
      <div
        className={cn(
          "absolute flex flex-col gap-[10px] items-start transition-all duration-300",
          positionClass
        )}
        style={{ zoom: settings.toast_scale ?? 1 }}
      >
        <LayoutGroup>
          <AnimatePresence mode="popLayout">
            {toasts.map((toast) => (
              <ToastCard
                key={toast.key}
                toast={toast}
                settings={settings}
                onDismiss={handleDismiss}
                onActivate={handleActivate}
                updateIgnoreMouse={updateIgnoreMouse}
              />
            ))}
          </AnimatePresence>
        </LayoutGroup>
      </div>
    </div>
  );
};
