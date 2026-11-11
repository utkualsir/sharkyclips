// 1.2.40: publish queue for Claude in Chrome (no platform APIs): files under 10 MB, texts, calendar.
import { req, type Job } from "./api";

export type QPlatform = "youtube" | "tiktok" | "instagram";
export const QPLATFORMS: QPlatform[] = ["youtube", "tiktok", "instagram"];
export const QNAME: Record<QPlatform, string> = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram" };
export type QStatus = "pending" | "scheduled" | "failed" | "skipped_duplicate";

export interface QPlatformSettings {
  on: boolean;
  per_day: number;
  times: string[];
}

export interface QSettings {
  root: string;
  brand_hashtag: string;
  tiktok_cap: number;
  instagram_account: string;
  instagram_accounts: string[];
  instagram_default: string;
  instagram_gaming: string;
  platforms: Record<QPlatform, QPlatformSettings>;
}

export interface QDraft {
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  platforms: QPlatform[] | null;
  times: Partial<Record<QPlatform, string>>;
  instagram_account: string | null;
  edited: boolean;
}

export interface QSlot {
  status: QStatus;
  scheduled_at: string | null;
  url: string | null;
  note: string | null;
  batch?: string | null;
  account?: string | null;
}

export interface QClip {
  project_id: string;
  project_title: string;
  mode: string;
  clip_id: string;
  rank: number | null;
  duration: number;
  rendered: boolean;
  uid: string;
  draft: QDraft;
  instagram_account: string;
  status: Partial<Record<QPlatform, QSlot>>;
}

export interface QEntry extends QSlot {
  id: string;
  platform: QPlatform;
  title: string | null;
  sha256: string | null;
  source: string | null;
}

export interface QBatch {
  batch: string;
  folder: string;
  created_at: string | null;
  clips: number;
  size_mb: number;
}

export interface QResult {
  batch: string;
  folder: string;
  queue: string;
  clips: { id: string; title: string; size_mb: number; duration_s: number; platforms: Partial<Record<QPlatform, QSlot>> }[];
  errors: { id: string; title: string; message: string; hint: string | null }[];
}

export interface QOverview {
  settings: QSettings;
  caps: Record<QPlatform, number>;
  timezone: string;
  root: string;
  clips: QClip[];
  calendar: QEntry[];
  batches: QBatch[];
  job: (Job & { result?: QResult | null }) | null;
  now: string;
}

export interface QItem {
  project_id: string;
  clip_id: string;
}

export const pqApi = {
  overview: () => req<QOverview>("GET", "/api/pubqueue"),
  settings: (body: Partial<QSettings> | { platforms: Partial<Record<QPlatform, Partial<QPlatformSettings>>> }) =>
    req<QOverview>("PUT", "/api/pubqueue/settings", body),
  draft: (pid: string, cid: string, body: Partial<QDraft> | { reset: true }) =>
    req<{ draft: QDraft }>("PUT", `/api/pubqueue/clips/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`, body),
  preview: (items: QItem[]) =>
    req<{ ok: boolean; error?: { message: string; hint: string | null }; clips: { id: string; platforms: Partial<Record<QPlatform, QSlot>> }[] }>(
      "POST",
      "/api/pubqueue/preview",
      { items },
    ),
  prepare: (items: QItem[]) => req<{ job: Job }>("POST", "/api/pubqueue/prepare", { items }),
  importStatus: (text: string) =>
    req<{ updated: number; unmatched: unknown[]; rows: number; overview: QOverview }>("POST", "/api/pubqueue/import", { text }),
  brief: (batch?: string) =>
    req<{ batch: string; folder: string; text: string }>("GET", `/api/pubqueue/brief${batch ? `?batch=${encodeURIComponent(batch)}` : ""}`),
  open: (batch?: string) => req<{ opened: boolean; folder: string }>("POST", "/api/pubqueue/open", { batch: batch ?? null }),
};

/** "2026-11-12T18:00:00+01:00" -> "12.11 18:00" (the ISO already holds the Budapest wall time). */
export function wall(iso: string | null | undefined, withYear = false): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}${withYear ? `.${m[1]}` : ""} ${m[4]}:${m[5]}`;
}

/** ISO -> the value of an <input type="datetime-local"> in Budapest wall time. */
export function toInput(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 16) : "";
}
