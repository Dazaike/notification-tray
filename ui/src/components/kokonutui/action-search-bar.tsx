import React from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ActionSearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export const ActionSearchBar: React.FC<ActionSearchBarProps> = ({
  value,
  onChange,
  placeholder = "Search notifications...",
  className,
}) => {
  return (
    <div
      className={cn(
        "relative flex items-center w-full h-10 px-3 rounded-xl border border-border bg-card/60 backdrop-blur-md",
        "focus-within:border-[var(--accent)] focus-within:ring-1 focus-within:ring-[var(--accent)]/50 transition-all duration-200",
        className
      )}
    >
      <Search className="w-4 h-4 text-muted shrink-0 mr-2" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-sm text-fg placeholder:text-muted/70 outline-none"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange("")}
          className="p-1 rounded-md text-muted hover:text-fg hover:bg-hover transition-colors shrink-0"
          title="Clear search"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      ) : (
        <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono text-muted/60 bg-hover rounded border border-border shrink-0 select-none">
          Esc
        </kbd>
      )}
    </div>
  );
};
