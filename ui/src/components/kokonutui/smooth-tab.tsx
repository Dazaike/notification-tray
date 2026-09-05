import React from "react";
import { motion } from "motion/react";
import { cn, spring } from "@/lib/utils";

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

export interface SmoothTabProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
}

export const SmoothTab: React.FC<SmoothTabProps> = ({
  tabs,
  activeTab,
  onChange,
  className,
}) => {
  return (
    <div
      className={cn(
        "flex items-center gap-1 p-1 rounded-xl bg-card border border-border/80 backdrop-blur-md",
        className
      )}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer outline-none select-none",
              isActive ? "text-fg" : "text-subtext hover:text-fg hover:bg-hover/50"
            )}
          >
            {isActive && (
              <motion.div
                layoutId="smooth-tab-pill"
                className="absolute inset-0 rounded-lg bg-[var(--accent)]/15 border border-[var(--accent)]/30"
                transition={spring}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {tab.icon}
              {tab.label}
            </span>
          </button>
        );
      })}
    </div>
  );
};
