import React, { useState, useRef, useCallback } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export interface HoldButtonProps {
  onAction: () => void;
  holdDurationMs?: number;
  className?: string;
  children?: React.ReactNode;
}

export const HoldButton: React.FC<HoldButtonProps> = ({
  onAction,
  holdDurationMs = 1000,
  className,
  children = "Hold to Clear All",
}) => {
  const [progress, setProgress] = useState(0);
  const [isHolding, setIsHolding] = useState(false);
  const animRef = useRef<number | null>(null);
  const startRef = useRef<number>(0);

  const startHold = useCallback(() => {
    setIsHolding(true);
    startRef.current = performance.now();

    const loop = (now: number) => {
      const elapsed = now - startRef.current;
      const pct = Math.min(1, elapsed / holdDurationMs);
      setProgress(pct);

      if (pct >= 1) {
        setIsHolding(false);
        setProgress(0);
        onAction();
      } else {
        animRef.current = requestAnimationFrame(loop);
      }
    };

    animRef.current = requestAnimationFrame(loop);
  }, [holdDurationMs, onAction]);

  const cancelHold = useCallback(() => {
    setIsHolding(false);
    setProgress(0);
    if (animRef.current !== null) {
      cancelAnimationFrame(animRef.current);
      animRef.current = null;
    }
  }, []);

  return (
    <button
      type="button"
      onMouseDown={startHold}
      onMouseUp={cancelHold}
      onMouseLeave={cancelHold}
      onTouchStart={startHold}
      onTouchEnd={cancelHold}
      className={cn(
        "relative overflow-hidden flex items-center justify-center px-3 py-1.5 rounded-lg",
        "text-xs font-medium text-muted hover:text-fg border border-border bg-card/70 hover:bg-hover/80",
        "transition-colors cursor-pointer select-none outline-none active:scale-[0.98]",
        className
      )}
    >
      {/* Fill progress layer */}
      <motion.div
        className="absolute inset-y-0 left-0 bg-[var(--color-badge)]/25 pointer-events-none"
        style={{ width: `${progress * 100}%` }}
        transition={{ ease: "linear", duration: 0 }}
      />
      <span className="relative z-10 flex items-center gap-1.5">
        {children}
        {isHolding && (
          <span className="text-[10px] opacity-75 font-mono">
            {Math.round((1 - progress) * 10) / 10}s
          </span>
        )}
      </span>
    </button>
  );
};
