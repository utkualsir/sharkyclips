import type { IconName } from "./components/Icons";

/** 1.2.77: the one reason a clip was picked, shown first on its card ("Chat went wild",
 *  "Big laugh", "Clutch", "You said “clip it”"). Written by the highlight engine
 *  (candidates.headline); older projects have none. */
export type Headline = { code: string; value?: string; n?: string };

type T = (k: string, v?: Record<string, string | number>) => string;

export function headlineLabel(t: T, h: Headline | null | undefined): string | null {
  if (!h?.code) return null;
  if (h.code === "game") {
    if (!h.value) return null;
    const base = t(`reason.${h.value}`);
    return h.n ? `${base} ×${h.n}` : base;
  }
  if (h.code === "said") return t("headline.said", { p: h.value ?? "" });
  return t(`headline.${h.code}`);
}

const ICON: Record<string, IconName> = {
  chat_wild: "message",
  big_laugh: "sparkles",
  funny: "sparkles",
  clutch: "target",
  game: "gamepad",
  scream: "volume",
  hype_voice: "mic",
  out_of_nowhere: "zap",
  fail: "alert",
  big_reaction: "zap",
  explanation: "book",
  music_peak: "music",
  marked: "bell",
  said: "mic",
};

export const headlineIcon = (h: Headline): IconName => ICON[h.code] ?? "zap";
