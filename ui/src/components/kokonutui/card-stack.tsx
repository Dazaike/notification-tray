import React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export interface CardStackProps {
  children: React.ReactNode;
  count: number;
  maxPeek?: number;
  className?: string;
  peekOffset?: number;
}

export const CardStack: React.FC<CardStackProps> = ({
  children,
  count,
  maxPeek = 2,
  className,
  peekOffset = 4,
}) => {
  const peekLayers = Math.min(Math.max(0, count - 1), maxPeek);

  return (
    <div className={cn("relative w-full", className)}>
      {Array.from({ length: peekLayers }).map((_, index) => {
        const depth = peekLayers - index;
        const offsetX = depth * peekOffset;
        const offsetY = depth * peekOffset;
        const scale = 1 - depth * 0.02;
        const opacity = 0.5 - depth * 0.15;

        return (
          <motion.div
            key={`peek-${depth}`}
            aria-hidden="true"
            initial={{ opacity: 0, y: 0, scale: 0.98 }}
            animate={{
              opacity,
              x: offsetX,
              y: offsetY,
              scale,
            }}
            transition={{ type: "spring", visualDuration: 0.26, bounce: 0.18 }}
            className="absolute inset-0 pointer-events-none rounded-card border border-border bg-card shadow-md"
            style={{ zIndex: -depth }}
          />
        );
      })}
      <div className="relative z-10 w-full">{children}</div>
    </div>
  );
};
