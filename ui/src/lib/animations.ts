import type {
  IncomingAnimationType,
  OutgoingAnimationType,
  AnimationPresetType,
  AnimationDirection,
  AnimationEasing,
  AppSettings,
} from "@/types/tray";
import type { Transition, TargetAndTransition } from "motion/react";

export interface AnimationInfo<T extends string = string> {
  id: T;
  label: string;
  description: string;
}

export interface PresetInfo {
  id: AnimationPresetType;
  label: string;
  incoming: IncomingAnimationType;
  outgoing: OutgoingAnimationType;
  description: string;
  duration?: number;
  easing?: AnimationEasing;
  bounce?: number;
  distance?: number;
  blur?: number;
  scale?: number;
}

export const INCOMING_ANIMATIONS: AnimationInfo<IncomingAnimationType>[] = [
  { id: "slide-in", label: "Slide In", description: "Enters from the screen edge and settles into place" },
  { id: "soft-slide", label: "Soft Slide", description: "Slight horizontal drift combined with a gentle fade" },
  { id: "drop-down", label: "Drop Down", description: "Descends smoothly from above with soft gravity" },
  { id: "pop-in", label: "Pop In", description: "Snappy 90% → 103% → 100% scale expansion" },
  { id: "spring", label: "Spring", description: "Slides in, overshoots slightly, and springs back" },
  { id: "blur-in", label: "Blur In", description: "Dissolves in from frosted 14px blur to crisp card" },
  { id: "zoom-in", label: "Zoom In", description: "Starts compact in depth and quickly zooms forward" },
  { id: "card-flip", label: "Card Flip", description: "Subtle 3D perspective rotation unfolding into view" },
  { id: "elastic-stretch", label: "Elastic Stretch", description: "Horizontally elongated on entry, snaps into place" },
  { id: "reveal", label: "Reveal", description: "Wipes into view through an expanding directional mask" },
  { id: "stack-push", label: "Stack Push", description: "Pushes downward from above as a solid card layer" },
  { id: "material-rise", label: "Material Rise", description: "Rises ~20px with subtle depth elevation and fade" },
  { id: "liquid", label: "Liquid", description: "Slightly squished fluid morph that relaxes into form" },
  { id: "glide", label: "Glide", description: "Long, silky cinematic deceleration across space" },
  { id: "bounce", label: "Bounce", description: "Slides in and lightly rebounds against resting bounds" },
  { id: "flash-fade", label: "Flash Fade", description: "Quick luminance accent pulse settling into card" },
];

export const OUTGOING_ANIMATIONS: AnimationInfo<OutgoingAnimationType>[] = [
  { id: "slide-away", label: "Slide Away", description: "Slides smoothly back toward the screen perimeter" },
  { id: "swipe-out", label: "Swipe Out", description: "Accelerates offscreen as if briskly flicked away" },
  { id: "fade-out", label: "Fade Out", description: "Clean, distraction-free opacity dissipation" },
  { id: "shrink", label: "Shrink", description: "Scales down into vanishing zero point" },
  { id: "blur-away", label: "Blur Away", description: "Dissolves progressively into frosted glass blur" },
  { id: "drop-away", label: "Drop Away", description: "Falls downward as if released by gravity" },
  { id: "lift-away", label: "Lift Away", description: "Floats upward into the atmosphere while fading" },
  { id: "collapse", label: "Collapse", description: "Height and scale seamlessly collapse to zero" },
  { id: "card-flip-out", label: "Card Flip Out", description: "Spins away along 3D Y-axis perspective" },
  { id: "zoom-away", label: "Zoom Away", description: "Expands toward the viewer while dissolving out" },
  { id: "elastic-exit", label: "Elastic Exit", description: "Stretches toward the exit direction and snaps away" },
  { id: "dissolve", label: "Dissolve", description: "Fragmented soft blur-scale dispersal" },
  { id: "squish", label: "Squish", description: "Horizontally compresses before disappearing" },
  { id: "stack-collapse", label: "Stack Collapse", description: "Subtle sink and fade as remaining stack closes gap" },
  { id: "accelerate", label: "Accelerate", description: "Starts slowly then rapidly shoots offscreen" },
  { id: "scale-fade", label: "Scale + Fade", description: "Subtle 100% → 94% scale sink with gentle opacity fade" },
];

export const ANIMATION_PRESETS: PresetInfo[] = [
  {
    id: "default",
    label: "Default",
    incoming: "soft-slide",
    outgoing: "slide-away",
    description: "Soft horizontal slide entering with classic slide exit",
    duration: 320,
    easing: "spring",
    bounce: 0.18,
    distance: 400,
  },
  {
    id: "smooth",
    label: "Smooth",
    incoming: "glide",
    outgoing: "fade-out",
    description: "Long cinematic deceleration with gentle fade exit",
    duration: 440,
    easing: "ease-out",
    distance: 350,
  },
  {
    id: "spring",
    label: "Spring",
    incoming: "spring",
    outgoing: "accelerate",
    description: "Bouncy overshoot entrance with high-speed accelerated exit",
    duration: 350,
    easing: "spring",
    bounce: 0.35,
    distance: 420,
  },
  {
    id: "pop",
    label: "Pop",
    incoming: "pop-in",
    outgoing: "shrink",
    description: "Snappy scale bounce entering, shrink to point exiting",
    duration: 280,
    easing: "back-out",
    scale: 0.88,
  },
  {
    id: "glass",
    label: "Glass",
    incoming: "blur-in",
    outgoing: "blur-away",
    description: "Frosted blur dissolution on both entrance and exit",
    duration: 340,
    easing: "ease-out",
    blur: 14,
  },
  {
    id: "material",
    label: "Material",
    incoming: "material-rise",
    outgoing: "lift-away",
    description: "Elevation rise entering, atmospheric float exiting",
    duration: 300,
    easing: "ease-out",
    distance: 30,
  },
  {
    id: "elastic",
    label: "Elastic",
    incoming: "elastic-stretch",
    outgoing: "elastic-exit",
    description: "Rubbery horizontal stretch and elastic snap",
    duration: 380,
    easing: "spring",
    bounce: 0.45,
    distance: 380,
  },
  {
    id: "3d",
    label: "3D Flip",
    incoming: "card-flip",
    outgoing: "card-flip-out",
    description: "3D perspective rotation on entrance and departure",
    duration: 340,
    easing: "ease-out",
  },
  {
    id: "liquid",
    label: "Liquid",
    incoming: "liquid",
    outgoing: "squish",
    description: "Fluid morph entering and horizontal squash exiting",
    duration: 360,
    easing: "spring",
    bounce: 0.25,
  },
  {
    id: "minimal",
    label: "Minimal",
    incoming: "soft-slide",
    outgoing: "scale-fade",
    description: "Subtle micro-transforms with soft, clean fades",
    duration: 240,
    easing: "ease-out",
    distance: 24,
  },
  {
    id: "dynamic",
    label: "Dynamic",
    incoming: "bounce",
    outgoing: "swipe-out",
    description: "High-energy rebound entrance with fast swipe exit",
    duration: 380,
    easing: "bounce",
    bounce: 0.52,
    distance: 440,
  },
  {
    id: "compact",
    label: "Compact",
    incoming: "stack-push",
    outgoing: "collapse",
    description: "Vertical stack push entering and accordion collapse exiting",
    duration: 280,
    easing: "spring",
    bounce: 0.15,
  },
];

export interface ResolvedAnimationConfig {
  incoming: IncomingAnimationType;
  outgoing: OutgoingAnimationType;
  direction: AnimationDirection;
  duration: number; // in ms
  easing: AnimationEasing;
  distance: number; // in px
  bounce: number; // 0 to 1
  blur: number; // in px
  scale: number; // scale factor
}

export function resolveAnimationConfig(settings: AppSettings): ResolvedAnimationConfig {
  const presetId = settings.animation_preset || "default";
  const matchedPreset = ANIMATION_PRESETS.find((p) => p.id === presetId);

  const incoming = settings.anim_incoming || matchedPreset?.incoming || "soft-slide";
  const outgoing = settings.anim_outgoing || matchedPreset?.outgoing || "slide-away";
  const direction = settings.anim_direction || "auto";
  const duration = settings.anim_duration ?? matchedPreset?.duration ?? 350;
  const easing = settings.anim_easing || matchedPreset?.easing || "spring";
  const distance = settings.anim_distance ?? matchedPreset?.distance ?? 400;
  const bounce = settings.anim_bounce ?? matchedPreset?.bounce ?? 0.3;
  const blur = settings.anim_blur ?? matchedPreset?.blur ?? 12;
  const scale = settings.anim_scale ?? matchedPreset?.scale ?? 0.9;

  return {
    incoming,
    outgoing,
    direction,
    duration,
    easing,
    distance,
    bounce,
    blur,
    scale,
  };
}

function resolveVector(
  dir: AnimationDirection,
  screenPosition: "left" | "center" | "right",
  distance: number
): { x: number; y: number } {
  if (dir === "right") return { x: distance, y: 0 };
  if (dir === "left") return { x: -distance, y: 0 };
  if (dir === "top") return { x: 0, y: -distance };
  if (dir === "bottom") return { x: 0, y: distance };

  // auto: derive from screen position
  if (screenPosition === "left") return { x: -distance, y: 0 };
  if (screenPosition === "center") return { x: 0, y: -Math.min(distance, 140) };
  return { x: distance, y: 0 };
}

export function buildTransition(
  easing: AnimationEasing,
  durationMs: number,
  bounce: number,
  isExit = false
): Transition {
  const durSec = Math.max(0.1, durationMs / 1000);

  if (easing === "spring") {
    return {
      type: "spring",
      visualDuration: isExit ? durSec * 0.8 : durSec,
      bounce: isExit ? 0 : bounce,
    };
  }

  if (easing === "bounce") {
    return {
      type: "spring",
      visualDuration: isExit ? durSec * 0.75 : durSec,
      bounce: isExit ? 0 : Math.max(0.4, bounce),
    };
  }

  if (easing === "back-out") {
    return {
      duration: isExit ? durSec * 0.75 : durSec,
      ease: isExit ? [0.6, -0.28, 0.735, 0.045] : [0.34, 1.56, 0.64, 1],
    };
  }

  if (easing === "ease-in-out") {
    return {
      duration: durSec,
      ease: [0.65, 0, 0.35, 1],
    };
  }

  if (easing === "linear") {
    return {
      duration: durSec,
      ease: "linear",
    };
  }

  // default: ease-out
  return {
    duration: durSec,
    ease: isExit ? [0.4, 0, 0.6, 1] : [0.16, 1, 0.3, 1],
  };
}

export interface ToastMotionProps {
  initial: TargetAndTransition;
  animate: TargetAndTransition;
  exit: TargetAndTransition;
  transition: Transition;
  style?: React.CSSProperties;
}

export function getToastMotionProps(
  settings: AppSettings,
  shouldReduceMotion: boolean | null | undefined = false
): ToastMotionProps {
  if (shouldReduceMotion) {
    return {
      initial: { opacity: 0 },
      animate: { opacity: 1, x: 0, y: 0, scale: 1, filter: "blur(0px)" },
      exit: { opacity: 0, transition: { duration: 0.15 } },
      transition: { duration: 0.2 },
    };
  }

  const config = resolveAnimationConfig(settings);
  const vec = resolveVector(config.direction, settings.position, config.distance);
  const enterTransition = buildTransition(config.easing, config.duration, config.bounce, false);
  const exitTransition = buildTransition(config.easing, config.duration, config.bounce, true);

  // Common resting animate state
  const animateState: TargetAndTransition = {
    opacity: 1,
    x: 0,
    y: 0,
    scale: 1,
    scaleX: 1,
    scaleY: 1,
  };

  if (config.incoming === "card-flip" || config.outgoing === "card-flip-out") {
    animateState.rotateY = 0;
  }
  if (
    config.incoming === "blur-in" ||
    config.incoming === "flash-fade" ||
    config.outgoing === "blur-away" ||
    config.outgoing === "dissolve"
  ) {
    animateState.filter = "blur(0px) brightness(1)";
  }
  if (config.incoming === "reveal") {
    animateState.clipPath = "inset(0% 0% 0% 0%)";
  }

  // --- Compute Initial (Incoming) ---
  let initialState: TargetAndTransition = { opacity: 0, x: 0, y: 0, scale: 1 };

  switch (config.incoming) {
    case "slide-in":
      initialState = { opacity: 0, x: vec.x, y: vec.y, scale: 1 };
      break;

    case "soft-slide":
      initialState = {
        opacity: 0,
        x: vec.x * 0.45,
        y: vec.y * 0.45,
        scale: 0.98,
      };
      break;

    case "drop-down":
      initialState = {
        opacity: 0,
        x: 0,
        y: -Math.max(60, config.distance * 0.5),
        scale: 0.97,
      };
      break;

    case "pop-in":
      initialState = {
        opacity: 0,
        scale: Math.max(0.7, config.scale),
      };
      break;

    case "spring":
      initialState = {
        opacity: 0,
        x: vec.x,
        y: vec.y,
        scale: 0.92,
      };
      break;

    case "blur-in":
      initialState = {
        opacity: 0,
        filter: `blur(${config.blur}px) brightness(1.05)`,
        scale: 0.96,
      };
      break;

    case "zoom-in":
      initialState = {
        opacity: 0,
        scale: 0.45,
      };
      break;

    case "card-flip":
      initialState = {
        opacity: 0,
        rotateY: vec.x < 0 ? -65 : 65,
        scale: 0.92,
      };
      break;

    case "elastic-stretch":
      initialState = {
        opacity: 0,
        x: vec.x * 0.8,
        scaleX: 1.35,
        scaleY: 0.72,
      };
      break;

    case "reveal":
      initialState = {
        opacity: 0.2,
        clipPath:
          vec.x < 0
            ? "inset(0% 0% 0% 100%)"
            : vec.y !== 0
            ? "inset(0% 0% 100% 0%)"
            : "inset(0% 100% 0% 0%)",
      };
      break;

    case "stack-push":
      initialState = {
        opacity: 0,
        y: -110,
        scale: 0.92,
      };
      break;

    case "material-rise":
      initialState = {
        opacity: 0,
        y: Math.max(20, config.distance * 0.15),
        scale: 0.98,
      };
      break;

    case "liquid":
      initialState = {
        opacity: 0,
        scaleX: 0.82,
        scaleY: 1.22,
      };
      break;

    case "glide":
      initialState = {
        opacity: 0,
        x: vec.x * 1.25,
        y: vec.y * 1.25,
        scale: 0.99,
      };
      break;

    case "bounce":
      initialState = {
        opacity: 0,
        x: vec.x,
        y: vec.y,
        scale: 0.88,
      };
      break;

    case "flash-fade":
      initialState = {
        opacity: 0,
        filter: "blur(0px) brightness(2)",
        scale: 0.97,
      };
      break;

    default:
      initialState = { opacity: 0, x: vec.x, y: vec.y, scale: 0.96 };
  }

  // --- Compute Exit (Outgoing) ---
  let exitState: TargetAndTransition = { opacity: 0 };

  switch (config.outgoing) {
    case "slide-away":
      exitState = {
        opacity: 0,
        x: vec.x,
        y: vec.y,
        scale: 0.96,
      };
      break;

    case "swipe-out":
      exitState = {
        opacity: 0,
        x: vec.x * 1.6,
        y: vec.y * 1.6,
        scale: 0.98,
      };
      break;

    case "fade-out":
      exitState = {
        opacity: 0,
      };
      break;

    case "shrink":
      exitState = {
        opacity: 0,
        scale: 0.05,
      };
      break;

    case "blur-away":
      exitState = {
        opacity: 0,
        filter: `blur(${config.blur}px)`,
        scale: 0.95,
      };
      break;

    case "drop-away":
      exitState = {
        opacity: 0,
        y: Math.max(80, config.distance * 0.45),
        scale: 0.96,
      };
      break;

    case "lift-away":
      exitState = {
        opacity: 0,
        y: -Math.max(80, config.distance * 0.45),
        scale: 0.96,
      };
      break;

    case "collapse":
      exitState = {
        opacity: 0,
        scaleY: 0,
        height: 0,
        marginBottom: 0,
        paddingTop: 0,
        paddingBottom: 0,
      };
      break;

    case "card-flip-out":
      exitState = {
        opacity: 0,
        rotateY: vec.x < 0 ? -70 : 70,
        scale: 0.9,
      };
      break;

    case "zoom-away":
      exitState = {
        opacity: 0,
        scale: 1.28,
      };
      break;

    case "elastic-exit":
      exitState = {
        opacity: 0,
        x: vec.x * 0.7,
        scaleX: 1.28,
        scaleY: 0.72,
      };
      break;

    case "dissolve":
      exitState = {
        opacity: 0,
        filter: `blur(${Math.max(8, config.blur * 0.8)}px)`,
        scale: 0.88,
      };
      break;

    case "squish":
      exitState = {
        opacity: 0,
        scaleX: 0.15,
        scaleY: 1.25,
      };
      break;

    case "stack-collapse":
      exitState = {
        opacity: 0,
        scale: 0.92,
        y: 18,
      };
      break;

    case "accelerate":
      exitState = {
        opacity: 0,
        x: vec.x * 1.8,
        y: vec.y * 1.8,
      };
      break;

    case "scale-fade":
      exitState = {
        opacity: 0,
        scale: 0.94,
      };
      break;

    default:
      exitState = { opacity: 0, x: vec.x, y: vec.y, scale: 0.96 };
  }

  // Bind exit transition directly onto the exit target
  exitState.transition = exitTransition;

  return {
    initial: initialState,
    animate: animateState,
    exit: exitState,
    transition: enterTransition,
    style: {
      perspective: 1200,
    },
  };
}
