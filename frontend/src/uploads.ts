// 1.2.75 Uploads stats + honest YouTube quota (backend: uploadstats.py, web/uploads_api.py).
import { req, type YoutubeQuota } from "./api";
import type { Target } from "./multipost";

/** The four groups of the stats, in their fixed order (the chart colours follow it). */
export const GROUPS = ["youtube", "reels", "tiktok", "manual"] as const;
export type Group = (typeof GROUPS)[number];

export interface StatItem {
  key: string;
  title: string;
  project_title: string | null;
  game: string | null;
  platform: Target;
  group: Group;
  at: string;
  url: string | null;
  status: "published" | "private" | "by_hand";
}

export interface StatBucket {
  total: number;
  by: Record<Group, number>;
  items: StatItem[];
}

export interface UploadStats {
  groups: Group[];
  today: StatBucket & { from: string };
  week: StatBucket & { from: string };
  total: StatBucket & { from: string | null };
  days: (StatBucket & { date: string })[];
  generated_at: string;
}

export interface QuotaView {
  quota: YoutubeQuota;
  mode: "own" | "shared" | null;
  connected: boolean;
  resets_at: string;
  own_console_url: string | null;
  owner: { enabled: boolean; console_url: string | null };
  pool_counter: { enabled: boolean; on: boolean; url: string };
}

export const uploadsApi = {
  stats: () => req<UploadStats>("GET", "/api/uploads/stats"),
  quota: () => req<QuotaView>("GET", "/api/youtube/quota"),
  saveQuotaSettings: (body: { owner_view?: boolean; pool_counter?: boolean; pool_url?: string }) =>
    req<QuotaView>("PUT", "/api/youtube/quota/settings", body),
};

/** "09:00": the local time of a UTC instant (the reset at midnight Pacific Time). */
export function localTime(iso: string, lang: string): string {
  return new Date(iso).toLocaleTimeString(`${lang}-u-nu-latn`, { hour: "2-digit", minute: "2-digit" });
}

/** A count is only honest with the own client or the real shared-pool number. */
export const isExact = (q: Pick<YoutubeQuota, "exact"> | null | undefined) => q?.exact !== false;
