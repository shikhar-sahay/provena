// Compact light / dark theme toggle.

import { Moon, Sun } from "lucide-react";
import { useTheme } from "../theme/ThemeContext";

export function ThemeToggle() {
  const { dark, setChoice } = useTheme();
  return (
    <button
      type="button"
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setChoice(dark ? "light" : "dark")}
      className="pv-transition flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-line bg-surface text-ink2 hover:bg-hover hover:text-ink focus-visible:outline-none"
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
