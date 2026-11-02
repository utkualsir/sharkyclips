import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { easyApi, type EasySettings, type UiMode } from "./api";

// Easy mode (default) or Pro mode (every tool). Remembered on the server (config ui_mode) and in
// this browser for the first paint, so the right screen shows without a flash.
const KEY = "sc-ui-mode";

function stored(): UiMode {
  try {
    return localStorage.getItem(KEY) === "pro" ? "pro" : "easy";
  } catch {
    return "easy";
  }
}

interface Ctx {
  mode: UiMode;
  settings: EasySettings | null;
  setMode: (m: UiMode) => void;
  update: (s: Partial<Omit<EasySettings, "downloads">>) => Promise<void>;
}

const UiCtx = createContext<Ctx>({ mode: "easy", settings: null, setMode: () => {}, update: async () => {} });

export function UiModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<UiMode>(stored);
  const [settings, setSettings] = useState<EasySettings | null>(null);

  const apply = useCallback((s: EasySettings) => {
    setSettings(s);
    setModeState(s.mode);
    try {
      localStorage.setItem(KEY, s.mode);
    } catch {
      /* private mode */
    }
  }, []);

  useEffect(() => {
    easyApi.settings().then(apply).catch(() => {});
  }, [apply]);

  useEffect(() => {
    document.documentElement.dataset.ui = mode;
  }, [mode]);

  const update = useCallback(
    async (s: Partial<Omit<EasySettings, "downloads">>) => {
      if (s.mode) setModeState(s.mode);
      setSettings((cur) => (cur ? { ...cur, ...s } : cur));
      try {
        apply(await easyApi.saveSettings(s));
      } catch {
        /* offline: the local choice stays for this session */
      }
    },
    [apply],
  );

  const setMode = useCallback((m: UiMode) => void update({ mode: m }), [update]);
  return <UiCtx.Provider value={{ mode, settings, setMode, update }}>{children}</UiCtx.Provider>;
}

export const useUiMode = () => useContext(UiCtx);
