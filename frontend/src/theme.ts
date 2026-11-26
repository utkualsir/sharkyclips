import { useCallback } from "react";
import { resolveMode, setPersonal, getPersonal, usePersonal, type Mode } from "./personalize";

export type Theme = Mode;

/** Dark / light (the top bar's sun / moon button and the Easy settings switch). 1.2.69: a thin
 *  layer over Settings > Personalization (personalize.ts): choosing one here sets the mode. */
export function useTheme(): [Theme, (t: Theme) => void, () => void] {
  const { mode } = usePersonal();
  const set = useCallback((t: Theme) => setPersonal({ mode: t }), []);
  const toggle = useCallback(() => setPersonal({ mode: resolveMode(getPersonal()) === "dark" ? "light" : "dark" }), []);
  return [mode, set, toggle];
}

/** Read a CSS custom property (for canvas drawing). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
