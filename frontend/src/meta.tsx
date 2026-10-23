import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Meta } from "./api";
import { useI18n } from "./i18n";

const Ctx = createContext<Meta | null>(null);

/** Server facts (languages, modes, encoders, ...) + syncs the UI language with the server config. */
export function MetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const { lang, setLang } = useI18n();
  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
    api.settings()
      .then((s) => {
        let explicit = false;
        try {
          explicit = localStorage.getItem("cf-lang-set") === "1";
        } catch {
          /* ignore */
        }
        // The config file wins unless this browser chose a language itself.
        if (!explicit && s.ui_language && s.ui_language !== lang) setLang(s.ui_language);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <Ctx.Provider value={meta}>{children}</Ctx.Provider>;
}

export const useMeta = () => useContext(Ctx);

export function chooseLanguage(code: string, setLang: (c: string) => void) {
  setLang(code);
  try {
    localStorage.setItem("cf-lang-set", "1");
  } catch {
    /* ignore */
  }
  api.saveSettings({ ui_language: code }).catch(() => {});
}
