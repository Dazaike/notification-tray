import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Particle {
  id: number;
  x: number;
  y: number;
  color: string;
  size: number;
}

export interface ParticleButtonProps {
  onClick: () => void;
  className?: string;
  children?: React.ReactNode;
}

const PARTICLE_COLORS = ["var(--accent)", "#f4f4f6", "#dd6974", "#ffd166", "#06d6a0"];

export const ParticleButton: React.FC<ParticleButtonProps> = ({
  onClick,
  className,
  children = "Demo burst",
}) => {
  const [particles, setParticles] = useState<Particle[]>([]);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const originX = rect.width / 2;
    const originY = rect.height / 2;

    const count = 14;
    const newParticles: Particle[] = Array.from({ length: count }).map((_, i) => {
      const angle = (i / count) * 2 * Math.PI + (Math.random() - 0.5) * 0.5;
      const distance = 35 + Math.random() * 45;
      return {
        id: Date.now() + i,
        x: originX + Math.cos(angle) * distance,
        y: originY + Math.sin(angle) * distance,
        color: PARTICLE_COLORS[i % PARTICLE_COLORS.length],
        size: 3 + Math.random() * 3,
      };
    });

    setParticles(newParticles);
    onClick();

    setTimeout(() => {
      setParticles([]);
    }, 600);
  };

  return (
    <div className="relative inline-block">
      <motion.button
        type="button"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.96 }}
        onClick={handleClick}
        className={cn(
          "relative z-10 flex items-center justify-center gap-2 px-4 py-2 rounded-xl",
          "text-xs font-semibold text-fg bg-card border border-[var(--accent)]/40 hover:border-[var(--accent)]",
          "shadow-[0_0_15px_rgba(79,152,163,0.15)] hover:shadow-[0_0_20px_rgba(79,152,163,0.3)]",
          "cursor-pointer outline-none select-none transition-all duration-200",
          className
        )}
      >
        <Sparkles className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
        <span>{children}</span>
      </motion.button>

      {/* Burst particles */}
      <AnimatePresence>
        {particles.map((p) => (
          <motion.span
            key={p.id}
            initial={{ opacity: 1, scale: 1, x: 0, y: 0 }}
            animate={{
              opacity: 0,
              scale: 0.3,
              x: p.x - 30,
              y: p.y - 15,
            }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.55, ease: [0.25, 1, 0.5, 1] }}
            style={{
              backgroundColor: p.color,
              width: p.size,
              height: p.size,
            }}
            className="absolute top-1/2 left-1/2 rounded-full pointer-events-none z-20 shadow-sm"
          />
        ))}
      </AnimatePresence>
    </div>
  );
};
