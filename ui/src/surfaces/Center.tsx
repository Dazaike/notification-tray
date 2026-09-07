import React, { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Info, Check, TriangleAlert, X, BellOff, Settings } from "lucide-react";
import { ActionSearchBar } from "@/components/kokonutui/action-search-bar";
import { HoldButton } from "@/components/kokonutui/hold-button";
import { LiquidGlassCard } from "@/components/kokonutui/liquid-glass-card";
import { spring, cn } from "@/lib/utils";
import type { AppSettings, HistoryEntry, NotificationKind } from "@/types/tray";

function getKindIcon(kind: NotificationKind) {
  switch (kind) {
    case "success":
      return <Check className="w-3.5 h-3.5 text-[var(--accent)]" />;
    case "warning":
      return <TriangleAlert className="w-3.5 h-3.5 text-[var(--accent)]" />;
    case "error":
      return <X className="w-3.5 h-3.5 text-[var(--accent)]" />;
    case "info":
    default:
      return <Info className="w-3.5 h-3.5 text-[var(--accent)]" />;
  }
}
function NotificationIcon({ iconPath, kind }: { iconPath?: string; kind: NotificationKind }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [iconPath]);

  const hasIcon = Boolean(iconPath && !failed);

  return (
    <div
      className={`shrink-0 w-9 h-9 rounded-icon overflow-hidden flex items-center justify-center ${
        hasIcon ? "bg-transparent" : "bg-card border border-border/40"
      }`}
    >
      {hasIcon ? (
        <img
          src={`res:///${iconPath!.replace(/\\/g, "/")}`}
          alt=""
          className="w-full h-full object-contain rounded-icon"
          onError={() => setFailed(true)}
        />
      ) : (
        getKindIcon(kind)
      )}
    </div>
  );
}
export const Center: React.FC = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [settings, setSettings] = useState<AppSettings>({
    version: "2.0.13",
    position: "right",
    monitor: 0,
    tray_click_action: "center",
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

  useEffect(() => {
    if (!window.tray) return;

    window.tray
      ?.request<{
        history?: HistoryEntry[];
        settings?: AppSettings;
      }>("getState")
      .then((res) => {
        if (res && Array.isArray(res.history)) {
          setHistory(res.history);
        }
        if (res?.settings) {
          setSettings((prev) => ({ ...prev, ...res.settings }));
        }
      })
      .catch(() => {});

    // Listen for history updates
    const unsubHistory = window.tray.on<{ history: HistoryEntry[] }>("history", (data) => {
      if (data && Array.isArray(data.history)) {
        setHistory(data.history);
      }
    });

    const unsubReady = window.tray.on<{ history: HistoryEntry[]; settings: AppSettings }>("ready", (data) => {
      if (data?.history) {
        setHistory(data.history);
      }
      if (data?.settings) {
        setSettings(data.settings);
      }
    });

    const unsubSettings = window.tray.on<AppSettings>("settings", (newSettings) => {
      setSettings((prev) => ({ ...prev, ...newSettings }));
    });

    // Close on Escape key
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        window.tray?.hideSelf();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      unsubHistory();
      unsubReady();
      unsubSettings();
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Filter and reverse history (newest first)
  const filteredHistory = useMemo(() => {
    const q = search.trim().toLowerCase();
    const reversed = [...history].reverse();
    if (!q) return reversed;

    return reversed.filter((item) => {
      const titleMatch = item.title?.toLowerCase().includes(q);
      const msgMatch = item.message?.toLowerCase().includes(q);
      const appMatch = item.app_name?.toLowerCase().includes(q);
      return titleMatch || msgMatch || appMatch;
    });
  }, [history, search]);

  const handleActivate = (entry: HistoryEntry) => {
    window.tray?.request("activate", { ids: [entry.id] }).catch(() => {});
    setHistory((prev) => prev.filter((h) => h.id !== entry.id));
  };

  const handleDismiss = (e: React.MouseEvent, entry: HistoryEntry) => {
    e.stopPropagation();
    window.tray?.request("dismissHistory", { ids: [entry.id] }).catch(() => {});
    setHistory((prev) => prev.filter((h) => h.id !== entry.id));
  };

  const handleClearAll = () => {
    window.tray?.request("clearHistory").catch(() => {});
    setHistory([]);
  };

  // Grouping into sections: consecutive entries sharing title || capitalize(kind)
  const sections = useMemo(() => {
    const result: Array<{ header: string; items: HistoryEntry[] }> = [];
    let currentHeader = "";
    let currentItems: HistoryEntry[] = [];

    for (const entry of filteredHistory) {
      const header = entry.title || (entry.kind.charAt(0).toUpperCase() + entry.kind.slice(1));
      if (header !== currentHeader) {
        if (currentItems.length > 0) {
          result.push({ header: currentHeader, items: currentItems });
        }
        currentHeader = header;
        currentItems = [entry];
      } else {
        currentItems.push(entry);
      }
    }

    if (currentItems.length > 0) {
      result.push({ header: currentHeader, items: currentItems });
    }

    return result;
  }, [filteredHistory]);

  return (
    <div
      style={
        {
          "--accent": settings.accent_color || "#4f98a3",
          "--accent-soft": `color-mix(in srgb, ${settings.accent_color || "#4f98a3"} 18%, #121214)`,
        } as React.CSSProperties
      }
      className="flex flex-col h-screen w-screen bg-bg/95 text-fg p-4 select-none overflow-hidden"
    >
      {/* Header bar */}
      <div
        style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
        className="flex items-center justify-between gap-3 mb-3 shrink-0 cursor-move"
      >
        <div className="pointer-events-none">
          <h1 className="text-sm font-semibold text-fg tracking-tight">Notifications</h1>
          <p className="text-[11px] text-muted">
            {history.length} {history.length === 1 ? "notification" : "notifications"}
          </p>
        </div>
        <div
          className="flex items-center gap-2"
          style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        >
          {history.length > 0 && (
            <HoldButton onAction={handleClearAll} holdDurationMs={900}>
              Clear all
            </HoldButton>
          )}
          <button
            type="button"
            onClick={() => window.tray?.showPanel?.()}
            className="p-1.5 rounded-lg border border-border bg-card/60 hover:bg-hover text-muted hover:text-fg transition-colors cursor-pointer"
            title="Open Settings Panel"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Search field */}
      <div className="mb-3 shrink-0">
        <ActionSearchBar
          value={search}
          onChange={setSearch}
          placeholder="Filter by title, message, or app..."
        />
      </div>

      {/* Notifications list */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden pr-1 space-y-3 scrollbar-thin">
        {sections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted/70 gap-2">
            <BellOff className="w-8 h-8 stroke-1" />
            <span className="text-xs">No notifications yet</span>
          </div>
        ) : (
          sections.map((section, sIndex) => (
            <div key={`section-${sIndex}`} className="space-y-1.5">
              {/* Sticky section header */}
              <div className="sticky top-0 z-20 py-1 px-2 text-[11px] font-semibold text-header uppercase tracking-wider bg-bg/90 backdrop-blur-md rounded-md">
                {section.header}
              </div>

              {/* Rows */}
              <AnimatePresence mode="popLayout">
                {section.items.map((entry, itemIndex) => {
                  const isUnread = !entry.read;
                  return (
                    <motion.div
                      key={entry.id}
                      layout
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.16 } }}
                      transition={{
                        ...spring,
                        delay: Math.min(itemIndex * 0.03, 0.2),
                      }}
                    >
                      <LiquidGlassCard
                        onClick={() => handleActivate(entry)}
                        className={cn(
                          "group flex items-center gap-3 p-2.5 rounded-xl cursor-pointer transition-colors border",
                          isUnread
                            ? "bg-[var(--accent-soft)] border-[var(--accent)]/30 text-fg"
                            : "bg-card/70 border-border text-subtext hover:bg-hover hover:text-fg"
                        )}
                      >
                        {/* Icon */}
                        <NotificationIcon iconPath={entry.icon_path} kind={entry.kind} />

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-0.5">
                            <span className="text-xs font-medium text-fg truncate">
                              {entry.app_name || entry.title}
                            </span>
                            <span className="text-[10px] text-muted shrink-0 font-mono">
                              {entry.timestamp}
                            </span>
                          </div>
                          <p className="text-[11px] leading-relaxed line-clamp-2 text-subtext group-hover:text-fg/90 transition-colors">
                            {entry.message}
                          </p>
                        </div>

                        {/* Dismiss button */}
                        <button
                          type="button"
                          onClick={(e) => handleDismiss(e, entry)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-muted hover:text-fg hover:bg-hover transition-opacity shrink-0 cursor-pointer"
                          title="Dismiss"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </LiquidGlassCard>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
