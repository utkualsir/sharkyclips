// 1.2.66 "Share clips": every clip of a project on one board, the daily upload limit, batches.
import { req } from "./api";
import type { ClipPosts, PostError, PostMode, Target } from "./multipost";

export type ShareKind = "not_shared" | "scheduled" | "working" | "shared" | "failed";

export interface ShareStatus {
  kind: ShareKind;
  shared: { platform: Target; url: string | null }[];
  planned: { platform: Target; at: string | null; by_hand: boolean }[];
  failed: { platform: Target; message: string | null; hint: string | null }[];
  busy: Target[];
  next_at: string | null;
  progress: number | null;
}

export interface ShareCard {
  id: string;
  rank: number;
  title: string;
  duration: number;
  start: number;
  end: number;
  peak: number;
  viral_score: number | null;
  viral_label: string | null;
  video: { kind: "clip"; stamp: string } | { kind: "source" };
  status: ShareStatus;
  posts: ClipPosts;
}

export interface DailyLimit {
  limit: number;
  used: number;
  left: number;
  max: number;
  resets_at: string;
}

export interface SharePlatform {
  platform: Target;
  name: string;
  usable: boolean;
  connected: boolean;
  mode: PostMode;
  by_hand: boolean;
  manual: boolean;
  handle: string | null;
  pill: string;
}

export interface BatchRow {
  clip_id: string;
  title: string;
  when: string;
  state: "queued" | "starting" | "done" | "failed";
  platforms: Target[];
  error: PostError | null;
}

export interface Batch {
  id: string;
  started_at: number;
  finished_at: number | null;
  state: "running" | "done" | "stopped";
  rows: BatchRow[];
  skipped: { clip_id: string; reason: string }[];
  dismissed?: boolean;
}

export interface ShareBoard {
  project_id: string;
  title: string;
  clips: ShareCard[];
  limit: DailyLimit;
  platforms: Record<Target, SharePlatform>;
  targets: Target[];
  batch: Batch | null;
  ig_gap_hours: number;
}

export interface PlanPlatform {
  platform: Target;
  when: string; // "now" | ISO
  moved: "ig_pace" | "tiktok_cap" | null;
  mode: PostMode;
  by_hand: boolean;
  manual: boolean;
}

export interface PlanProblem {
  platform: Target | "all";
  code: string;
  fix: string | null;
  params: Record<string, string | number>;
}

export interface PlanRow {
  clip_id: string;
  title?: string;
  duration?: number;
  already: { platform: Target; status: string; url: string | null; at: string | null }[];
  not_connected?: Target[];
  platforms: PlanPlatform[];
  skipped: "already" | "no_platform" | "missing" | "cant" | null;
  problems: PlanProblem[];
  /** platforms this clip can't go to (too long / too short there): left out with the reason */
  dropped?: PlanProblem[];
  day?: string;
  when?: string;
  rolled?: boolean;
}

export interface SharePlan {
  rows: PlanRow[];
  limit: DailyLimit;
  uses_today: number;
  left_after: number;
  days: { day: string; count: number }[];
  count: number;
  skipped: number;
  duplicates: number;
  problems: number;
  needs_consent: boolean;
  platforms: Record<Target, SharePlatform>;
  ig_gap_hours: number;
}

export interface ShareBody {
  clips: string[];
  platforms: Target[];
  per_clip?: Record<string, { platforms: Target[] }>;
  consent?: boolean;
}

const S = (pid: string) => `/api/share/${encodeURIComponent(pid)}`;

export const shareApi = {
  board: (pid: string) => req<ShareBoard>("GET", S(pid)),
  plan: (pid: string, body: ShareBody) => req<SharePlan>("POST", `${S(pid)}/plan`, body),
  publish: (pid: string, body: ShareBody) => req<{ batch: Batch; plan: SharePlan }>("POST", `${S(pid)}/publish`, body),
  unschedule: (pid: string, clips: string[]) =>
    req<{ done: { clip_id: string; platform: Target }[]; errors: { clip_id: string; message: string }[] }>("POST", `${S(pid)}/unschedule`, { clips }),
  retry: (pid: string, clips: string[]) =>
    req<{ done: { clip_id: string; platform: Target }[]; errors: { clip_id: string; message: string; hint: string | null }[] }>(
      "POST",
      `${S(pid)}/retry`,
      { clips },
    ),
  dismiss: (pid: string) => req<{ batch: Batch | null }>("POST", `${S(pid)}/batch/dismiss`),
  limit: () => req<DailyLimit>("GET", "/api/share/limit"),
  setLimit: (limit: number) => req<DailyLimit>("PUT", "/api/share/limit", { limit }),
};

/** Tell the "uploads left today" pill (and other screens) that something was shared / changed. */
export function shareChanged() {
  window.dispatchEvent(new CustomEvent("sc-share-changed"));
}

/** "18:00" today, "Tue 24 Nov 12:00" another day (the viewer's language). */
export function whenText(iso: string | null | undefined, lang: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const same = d.toDateString() === today.toDateString();
  const time = d.toLocaleTimeString(`${lang}-u-nu-latn`, { hour: "2-digit", minute: "2-digit" });
  if (same) return time;
  return `${d.toLocaleDateString(`${lang}-u-nu-latn`, { weekday: "short", day: "numeric", month: "short" })} ${time}`;
}
