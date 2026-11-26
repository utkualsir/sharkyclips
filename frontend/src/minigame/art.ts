// The mini game's artwork (1.2.59): sprite colours of the sharks, fish, hazards and effects.
// Fixed on purpose (a fish is orange in every theme); the water and the sea floor follow the app
// theme instead (--mg-* tokens, render.ts). One of the few files that may hold colour values
// (test_theme_tokens.py).

export interface Skin {
  body: string;
  belly: string;
  fin: string;
  eye: string;
  /** "" | stripes | spots | glow | ghost | dots | shine */
  pattern: string;
  accent: string;
}

export const SKINS: Record<string, Skin> = {
  classic: { body: "#6f8fb8", belly: "#eef3fa", fin: "#5a7aa3", eye: "#0e1a33", pattern: "", accent: "#ffd23f" },
  reef: { body: "#3fa7a0", belly: "#e9fbf6", fin: "#2f8a84", eye: "#0e1a33", pattern: "spots", accent: "#ffcf5c" },
  tiger: { body: "#c98a3c", belly: "#fff2dc", fin: "#a86e2a", eye: "#1b1206", pattern: "stripes", accent: "#3b2410" },
  neon: { body: "#2a2f7a", belly: "#c9f7ff", fin: "#1f2463", eye: "#ffffff", pattern: "glow", accent: "#3ef0ff" },
  ghost: { body: "#cfd8ea", belly: "#ffffff", fin: "#b7c3dc", eye: "#4a5a80", pattern: "ghost", accent: "#ffffff" },
  deep: { body: "#1c2740", belly: "#40507a", fin: "#141d33", eye: "#9ff7d8", pattern: "dots", accent: "#7dffcf" },
  gold: { body: "#d9b56a", belly: "#fff6d8", fin: "#b8913f", eye: "#2a1d05", pattern: "shine", accent: "#ffffff" },
};

export const FISH_COLORS = ["#ff8a5b", "#ffd35b", "#7fd36b", "#5bc8ff", "#c38bff", "#ff6fa8", "#5be0c8", "#ffe08a"];
export const TONES = ["#ffffff", "#ffe08a", "#7df9ff", "#ff8a8a"];

export const POWER_COLORS: Record<string, string> = { magnet: "#ff6b6b", frenzy: "#ffd35b", shield: "#6bd6ff", time: "#8cff9e" };

/** Fallback water (Classic) if the theme tokens can't be read. */
export const SEA_DEFAULT = { a: "#1b5b8f", b: "#0f3a66", c: "#08203f", floor: "#0a2340", dark: "#0b1426" };

export const ART = {
  ray: "#cfe9ff",
  kelp: "rgba(40, 110, 110, 0.45)",
  bubble: "rgba(220, 240, 255, 0.25)",
  predator: "#3d4a5c",
  predatorSafe: "#7a8a99",
  dangerEye: "#ff5d5d",
  dangerRing: "rgba(255, 120, 120, 0.8)",
  goldFish: "#ffd44d",
  jelly: "rgba(214, 140, 255, 0.85)",
  jellyLine: "rgba(230, 180, 255, 0.8)",
  urchin: "#2b1d3a",
  urchinLine: "#e05bff",
  shield: "rgba(120, 220, 255, 0.7)",
  trail: "rgba(235, 245, 255, 0.55)",
  shade: "rgba(0,0,0,0.25)",
  pop: "rgba(220,240,255,0.9)",
  spark: "#fff3b0",
  textEdge: "rgba(5, 15, 35, 0.8)",
  frenzyEdge: "rgba(255, 211, 91, 0.55)",
  hurtEdge: "rgba(255, 107, 107, 0.45)",
  white: "#ffffff",
  white80: "rgba(255,255,255,0.8)",
  white55: "rgba(255,255,255,0.55)",
  white35: "rgba(255,255,255,0.35)",
  white12: "rgba(255,255,255,0.12)",
} as const;

export const glow = (a: number): string => `rgba(255,255,255,${a})`;
