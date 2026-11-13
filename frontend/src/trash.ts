// 1.2.41: delete + trash + disk usage (backend: trash.py, web/trash_api.py).
import { req } from "./api";

export interface TrashItem {
  id: string;
  kind: "project" | "clips" | "cleanup";
  project_id: string;
  project_title: string;
  clip_ids: string[];
  /** clip titles; for "cleanup" what was cleaned (rejected / previews) */
  titles: string[];
  deleted_at: string;
  expires_at: string;
  days_left: number;
  bytes: number;
  restorable: boolean;
  original: { path: string; moved: boolean; bytes: number; outside_workspace: boolean; error?: string } | null;
  posts: { deleted: Post[]; by_hand: Post[]; failed: (Post & { error: string })[] } | null;
}

export interface Post {
  platform: "youtube" | "tiktok" | "reels";
  clip_id: string;
  id: string | null;
  url: string | null;
  title: string | null;
  can_delete: boolean;
}

export interface TrashSummary {
  items: TrashItem[];
  count: number;
  bytes: number;
  keep_days: number;
}

export interface DeleteInfo {
  project_id: string;
  title: string;
  bytes: number;
  keep_days: number;
  posts: Post[];
  original: { path: string; bytes: number; outside_workspace: boolean } | null;
}

export interface Cleanable {
  rejected: { bytes: number; files: number; clips: number };
  previews: { bytes: number };
  caches: { bytes: number };
}

export interface ProjectUsage {
  project_id: string;
  title: string;
  total: number;
  source: number;
  audio: number;
  clips: number;
  exports: number;
  cache: number;
  other: number;
  cleanable: Cleanable;
  cleanable_bytes: number;
}

export interface DiskUsage {
  projects: ProjectUsage[];
  total: number;
  trash_bytes: number;
  trash_count: number;
  cleanable_bytes: number;
}

const P = (id: string) => encodeURIComponent(id);

export const trashApi = {
  list: () => req<TrashSummary>("GET", "/api/trash"),
  restore: (id: string) =>
    req<{ restored: string; kind: string; project_id: string; clip_ids: string[]; trash: TrashSummary }>("POST", `/api/trash/${P(id)}/restore`),
  purge: (id: string) => req<{ bytes: number; trash: TrashSummary }>("DELETE", `/api/trash/${P(id)}`),
  empty: (count: number) => req<{ deleted: number; bytes: number; left: number; trash: TrashSummary }>("POST", "/api/trash/empty", { count }),
  info: (pid: string, clips?: string[]) =>
    req<DeleteInfo>("GET", `/api/projects/${P(pid)}/delete-info${clips?.length ? `?clips=${clips.map(P).join(",")}` : ""}`),
  deleteProject: (pid: string, o: { original: boolean; posts: boolean }) =>
    req<{ item: TrashItem; trash: TrashSummary }>("POST", `/api/projects/${P(pid)}/delete`, o),
  deleteClips: (pid: string, clip_ids: string[], posts: boolean) =>
    req<{ item: TrashItem; trash: TrashSummary }>("POST", `/api/projects/${P(pid)}/clips/delete`, { clip_ids, posts }),
  disk: () => req<DiskUsage>("GET", "/api/disk"),
  cleanup: (pid: string, what: ("rejected" | "previews" | "caches")[]) =>
    req<{ freed_now: number; trashed: TrashItem | null; usage: ProjectUsage }>("POST", `/api/projects/${P(pid)}/cleanup`, { what }),
};
