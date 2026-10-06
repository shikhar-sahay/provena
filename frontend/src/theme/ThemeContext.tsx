// First-class light / dark / system theming with persistence and no flash.
// The inline script in index.html applies the stored theme before first paint;
// this provider owns the theme afterwards and follows OS changes in system mode.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type ThemeChoice = "light" | "dark" | "system";

const STORAGE_KEY = "provena-theme";

function systemIsDark(): boolean {
  if (typeof window.matchMedia !== "function") return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function storedChoice(): ThemeChoice {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
}

function applyChoice(choice: ThemeChoice): boolean {
  const dark = choice === "dark" || (choice === "system" && systemIsDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark;
}

interface ThemeState {
  choice: ThemeChoice;
  dark: boolean;
  setChoice: (choice: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(() =>
    typeof window === "undefined" ? "system" : storedChoice(),
  );
  const [dark, setDark] = useState<boolean>(() =>
    typeof window === "undefined" ? true : applyChoice(storedChoice()),
  );

  useEffect(() => {
    setDark(applyChoice(choice));
    if (choice !== "system") return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setDark(applyChoice("system"));
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [choice]);

  const setChoice = useCallback((next: ThemeChoice) => {
    localStorage.setItem(STORAGE_KEY, next);
    setChoiceState(next);
  }, []);

  return <ThemeContext.Provider value={{ choice, dark, setChoice }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext);
  if (!state) throw new Error("useTheme must be used inside ThemeProvider.");
  return state;
}
