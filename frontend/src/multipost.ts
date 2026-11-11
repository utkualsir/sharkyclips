// 1.2.36: one Publish button, three platforms (YouTube + Instagram Reels + TikTok) and the accounts.
import { req } from "./api";

export type Target = "youtube" | "tiktok" | "reels";
export const TARGETS: Target[] = ["youtube", "tiktok", "reels"];
export const TARGET_NAME: Record<Target, string> = { youtube: "YouTube", tiktok: "TikTok", reels: "Instagram" };

export type PostStatus = "idle" | "scheduled" | "preparing" | "uploading" | "processing" | "ready" | "published" | "failed" | "cancelled";

/** 1.2.39: semi (default for TikTok / Instagram) = SharkyClips makes the file + copies the caption,
 *  you paste and share; api = posted by itself (automatic posting on + a working token). */
export type PostMode = "semi" | "api";

export interface PostError {
  message: string;
  hint: string | null;
  code?: string | null;
  kind?: "auth" | "rate_limit" | "quota" | "transient" | "fatal";
}

export interface PostState {
  platform: Target;
  status: PostStatus;
  progress: number | null;
  url: string | null;
  privacy: string | null;
  publish_at: string | null;
  posted_at: string | null;
  late: boolean;
  error: PostError | null;
  views: number | null;
  likes: number | null;
  stats_at: number | string | null;
  next_try_at: number | string | null;
  make_public_url: string | null;
  locked?: boolean;
  job: string | null;
  mode?: PostMode | null;
  manual?: boolean;
  remind_at?: string | null;
}

export type ClipPosts = Record<Target, PostState> & { total_views: number | null; everywhere: boolean };

export type Pill = "ok" | "attention" | "signed_out";

export interface Account {
  platform: Target;
  connected: boolean;
  handle: string | null;
  name: string | null;
  avatar: boolean;
  health: { pill: Pill; reason: string | null; message: string | null };
  audited: boolean;
  has_app: boolean;
  app_id?: string | null;
  expires_at?: number | null;
  connected_at?: number | string | null;
  encrypted: boolean;
  stats?: boolean;
  scopes?: string[];
  redirect?: string | null;
  mode?: PostMode;
  upload_page?: string | null;
}

export interface Quota {
  used: number;
  total: number;
  approx?: boolean;
  uploads_left?: number;
  resets_at?: string;
}

export type Accounts = Record<Target, Account> & { quota?: Record<Target, Quota | null> };

export interface Problem {
  platform: Target | "all";
  code: string;
  fix: string | null;
  params: Record<string, string | number>;
}

export interface TikTokSettings {
  privacy: string | null;
  allow_comment: boolean;
  allow_duet: boolean;
  allow_stitch: boolean;
  disclose: boolean;
  brand_organic: boolean;
  brand_content: boolean;
}

export interface TikTokView {
  ok: boolean;
  audited: boolean;
  error?: { message: string; hint: string | null; code?: string | null };
  creator?: { username: string | null; nickname: string | null };
  privacy_options?: string[];
  comment_disabled?: boolean;
  duet_disabled?: boolean;
  stitch_disabled?: boolean;
  max_seconds?: number;
  settings?: TikTokSettings;
  privacy?: string | null;
  music_url?: string;
  branded_url?: string;
}

export interface PublishView {
  project_id: string;
  clip_id: string;
  targets: Target[];
  drafts: {
    youtube: { title: string; description: string; full_description: string; hashtags: string[]; tags: string[]; edited: boolean };
    tiktok: { caption: string; edited: boolean };
    reels: { caption: string; edited: boolean };
  };
  accounts: Accounts;
  states: ClipPosts;
  problems: Problem[];
  tiktok: TikTokView | null;
  quota: Record<Target, Quota | null>;
  limits: {
    youtube: { title: number; description: number; max_seconds: number; min_seconds: number };
    tiktok: { caption: number; max_seconds: number; min_seconds: number };
    reels: { caption: number; hashtags: number; max_seconds: number; min_seconds: number };
  };
  duration: number;
  cover_ms: number;
  source: "clip" | "rendering" | "export";
  ai_voice: { dub: string; line: string | null; note: boolean; label: boolean };
  cover_kind: string;
  bleep_hold: number;
  lead_s: number;
  ready: boolean;
  modes: Record<Target, PostMode>;
}

export interface HandoffPlatform extends PostState {
  file: string | null;
  caption: string;
  upload_page: string;
  ai_label: boolean;
}

export interface Handoff {
  project_id: string;
  clip_id: string;
  platforms: Partial<Record<"tiktok" | "reels", HandoffPlatform>>;
}

export interface StartResult {
  results: Partial<Record<Target, { status: PostStatus; skipped?: boolean; publish_at?: string; moved?: boolean; error?: PostError; mode?: PostMode; upload_page?: string }>>;
  view: PublishView;
}

const B = (pid: string, cid: string) => `/api/publish/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;
const q = (targets?: Target[]) => (targets ? `?platforms=${targets.join(",")}` : "");

export const publishApi = {
  view: (pid: string, cid: string, targets?: Target[]) => req<PublishView>("GET", `${B(pid, cid)}${q(targets)}`),
  save: (pid: string, cid: string, body: { drafts?: Record<string, unknown>; tiktok?: Partial<TikTokSettings> }, targets?: Target[]) =>
    req<PublishView>("PUT", `${B(pid, cid)}${q(targets)}`, body),
  fix: (pid: string, cid: string, platform: string, code: string) => req<PublishView>("POST", `${B(pid, cid)}/fix`, { platform, code }),
  start: (
    pid: string,
    cid: string,
    body: { platforms: Target[]; when: string; consent?: boolean; drafts?: Record<string, unknown>; tiktok?: Partial<TikTokSettings> },
  ) => req<StartResult>("POST", B(pid, cid), body),
  retry: (pid: string, cid: string, p: Target) => req<PublishView>("POST", `${B(pid, cid)}/retry/${p}`),
  unplan: (pid: string, cid: string, p: Target) => req<PublishView>("POST", `${B(pid, cid)}/unplan/${p}`),
  handoff: (pid: string, cid: string, targets?: Target[]) => req<Handoff>("GET", `${B(pid, cid)}/handoff${q(targets)}`),
  shared: (pid: string, cid: string, p: Target, url?: string) => req<Handoff>("POST", `${B(pid, cid)}/shared/${p}`, { url: url ?? "" }),
  targets: () => req<{ targets: Target[] }>("GET", "/api/publish/targets"),
  setTargets: (targets: Target[]) => req<{ targets: Target[] }>("PUT", "/api/publish/targets", { targets }),
};

export const accountsApi = {
  list: () => req<Accounts>("GET", "/api/accounts"),
  check: (p: Target) => req<Accounts>("POST", `/api/accounts/${p}/check`),
  disconnect: (p: "tiktok" | "reels") => req<Accounts>("DELETE", `/api/accounts/${p}`),
  avatar: (p: Target, stamp: string | number = "") => `/api/accounts/${p}/avatar?v=${encodeURIComponent(String(stamp))}`,
  tiktokRedirect: () => req<{ redirect_uri: string }>("GET", "/api/platforms/tiktok/redirect"),
  tiktokConnect: (client_key: string, client_secret: string) =>
    req<{ url: string; redirect_uri: string }>("POST", "/api/platforms/tiktok/connect", { client_key, client_secret }),
  igRedirect: () => req<{ redirect_uri: string }>("GET", "/api/platforms/reels/redirect"),
  igToken: (token: string, account = "") => req<unknown>("POST", "/api/platforms/reels/connect", { token, account }),
  igOauth: (app_id: string, app_secret: string) => req<{ url: string; redirect_uri: string }>("POST", "/api/platforms/reels/oauth", { app_id, app_secret }),
  igFinish: (url: string) => req<Accounts>("POST", "/api/platforms/reels/oauth/finish", { url }),
  setAudited: (p: "tiktok" | "reels", audited: boolean) => req<unknown>("PUT", `/api/platforms/${p}/audited`, { audited }),
};

/** Which platforms still need this post (idle / failed / cancelled). */
export function todo(posts: ClipPosts | undefined | null, targets: Target[]): Target[] {
  return targets.filter((p) => !posts || ["idle", "failed", "cancelled"].includes(posts[p]?.status ?? "idle"));
}

/** The platforms that go "by hand" after Publish: semi mode and not out yet. */
export function byHand(targets: Target[], modes: Partial<Record<Target, PostMode>> | null | undefined, posts?: ClipPosts | null): Target[] {
  return (["reels", "tiktok"] as Target[]).filter(
    (p) => targets.includes(p) && (modes?.[p] ?? "semi") === "semi" && posts?.[p]?.status !== "published",
  );
}

export interface HandoffRequest {
  pid: string;
  cid: string;
  title?: string;
  platforms: Target[];
}

/** Opens the "post it yourself" steps (one platform after the other), wherever Publish was pressed. */
export function openHandoff(d: HandoffRequest) {
  if (d.platforms.length) window.dispatchEvent(new CustomEvent<HandoffRequest>("sc-handoff", { detail: d }));
}

export function busyState(s: PostStatus | undefined): boolean {
  return s === "preparing" || s === "uploading" || s === "processing";
}
