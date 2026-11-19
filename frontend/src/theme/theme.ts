import { useSyncExternalStore } from "react";

import { readStored, writeStored } from "../lib/safeStorage";

export const THEMES = ["business-light", "control-dark"] as const;
export type Theme = (typeof THEMES)[number];
export const DEFAULT_THEME: Theme = "business-light";
/** Keep in sync with public/theme-init.js (checked by themeInit.test.ts). */
export const THEME_STORAGE_KEY = "ff.theme";

export function isTheme(value: string | null): value is Theme {
  return THEMES.some((theme) => theme === value);
}

function readStoredTheme(): Theme {
  const stored = readStored(THEME_STORAGE_KEY);
  return isTheme(stored) ? stored : DEFAULT_THEME;
}

let current: Theme = DEFAULT_THEME;
const listeners = new Set<() => void>();

/** Browser chrome colour on phones (D81): follows the theme's top bar colour. */
function syncThemeColor(): void {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) return;
  const color = getComputedStyle(document.documentElement).getPropertyValue("--panel-header").trim();
  if (color) meta.setAttribute("content", color);
}

function apply(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  syncThemeColor();
}

/** Applies the remembered (or default) theme. Call before the first render. */
export function initTheme(): Theme {
  current = readStoredTheme();
  apply(current);
  listeners.forEach((listener) => {
    listener();
  });
  return current;
}

export function setTheme(theme: Theme): void {
  current = theme;
  apply(theme);
  writeStored(THEME_STORAGE_KEY, theme);
  listeners.forEach((listener) => {
    listener();
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useTheme(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const theme = useSyncExternalStore(subscribe, () => current);
  return { theme, setTheme };
}
