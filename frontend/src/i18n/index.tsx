import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import ar from "./locales/ar";
import de from "./locales/de";
import en from "./locales/en";
import hu from "./locales/hu";
import ru from "./locales/ru";
import tr from "./locales/tr";
import zh from "./locales/zh";

export const CATALOGS: Record<string, Record<string, string>> = { tr, en, ru, hu, de, ar, zh };
export const UI_LANGUAGES = [
  { code: "tr", name: "Türkçe" },
  { code: "en", name: "English" },
  { code: "ru", name: "Русский" },
  { code: "hu", name: "Magyar" },
  { code: "de", name: "Deutsch" },
  { code: "ar", name: "العربية" },
  { code: "zh", name: "中文" },
];
export const RTL = new Set(["ar"]);
const DEFAULT = "tr";

type Vars = Record<string, string | number>;
export type T = (key: string, vars?: Vars) => string;

interface I18n {
  lang: string;
  dir: "ltr" | "rtl";
  t: T;
  setLang: (code: string) => void;
  /** Number formatting with Latin digits (they match the timecodes). */
  num: (n: number, digits?: number) => string;
  relTime: (iso: string) => string;
}

const Ctx = createContext<I18n | null>(null);

function stored(): string {
  try {
    const l = localStorage.getItem("cf-lang");
    if (l && CATALOGS[l]) return l;
  } catch {
    /* private mode */
  }
  return DEFAULT;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState(stored);

  useEffect(() => {
    const el = document.documentElement;
    el.lang = lang;
    el.dir = RTL.has(lang) ? "rtl" : "ltr";
    try {
      localStorage.setItem("cf-lang", lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  const setLang = useCallback((code: string) => {
    if (CATALOGS[code]) setLangState(code);
  }, []);

  const value = useMemo<I18n>(() => {
    const cat = CATALOGS[lang];
    const plural = new Intl.PluralRules(lang);
    const t: T = (key, vars) => {
      let s: string | undefined;
      if (vars && typeof vars.n === "number") {
        const rule = plural.select(vars.n);
        s = cat[`${key}_${rule}`] ?? cat[`${key}_other`] ?? en[`${key}_${rule}`] ?? en[`${key}_other`];
      }
      s = s ?? cat[key] ?? en[key] ?? key;
      if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
      return s;
    };
    const locale = `${lang}-u-nu-latn`;
    const nf = new Map<number, Intl.NumberFormat>();
    const num = (n: number, digits = 0) => {
      if (!nf.has(digits))
        nf.set(digits, new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }));
      return nf.get(digits)!.format(n);
    };
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    const relTime = (iso: string) => {
      const diff = (new Date(iso).getTime() - Date.now()) / 1000;
      const abs = Math.abs(diff);
      if (abs < 60) return rtf.format(Math.round(diff), "second");
      if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
      if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
      return rtf.format(Math.round(diff / 86400), "day");
    };
    return { lang, dir: RTL.has(lang) ? "rtl" : "ltr", t, setLang, num, relTime };
  }, [lang, setLang]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside provider");
  return v;
}
