// 1.2.18 API: cover studio, TikTok / Reels, my-voice dubbing, study cards, music visualizer.
import { req, type Job } from "./api";

const L = (pid: string, cid: string) => `/api/library/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;

export type CoverFrame = "tall" | "wide";

export interface CoverAiPlan {
  use: "gpu" | "cpu" | "fallback";
  build: string | null;
  capability: { tier: "gpu" | "cpu" | "none"; reason: string; vram_mb: number | null };
  device: "auto" | "gpu" | "cpu";
  model_ready: boolean;
  tool_ready: boolean;
  download_bytes: number;
  downloaded_bytes: number;
  minutes_per_picture: number | null;
  licenses: { name: string; by: string; license: string }[];
}

export interface AiCoversView {
  prompt: string;
  seeds: number[];
  options: Record<CoverFrame, number[]>;
  chosen: Partial<Record<CoverFrame, number>>;
  made_with: "gpu" | "cpu" | null;
  made_at: string | null;
  plan: CoverAiPlan;
  job: Job | null;
}

export const coversApi = {
  plan: () => req<CoverAiPlan>("GET", "/api/covers/ai"),
  setDevice: (device: CoverAiPlan["device"]) => req<CoverAiPlan>("PUT", "/api/covers/ai", { device }),
  removeModel: () => req<CoverAiPlan & { freed_bytes: number }>("DELETE", "/api/covers/ai/model"),
  view: (pid: string, cid: string) => req<AiCoversView>("GET", `${L(pid, cid)}/ai-covers`),
  make: (pid: string, cid: string, frames: CoverFrame[], fresh = true) =>
    req<{ job: Job }>("POST", `${L(pid, cid)}/ai-covers`, { frames, new: fresh }),
  choose: (pid: string, cid: string, frame: CoverFrame, seed: number) =>
    req<AiCoversView>("POST", `${L(pid, cid)}/ai-covers/choose`, { frame, seed }),
};

export const coverUrls = {
  option: (pid: string, cid: string, seed: number, frame: CoverFrame, text: string, lang: string | null, v = "") =>
    `${L(pid, cid)}/ai-covers/${seed}/${frame}.jpg?${new URLSearchParams({ text, ...(lang ? { lang } : {}), v })}`,
};
