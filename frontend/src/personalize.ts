// 1.2.69 Settings > Personalization (like Windows' Personalization page):
//   preset   Classic (default) / Ocean / Shark Sign / High contrast  -> <html data-preset>
//   mode     Light / Dark / Follow Windows                          -> <html data-theme>
//   accent   one colour for buttons, active tabs, progress bars, highlights, focus (+ the window
//            title bar, optional, via <meta name="theme-color">)
//   colors   own colours per mode (background, panels, text, ...), written as inline custom
//            properties on <html>, which win over themes.css
//   autofix  text that a change made unreadable is moved towards black / white until it reaches
//            WCAG AA (4.5:1; 3:1 for marks), and the panel says so
// Everything is computed for both modes at once and kept in localStorage ("sc-personal"), so
// index.html paints the right colours before the app loads (no flash); the server keeps a copy
// (config ui_personal) for other browsers and the splash page's colours (ui_splash).
import { useSyncExternalStore } from "react";
import { api } from "./api";
import {
  AA_TEXT,
  AA_UI,
  BLACK,
  bestOn,
  contrast,
  fixContrast,
  hoverShade,
  isHex6,
  mix,
  over,
  parseColor,
  alpha,
  toHex,
  type RGB,
} from "./themeMath";

export type PresetId = "classic" | "ocean" | "sign" | "contrast";
export type ModeSetting = "dark" | "light" | "system";
export type Mode = "dark" | "light";
export const PRESETS: PresetId[] = ["classic", "ocean", "sign", "contrast"];
export const COLOR_KEYS = [
  "bg",
  "surface",
  "text",
  "muted",
  "border",
  "button",
  "link",
  "success",
  "warn",
  "danger",
  "bleep",
  "caption",
] as const;
export type ColorKey = (typeof COLOR_KEYS)[number];

export interface Personal {
  v: 1;
  preset: PresetId;
  mode: ModeSetting;
  accent: string | null;
  titlebar: boolean;
  autofix: boolean;
  colors: Record<Mode, Partial<Record<ColorKey, string>>>;
  /** ms since epoch of the last change (the newest copy wins between browser and server) */
  at: number;
}

export interface Problem {
  /** which setting it belongs to (a ColorKey, or "accent") */
  what: ColorKey | "accent";
  token: string;
  /** contrast before the fix */
  ratio: number;
  need: number;
  /** contrast after the automatic fix (null: autofix is off) */
  fixed: number | null;
}

export const DEFAULT: Personal = {
  v: 1,
  preset: "classic",
  mode: "system",
  accent: null,
  titlebar: false,
  autofix: true,
  colors: { dark: {}, light: {} },
  at: 0,
};

const STORE = "sc-personal";

/** The token each colour setting shows (the panel reads the current value from it). */
export const TOKEN_OF: Record<ColorKey, string> = {
  bg: "--bg",
  surface: "--surface",
  text: "--text",
  muted: "--muted",
  border: "--border",
  button: "--primary-bg",
  link: "--link",
  success: "--success",
  warn: "--warn",
  danger: "--danger",
  bleep: "--bleep",
  caption: "--mark",
};

/** Every custom property this module may write on <html>. */
const MANAGED = [
  "--bg", "--surface", "--surface-2", "--surface-3", "--chip-bg", "--chip-text", "--text", "--strong", "--select",
  "--muted", "--border", "--border-strong", "--btn-border", "--btn-hover-bg", "--gold", "--gold-text", "--gold-soft",
  "--gold-line", "--focus", "--series-ours", "--on-sign", "--primary-bg", "--primary-text", "--primary-hover", "--link",
  "--success", "--success-soft", "--on", "--warn", "--warn-soft", "--danger", "--danger-soft", "--bleep", "--bleep-text",
  "--mark", "--l-bg", "--l-text", "--l-muted", "--l-cut",
];

/** The text / mark pairs that must stay readable, and which setting each belongs to. */
const CHECKS: Array<[string, string[], number, ColorKey | "accent"]> = [
  ["--text", ["--bg", "--surface", "--surface-2"], AA_TEXT, "text"],
  ["--strong", ["--bg", "--surface"], AA_TEXT, "text"],
  ["--chip-text", ["--chip-bg"], AA_TEXT, "text"],
  ["--muted", ["--bg", "--surface", "--surface-2"], AA_TEXT, "muted"],
  ["--primary-text", ["--primary-bg", "--primary-hover"], AA_TEXT, "button"],
  ["--on-sign", ["--gold"], AA_TEXT, "accent"],
  ["--gold-text", ["--surface", "--bg"], AA_TEXT, "accent"],
  ["--link", ["--surface", "--bg"], AA_TEXT, "link"],
  ["--success", ["--surface", "--bg"], AA_TEXT, "success"],
  ["--warn", ["--surface", "--bg"], AA_TEXT, "warn"],
  ["--danger", ["--surface", "--bg"], AA_TEXT, "danger"],
  ["--bleep-text", ["--surface", "--bg"], AA_TEXT, "bleep"],
  ["--l-text", ["--l-bg"], AA_TEXT, "text"],
  ["--l-muted", ["--l-bg"], AA_TEXT, "muted"],
  ["--bleep", ["--surface"], AA_UI, "bleep"],
  ["--mark", ["--surface"], AA_UI, "caption"],
  ["--on", ["--surface"], AA_UI, "success"],
];

const SPLASH_KEYS = ["l-bg", "l-text", "l-muted", "l-water", "l-fin-a", "l-fin-b", "l-cut", "mark-fin"];

interface Computed {
  vars: Record<string, string>;
  problems: Problem[];
  bar: string;
  splash: Record<string, string>;
}

interface Stored {
  p: Personal;
  vars: Record<Mode, Record<string, string>>;
  bar: Record<Mode, string>;
}

// ------------------------------------------------------------------ checking a setting / file

/** A theme setting or a theme file, checked (only known keys, colours only as #rrggbb). */
export function clean(v: unknown): Personal | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  if (!PRESETS.includes(o.preset as PresetId)) return null;
  if (!["dark", "light", "system"].includes(o.mode as string)) return null;
  const raw = (o.colors && typeof o.colors === "object" ? o.colors : {}) as Record<string, unknown>;
  const colors = { dark: {}, light: {} } as Personal["colors"];
  for (const m of ["dark", "light"] as Mode[]) {
    const row = (raw[m] && typeof raw[m] === "object" ? raw[m] : {}) as Record<string, unknown>;
    for (const k of COLOR_KEYS) if (isHex6(row[k])) colors[m][k] = (row[k] as string).toLowerCase();
  }
  return {
    v: 1,
    preset: o.preset as PresetId,
    mode: o.mode as ModeSetting,
    accent: isHex6(o.accent) ? o.accent.toLowerCase() : null,
    titlebar: !!o.titlebar,
    autofix: o.autofix !== false,
    colors,
    at: typeof o.at === "number" && o.at > 0 ? o.at : 0,
  };
}

// ------------------------------------------------------------------ the colour work

function systemMode(): Mode {
  try {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function resolveMode(p: Personal): Mode {
  return p.mode === "system" ? systemMode() : p.mode;
}

/** The colours of `p` in `mode`: switches <html> to it for a moment (same task: nothing paints). */
export function compute(p: Personal, mode: Mode): Computed {
  const root = document.documentElement;
  const prevPreset = root.getAttribute("data-preset");
  const prevTheme = root.getAttribute("data-theme");
  const saved = MANAGED.map((n) => [n, root.style.getPropertyValue(n)] as const);
  MANAGED.forEach((n) => root.style.removeProperty(n));
  root.setAttribute("data-preset", p.preset);
  root.setAttribute("data-theme", mode);
  const cs = getComputedStyle(root);
  const vars: Record<string, string> = {};
  const raw = (n: string) => vars[n] ?? cs.getPropertyValue(n).trim();
  const solid = (n: string, under?: RGB): RGB | null => {
    const c = parseColor(raw(n));
    if (!c) return null;
    if (c[3] >= 1) return [c[0], c[1], c[2]];
    const base = under ?? solid("--surface") ?? [0, 0, 0];
    return over(c, base);
  };
  const set = (n: string, v: string) => (vars[n] = v);

  try {
    const c = p.colors[mode] ?? {};
    const P = (v: string) => parseColor(v)!;
    if (c.bg) {
      set("--bg", c.bg);
      set("--l-bg", c.bg);
    }
    if (c.text) {
      for (const n of ["--text", "--strong", "--select", "--chip-text", "--l-text"]) set(n, c.text);
    }
    const text = solid("--text") ?? [255, 255, 255];
    if (c.surface) {
      const s = P(c.surface);
      set("--surface", c.surface);
      set("--surface-2", toHex(mix(s, text, 0.045)));
      set("--surface-3", toHex(mix(s, text, 0.09)));
      set("--chip-bg", toHex(mix(s, text, 0.09)));
      set("--btn-hover-bg", alpha(text, 0.06));
    }
    if (c.muted) {
      set("--muted", c.muted);
      set("--l-muted", c.muted);
    }
    if (c.border) {
      const strong = toHex(mix(P(c.border), text, 0.3));
      set("--border", c.border);
      set("--border-strong", strong);
      set("--btn-border", strong);
    }
    if (p.accent) {
      const a = P(p.accent);
      set("--gold", p.accent);
      set("--gold-text", p.accent);
      set("--gold-soft", alpha(a, 0.14));
      set("--gold-line", alpha(a, 0.55));
      set("--focus", `0 0 0 3px ${alpha(a, 0.5)}`);
      set("--series-ours", p.accent);
      set("--on-sign", toHex(bestOn(a)));
      set("--l-cut", p.accent);
    }
    const button = c.button ?? p.accent;
    if (button) {
      const b = P(button);
      const on = bestOn(b);
      set("--primary-bg", button);
      set("--primary-text", toHex(on));
      set("--primary-hover", toHex(hoverShade(b, on)));
    }
    if (c.link) set("--link", c.link);
    if (c.success) {
      set("--success", c.success);
      set("--on", c.success);
      set("--success-soft", alpha(P(c.success), 0.12));
    }
    if (c.warn) {
      set("--warn", c.warn);
      set("--warn-soft", alpha(P(c.warn), 0.13));
    }
    if (c.danger) {
      set("--danger", c.danger);
      set("--danger-soft", alpha(P(c.danger), 0.1));
    }
    if (c.bleep) {
      set("--bleep", c.bleep);
      set("--bleep-text", c.bleep);
    }
    if (c.caption) set("--mark", c.caption);

    // the contrast check (+ the automatic fix)
    const problems: Problem[] = [];
    for (const [fg, bgs, need, what] of CHECKS) {
      const backs = bgs.map((b) => solid(b)).filter((x): x is RGB => !!x);
      const worst = () => {
        const f = solid(fg, backs[0]);
        if (!f || !backs.length) return null;
        let r = Infinity;
        let at = backs[0];
        for (const b of backs) {
          const x = contrast(solid(fg, b) ?? f, b);
          if (x < r) {
            r = x;
            at = b;
          }
        }
        return { f, r, at };
      };
      const w = worst();
      if (!w || w.r >= need - 0.005) continue;
      const pr: Problem = { what, token: fg, ratio: Math.round(w.r * 100) / 100, need, fixed: null };
      if (p.autofix) {
        let cur = w;
        for (let i = 0; i < 4 && cur && cur.r < need - 0.005; i++) {
          set(fg, toHex(fixContrast(cur.f, cur.at, need)));
          cur = worst()!;
        }
        pr.fixed = cur ? Math.round(cur.r * 100) / 100 : null;
      }
      problems.push(pr);
    }

    const hex = (n: string, under?: RGB) => {
      const x = solid(n, under);
      return x ? toHex(x) : "";
    };
    const bg = hex("--bg");
    const bar = p.titlebar && p.accent ? p.accent : bg;
    const lbg = solid("--l-bg") ?? undefined;
    const splash: Record<string, string> = {};
    for (const k of SPLASH_KEYS) splash[k] = hex(`--${k}`, lbg);
    return { vars, problems, bar, splash };
  } finally {
    if (prevPreset == null) root.removeAttribute("data-preset");
    else root.setAttribute("data-preset", prevPreset);
    if (prevTheme == null) root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", prevTheme);
    saved.forEach(([n, v]) => (v ? root.style.setProperty(n, v) : root.style.removeProperty(n)));
  }
}

/** Swatches for the preset cards (read from themes.css, so nothing is written twice). */
export function presetSwatches(preset: PresetId, mode: Mode): Record<"bg" | "surface" | "text" | "accent" | "button" | "muted", string> {
  const p: Personal = { ...DEFAULT, preset };
  const root = document.documentElement;
  const prev = [root.getAttribute("data-preset"), root.getAttribute("data-theme")];
  const saved = MANAGED.map((n) => [n, root.style.getPropertyValue(n)] as const);
  MANAGED.forEach((n) => root.style.removeProperty(n));
  root.setAttribute("data-preset", p.preset);
  root.setAttribute("data-theme", mode);
  const cs = getComputedStyle(root);
  const g = (n: string) => cs.getPropertyValue(n).trim();
  const out = { bg: g("--bg"), surface: g("--surface"), text: g("--text"), accent: g("--gold"), button: g("--primary-bg"), muted: g("--muted") };
  root.setAttribute("data-preset", prev[0] ?? "classic");
  root.setAttribute("data-theme", prev[1] ?? "dark");
  saved.forEach(([n, v]) => (v ? root.style.setProperty(n, v) : root.style.removeProperty(n)));
  return out;
}

/** The accent palette (themes.css --accent-1..12). */
export function accentPalette(): string[] {
  const cs = getComputedStyle(document.documentElement);
  const out: string[] = [];
  for (let i = 1; i <= 12; i++) {
    const v = cs.getPropertyValue(`--accent-${i}`).trim();
    if (isHex6(v)) out.push(v.toLowerCase());
  }
  return out;
}

/** The colour a setting has right now (its own value, or the theme's). */
export function currentColor(key: ColorKey): string {
  const v = parseColor(getComputedStyle(document.documentElement).getPropertyValue(TOKEN_OF[key]).trim());
  return toHex(v ?? BLACK);
}

// ------------------------------------------------------------------ state

let current: Personal = DEFAULT;
let problems: Record<Mode, Problem[]> = { dark: [], light: [] };
let snapshot = { p: current, problems, mode: "dark" as Mode };
const subs = new Set<() => void>();
let saveTimer = 0;
let lastSentMode: Mode | null = null;

function notify() {
  snapshot = { p: current, problems, mode: resolveMode(current) };
  subs.forEach((f) => f());
}

function readStore(): Stored | null {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || "null") as Stored | null;
    const p = clean(s?.p);
    return p && s ? { ...s, p } : null;
  } catch {
    return null;
  }
}

function themeColorMeta(): HTMLMetaElement {
  let m = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (!m) {
    m = document.createElement("meta");
    m.name = "theme-color";
    document.head.appendChild(m);
  }
  return m;
}

/** Compute both modes, remember them, paint the current one. */
function apply(sendToServer: boolean) {
  const both = { dark: compute(current, "dark"), light: compute(current, "light") };
  problems = { dark: both.dark.problems, light: both.light.problems };
  const mode = resolveMode(current);
  const root = document.documentElement;
  root.setAttribute("data-preset", current.preset);
  root.setAttribute("data-theme", mode);
  MANAGED.forEach((n) => root.style.removeProperty(n));
  for (const [n, v] of Object.entries(both[mode].vars)) root.style.setProperty(n, v);
  if (both[mode].bar) themeColorMeta().content = both[mode].bar;
  try {
    const st: Stored = {
      p: current,
      vars: { dark: both.dark.vars, light: both.light.vars },
      bar: { dark: both.dark.bar, light: both.light.bar },
    };
    localStorage.setItem(STORE, JSON.stringify(st));
    localStorage.setItem("cf-theme", mode); // older code paths and the 1.2.68 pre-paint script
  } catch {
    /* private window */
  }
  window.dispatchEvent(new CustomEvent("cf-theme", { detail: mode }));
  notify();
  if (sendToServer || lastSentMode !== mode) {
    window.clearTimeout(saveTimer);
    const body = sendToServer
      ? { ui_personal: current, ui_theme: mode, ui_splash: { dark: both.dark.splash, light: both.light.splash } }
      : { ui_theme: mode };
    saveTimer = window.setTimeout(() => {
      api.saveSettings(body).catch(() => {});
    }, 350);
    lastSentMode = mode;
  }
}

/** Once, at start-up (main.tsx): the remembered theme, then the server's copy if it is newer. */
export function initPersonal(): void {
  const st = readStore();
  if (st) current = st.p;
  else {
    let old: string | null = null;
    try {
      old = localStorage.getItem("cf-theme");
    } catch {
      /* ignore */
    }
    current = { ...DEFAULT, mode: old === "light" || old === "dark" ? old : "system" };
  }
  apply(false);
  // the built app's stylesheet can still be loading here: compute again once it is there
  if (!getComputedStyle(document.documentElement).getPropertyValue("--bg").trim()) {
    window.addEventListener("load", () => apply(false), { once: true });
  }
  try {
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => current.mode === "system" && apply(false));
  } catch {
    /* old browser */
  }
  api
    .settings()
    .then((s) => {
      const server = clean(s.ui_personal);
      if (server && server.at > current.at) {
        current = server;
        apply(false);
      } else if (current.at > (server?.at ?? 0)) {
        apply(true); // this browser has the newest: the server (and the splash page) catch up
      }
    })
    .catch(() => {});
}

export function setPersonal(next: Partial<Personal>): void {
  current = { ...current, ...next, v: 1, at: Date.now() };
  apply(true);
}

export function setColor(mode: Mode, key: ColorKey, value: string | null): void {
  const row = { ...current.colors[mode] };
  if (value && isHex6(value)) row[key] = value.toLowerCase();
  else delete row[key];
  setPersonal({ colors: { ...current.colors, [mode]: row } });
}

export function resetPersonal(): void {
  setPersonal({ ...DEFAULT });
}

export function getPersonal(): Personal {
  return current;
}

export function usePersonal(): { p: Personal; problems: Record<Mode, Problem[]>; mode: Mode } {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    () => snapshot,
  );
}

// ------------------------------------------------------------------ theme files

export const FILE_KIND = "sharkyclips-theme";

export function themeFile(p: Personal): string {
  const { at: _at, ...rest } = p;
  void _at;
  return JSON.stringify({ kind: FILE_KIND, ...rest }, null, 2);
}

export function downloadTheme(p: Personal): void {
  const blob = new Blob([themeFile(p)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sharkyclips-theme-${p.preset}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** A theme file's text -> the theme (null: not a SharkyClips theme). */
export function readThemeFile(text: string): Personal | null {
  try {
    const o = JSON.parse(text) as Record<string, unknown>;
    if (!o || o.kind !== FILE_KIND) return null;
    return clean(o);
  } catch {
    return null;
  }
}
