// Typed client for the ClipForge REST API (backend/clipforge/web/app.py).

export type Mode = "gaming" | "study" | "music";
export type Layout = "auto" | "split" | "fit" | "crop";
export type SubtitleStyle = "bold" | "clean" | "minimal" | "none";
export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";

export interface Language {
  code: string;
  native_name: string;
  english_name: string;
  is_rtl: boolean;
}

export interface Meta {
  version: string;
  languages: Language[];
  default_language: string;
  modes: Mode[];
  layouts: Layout[];
  subtitle_styles: SubtitleStyle[];
  encoders: { name: string; label: string; hardware: boolean }[];
  reason_codes: string[];
  is_local: boolean;
  lan_url: string | null;
  workspace: string | null;
}

export interface Job {
  id: string;
  kind: "import" | "transcribe" | "highlights" | "render" | "facecam" | "proxy";
  lane: string;
  project_id: string | null;
  params: Record<string, any>;
  status: JobStatus;
  stage: string | null;
  progress: number | null;
  detail: Record<string, any>;
  error: { message: string; hint: string | null } | null;
  result: any;
  created: number;
  started: number | null;
  finished: number | null;
}

export interface ProjectSummary {
  id: string;
  title: string;
  mode: Mode | null;
  duration: number | null;
  resolution: string | null;
  source: { type: string | null; value: string | null; extractor: string | null; uploader: string | null };
  language: string | null;
  created_at: string | null;
  state: "running" | "queued" | "error" | "ready" | "transcribed" | "imported" | "importing";
  candidates: number | null;
  clips: number;
  job: Job | null;
  last_error: { message: string; hint: string | null } | null;
  last_error_kind: string | null;
}

export interface Reason {
  code: string;
  value?: string;
  t: number;
  strength: number;
  signal: string;
}

export interface Publish {
  available: boolean;
  viral_score: number | null;
  viral_label: "low" | "medium" | "high" | "very_high" | null;
  titles: string[];
  hashtags: string[];
  cover_prompt: string | null;
}

export interface Candidate {
  id: string;
  rank: number;
  start: number;
  end: number;
  duration: number;
  peak: number;
  hype_score: number;
  reasons: Reason[];
  signal_scores: Record<string, number>;
  text: string;
  default_hook: string;
  publish: Publish;
}

export interface ClipOptions {
  layout: Layout;
  subtitles: SubtitleStyle;
  hook: boolean;
}

export interface Facecam {
  x: number;
  y: number;
  w: number;
  h: number;
  source?: "auto" | "manual";
  confidence?: number | null;
}

export interface Review {
  accepted: string[];
  hooks: Record<string, string>;
  options: ClipOptions;
  facecam: Facecam | null;
  facecam_checked: boolean;
}

export interface RenderedClip {
  file: string;
  id: string;
  rank: number;
  start: number;
  end: number;
  duration: number;
  options: ClipOptions & { hook_text: string };
  rendered_at: string;
  size_bytes: number;
  render_seconds: number;
  encoder: string;
}

export interface ProjectDetail extends Omit<ProjectSummary, "clips"> {
  meta: { width: number; height: number; fps: number; video_codec: string; source_size_bytes: number };
  playable: boolean;
  is_rtl: boolean;
  highlights: null | {
    mode: Mode;
    created_at: string;
    signals: Record<string, { status: string; weight: number; share: number; reason?: string }>;
    candidates: Candidate[];
  };
  review: Review;
  clips: Record<string, RenderedClip>;
  jobs: Job[];
}

export interface HypeCurve {
  duration: number;
  resolution_s: number;
  combined: number[];
  signals: Record<string, { share: number; values: number[] }>;
  candidates: { rank: number; start: number; end: number; peak: number; hype_score: number }[];
}

export interface Word {
  start: number;
  end: number;
  word: string;
}

export interface Settings {
  ui_language: string;
  default_mode: Mode;
  video_encoder: string;
  custom_triggers: Record<string, string[]>;
}

export class ApiError extends Error {
  hint: string | null;
  status: number;
  constructor(message: string, hint: string | null, status: number) {
    super(message);
    this.hint = hint;
    this.status = status;
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    let hint: string | null = null;
    try {
      const data = await res.json();
      msg = data.error || data.detail || msg;
      hint = data.hint || null;
    } catch {
      /* not JSON */
    }
    throw new ApiError(msg, hint, res.status);
  }
  return res.json() as Promise<T>;
}

const P = (id: string) => `/api/projects/${encodeURIComponent(id)}`;

export const api = {
  meta: () => req<Meta>("GET", "/api/meta"),
  settings: () => req<Settings>("GET", "/api/settings"),
  saveSettings: (s: Partial<Settings>) => req<Settings>("PUT", "/api/settings", s),
  projects: () => req<ProjectSummary[]>("GET", "/api/projects"),
  project: (id: string) => req<ProjectDetail>("GET", P(id)),
  hype: (id: string) => req<HypeCurve>("GET", `${P(id)}/hype`),
  words: (id: string, start: number, end: number) =>
    req<Word[]>("GET", `${P(id)}/words?start=${start}&end=${end}`),
  create: (body: { url?: string; path?: string; mode: Mode; language: string }) =>
    req<Job>("POST", "/api/projects", body),
  transcribe: (id: string, language = "auto", force = false) =>
    req<Job>("POST", `${P(id)}/transcribe`, { language, force }),
  highlights: (id: string, mode?: Mode, force = false) =>
    req<Job>("POST", `${P(id)}/highlights`, { mode, force }),
  saveReview: (id: string, changes: Partial<Review>) => req<Review>("PUT", `${P(id)}/review`, changes),
  detectFacecam: (id: string) => req<Job>("POST", `${P(id)}/facecam/detect`),
  render: (id: string, clip_ids: string[], options: ClipOptions, hooks: Record<string, string>) =>
    req<Job>("POST", `${P(id)}/render`, { clip_ids, options, hooks }),
  regeneratePublish: (id: string, cid: string) => req<Publish>("POST", `${P(id)}/candidates/${cid}/publish`),
  cancelJob: (jobId: string) => req<Job>("POST", `/api/jobs/${jobId}/cancel`),
  jobs: () => req<Job[]>("GET", "/api/jobs"),
};

export const urls = {
  source: (id: string) => `${P(id)}/media/source`,
  thumb: (id: string, v?: string | null) => `${P(id)}/thumb.jpg${v ? `?v=${encodeURIComponent(v)}` : ""}`,
  frame: (id: string, t: number, w = 1280) => `${P(id)}/frame.jpg?t=${t.toFixed(1)}&w=${w}`,
  clip: (id: string, cid: string, stamp: string) => `${P(id)}/clips/${cid}/video?v=${encodeURIComponent(stamp)}`,
  clipDownload: (id: string, cid: string) => `${P(id)}/clips/${cid}/video?download=true`,
};

/** Upload a file with progress (streamed to disk by the server). */
export function uploadFile(
  file: File,
  mode: Mode,
  language: string,
  onProgress: (fraction: number) => void,
): { promise: Promise<Job>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const q = new URLSearchParams({ filename: file.name, mode, language });
  const promise = new Promise<Job>((resolve, reject) => {
    xhr.open("PUT", `/api/uploads?${q}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let data: any = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as Job);
      else reject(new ApiError(data?.error || xhr.statusText, data?.hint || null, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Network error", null, 0));
    xhr.onabort = () => reject(new ApiError("aborted", null, 0));
    xhr.send(file);
  });
  return { promise, abort: () => xhr.abort() };
}
