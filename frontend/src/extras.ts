// 1.2.18 API: cover studio, TikTok / Reels, my-voice dubbing, study cards, music visualizer.
import { ApiError, req, type Job } from "./api";

const L = (pid: string, cid: string) => `/api/library/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;

export type CoverFrame = "tall" | "wide";

/** A third-party model / tool and its license (1.2.19: with links and a note of changes). */
export interface ModelLicense {
  name: string;
  by: string;
  license: string;
  license_url?: string;
  source_url?: string;
  /** what was changed from the original, e.g. "onnx_chain" */
  changes?: string;
  /** who made each step, in order (1.2.20: exported to ONNX, then packaged as int8) */
  chain?: { by: string; url?: string }[];
}

export interface LicensesView {
  app: { name: string; version: string; license: string };
  groups: { id: "voice" | "covers"; items: ModelLicense[] }[];
}

/** 1.2.19: what an upload of a file says about its AI voice. */
export interface AiVoiceInfo {
  dub: string;
  line: string | null;
  note: boolean;
  synthetic: boolean;
}

export const aboutApi = {
  licenses: () => req<LicensesView>("GET", "/api/licenses"),
  aiVoice: (pid: string, cid: string, source: string) =>
    req<AiVoiceInfo>(
      "GET",
      `/api/projects/${encodeURIComponent(pid)}/clips/${encodeURIComponent(cid)}/ai_voice?source=${encodeURIComponent(source)}`,
    ),
};

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
  licenses: ModelLicense[];
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

/** 1.2.20: a dubbed clip on TikTok / Reels: the caption line and the AI label (or a reminder). */
export interface PlatformAiVoice {
  dub: string;
  line: string | null;
  note: boolean;
  label: boolean;
}

export interface PlatformAiFlags {
  ai_voice_note: boolean;
  ai_label: boolean;
}

export interface PostResult {
  job: Job;
  mode: "semi" | "api";
  caption: string;
  upload_page: string;
  local: boolean;
  ai_voice: PlatformAiVoice;
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
  clip: (p: PostPlatform, pid: string, cid: string, flags?: PlatformAiFlags) =>
    req<{ caption: string; ai_voice: PlatformAiVoice; mode: "semi" | "api"; upload_page: string; record: any; job: Job | null }>(
      "GET",
      PC(p, pid, cid) + (flags ? `?ai_voice_note=${flags.ai_voice_note}&ai_label=${flags.ai_label}` : ""),
    ),
  post: (p: PostPlatform, pid: string, cid: string, flags?: PlatformAiFlags) => req<PostResult>("POST", PC(p, pid, cid), flags),
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

// ---------------------------------------------------------------- my-voice dubbing

export interface VoiceProfile {
  consent: boolean;
  agreed_at: string | null;
  name: string | null;
  sample: boolean;
  sample_seconds: number | null;
  sample_source: "recorded" | "file" | null;
  targets: string[];
  model_ready: boolean;
  model_mb: number;
  licenses: ModelLicense[];
  ready: boolean;
}

export interface ClipDub {
  lang: string;
  targets: string[];
  profile: VoiceProfile;
  info: {
    lines: { start: number; end: number; text: string; source: string; dub: boolean; why: string }[];
    dubbed: number;
    kept: number;
    made_at: string;
    voice_pass: boolean;
  } | null;
  job: Job | null;
}

export const voiceApi = {
  profile: () => req<VoiceProfile>("GET", "/api/voice"),
  consent: (name: string, own_voice: boolean, no_others: boolean) =>
    req<VoiceProfile>("POST", "/api/voice/consent", { name, own_voice, no_others }),
  revoke: () => req<VoiceProfile>("DELETE", "/api/voice"),
  async sample(blob: Blob, source: "recorded" | "file"): Promise<VoiceProfile> {
    const res = await fetch(`/api/voice/sample?source=${source}`, { method: "PUT", body: blob });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(data.error || res.statusText, data.hint || null, res.status, data.code || null);
    return data as VoiceProfile;
  },
};

const CD = (pid: string, cid: string) => `/api/projects/${encodeURIComponent(pid)}/clips/${encodeURIComponent(cid)}/dub`;

export const dubApi = {
  clip: (pid: string, cid: string) => req<ClipDub>("GET", CD(pid, cid)),
  set: (pid: string, cid: string, lang: string) => req<ClipDub>("POST", CD(pid, cid), { lang }),
};
