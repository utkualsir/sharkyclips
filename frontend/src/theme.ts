import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

function initial(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

/** Dark / light, remembered in localStorage (index.html applies it before first paint). */
export function useTheme(): [Theme, (t: Theme) => void, () => void] {
  const [theme, setThemeState] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("cf-theme", theme);
    } catch {
      /* ignore */
    }
    window.dispatchEvent(new CustomEvent("cf-theme", { detail: theme }));
  }, [theme]);
  useEffect(() => {
    const on = (e: Event) => setThemeState((e as CustomEvent<Theme>).detail);
    window.addEventListener("cf-theme", on);
    return () => window.removeEventListener("cf-theme", on);
  }, []);
  const toggle = useCallback(() => setThemeState((t) => (t === "dark" ? "light" : "dark")), []);
  return [theme, setThemeState, toggle];
}

/** Read a CSS custom property (for canvas drawing). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
