// 1.2.70 assisted upload: SharkyClips fills in TikTok Studio / Instagram in your own browser and
// you click Post (backend: assist.py + web/assist_api.py, the extension in assist_ext/).
import { req } from "./api";
import type { Target } from "./multipost";

export type AssistState =
  | "new"
  | "pause"
  | "opening"
  | "claimed"
  | "uploading"
  | "filling"
  | "login"
  | "captcha"
  | "ready"
  | "post_clicked"
  | "tab_closed"
  | "posted"
  | "failed"
  | "fallback"
  | "confirm"
  | "cancelled"
  | "not_posted";

/** One assisted post as the clip's record / the app's panel show it. */
export interface AssistSnap {
  id: string;
  state: AssistState;
  step: string | null;
  progress: number | null;
  notes: string[] | null;
  reason: string | null;
  detail?: string | null;
  url: string | null;
  setup: boolean | null;
  browser: string | null;
  browser_name: string | null;
  until: number | null;
  ready_at: number | null;
  message?: string | null;
  hint?: string | null;
}

export interface AssistTask extends AssistSnap {
  project_id: string;
  clip_id: string;
  platform: Exclude<Target, "youtube">;
  title: string | null;
}

export interface AssistBrowser {
  key: string;
  name: string;
  fills: boolean;
  autoload: boolean;
}

export interface AssistView {
  browsers: {
    installed: AssistBrowser[];
    default: string | null;
    chosen: string;
    using: string | null;
    using_name: string | null;
    fills: boolean;
  };
  pause_s: number;
  tasks: AssistTask[];
  ext: { dir: string; seen_at: number; page: string | null; autoload: boolean };
  modes: { tiktok: string; reels: string };
}

export type AssistAction = "show" | "posted" | "not_posted" | "skip" | "manual";

export const assistApi = {
  view: () => req<AssistView>("GET", "/api/assist"),
  settings: (body: { browser?: string; pause_s?: number }) => req<AssistView>("PUT", "/api/assist/settings", body),
  open: (platform: "tiktok" | "reels") => req<{ browser: string; name: string }>("POST", "/api/assist/open", { platform }),
  setup: (action: "extensions" | "folder") => req<{ dir: string }>("POST", "/api/assist/setup", { action }),
  /** 1.2.74: a 6-digit code for a Helper installed from a store (Edge Add-ons / Firefox Add-ons) */
  pairCode: () => req<{ code: string; expires_in: number }>("POST", "/api/assist/pair-code"),
  act: (id: string, action: AssistAction, url?: string) =>
    req<AssistView>("POST", `/api/assist/task/${encodeURIComponent(id)}/${action}`, url ? { url } : {}),
};

/** States in which the post is still on its way (the bar shows it). */
export const ASSIST_LIVE: AssistState[] = ["pause", "opening", "claimed", "uploading", "filling", "login", "captcha", "ready", "post_clicked", "tab_closed"];

/** The i18n key of a state's line ("Everything is ready. Check and click Post." ...). */
export function assistKey(s: Pick<AssistSnap, "state" | "setup">, platform: string): string {
  if (s.setup && s.state === "opening") return "assist.st_setup";
  if (s.state === "ready" && platform === "reels") return "assist.st_ready_ig";
  if (s.state === "claimed" || s.state === "new") return "assist.st_filling";
  if (s.state === "tab_closed") return "assist.st_confirm";
  return `assist.st_${s.state}`;
}

export function openAssistGuide() {
  window.dispatchEvent(new CustomEvent("sc-assist-guide"));
}
