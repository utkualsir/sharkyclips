// Typed client for the SharkyClips REST API (backend/sharkyclips/web/app.py).

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
  llm: { available: boolean };
}

export interface Job {
  id: string;
  kind: "import" | "transcribe" | "highlights" | "render" | "facecam" | "proxy" | "analyze" | "titles" | "chat" | "montage" | "benchmark" | "update";
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
  persist?: boolean;
  attempt?: number;
  /** running job waiting for the resource governor: why (game, fullscreen, ...) */
  paused?: string | null;
  paused_seconds?: number;
  /** /api/queue only: seconds left for this job / until it is done (with the jobs before it) */
  eta_seconds?: number | null;
  eta_finish_seconds?: number | null;
}

export interface ShutdownState {
  enabled: boolean;
  supported: boolean;
  countdown: number | null;
  seconds: number;
  dry_run: boolean;
  fired_at: number | null;
  error: string | null;
}

export interface QueueView {
  lanes: { gpu: Job[]; io: Job[] };
  history: Job[];
  eta_total_seconds: number | null;
  shutdown: ShutdownState;
  speeds: Record<string, number>;
}

export interface AcceptedOverview {
  project_id: string;
  title: string;
  accepted: number;
  rendered: number;
  to_render: number;
  seconds: number;
}

export interface Calibrated {
  score: number;
  default: number;
  model_score: number;
  predicted_views: number;
  weight: number;
  n: number;
}

export interface CalibrationStatus {
  calibrated: boolean;
  n: number;
  needed: number;
  model_points: number;
  r2_loo: number | null;
  weight: number;
  top_features: { name: string; effect: number }[];
  fitted_at: string | null;
}

export interface Performance {
  views: number;
  likes: number | null;
  published_at: string | null;
  updated_at?: string;
}

export interface CalibrationGroup {
  key: string;
  count: number;
  median_views: number;
  mean_views: number;
}

export interface CalibrationStats {
  status: CalibrationStatus;
  points: {
    key: string;
    project_id: string;
    clip_id: string;
    title: string | null;
    project_title: string | null;
    views: number;
    likes: number | null;
    published_at: string | null;
    predicted: number | null;
    viral_score: number | null;
    mode: string | null;
    duration: number | null;
  }[];
  best: {
    mode: CalibrationGroup[];
    length: CalibrationGroup[];
    moment: CalibrationGroup[];
    time: CalibrationGroup[];
    time_basis: "published" | "stream";
  };
}

export interface MontageExport {
  file: string;
  name: string;
  created_at: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  size_bytes: number;
  render_seconds: number;
  encoder: string;
  language: string;
  model: string | null;
  settings: { intro: boolean; outro: boolean; cards: boolean; crossfade: number; loudness_lufs: number };
  items: { clip_id: string; rank: number; start: number; end: number; label: string | null; viral_score: number | null }[];
  titles: string[];
  description: string;
  chapters: { t: number; label: string; clip: number | null }[];
  chapters_text: string;
}

export interface SpeedEntry {
  model: string;
  seconds_per_clip: number;
  samples: number;
  source: "benchmark" | "analysis";
  updated: string;
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
  sub_scores: { hook: number; retention: number; trend_fit: number; length_fit: number } | null;
  titles: string[];
  title_styles: string[] | null;
  hashtags: string[];
  cover_prompt: string | null;
  cover_text: string | null;
  /** YouTube description: 2-3 sentences + the hashtags at the end */
  description: string | null;
  hook_text: string | null;
  language: string | null;
  /** title text -> 1 (liked) / -1 (disliked) */
  title_votes?: Record<string, number>;
  /** viral score adjusted to this channel's real views (null until calibrated) */
  calibrated?: Calibrated | null;
}

export interface ChatStats {
  messages: number;
  authors: number;
  per_minute: number;
  average_per_minute: number;
  ratio: number | null;
  spikes: { t: number; value: string | null; strength: number | null }[];
  reactions: string[];
  score: number;
}

export interface LlmInfo {
  available: boolean;
  server: string | null;
  installed: { name: string; size_gb: number; params: string | null; family: string | null; quant: string | null }[];
  selected: string;
  auto: string;
  normal_model: string;
  fast_model: string;
  fast_installed: boolean;
  speed: { normal?: SpeedEntry; fast?: SpeedEntry };
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
  llm: null | {
    what_happens: string;
    self_contained: boolean;
    moment_type: string;
    game_or_topic: string;
    refined: boolean;
    original: { start: number; end: number };
  };
  subtitle_languages: string[];
  chat?: ChatStats | null;
}

export interface ClipOptions {
  layout: Layout;
  subtitles: SubtitleStyle;
  hook: boolean;
  hook_flash: boolean;
  subtitle_lang: string;
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
  performance?: Performance | null;
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
  calibration: CalibrationStatus;
  exports: number;
  jobs: Job[];
  chat: null | { status: "ok" | "none"; source: string; reason: string | null; count: number; authors: number };
  game: null | GameSummary;
  analysis: null | { language: string; model: string; analyzed_at: string; glossary?: string[] };
  output_language: string;
}

export type GameId = "delta_force" | "lol";
export type GameChoice = "auto" | GameId | "other";

export interface GameSummary {
  choice: GameChoice;
  game: GameId | null;
  detected: GameId | null;
  why: string;
  name: string | null;
  scanned?: boolean;
  champion?: string | null;
}

export interface GameEvent {
  t: number;
  code: string;
  value?: string;
  strength: number;
  start: number;
  end: number;
  source: string;
  champion?: string;
}

export interface GameRegion {
  box: [number, number, number, number]; // x, y, w, h on a 1920x1080 frame
  label: string;
  custom?: boolean;
}

export interface GameRead {
  t: number;
  region: string;
  text: string;
  how: string;
}

export interface GameView extends GameSummary {
  choices: GameChoice[];
  games: Record<GameId, string>;
  base_size: [number, number];
  regions: Record<string, GameRegion>;
  scan: null | {
    game: GameId;
    current: boolean;
    champion: null | { name: string; confidence: number };
    frame_size: [number, number];
    boxes: Record<string, [number, number, number, number]>;
    stats: { decoder: string; seconds: number; speed: number; frames: number; ocr_calls: number; ocr_seconds?: number };
  };
  events: GameEvent[];
  sounds: { folder?: string; clips?: string[]; ignored?: string[] };
  event_codes: string[];
  reads?: GameRead[];
}

export interface GameProbe {
  t: number;
  regions: Record<string, { text: string; events: string[] }>;
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
  output_language: string;
  custom_triggers: Record<string, string[]>;
  llm_model: string;
  auto_analyze: boolean;
  fast_analysis: boolean;
  glossary: string[];
  performance_mode: PerfMode;
  perf_idle_minutes: number;
  perf_pause_fullscreen: boolean;
  perf_pause_video: boolean;
  perf_pause_busy: boolean;
  perf_idle_only: boolean;
  perf_gpu_temp_limit: number;
  perf_vram_headroom_mb: number;
  perf_games: string[];
  perf_games_default: string[];
  /** Windows: Ollama starts with Windows (null: not Windows / Ollama not installed) */
  ollama_autostart: boolean | null;
}

export type PerfMode = "silent" | "balanced" | "turbo";
export type GovState = "running" | "throttled" | "paused" | "waiting_idle" | "cooling" | "idle" | "off";

/** One resource sample (every ~2 s). *_ours = SharkyClips's own processes. */
export interface ResourceSample {
  t: number;
  cpu: number;
  cpu_ours: number;
  ram_used_mb: number;
  ram_total_mb: number;
  ram_ours_mb: number;
  gpu: number | null;
  gpu_ours: number | null;
  vram_used_mb: number | null;
  vram_total_mb: number | null;
  vram_ours_mb: number | null;
  gpu_temp: number | null;
  cpu_temp: number | null;
  state?: GovState;
}

export interface GovernorView {
  mode: PerfMode;
  state: GovState;
  reason: string | null;
  detail: string | null;
  away?: boolean;
  throttle?: number;
  cores?: number | null;
  cpu_count?: number;
  override?: boolean;
  paused?: boolean;
  busy?: boolean;
  sample: ResourceSample | null;
  limits?: { gpu_temp: number; vram_headroom_mb: number | null; vram_budget_mb: number | null };
  sensors?: { gpu: boolean; per_process_gpu: boolean; gpu_name: string | null };
  job_object?: boolean;
  history?: ResourceSample[];
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

// Heavy jobs (GPU / long CPU work). While an update is being built ("under construction"
// banner), starting one asks first; DevBanner registers the dialog.
const HEAVY: [string, RegExp][] = [
  ["POST", /^\/api\/projects$/],
  ["POST", /\/(transcribe|highlights|analyze|render|montage)$/],
  ["POST", /\/game\/rescan$/],
  ["PUT", /\/game$/],
  ["POST", /^\/api\/(llm\/benchmark|queue\/render|update)$/],
  ["PUT", /^\/api\/uploads/],
];
let heavyGuard: (() => Promise<void>) | null = null;
export function setHeavyGuard(guard: (() => Promise<void>) | null) {
  heavyGuard = guard;
}
async function guardHeavy(method: string, path: string) {
  const p = path.split("?")[0];
  if (heavyGuard && HEAVY.some(([m, re]) => m === method && re.test(p))) await heavyGuard();
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  await guardHeavy(method, path);
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

export interface DevState {
  task: string;
  started_at: string;
  hours: number;
  stale: boolean;
}

export interface AppState {
  version: string;
  /** first launch: show the 3-step onboarding */
  onboarding: boolean;
  /** version whose "What's new" should be shown once */
  whats_new: string | null;
  /** "under construction" banner (fresh flag) */
  dev: DevState | null;
  /** flag older than 12 h: no banner, a note in Settings */
  dev_stale: DevState | null;
  content_types: string[];
}

export interface ChangelogEntry {
  version: string;
  date: string | null;
  lang: string;
  markdown: string;
}

export interface HardwareCheck {
  cpu: string;
  cores: number;
  ram_gb: number;
  gpu: string | null;
  vram_gb: number | null;
  apple_silicon: boolean;
  whisper: { model: string | null; device: string };
  encoder: { name: string; label: string; hardware: boolean } | null;
  llm: { available: boolean; model: string };
  verdict: "great" | "good" | "cpu";
}

export const api = {
  appState: () => req<AppState>("GET", "/api/app"),
  changelog: (version: string, lang: string) =>
    req<ChangelogEntry>("GET", `/api/changelog/${encodeURIComponent(version)}?lang=${encodeURIComponent(lang)}`),
  whatsNewSeen: (version: string) => req<AppState>("POST", "/api/app/whats-new-seen", { version }),
  finishOnboarding: (body: { ui_language?: string; content_types?: string[]; performance_mode?: string }) =>
    req<AppState & { settings: Settings }>("POST", "/api/app/onboarding", body),
  hardwareCheck: () => req<HardwareCheck>("GET", "/api/app/hardware"),
  clearDevFlag: () => req<AppState>("DELETE", "/api/app/dev"),
  meta: () => req<Meta>("GET", "/api/meta"),
  settings: () => req<Settings>("GET", "/api/settings"),
  saveSettings: (s: Partial<Settings>) => req<Settings>("PUT", "/api/settings", s),
  governor: (history = false) => req<GovernorView>("GET", `/api/governor?history=${history}`),
  setPerfMode: (mode: PerfMode) => req<GovernorView>("PUT", "/api/governor", { mode }),
  resumeAnyway: () => req<GovernorView>("POST", "/api/governor/resume"),
  watchGovernor: () => req<{ ok: boolean }>("POST", "/api/governor/watch"),
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
  game: (id: string, reads = false) => req<GameView>("GET", `${P(id)}/game${reads ? "?reads=true" : ""}`),
  setGame: (id: string, choice: GameChoice) =>
    req<{ game: GameSummary; job: Job | null }>("PUT", `${P(id)}/game`, { choice }),
  rescanGame: (id: string) => req<Job>("POST", `${P(id)}/game/rescan`),
  probeGame: (id: string, t: number, game?: GameId) => req<GameProbe>("POST", `${P(id)}/game/probe`, { t, game }),
  saveGameRegion: (game: GameId, region: string, box: [number, number, number, number] | null) =>
    req<Record<string, GameRegion>>("PUT", "/api/game/regions", { game, region, box }),
  detectFacecam: (id: string) => req<Job>("POST", `${P(id)}/facecam/detect`),
  render: (id: string, clip_ids: string[], options: ClipOptions, hooks: Record<string, string>) =>
    req<{ jobs: Job[] }>("POST", `${P(id)}/render`, { clip_ids, options, hooks }),
  regeneratePublish: (id: string, cid: string) => req<Job>("POST", `${P(id)}/candidates/${cid}/publish`),
  analyze: (id: string, lang?: string, force = false) => req<Job>("POST", `${P(id)}/analyze`, { lang, force }),
  voteTitle: (id: string, cid: string, text: string, vote: -1 | 0 | 1) =>
    req<{ text: string; vote: number }>("POST", `${P(id)}/candidates/${cid}/titles/vote`, { text, vote }),
  llm: () => req<LlmInfo>("GET", "/api/llm"),
  importChat: async (id: string, file: File) => {
    const res = await fetch(`${P(id)}/chat?filename=${encodeURIComponent(file.name)}`, { method: "PUT", body: file });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || res.statusText, data.hint || null, res.status);
    return data as NonNullable<ProjectDetail["chat"]>;
  },
  cancelJob: (jobId: string) => req<Job>("POST", `/api/jobs/${jobId}/cancel`),
  moveJob: (jobId: string, to: number) => req<Job>("POST", `/api/jobs/${jobId}/move`, { to }),
  retryJob: (jobId: string) => req<Job>("POST", `/api/jobs/${jobId}/retry`),
  forgetJob: (jobId: string) => req<{ removed: boolean }>("DELETE", `/api/jobs/${jobId}`),
  queue: () => req<QueueView>("GET", "/api/queue"),
  queueAccepted: () => req<AcceptedOverview[]>("GET", "/api/queue/accepted"),
  queueRender: (project_ids: string[], rerender = false) =>
    req<{ queued: number; jobs: Job[] }>("POST", "/api/queue/render", { project_ids, rerender }),
  queueCancel: (filter: { project_id?: string; kind?: string; batch?: string } = {}) =>
    req<{ cancelled: number }>("POST", "/api/queue/cancel", filter),
  queueClear: () => req<{ removed: number }>("POST", "/api/queue/clear"),
  setShutdown: (enabled: boolean) => req<ShutdownState>("PUT", "/api/queue/shutdown", { enabled }),
  cancelShutdown: () => req<ShutdownState>("POST", "/api/queue/shutdown/cancel"),
  montage: (id: string, body: { clip_ids: string[]; intro: boolean; outro: boolean; cards: boolean; lang?: string }) =>
    req<Job>("POST", `${P(id)}/montage`, body),
  exports: (id: string) => req<MontageExport[]>("GET", `${P(id)}/exports`),
  deleteExport: (id: string, name: string) => req<{ removed: boolean }>("DELETE", `${P(id)}/exports/${name}`),
  setPerformance: (id: string, cid: string, body: { views: number; likes?: number | null; published_at?: string | null }) =>
    req<{ entry: any; calibration: CalibrationStatus }>("PUT", `${P(id)}/clips/${cid}/performance`, body),
  deletePerformance: (id: string, cid: string) =>
    req<{ removed: boolean; calibration: CalibrationStatus }>("DELETE", `${P(id)}/clips/${cid}/performance`),
  calibration: () => req<CalibrationStats>("GET", "/api/calibration"),
  clearCalibration: () => req<{ removed: number }>("DELETE", "/api/calibration"),
  deleteCalibrationEntry: (key: string) =>
    req<{ removed: boolean }>("DELETE", `/api/calibration/${encodeURIComponent(key)}`),
  benchmark: () => req<Job>("POST", "/api/llm/benchmark"),
  jobs: () => req<Job[]>("GET", "/api/jobs"),
  updateStatus: () => req<UpdateStatus>("GET", "/api/update"),
  updateApply: () => req<Job>("POST", "/api/update"),
  updateRestart: () => req<{ restarting: boolean }>("POST", "/api/update/restart"),
};

export interface UpdateStatus {
  current: string;
  latest: string | null;
  available: boolean;
  behind: number;
  changes: string[];
  supported: boolean;
  reason: null | "no_git" | "not_git_checkout" | "no_upstream" | "fetch_failed";
  error?: string;
  releases_url: string;
  can_restart: boolean;
}

export const urls = {
  source: (id: string) => `${P(id)}/media/source`,
  thumb: (id: string, v?: string | null) => `${P(id)}/thumb.jpg${v ? `?v=${encodeURIComponent(v)}` : ""}`,
  frame: (id: string, t: number, w = 1280) => `${P(id)}/frame.jpg?t=${t.toFixed(1)}&w=${w}`,
  clip: (id: string, cid: string, stamp: string) => `${P(id)}/clips/${cid}/video?v=${encodeURIComponent(stamp)}`,
  clipDownload: (id: string, cid: string) => `${P(id)}/clips/${cid}/video?download=true`,
  export: (id: string, name: string) => `${P(id)}/exports/${name}/video`,
  exportDownload: (id: string, name: string) => `${P(id)}/exports/${name}/video?download=true`,
  exportPoster: (id: string, name: string) => `${P(id)}/exports/${name}/poster.jpg`,
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
  const promise = guardHeavy("PUT", "/api/uploads").then(() => new Promise<Job>((resolve, reject) => {
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
  }));
  return { promise, abort: () => xhr.abort() };
}
