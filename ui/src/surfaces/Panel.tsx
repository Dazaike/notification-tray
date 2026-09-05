import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Palette,
  Sliders,
  Filter,
  Sparkles,
  Monitor,
  Volume2,
  VolumeX,
  Plus,
  Trash2,
  Check,
  FolderOpen,
  RotateCcw,
  X,
  Wand2,
  Play,
  RefreshCw,
  Eye,
} from "lucide-react";
import {
  INCOMING_ANIMATIONS,
  OUTGOING_ANIMATIONS,
  ANIMATION_PRESETS,
  type PresetInfo,
  getToastMotionProps,
} from "@/lib/animations";
import { SmoothTab, type TabItem } from "@/components/kokonutui/smooth-tab";
import { SpotlightCard } from "@/components/kokonutui/spotlight-cards";
import { ParticleButton } from "@/components/kokonutui/particle-button";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { spring, cn } from "@/lib/utils";
import type { AppSettings, MonitorInfo, NotificationKind } from "@/types/tray";

const TABS: TabItem[] = [
  { id: "appearance", label: "Appearance", icon: <Palette className="w-3.5 h-3.5" /> },
  { id: "animations", label: "Animations", icon: <Wand2 className="w-3.5 h-3.5" /> },
  { id: "behaviour", label: "Behaviour", icon: <Sliders className="w-3.5 h-3.5" /> },
  { id: "filters", label: "Filters", icon: <Filter className="w-3.5 h-3.5" /> },
  { id: "ai", label: "AI", icon: <Sparkles className="w-3.5 h-3.5" /> },
];

const DEMO_NOTIFICATIONS = [
  {
    message: "Team sync starts in 10 minutes in Room 4A.",
    title: "Calendar",
    kind: "info" as NotificationKind,
    app_name: "Calendar",
  },
  {
    message: "All 42 unit tests passed in 1.2s.",
    title: "Build System",
    kind: "success" as NotificationKind,
    app_name: "Visual Studio",
  },
  {
    message: "Battery level below 20%. Connect charger.",
    title: "System Alert",
    kind: "warning" as NotificationKind,
    app_name: "Windows",
  },
  {
    message: "Connection timed out while syncing data.",
    title: "Cloud Sync",
    kind: "error" as NotificationKind,
    app_name: "OneDrive",
  },
];

function normalizeAccent(raw: string): string | null {
  let hex = raw.trim();
  if (!hex) return null;
  if (!hex.startsWith("#")) hex = `#${hex}`;
  if (/^#[0-9a-fA-F]{3}$/.test(hex)) {
    hex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
  }
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return null;
  return hex.toLowerCase();
}

export const Panel: React.FC = () => {
  const [activeTab, setActiveTab] = useState("appearance");
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [startOnLogin, setStartOnLogin] = useState(false);
  const [geminiKeyPresent, setGeminiKeyPresent] = useState(false);
  const [geminiInput, setGeminiInput] = useState("");
  const [saveStatus, setSaveStatus] = useState("All changes saved");
  const [newAppExe, setNewAppExe] = useState("");
  const [newAppColor, setNewAppColor] = useState("#4f98a3");
  const [accentInput, setAccentInput] = useState("#4f98a3");

  const [sandboxVisible, setSandboxVisible] = useState(true);
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
    custom_sound_path: "",
    toast_alpha: 0.94,
    toast_scale: 1,
    gemini_enabled: true,
    animation_preset: "default",
    anim_incoming: "soft-slide",
    anim_outgoing: "slide-away",
    anim_direction: "auto",
    anim_duration: 350,
    anim_easing: "spring",
    anim_distance: 400,
    anim_bounce: 0.3,
    anim_blur: 12,
    anim_scale: 0.9,
  });

  const flashSave = useCallback((msg = "Saved") => {
    setSaveStatus(msg);
    setTimeout(() => setSaveStatus("All changes saved"), 2000);
  }, []);

  // Sync state from core
  useEffect(() => {
    if (!window.tray) return;

    window.tray
      .request<{ monitors: MonitorInfo[] }>("monitors")
      .then((res) => {
        if (res && Array.isArray(res.monitors)) {
          setMonitors(res.monitors);
        }
      })
      .catch(() => {});

    window.tray
      .request<{ present: boolean }>("geminiKeyPresent")
      .then((res) => {
        if (res) setGeminiKeyPresent(Boolean(res.present));
      })
      .catch(() => {});

    window.tray.loginItem
      ?.get()
      .then((v) => setStartOnLogin(v))
      .catch(() => {});

    const unsubSettings = window.tray.on<AppSettings>("settings", (newSettings) => {
      setSettings((prev) => ({ ...prev, ...newSettings }));
      if (newSettings.accent_color) {
        setAccentInput(newSettings.accent_color);
      }
    });

    const unsubReady = window.tray.on<{
      settings: AppSettings;
      monitors: MonitorInfo[];
    }>("ready", (data) => {
      if (data?.settings) {
        setSettings(data.settings);
        setAccentInput(data.settings.accent_color || "#4f98a3");
      }
      if (Array.isArray(data?.monitors)) {
        setMonitors(data.monitors);
      }
    });

    return () => {
      unsubSettings();
      unsubReady();
    };
  }, []);

  const updateSetting = async (key: string, value: unknown) => {
    if (!window.tray) return;
    try {
      setSettings((prev) => ({ ...prev, [key]: value }));
      if (key === "accent_color" && typeof value === "string") {
        setAccentInput(value);
      }
      await window.tray.request("setSetting", { key, value });
      flashSave();
    } catch (e) {
      console.error("Failed to update setting:", key, value, e);
    }
  };

  const triggerTestToast = (titlePrefix?: string) => {
    const incObj = INCOMING_ANIMATIONS.find((a) => a.id === settings.anim_incoming);
    const outObj = OUTGOING_ANIMATIONS.find((a) => a.id === settings.anim_outgoing);
    const inc = incObj?.label || settings.anim_incoming || "Soft Slide";
    const out = outObj?.label || settings.anim_outgoing || "Slide Away";
    window.tray
      ?.request("notify", {
        title: titlePrefix ? `${titlePrefix}` : "Notification Animation",
        message: `In: ${inc} ➔ Out: ${out}`,
        kind: "info",
        app_name: "Animation Preview",
      })
      .catch(() => {});
  };

  const applyPreset = async (preset: PresetInfo) => {
    setSettings((prev) => ({
      ...prev,
      animation_preset: preset.id,
      anim_incoming: preset.incoming,
      anim_outgoing: preset.outgoing,
      anim_duration: preset.duration ?? prev.anim_duration,
      anim_easing: preset.easing ?? prev.anim_easing,
      anim_bounce: preset.bounce ?? prev.anim_bounce,
      anim_distance: preset.distance ?? prev.anim_distance,
      anim_blur: preset.blur ?? prev.anim_blur,
      anim_scale: preset.scale ?? prev.anim_scale,
    }));

    await window.tray?.request("setSetting", { key: "animation_preset", value: preset.id });
    await window.tray?.request("setSetting", { key: "anim_incoming", value: preset.incoming });
    await window.tray?.request("setSetting", { key: "anim_outgoing", value: preset.outgoing });
    if (preset.duration !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_duration", value: preset.duration });
    }
    if (preset.easing !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_easing", value: preset.easing });
    }
    if (preset.bounce !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_bounce", value: preset.bounce });
    }
    if (preset.distance !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_distance", value: preset.distance });
    }
    if (preset.blur !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_blur", value: preset.blur });
    }
    if (preset.scale !== undefined) {
      await window.tray?.request("setSetting", { key: "anim_scale", value: preset.scale });
    }
    flashSave(`Preset applied: ${preset.label}`);
    triggerTestToast(preset.label);
  };

  const replaySandbox = () => {
    setSandboxVisible(false);
    setTimeout(() => {
      setSandboxVisible(true);
    }, 280);
  };

  const applyAccent = (raw: string) => {
    const hex = normalizeAccent(raw);
    if (!hex) return;
    if (hex === normalizeAccent(settings.accent_color || "")) return;
    void updateSetting("accent_color", hex);
  };

  const handleDemoBurst = () => {
    DEMO_NOTIFICATIONS.forEach((item, index) => {
      setTimeout(() => {
        window.tray?.request("notify", item).catch(() => {});
      }, index * 450);
    });
  };

  const handleBrowseFont = async () => {
    const file = await window.tray?.pickFile("font");
    if (!file) return;

    const res = await window.tray?.request<{ ok: boolean }>("validateFont", { path: file });
    if (res?.ok) {
      await updateSetting("font_path", file);

      // Inject custom font preview in current document
      const styleId = "notif-custom-font-style";
      let styleTag = document.getElementById(styleId) as HTMLStyleElement | null;
      if (!styleTag) {
        styleTag = document.createElement("style");
        styleTag.id = styleId;
        document.head.appendChild(styleTag);
      }
      const fontUrl = `res:///${file.replace(/\\/g, "/")}`;
      styleTag.textContent = `@font-face { font-family: 'NotifCustom'; src: url('${fontUrl}'); }`;
      document.body.style.fontFamily = "'NotifCustom', sans-serif";

      handleDemoBurst();
    }
  };

  const handleResetFont = async () => {
    await updateSetting("font_path", "");
    const styleTag = document.getElementById("notif-custom-font-style");
    if (styleTag) styleTag.remove();
    document.body.style.fontFamily = "";
    flashSave("Font reset to default");
  };
  const handleBrowseSound = async () => {
    const file = await window.tray?.pickFile("audio");
    if (!file) return;
    await updateSetting("custom_sound_path", file);
    flashSave("Notification sound updated");
    window.tray?.request("testSound", { path: file }).catch(() => {});
  };

  const handleTestSound = () => {
    window.tray?.request("testSound", { path: settings.custom_sound_path }).catch(() => {});
  };

  const handleResetSound = async () => {
    await updateSetting("custom_sound_path", "");
    flashSave("Sound reset to default");
    window.tray?.request("testSound", { path: "" }).catch(() => {});
  };


  const handleAddExcludedApp = async () => {
    const file = await window.tray?.pickFile("exe");
    if (!file) return;
    await window.tray?.request("addExcludedApp", { path: file });
    flashSave("Excluded app added");
  };

  const handleRemoveExcludedApp = async (index: number) => {
    await window.tray?.request("removeExcludedApp", { index });
    flashSave("Excluded app removed");
  };

  const handleAddAppColor = async () => {
    if (!newAppExe.trim() || !newAppColor.trim()) return;
    await window.tray?.request("addAppColor", { exe: newAppExe.trim(), color: newAppColor.trim() });
    setNewAppExe("");
    flashSave("App color added");
  };

  const handleRemoveAppColor = async (index: number) => {
    await window.tray?.request("removeAppColor", { index });
    flashSave("App color removed");
  };

  const handleSaveGeminiKey = async () => {
    if (!geminiInput.trim()) return;
    const res = await window.tray?.request<{ ok: boolean }>("saveGeminiKey", {
      key: geminiInput.trim(),
    });
    if (res?.ok) {
      setGeminiInput("");
      setGeminiKeyPresent(true);
      flashSave("API Key saved securely in Windows Credential Manager");
    }
  };

  const handleClearGeminiKey = async () => {
    await window.tray?.request("saveGeminiKey", { key: "" });
    setGeminiKeyPresent(false);
    setGeminiInput("");
    flashSave("API Key cleared");
  };

  return (
    <div
      style={
        {
          "--accent": settings.accent_color || "#4f98a3",
          "--accent-soft": `color-mix(in srgb, ${settings.accent_color || "#4f98a3"} 18%, #121214)`,
        } as React.CSSProperties
      }
      className="flex flex-col h-screen w-screen bg-bg/95 text-fg p-5 select-none overflow-hidden"
    >
      {/* Header bar */}
      {/* Header bar (draggable window titlebar) */}
      <div
        style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
        className="flex items-center justify-between gap-4 pb-3 border-b border-border/70 shrink-0 cursor-move"
      >
        <div className="flex items-center gap-2.5 pointer-events-none">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center border border-[var(--accent)]/30">
            <Sliders className="w-4 h-4 text-[var(--accent)]" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight">Notification Settings</h1>
            <p className="text-[10px] text-muted">Version {settings.version || "2.0.12"}</p>
          </div>
        </div>

        <button
          type="button"
          style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
          onClick={() => window.tray?.hideSelf()}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-fg hover:bg-hover transition-colors cursor-pointer outline-none"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs navigation */}
      <div className="py-3 shrink-0">
        <SmoothTab tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden pr-1 space-y-4 scrollbar-thin">
        <AnimatePresence mode="wait">
          {activeTab === "appearance" && (
            <motion.div
              key="tab-appearance"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {/* Position */}
              <SpotlightCard>
                <h3 className="text-xs font-semibold text-fg mb-2">Screen Position</h3>
                <div className="grid grid-cols-3 gap-2">
                  {(["left", "center", "right"] as const).map((pos) => (
                    <button
                      key={pos}
                      type="button"
                      onClick={() => updateSetting("position", pos)}
                      className={cn(
                        "py-2 px-3 rounded-lg text-xs font-medium capitalize border transition-all cursor-pointer",
                        settings.position === pos
                          ? "bg-[var(--accent)] text-white border-[var(--accent)] shadow-sm"
                          : "bg-card border-border text-subtext hover:text-fg hover:bg-hover"
                      )}
                    >
                      {pos}
                    </button>
                  ))}
                </div>
              </SpotlightCard>

              {/* Monitor */}
              <SpotlightCard>
                <h3 className="text-xs font-semibold text-fg mb-2">Display Monitor</h3>
                <div className="space-y-1.5">
                  {monitors.length === 0 ? (
                    <div className="text-xs text-muted">Enumerating displays...</div>
                  ) : (
                    monitors.map((m) => {
                      const isSelected =
                        settings.monitor_device === m.device ||
                        (!settings.monitor_device && settings.monitor === m.index);
                      return (
                        <div
                          key={`mon-${m.index}`}
                          onClick={() => {
                            updateSetting("monitor", m.index);
                            updateSetting("monitor_device", m.device);
                          }}
                          className={cn(
                            "flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors text-xs",
                            isSelected
                              ? "bg-[var(--accent-soft)] border-[var(--accent)]/50 text-fg"
                              : "bg-card border-border text-subtext hover:bg-hover hover:text-fg"
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <Monitor className="w-3.5 h-3.5 shrink-0" />
                            <span>
                              Display {m.index + 1} · {m.width}×{m.height}
                              {m.primary ? " (Primary)" : ""}
                            </span>
                          </div>
                          {isSelected && <Check className="w-4 h-4 text-[var(--accent)]" />}
                        </div>
                      );
                    })
                  )}
                </div>
              </SpotlightCard>

              {/* Accent Color */}
              <SpotlightCard>
                <h3 className="text-xs font-semibold text-fg mb-2">Notification Accent Color</h3>
                <div className="flex items-center gap-2.5">
                  <label
                    className="relative w-8 h-8 rounded-lg border border-border shadow-inner shrink-0 cursor-pointer overflow-hidden"
                    style={{ backgroundColor: accentInput }}
                    title="Pick accent color"
                  >
                    <input
                      type="color"
                      value={normalizeAccent(accentInput) || settings.accent_color || "#4f98a3"}
                      onChange={(e) => applyAccent(e.target.value)}
                      className="absolute inset-0 opacity-0 cursor-pointer"
                    />
                  </label>
                  <Input
                    type="text"
                    value={accentInput}
                    onChange={(e) => {
                      setAccentInput(e.target.value);
                      applyAccent(e.target.value);
                    }}
                    onBlur={() => applyAccent(accentInput)}
                    placeholder="#4f98a3"
                    className="w-36 font-mono text-xs"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => applyAccent(accentInput)}
                  >
                    Apply
                  </Button>
                </div>
              </SpotlightCard>

              {/* Opacity */}
              <SpotlightCard>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-fg">Toast Opacity</h3>
                  <span className="text-xs font-mono text-muted">
                    {Math.round(settings.toast_alpha * 100)}%
                  </span>
                </div>
                <Slider
                  min={0.6}
                  max={1.0}
                  step={0.02}
                  value={[settings.toast_alpha]}
                  onValueChange={([val]) => updateSetting("toast_alpha", val)}
                />
              </SpotlightCard>

              {/* Scale */}
              <SpotlightCard>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-fg">Notification Size</h3>
                  <span className="text-xs font-mono text-muted">
                    {Math.round((settings.toast_scale ?? 1) * 100)}%
                  </span>
                </div>
                <Slider
                  min={0.5}
                  max={1.5}
                  step={0.05}
                  value={[settings.toast_scale ?? 1]}
                  onValueChange={([val]) => updateSetting("toast_scale", val)}
                />
              </SpotlightCard>

              {/* Font */}
              <SpotlightCard>
                <h3 className="text-xs font-semibold text-fg mb-1">Custom Font</h3>
                <p className="text-[11px] text-muted mb-3 truncate">
                  {settings.font_path || "Default (Segoe UI Emoji)"}
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={handleBrowseFont}>
                    <FolderOpen className="w-3.5 h-3.5 mr-1" /> Browse (.ttf, .otf, .woff2)
                  </Button>
                  {settings.font_path && (
                    <Button variant="outline" size="sm" onClick={handleResetFont}>
                      <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reset
                    </Button>
                  )}
                </div>
              </SpotlightCard>
            </motion.div>
          )}
          {activeTab === "animations" && (
            <motion.div
              key="tab-animations"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {/* Header & Live Interactive Sandbox */}
              <SpotlightCard className="p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Wand2 className="w-4 h-4 text-[var(--accent)]" />
                      <h3 className="text-xs font-semibold text-fg">Notification Animation Dynamics</h3>
                    </div>
                    <p className="text-[11px] text-muted mt-0.5 leading-relaxed">
                      Pair entrance and exit kinematics, or craft custom directional curves.
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="shrink-0 text-xs font-medium cursor-pointer"
                    onClick={() => triggerTestToast()}
                  >
                    <Play className="w-3.5 h-3.5 mr-1 text-[var(--accent)]" /> Test on Desktop
                  </Button>
                </div>

                {/* In-Panel Sandbox */}
                <div className="p-3 rounded-xl bg-card/60 border border-border/80 flex flex-col items-center justify-center min-h-[125px] overflow-hidden relative">
                  <div className="w-full flex items-center justify-between pb-2 mb-1 border-b border-border/40 text-[11px] text-muted">
                    <span className="flex items-center gap-1.5 font-medium text-fg">
                      <Eye className="w-3.5 h-3.5 text-[var(--accent)]" /> Live Sandbox Preview
                    </span>
                    <button
                      type="button"
                      onClick={replaySandbox}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-card border border-border hover:bg-hover hover:text-fg transition-colors cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" /> Replay Effect
                    </button>
                  </div>
                  <div className="h-[74px] flex items-center justify-center w-full py-1">
                    <AnimatePresence mode="wait">
                      {sandboxVisible && (
                        <motion.div
                          key={`sb-${settings.anim_incoming}-${settings.anim_outgoing}-${settings.animation_preset}`}
                          initial={getToastMotionProps(settings).initial}
                          animate={getToastMotionProps(settings).animate}
                          exit={getToastMotionProps(settings).exit}
                          transition={getToastMotionProps(settings).transition}
                          style={getToastMotionProps(settings).style}
                          className="w-[300px] p-2.5 rounded-lg bg-card border border-border shadow-lg flex items-center gap-2.5 select-none"
                        >
                          <div className="w-8 h-8 rounded-md bg-[var(--accent-soft)] border border-[var(--accent)]/30 flex items-center justify-center shrink-0">
                            <Wand2 className="w-4 h-4 text-[var(--accent)]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-[11px] font-semibold text-fg truncate">
                              {ANIMATION_PRESETS.find((p) => p.id === settings.animation_preset)?.label || "Custom Preset"}
                            </div>
                            <div className="text-[9px] text-muted truncate">
                              {INCOMING_ANIMATIONS.find((a) => a.id === settings.anim_incoming)?.label || settings.anim_incoming}
                              {" ➔ "}
                              {OUTGOING_ANIMATIONS.find((a) => a.id === settings.anim_outgoing)?.label || settings.anim_outgoing}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </SpotlightCard>

              {/* Paired Presets Section */}
              <SpotlightCard className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-xs font-semibold text-fg">Paired Animation Presets</h3>
                    <p className="text-[11px] text-muted">
                      Pre-configured matching entrance and exit behaviors
                    </p>
                  </div>
                  {settings.animation_preset && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--accent-soft)] border border-[var(--accent)]/30 text-[var(--accent)] uppercase font-semibold">
                      {settings.animation_preset}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {ANIMATION_PRESETS.map((preset) => {
                    const isSelected = settings.animation_preset === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyPreset(preset)}
                        className={cn(
                          "flex flex-col text-left p-2.5 rounded-lg border transition-all cursor-pointer relative group",
                          isSelected
                            ? "bg-[var(--accent-soft)] border-[var(--accent)]/60 text-fg shadow-sm"
                            : "bg-card/60 border-border text-subtext hover:text-fg hover:bg-hover hover:border-border/90"
                        )}
                      >
                        <div className="flex items-center justify-between w-full mb-1">
                          <span className="font-semibold text-xs text-fg flex items-center gap-1.5">
                            {preset.label}
                          </span>
                          {isSelected ? (
                            <Check className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
                          ) : (
                            <span className="text-[10px] font-mono text-muted group-hover:text-subtext">
                              {preset.duration}ms
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 text-[10px] font-mono text-muted mb-1 truncate">
                          <span className="text-[var(--accent)] font-medium">
                            {INCOMING_ANIMATIONS.find((a) => a.id === preset.incoming)?.label || preset.incoming}
                          </span>
                          <span className="text-muted/60">→</span>
                          <span className="text-subtext">
                            {OUTGOING_ANIMATIONS.find((a) => a.id === preset.outgoing)?.label || preset.outgoing}
                          </span>
                        </div>
                        <p className="text-[10px] text-muted line-clamp-1 leading-snug">
                          {preset.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </SpotlightCard>

              {/* Independent Incoming / Outgoing Motion Selection */}
              <SpotlightCard className="p-4 space-y-4">
                <div>
                  <h3 className="text-xs font-semibold text-fg">Custom Directional Selection</h3>
                  <p className="text-[11px] text-muted">
                    Choose any incoming and outgoing animation effect independently
                  </p>
                </div>

                {/* Incoming Animation */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-fg flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[var(--accent)]" /> Incoming Animation (Entrance)
                    </span>
                    <span className="font-mono text-[11px] text-muted">
                      {INCOMING_ANIMATIONS.find((a) => a.id === (settings.anim_incoming || "soft-slide"))?.label}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
                    {INCOMING_ANIMATIONS.map((anim) => {
                      const isSelected = (settings.anim_incoming || "soft-slide") === anim.id;
                      return (
                        <button
                          key={anim.id}
                          type="button"
                          onClick={() => {
                            void updateSetting("anim_incoming", anim.id);
                            void updateSetting("animation_preset", "custom");
                            triggerTestToast(anim.label);
                          }}
                          className={cn(
                            "p-2 rounded-lg border text-left text-xs transition-all cursor-pointer",
                            isSelected
                              ? "bg-[var(--accent-soft)] border-[var(--accent)] text-fg font-medium"
                              : "bg-card/50 border-border text-subtext hover:text-fg hover:bg-hover"
                          )}
                          title={anim.description}
                        >
                          <div className="truncate font-medium">{anim.label}</div>
                          <div className="text-[9px] text-muted truncate mt-0.5">{anim.description}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Outgoing Animation */}
                <div className="space-y-1.5 pt-2 border-t border-border/50">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-fg flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-badge" /> Outgoing Animation (Exit)
                    </span>
                    <span className="font-mono text-[11px] text-muted">
                      {OUTGOING_ANIMATIONS.find((a) => a.id === (settings.anim_outgoing || "slide-away"))?.label}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
                    {OUTGOING_ANIMATIONS.map((anim) => {
                      const isSelected = (settings.anim_outgoing || "slide-away") === anim.id;
                      return (
                        <button
                          key={anim.id}
                          type="button"
                          onClick={() => {
                            void updateSetting("anim_outgoing", anim.id);
                            void updateSetting("animation_preset", "custom");
                            triggerTestToast(anim.label);
                          }}
                          className={cn(
                            "p-2 rounded-lg border text-left text-xs transition-all cursor-pointer",
                            isSelected
                              ? "bg-[var(--accent-soft)] border-[var(--accent)] text-fg font-medium"
                              : "bg-card/50 border-border text-subtext hover:text-fg hover:bg-hover"
                          )}
                          title={anim.description}
                        >
                          <div className="truncate font-medium">{anim.label}</div>
                          <div className="text-[9px] text-muted truncate mt-0.5">{anim.description}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </SpotlightCard>

              {/* Motion & Physics Tuning */}
              <SpotlightCard className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-semibold text-fg">Motion & Physics Tuning</h3>
                    <p className="text-[11px] text-muted">
                      Fine-tune direction, timing, distance, bounce, blur, and scale
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-[11px] h-7 px-2 cursor-pointer"
                    onClick={() => {
                      void updateSetting("anim_duration", 350);
                      void updateSetting("anim_distance", 400);
                      void updateSetting("anim_bounce", 0.3);
                      void updateSetting("anim_blur", 12);
                      void updateSetting("anim_scale", 0.9);
                      void updateSetting("anim_direction", "auto");
                      void updateSetting("anim_easing", "spring");
                      flashSave("Motion parameters reset to defaults");
                    }}
                  >
                    <RotateCcw className="w-3 h-3 mr-1" /> Reset
                  </Button>
                </div>

                {/* Direction */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-subtext">Motion Direction</span>
                    <span className="font-mono text-muted text-[11px] uppercase">
                      {settings.anim_direction || "auto"}
                    </span>
                  </div>
                  <div className="grid grid-cols-5 gap-1.5">
                    {(
                      [
                        { id: "auto", label: "Auto" },
                        { id: "right", label: "Right" },
                        { id: "left", label: "Left" },
                        { id: "top", label: "Top" },
                        { id: "bottom", label: "Bottom" },
                      ] as const
                    ).map((dir) => {
                      const isSelected = (settings.anim_direction || "auto") === dir.id;
                      return (
                        <button
                          key={dir.id}
                          type="button"
                          onClick={() => updateSetting("anim_direction", dir.id)}
                          className={cn(
                            "py-1.5 px-2 rounded-lg text-xs font-medium capitalize border transition-all cursor-pointer text-center",
                            isSelected
                              ? "bg-[var(--accent)] text-white border-[var(--accent)] shadow-sm"
                              : "bg-card border-border text-subtext hover:text-fg hover:bg-hover"
                          )}
                        >
                          {dir.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Easing Curves */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-subtext">Easing Curve</span>
                    <span className="font-mono text-muted text-[11px] capitalize">
                      {settings.anim_easing || "spring"}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                    {(
                      [
                        { id: "spring", label: "Spring" },
                        { id: "ease-out", label: "Ease Out" },
                        { id: "ease-in-out", label: "Ease InOut" },
                        { id: "bounce", label: "Bounce" },
                        { id: "back-out", label: "Back Out" },
                        { id: "linear", label: "Linear" },
                      ] as const
                    ).map((e) => {
                      const isSelected = (settings.anim_easing || "spring") === e.id;
                      return (
                        <button
                          key={e.id}
                          type="button"
                          onClick={() => updateSetting("anim_easing", e.id)}
                          className={cn(
                            "py-1 px-1.5 rounded-lg text-[11px] font-medium border transition-all cursor-pointer text-center truncate",
                            isSelected
                              ? "bg-[var(--accent)] text-white border-[var(--accent)] shadow-sm"
                              : "bg-card border-border text-subtext hover:text-fg hover:bg-hover"
                          )}
                        >
                          {e.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Sliders Grid */}
                <div className="space-y-3 pt-2">
                  {/* Duration */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-subtext">Duration</span>
                      <span className="font-mono text-muted">{settings.anim_duration ?? 350}ms</span>
                    </div>
                    <Slider
                      min={100}
                      max={1000}
                      step={25}
                      value={[settings.anim_duration ?? 350]}
                      onValueChange={([val]) => updateSetting("anim_duration", val)}
                    />
                  </div>

                  {/* Distance */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-subtext">Travel Distance</span>
                      <span className="font-mono text-muted">{settings.anim_distance ?? 400}px</span>
                    </div>
                    <Slider
                      min={50}
                      max={800}
                      step={25}
                      value={[settings.anim_distance ?? 400]}
                      onValueChange={([val]) => updateSetting("anim_distance", val)}
                    />
                  </div>

                  {/* Bounce Strength */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-subtext">Bounce Strength</span>
                      <span className="font-mono text-muted">{((settings.anim_bounce ?? 0.3) * 100).toFixed(0)}%</span>
                    </div>
                    <Slider
                      min={0}
                      max={1}
                      step={0.05}
                      value={[settings.anim_bounce ?? 0.3]}
                      onValueChange={([val]) => updateSetting("anim_bounce", Number(val.toFixed(2)))}
                    />
                  </div>

                  {/* Blur Amount */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-subtext">Blur Amount</span>
                      <span className="font-mono text-muted">{settings.anim_blur ?? 12}px</span>
                    </div>
                    <Slider
                      min={0}
                      max={24}
                      step={2}
                      value={[settings.anim_blur ?? 12]}
                      onValueChange={([val]) => updateSetting("anim_blur", val)}
                    />
                  </div>

                  {/* Scale Amount */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-subtext">Scale Factor</span>
                      <span className="font-mono text-muted">{((settings.anim_scale ?? 0.9) * 100).toFixed(0)}%</span>
                    </div>
                    <Slider
                      min={0.2}
                      max={1.5}
                      step={0.05}
                      value={[settings.anim_scale ?? 0.9]}
                      onValueChange={([val]) => updateSetting("anim_scale", Number(val.toFixed(2)))}
                    />
                  </div>
                </div>
              </SpotlightCard>
            </motion.div>
          )}

          {activeTab === "behaviour" && (
            <motion.div
              key="tab-behaviour"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {/* Notification Durations */}
              <SpotlightCard>
                <h3 className="text-xs font-semibold text-fg mb-3">Toast Durations</h3>
                <div className="space-y-3">
                  {(["info", "success", "warning", "error"] as const).map((kind) => {
                    const currentSec = (settings.durations?.[kind] ?? 5000) / 1000;
                    return (
                      <div key={kind} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="capitalize font-medium text-subtext">{kind}</span>
                          <span className="font-mono text-muted">{currentSec.toFixed(1)}s</span>
                        </div>
                        <Slider
                          min={2.0}
                          max={15.0}
                          step={0.5}
                          value={[currentSec]}
                          onValueChange={([val]) =>
                            updateSetting(`duration.${kind}`, Math.round(val * 1000))
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              </SpotlightCard>

              {/* Toggles */}
              <SpotlightCard className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-medium text-fg">Play Notification Sound</h4>
                    <p className="text-[11px] text-muted">Play alert audio when a toast arrives</p>
                  </div>
                  <Switch
                    checked={settings.sound_enabled}
                    onCheckedChange={(v) => updateSetting("sound_enabled", v)}
                  />
                </div>

                {settings.sound_enabled && (
                  <div className="pl-3 border-l-2 border-[var(--accent)]/40 space-y-2 pt-1 pb-1">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 pr-2">
                        <div className="text-[11px] font-medium text-fg flex items-center gap-1.5 truncate">
                          <Volume2 className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
                          <span className="truncate">
                            {settings.custom_sound_path
                              ? settings.custom_sound_path.replace(/^.*[\\/]/, "")
                              : "Default (Fears to Fathom)"}
                          </span>
                        </div>
                        <p
                          className="text-[10px] text-muted truncate mt-0.5"
                          title={settings.custom_sound_path || "Bundled notification audio"}
                        >
                          {settings.custom_sound_path || "Bundled notification sound"}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleBrowseSound}
                          className="h-7 text-[11px] px-2.5 cursor-pointer"
                        >
                          <FolderOpen className="w-3 h-3 mr-1" /> Browse
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleTestSound}
                          className="h-7 text-[11px] px-2.5 cursor-pointer"
                          title="Test notification sound"
                        >
                          <Volume2 className="w-3 h-3 mr-1" /> Test
                        </Button>
                        {settings.custom_sound_path && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleResetSound}
                            className="h-7 text-[11px] px-2 cursor-pointer"
                            title="Reset to default sound"
                          >
                            <RotateCcw className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="border-t border-border/50 pt-3 flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-medium text-fg">Suppress Focused App</h4>
                    <p className="text-[11px] text-muted">
                      Don't pop toasts for the app you're actively using
                    </p>
                  </div>
                  <Switch
                    checked={settings.suppress_focused_app}
                    onCheckedChange={(v) => updateSetting("suppress_focused_app", v)}
                  />
                </div>

                <div className="border-t border-border/50 pt-3 flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-medium text-fg">Start with Windows</h4>
                    <p className="text-[11px] text-muted">Launch automatically on login</p>
                  </div>
                  <Switch
                    checked={startOnLogin}
                    onCheckedChange={async (v) => {
                      setStartOnLogin(v);
                      await window.tray?.loginItem.set(v);
                      flashSave(v ? "Enabled start on login" : "Disabled start on login");
                    }}
                  />
                </div>

                <div className="border-t border-border/50 pt-3 flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-medium text-fg">Do Not Disturb</h4>
                    <p className="text-[11px] text-muted">Mute toasts and collect in history only</p>
                  </div>
                  <Switch
                    checked={settings.dnd}
                    onCheckedChange={(v) => updateSetting("dnd", v)}
                  />
                </div>
              </SpotlightCard>
            </motion.div>
          )}

          {activeTab === "filters" && (
            <motion.div
              key="tab-filters"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {/* Excluded Apps */}
              <SpotlightCard>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-xs font-semibold text-fg">Excluded Applications</h3>
                    <p className="text-[11px] text-muted">
                      Notifications from these apps are ignored entirely
                    </p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={handleAddExcludedApp}>
                    <Plus className="w-3.5 h-3.5 mr-1" /> Add App (.exe)
                  </Button>
                </div>

                <div className="space-y-1.5 mt-3 max-h-36 overflow-y-auto">
                  {settings.excluded_apps.length === 0 ? (
                    <div className="text-xs text-muted/70 italic p-2">No excluded apps</div>
                  ) : (
                    settings.excluded_apps.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border text-xs"
                      >
                        <span className="font-medium text-fg truncate">{item.name}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveExcludedApp(idx)}
                          className="text-muted hover:text-[var(--color-badge)] p-1 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </SpotlightCard>

              {/* App Colors */}
              <SpotlightCard>
                <div className="mb-3">
                  <h3 className="text-xs font-semibold text-fg">Per-App Accent Colors</h3>
                  <p className="text-[11px] text-muted">
                    Assign custom accent colors to specific apps
                  </p>
                </div>

                {/* Add new app color form */}
                <div className="flex items-center gap-2 mb-3">
                  <Input
                    placeholder="App name or exe (e.g. Discord)"
                    value={newAppExe}
                    onChange={(e) => setNewAppExe(e.target.value)}
                    className="text-xs"
                  />
                  <div
                    className="w-8 h-8 rounded-lg border border-border shrink-0"
                    style={{ backgroundColor: newAppColor }}
                  />
                  <Input
                    placeholder="#5865f2"
                    value={newAppColor}
                    onChange={(e) => setNewAppColor(e.target.value)}
                    className="w-24 font-mono text-xs shrink-0"
                  />
                  <Button variant="secondary" size="sm" onClick={handleAddAppColor} className="shrink-0">
                    <Plus className="w-3.5 h-3.5 mr-1" /> Add
                  </Button>
                </div>

                <div className="space-y-1.5 max-h-36 overflow-y-auto">
                  {settings.app_colors.length === 0 ? (
                    <div className="text-xs text-muted/70 italic p-2">No app-specific colors</div>
                  ) : (
                    settings.app_colors.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border text-xs"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <div
                            className="w-4 h-4 rounded-full shrink-0 border border-border"
                            style={{ backgroundColor: item.color }}
                          />
                          <span className="font-medium text-fg truncate">{item.exe}</span>
                          <span className="font-mono text-muted text-[11px]">{item.color}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveAppColor(idx)}
                          className="text-muted hover:text-[var(--color-badge)] p-1 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </SpotlightCard>
            </motion.div>
          )}

          {activeTab === "ai" && (
            <motion.div
              key="tab-ai"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              <SpotlightCard className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-semibold text-fg">Gemini AI Summarization</h3>
                    <p className="text-[11px] text-muted">
                      Automatically summarize messages over 20 words
                    </p>
                  </div>
                  <Switch
                    checked={settings.gemini_enabled}
                    onCheckedChange={(v) => updateSetting("gemini_enabled", v)}
                  />
                </div>

                <div className="border-t border-border/50 pt-3 space-y-2">
                  <label className="text-xs font-medium text-fg">Gemini API Key</label>
                  <p className="text-[11px] text-muted">
                    Stored securely in Windows Credential Manager. Never written to disk unencrypted.
                  </p>
                  <div className="flex items-center gap-2">
                    <Input
                      type="password"
                      value={geminiInput}
                      onChange={(e) => setGeminiInput(e.target.value)}
                      placeholder={
                        geminiKeyPresent ? "•••••••••••• (API Key Configured)" : "AIzaSy..."
                      }
                      className="text-xs font-mono"
                    />
                    <Button variant="secondary" size="sm" onClick={handleSaveGeminiKey}>
                      Save
                    </Button>
                    {geminiKeyPresent && (
                      <Button variant="outline" size="sm" onClick={handleClearGeminiKey}>
                        Clear
                      </Button>
                    )}
                  </div>
                </div>
              </SpotlightCard>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-border/70 shrink-0 mt-3">
        <ParticleButton onClick={handleDemoBurst}>Demo burst</ParticleButton>
        <span className="text-[11px] text-muted font-mono">{saveStatus}</span>
      </div>
    </div>
  );
};
