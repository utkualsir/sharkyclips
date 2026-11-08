import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./locales/en";

type Catalog = Record<string, string>;
// English is built in (it's the fallback for every key); the other languages are separate files
// that load on demand, so the app only downloads the one it shows (~60 KB each).
const LOADERS: Record<string, () => Promise<{ default: Catalog }>> = {
  tr: () => import("./locales/tr"),
  ru: () => import("./locales/ru"),
  hu: () => import("./locales/hu"),
  de: () => import("./locales/de"),
  ar: () => import("./locales/ar"),
  zh: () => import("./locales/zh"),
};
const loaded: Record<string, Catalog> = { en };
const SUPPORTED = new Set(["en", ...Object.keys(LOADERS)]);

function loadCatalog(code: string): Promise<Catalog> {
  if (loaded[code]) return Promise.resolve(loaded[code]);
  return LOADERS[code]()
    .then((m) => (loaded[code] = m.default))
    .catch(() => en); // offline / old cached page: English keeps the app usable
}
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
    if (l && SUPPORTED.has(l)) return l;
  } catch {
    /* private mode */
  }
  return DEFAULT;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState(stored);
  const [cat, setCat] = useState<Catalog | null>(() => loaded[lang] ?? null);

  useEffect(() => {
    let live = true;
    loadCatalog(lang).then((c) => live && setCat(c));
    return () => {
      live = false;
    };
  }, [lang]);

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
    if (SUPPORTED.has(code)) loadCatalog(code).then(() => setLangState(code));
  }, []);

  const value = useMemo<I18n>(() => {
    const cat = (loaded[lang] ?? en) as Catalog;
    const plural = new Intl.PluralRules(lang);
    const t: T = (key, vars) => {
      let s: string | undefined;
      // n may come already formatted (num(...) -> "1.234"): its digits still pick the plural form
      const n = vars ? (typeof vars.n === "number" ? vars.n : typeof vars.n === "string" ? Number(vars.n.replace(/[^\d-]/g, "")) : NaN) : NaN;
      if (vars && vars.n !== "" && Number.isFinite(n)) {
        const rule = plural.select(n);
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
  }, [lang, setLang, cat]); // eslint-disable-line react-hooks/exhaustive-deps

  // A few ms on first start: render nothing rather than flash English before the user's language.
  if (!cat) return null;
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside provider");
  return v;
}
