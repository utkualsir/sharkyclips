import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AppState } from "./api";

interface Ctx {
  state: AppState | null;
  refresh: () => Promise<void>;
  set: (s: AppState) => void;
}

const AppCtx = createContext<Ctx>({ state: null, refresh: async () => {}, set: () => {} });

/** Onboarding / "What's new" / dev banner state. Polled, so the dev banner appears and goes away
 * by itself while an update is being built. */
export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState | null>(null);
  const refresh = useCallback(async () => {
    try {
      setState(await api.appState());
    } catch {
      /* server restarting: keep the last state */
    }
  }, []);
  useEffect(() => {
    refresh();
    const id = window.setInterval(() => document.visibilityState === "visible" && refresh(), 30_000);
    const onVis = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [refresh]);
  return <AppCtx.Provider value={{ state, refresh, set: setState }}>{children}</AppCtx.Provider>;
}

export const useAppState = () => useContext(AppCtx);
