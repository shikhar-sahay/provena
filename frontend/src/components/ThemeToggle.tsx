// Compact light / dark / system theme switcher.

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "../theme/ThemeContext";
import type { ThemeChoice } from "../theme/ThemeContext";

const OPTIONS: { value: ThemeChoice; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light theme", icon: <Sun size={14} /> },
  { value: "system", label: "System theme", icon: <Monitor size={14} /> },
  { value: "dark", label: "Dark theme", icon: <Moon size={14} /> },
];

export function ThemeToggle() {
  const { choice, setChoice } = useTheme();
  return (
    <div
      role="group"
      aria-label="Color theme"
      className="flex items-center rounded-md border border-line bg-surface p-0.5"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          title={option.label}
          aria-label={option.label}
          aria-pressed={choice === option.value}
          onClick={() => setChoice(option.value)}
          className={`pv-transition flex h-7 w-8 cursor-pointer items-center justify-center rounded ${
            choice === option.value
              ? "bg-hover text-ink shadow-none"
              : "text-ink3 hover:text-ink2"
          }`}
        >
          {option.icon}
        </button>
      ))}
    </div>
  );
}
