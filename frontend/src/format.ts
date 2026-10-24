/** 75.4 -> "1:15", 3725 -> "1:02:05" */
export function fmtTime(sec: number | null | undefined, withTenths = false): string {
  if (sec == null || !isFinite(sec)) return "–";
  const neg = sec < 0;
  sec = Math.abs(sec);
  const whole = withTenths ? Math.floor(sec) : Math.round(sec);
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const base = h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  const tenths = withTenths ? `.${Math.floor((sec - whole) * 10)}` : "";
  return (neg ? "-" : "") + base + tenths;
}

export function fmtBytes(n: number): string {
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export function sourceLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const u = new URL(value);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return value.split(/[\/]/).pop() || value;
  }
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Remaining time for the queue: 42 -> "42 s", 380 -> "6 min", 4000 -> "1 h 7 min" (localized units) */
export function fmtEta(
  sec: number | null | undefined,
  num: (n: number) => string,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (sec == null || !isFinite(sec)) return "–";
  if (sec < 60) return t("unit.sec", { n: num(Math.max(1, Math.round(sec))) });
  const m = Math.round(sec / 60);
  if (m < 60) return t("unit.min", { n: num(m) });
  return t("unit.hour_min", { h: num(Math.floor(m / 60)), m: num(m % 60) });
}

/** 12345 -> "12K" in the UI language (Latin digits) */
export function fmtCompact(n: number, lang: string): string {
  try {
    return new Intl.NumberFormat(`${lang}-u-nu-latn`, { notation: "compact", maximumFractionDigits: 1 }).format(n);
  } catch {
    return String(n);
  }
}

/** 12345 -> "12,345" in the UI language (Latin digits) */
export function fmtInt(n: number, lang: string): string {
  return new Intl.NumberFormat(`${lang}-u-nu-latn`, { maximumFractionDigits: 0 }).format(n);
}
