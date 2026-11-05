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

// ---------------------------------------------------------------- TikTok / Instagram Reels

export type Platform = "youtube" | "tiktok" | "reels";
export type PostPlatform = "tiktok" | "reels";

export interface PlatformStatus {
  platform: Platform;
  mode: "semi" | "api";
  connected: boolean;
  account: string | null;
  audited?: boolean;
  has_app?: boolean;
  upload_page?: string | null;
  preset?: string;
  privacy_note?: "self_only" | "app_review" | null;
  expires_at?: number | null;
}

export interface PlatformsOverview {
  youtube: PlatformStatus;
  tiktok: PlatformStatus;
  reels: PlatformStatus;
  chosen: Platform;
}

export interface PostResult {
  job: Job;
  mode: "semi" | "api";
  caption: string;
  upload_page: string;
  local: boolean;
}

const PC = (p: PostPlatform, pid: string, cid: string) =>
  `/api/platforms/${p}/clips/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;

export const platformsApi = {
  overview: () => req<PlatformsOverview>("GET", "/api/platforms"),
  choose: (platform: Platform) => req<PlatformsOverview>("PUT", "/api/platforms/choice", { platform }),
  setMode: (p: PostPlatform, mode: "semi" | "api") => req<PlatformStatus>("PUT", `/api/platforms/${p}/mode`, { mode }),
  setAudited: (p: PostPlatform, audited: boolean) => req<PlatformStatus>("PUT", `/api/platforms/${p}/audited`, { audited }),
  forget: (p: PostPlatform) => req<PlatformStatus>("DELETE", `/api/platforms/${p}`),
  tiktokRedirect: () => req<{ redirect_uri: string }>("GET", "/api/platforms/tiktok/redirect"),
  tiktokConnect: (client_key: string, client_secret: string) =>
    req<{ url: string; redirect_uri: string }>("POST", "/api/platforms/tiktok/connect", { client_key, client_secret }),
  reelsConnect: (token: string) => req<PlatformStatus>("POST", "/api/platforms/reels/connect", { token }),
  clip: (p: PostPlatform, pid: string, cid: string) =>
    req<{ caption: string; mode: "semi" | "api"; upload_page: string; record: any; job: Job | null }>("GET", PC(p, pid, cid)),
  post: (p: PostPlatform, pid: string, cid: string) => req<PostResult>("POST", PC(p, pid, cid)),
  reveal: (file: string) => req<{ opened: boolean }>("POST", "/api/platforms/reveal", { file }),
};

/** Clipboard that also works on http:// LAN addresses (no secure context there). */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    ta.remove();
    return ok;
  }
}
