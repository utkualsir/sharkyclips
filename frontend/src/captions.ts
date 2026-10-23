import type { SubtitleStyle, Word } from "./api";

// Same rules as backend/clipforge/clips.py so the live 9:16 preview matches the rendered clip.
const NO_SPACE = new Set(["zh", "ja"]);
const BREAK_AFTER = /[.!?。！？…؟,，]$/;

export function groupWords(words: Word[], style: SubtitleStyle, lang: string | null): Word[][] {
  const [maxChars, maxWords] = style === "bold" ? [16, 3] : [30, 7];
  const joiner = lang && NO_SPACE.has(lang) ? "" : " ";
  const groups: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    if (cur.length) {
      const text = [...cur, w].map((x) => x.word).join(joiner);
      const gap = w.start - cur[cur.length - 1].end;
      const last = cur[cur.length - 1].word;
      if (text.length > maxChars || cur.length >= maxWords || gap > 0.7 || BREAK_AFTER.test(last)) {
        groups.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) groups.push(cur);
  return groups;
}

export function upper(text: string, lang: string | null): string {
  if (lang === "tr") text = text.replace(/i/g, "İ").replace(/ı/g, "I");
  if (lang === "ar" || lang === "zh" || lang === "ja") return text;
  return text.toUpperCase();
}

export function joinerFor(lang: string | null): string {
  return lang && NO_SPACE.has(lang) ? "" : " ";
}

export interface CaptionFrame {
  words: string[];
  active: number; // index of the word being spoken
}

/** Which caption is on screen at time t (absolute seconds). */
export function captionAt(groups: Word[][], t: number, clipEnd: number): CaptionFrame | null {
  for (let gi = 0; gi < groups.length; gi++) {
    const g = groups[gi];
    const start = g[0].start;
    const next = gi + 1 < groups.length ? groups[gi + 1][0].start : clipEnd;
    const end = Math.min(Math.max(g[g.length - 1].end + 0.35, start + 0.4), next, clipEnd);
    if (t >= start && t < end) {
      let active = 0;
      for (let i = 0; i < g.length; i++) if (t >= g[i].start) active = i;
      return { words: g.map((w) => w.word), active };
    }
  }
  return null;
}
