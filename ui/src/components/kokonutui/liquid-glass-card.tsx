import React from "react";
import { cn } from "@/lib/utils";

export interface LiquidGlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  glassOpacity?: number;
  highlight?: boolean;
}

export const LiquidGlassCard = React.forwardRef<HTMLDivElement, LiquidGlassCardProps>(
  ({ children, className, glassOpacity, highlight = true, style, ...props }, ref) => {
    return (
      <div
        ref={ref}
        style={{
          backgroundColor: glassOpacity !== undefined
            ? `color-mix(in srgb, var(--color-card) ${Math.round(glassOpacity * 100)}%, transparent)`
            : undefined,
          ...style,
        }}
        className={cn(
          "relative overflow-hidden rounded-card border border-border bg-card/94 backdrop-blur-xl",
          "shadow-[0_5px_18px_rgba(8,8,10,0.55)] transition-all",
          highlight && "before:absolute before:inset-x-0 before:top-0 before:h-[1px] before:bg-gradient-to-r before:from-transparent before:via-card-highlight before:to-transparent",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

LiquidGlassCard.displayName = "LiquidGlassCard";
