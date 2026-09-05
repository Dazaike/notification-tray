import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const spring = {
  type: "spring",
  visualDuration: 0.26,
  bounce: 0.18,
} as const;
