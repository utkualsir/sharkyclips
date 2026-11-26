// 1.2.69 Personalization: colour maths. Parse / mix colours, WCAG 2.1 contrast, and the automatic
// fix that makes unreadable text readable again (AA: 4.5:1 for text, 3:1 for marks).
// No imports and no DOM: test_personalize.py runs this file with Node.

export type RGB = [number, number, number]; // 0..255
export type RGBA = [number, number, number, number]; // alpha 0..1

const BLACK: RGB = [0, 0, 0];
const WHITE: RGB = [255, 255, 255];

export const AA_TEXT = 4.5;
export const AA_UI = 3;

/** "#rgb", "#rrggbb", "#rrggbbaa", "rgb(...)", "rgba(...)". null: anything else. */
export function parseColor(v: string | null | undefined): RGBA | null {
  if (!v) return null;
  const s = v.trim().toLowerCase();
  let m = /^#([0-9a-f]{3,8})$/.exec(s);
  if (m) {
    let h = m[1];
    if (h.length === 3 || h.length === 4) h = h.split("").map((c) => c + c).join("");
    if (h.length !== 6 && h.length !== 8) return null;
    const n = (i: number) => parseInt(h.slice(i, i + 2), 16);
    return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
  }
  m = /^rgba?\(([^)]+)\)$/.exec(s);
  if (m) {
    const p = m[1].split(/[\s,/]+/).filter(Boolean);
    if (p.length < 3) return null;
    const ch = (x: string) => (x.endsWith("%") ? (parseFloat(x) * 255) / 100 : parseFloat(x));
    const a = p.length > 3 ? (p[3].endsWith("%") ? parseFloat(p[3]) / 100 : parseFloat(p[3])) : 1;
    const out: RGBA = [ch(p[0]), ch(p[1]), ch(p[2]), a];
    return out.every((x) => Number.isFinite(x)) ? out : null;
  }
  return null;
}

/** A user-entered colour: only "#rrggbb" (what the colour picker gives; safe in CSS and files). */
export function isHex6(v: unknown): v is string {
  return typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v);
}

export function toHex([r, g, b]: RGB | RGBA): string {
  const c = (x: number) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

export function alpha([r, g, b]: RGB | RGBA, a: number): string {
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${Math.round(a * 1000) / 1000})`;
}

/** A see-through colour over an opaque one. */
export function over(top: RGBA, under: RGB): RGB {
  const a = top[3];
  return [top[0] * a + under[0] * (1 - a), top[1] * a + under[1] * (1 - a), top[2] * a + under[2] * (1 - a)];
}

/** a -> b by t (0..1). */
export function mix(a: RGB | RGBA, b: RGB | RGBA, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

export function luminance([r, g, b]: RGB | RGBA): number {
  const ch = (x: number) => {
    const c = x / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}

export function contrast(a: RGB | RGBA, b: RGB | RGBA): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function isDark(c: RGB | RGBA): boolean {
  return luminance(c) < 0.18;
}

/** Black or white, whichever reads better on `bg`. */
export function bestOn(bg: RGB | RGBA): RGB {
  return contrast(BLACK, bg) >= contrast(WHITE, bg) ? BLACK : WHITE;
}

/**
 * The automatic fix: the closest colour to `fg` (same hue, moved towards black or white) that
 * reaches `need` on `bg`. Returns `fg` itself when it already passes.
 */
export function fixContrast(fg: RGB | RGBA, bg: RGB | RGBA, need = AA_TEXT): RGB {
  const base: RGB = [fg[0], fg[1], fg[2]];
  if (contrast(base, bg) >= need) return base;
  const target = bestOn(bg);
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 18; i++) {
    const t = (lo + hi) / 2;
    if (contrast(mix(base, target, t), bg) >= need) hi = t;
    else lo = t;
  }
  const out = mix(base, target, hi);
  const rounded = parseColor(toHex(out));
  // rounding to whole channels can drop it just under the line: one more step if so
  return rounded && contrast(rounded, bg) >= need ? out : mix(base, target, Math.min(1, hi + 0.02));
}

/** A slightly lighter / darker shade for hover states (towards the readable side of `on`). */
export function hoverShade(c: RGB | RGBA, on: RGB | RGBA): RGB {
  return mix(c, isDark(on) ? WHITE : BLACK, 0.14);
}

export { BLACK, WHITE };
