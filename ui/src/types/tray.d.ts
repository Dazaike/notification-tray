export type NotificationKind = "info" | "success" | "warning" | "error";
export type IncomingAnimationType =
  | "slide-in"
  | "soft-slide"
  | "drop-down"
  | "pop-in"
  | "spring"
  | "blur-in"
  | "zoom-in"
  | "card-flip"
  | "elastic-stretch"
  | "reveal"
  | "stack-push"
  | "material-rise"
  | "liquid"
  | "glide"
  | "bounce"
  | "flash-fade";

export type OutgoingAnimationType =
  | "slide-away"
  | "swipe-out"
  | "fade-out"
  | "shrink"
  | "blur-away"
  | "drop-away"
  | "lift-away"
  | "collapse"
  | "card-flip-out"
  | "zoom-away"
  | "elastic-exit"
  | "dissolve"
  | "squish"
  | "stack-collapse"
  | "accelerate"
  | "scale-fade";

export type AnimationPresetType =
  | "default"
  | "smooth"
  | "spring"
  | "pop"
  | "glass"
  | "material"
  | "elastic"
  | "3d"
  | "liquid"
  | "minimal"
  | "dynamic"
  | "compact"
  | "custom";

export type AnimationDirection = "auto" | "right" | "left" | "top" | "bottom";
export type AnimationEasing =
  | "spring"
  | "ease-out"
  | "ease-in-out"
  | "linear"
  | "bounce"
  | "back-out";


export interface HistoryEntry {
  id: string;
  group_key: string;
  message: string;
  title: string;
  kind: NotificationKind;
  aumid: string;
  icon_path: string;
  app_name: string;
  launch_url: string;
  toast_tag: string;
  timestamp: string;
  ts: number;
  read: boolean;
}

export interface LiveToast {
  key: string;
  groupKey: string;
  ids: string[];
  count: number;
  messages: string[];
  title: string;
  kind: NotificationKind;
  appName: string;
  iconPath: string;
  accent: string;
  createdAt: number;
}

export interface AppSettings {
  version: string;
  position: "right" | "center" | "left";
  tray_click_action?: "center" | "panel";
  monitor: number;
  monitor_device: string;
  durations: Record<NotificationKind, number>;
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
  animation_preset?: AnimationPresetType;
  anim_incoming?: IncomingAnimationType;
  anim_outgoing?: OutgoingAnimationType;
  anim_direction?: AnimationDirection;
  anim_duration?: number;
  anim_easing?: AnimationEasing;
  anim_distance?: number;
  anim_bounce?: number;
  anim_blur?: number;
  anim_scale?: number;
}

export interface MonitorInfo {
  index: number;
  device: string;
  x: number;
  y: number;
  width: number;
  height: number;
  primary: boolean;
}

export interface ReadyData {
  version: string;
  settings: AppSettings;
  history: HistoryEntry[];
  unread: number;
  monitors: MonitorInfo[];
}

export interface TrayBridge {
  surface: "overlay" | "center" | "panel";
  request<T = unknown>(op: string, args?: Record<string, unknown>): Promise<T>;
  on<T = unknown>(event: string, cb: (data: T) => void): () => void;
  setIgnoreMouse(ignore: boolean): void;
  hideSelf(): void;
  showPanel?(): void;
  togglePanel?(): void;
  toggleCenter?(): void;
  pickFile(kind: "exe" | "font" | "audio"): Promise<string | null>;
  loginItem: {
    get(): Promise<boolean>;
    set(v: boolean): Promise<void>;
  };
}

declare global {
  interface Window {
    tray: TrayBridge;
  }
}
