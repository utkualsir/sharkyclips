// 1.2.66 "Share clips" board + 1.2.68 "share now": everything goes now, up to what YouTube
// really allows today; a choice for the rest; manual uploads; history; free up space.
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
  /** 1.2.68: why a clip that should go now still waits (never silent) */
  waits: { platform: Target; code: string; message: string | null; hint?: string | null; next_try_at?: string | null }[];
  /** 1.2.68: YouTube kept it private although public was asked for */
  private: { platform: Target; studio_url: string | null }[];
  /** 1.2.70: filled in in your browser, waiting for your click on Post (or "did you post it?") */
  assist?: ({ platform: Target } & import("./assist").AssistSnap)[];
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
  video: { kind: "clip"; stamp: string } | { kind: "source" } | { kind: "none" };
  status: ShareStatus;
  posts: ClipPosts;
}

/** What YouTube really allows today (its upload bucket; 100 a day by default). */
export interface DailyLimit {
  limit: number;
  used: number;
  left: number;
  max: number;
  resets_at: string;
  connected?: boolean;
  /** 1.2.75: with the shared client "left" is not exact (one pool for everyone) */
  mode?: "own" | "shared" | null;
  exact?: boolean;
  mine_today?: number;
  exhausted?: boolean;
}

export interface HistorySummary {
  count: number;
  by_platform: Partial<Record<Target, number>>;
  first_at: string | null;
  last_at: string | null;
  clips: number;
}

export interface SourceHistory {
  fingerprint: string | null;
  before: HistorySummary | null;
  before_projects: string[];
}

export interface ProjectHistory {
  fingerprint: string | null;
  before: HistorySummary | null;
  before_projects: string[];
  here: HistorySummary;
}

export interface SpaceView {
  bytes: number;
  source_bytes: number;
  render_bytes: number;
  original: { path: string; bytes: number } | null;
  clips: number;
  shared: number;
  all_shared: boolean;
  any_shared: boolean;
  waiting: { clip_id: string; platform: Target; status: string }[];
  freed_at: string | null;
  freed_bytes: number | null;
}

export interface HistoryRow {
  key: string;
  at: string;
  project_id: string;
  project_title: string;
  clip_id: string;
  title: string;
  game: string | null;
  platform: Target;
  url: string | null;
  video_id: string | null;
  manual: boolean;
  private: boolean;
}

export interface ManualView {
  project_id: string;
  clip_id: string;
  platform: Target;
  status: "idle" | "preparing" | "ready" | "failed" | "shared";
  file: string | null;
  folder: string | null;
  error: { message: string; hint: string | null } | null;
  url: string | null;
  fixed: string[];
  upload_page: string;
  texts: { title: string; description: string; hashtags: string; caption: string };
  progress: number | null;
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
  auto_note: "assist" | "tiktok_beta" | "tiktok_manual" | "ig_manual" | null;
  assist?: boolean;
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
  history: ProjectHistory | null;
  space: SpaceView;
  language: string;
  language_set: boolean;
  has_source: boolean;
}

export interface PlanPlatform {
  platform: Target;
  when: string; // "now" | ISO
  moved: "ig_pace" | "tiktok_cap" | null;
  mode: PostMode;
  by_hand: boolean;
  manual: boolean;
  /** over today's YouTube uploads: "ask" until a choice is made */
  over: "ask" | "manual" | "tomorrow" | "date" | null;
  force_manual?: boolean;
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
  warnings?: ({ code: "ig_pace"; hours: number; last_at: string | null } | { code: "hand_fix"; platform: Target; problem: string })[];
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
  over: number;
  overflow: Overflow | null;
  overflow_at: string | null;
  warnings: number;
}

export type Overflow = "manual" | "tomorrow" | "date";

export interface ShareBody {
  clips: string[];
  platforms: Target[];
  per_clip?: Record<string, { platforms: Target[] }>;
  consent?: boolean;
  overflow?: Overflow;
  overflow_date?: string;
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
  space: (pid: string) => req<SpaceView>("GET", `/api/space/${encodeURIComponent(pid)}`),
  freeSpace: (pid: string, original: boolean) =>
    req<{ freed: number; files: number; space: SpaceView }>("POST", `/api/space/${encodeURIComponent(pid)}/free`, { confirm: true, original }),
  history: (q: string, platform?: Target) =>
    req<{ rows: HistoryRow[]; total: number; all: number }>(
      "GET",
      `/api/history?q=${encodeURIComponent(q)}${platform ? `&platform=${platform}` : ""}`,
    ),
  projectHistory: (pid: string) => req<ProjectHistory>("GET", `/api/history/project/${encodeURIComponent(pid)}`),
  sourceHistory: (fp: string) => req<SourceHistory>("GET", `/api/history/source?fp=${encodeURIComponent(fp)}`),
  pathHistory: (path: string) => req<SourceHistory>("POST", "/api/history/check-path", { path }),
  setLanguage: (pid: string, language: string) =>
    req<{ language: string }>("PUT", `/api/projects/${encodeURIComponent(pid)}/content-language`, { language }),
};

const MAN = (pid: string, cid: string, p: Target) =>
  `/api/manual/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}/${p}`;

export const manualApi = {
  view: (pid: string, cid: string, p: Target) => req<ManualView>("GET", MAN(pid, cid, p)),
  prepare: (pid: string, cid: string, p: Target) => req<ManualView>("POST", MAN(pid, cid, p)),
  open: (pid: string, cid: string, p: Target) => req<{ ok: boolean; folder: string }>("POST", `${MAN(pid, cid, p)}/open`),
  done: (pid: string, cid: string, p: Target, url: string) => req<ManualView>("POST", `${MAN(pid, cid, p)}/done`, { url }),
};

/** "4.6 GB" */
export function gb(bytes: number, num: (n: number, digits?: number) => string): string {
  if (bytes >= 1024 ** 3) return `${num(bytes / 1024 ** 3, 1)} GB`;
  return `${num(Math.max(0, bytes) / 1024 ** 2)} MB`;
}

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
