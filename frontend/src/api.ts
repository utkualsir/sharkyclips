// Typed client for the SharkyClips REST API (backend/sharkyclips/web/app.py).

export type Mode = "gaming" | "study" | "music";
export type Layout = "auto" | "split" | "fit" | "crop";
export type SubtitleStyle = "bold" | "karaoke" | "speakers" | "clean" | "minimal" | "none";
export type BleepSound = "classic" | "boop" | "custom";
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
  kind: "import" | "transcribe" | "highlights" | "render" | "facecam" | "proxy" | "analyze" | "titles" | "chat" | "montage" | "benchmark" | "update" | "export" | "upload" | "yt_stats" | "music" | "story" | "story_render" | "ab" | "hook_fetch" | "cover_burn" | "voices" | "proofread" | "ai_cover" | "dub" | "platform_export" | "platform_upload" | "swearscan" | "long_metadata";
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
  lanes: { gpu: Job[]; io: Job[]; net?: Job[] };
  history: Job[];
  eta_total_seconds: number | null;
  shutdown: ShutdownState;
  speeds: Record<string, number>;
  /** 1.2.24 "Pause queue": no new job starts */
  paused?: boolean;
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
  /** YouTube tags (1.2.25: from the game bank; older analyses: none) */
  tags?: string[];
  /** the project's game these texts are about */
  game?: { id: string; name: string; source: string } | null;
  facts?: { events: string[]; terms: string[] } | null;
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
  /** marked by hand (I/O) */
  manual?: boolean;
}

export type ProfanityMode = "auto" | "bleep" | "mute" | "off";
export type CutLevel = "off" | "light" | "strong";
export type ZoomLevel = "off" | "subtle" | "strong";

export interface ClipOptions {
  layout: Layout;
  subtitles: SubtitleStyle;
  hook: boolean;
  hook_flash: boolean;
  subtitle_lang: string;
  profanity: ProfanityMode;
  profanity_captions: boolean;
  /** bleep sound (profanity "mute" = silence instead) */
  bleep_sound: BleepSound;
  /** captions: one colour per speaker / "Me:" name tags (after "Hear every speaker") */
  speaker_colors: boolean;
  speaker_names: boolean;
  cuts: CutLevel;
  zoom: ZoomLevel;
  music: boolean;
  brand: boolean;
  /** seamless loop (1.2.5): the end flows back into the start */
  loop: boolean;
  /** fun effects (1.2.17): slow-motion replay of the key event, chat bubbles, meme effects */
  replay?: ReplayMode;
  chat_bubbles?: boolean;
  memes?: MemeLevel;
  /** 1.2.18: dub language ("" = original voice), study cards (study mode), visualizer (music mode) */
  dub?: string;
  study_cards?: "off" | "auto";
  visualizer?: "off" | "auto";
  /** 1.2.21: which "maybe" swears are bleeped (auto = Strict) */
  swear_strict?: SwearStrict;
  /** 1.2.22: "****" with a pop in the captions, a "#@!" badge near the facecam */
  bleep_visual?: boolean;
  bleep_icon?: boolean;
}

export type SwearStrict = "auto" | "normal" | "strict" | "paranoid";
export type ReplayMode = "off" | "auto";
export type MemeLevel = "off" | "light" | "strong";

/** The seam of a seamless loop (source times). */
export interface LoopSeam {
  start: number;
  end: number;
  orig_start: number;
  orig_end: number;
  audio_xfade: number;
  video_xfade: number;
  music_like: boolean;
  tail_ok: boolean;
  gain_db: number;
  score: number;
  reasons: string[];
  last_word: string | null;
  first_word: string | null;
  hook_text: string | null;
  source: "signals" | "ai";
}

export interface SeamMeasure {
  click_ratio: number;
  hf_burst_db: number;
  lufs_end: number;
  lufs_start: number;
  loudness_step_lu: number;
  typical_step_lu: number;
  ok: boolean;
}

/** One clip's edits (transcript editor): trims and deleted source-time ranges. */
export interface ClipEdit {
  start?: number;
  end?: number;
  deleted?: [number, number][];
  /** source-time ranges bleeped by hand / swears switched off in the review list */
  bleep?: [number, number][];
  unbleep?: [number, number][];
}

/** One detected / "maybe" / manual swear of a clip (edit/swears.py), source times. */
export interface SwearItem {
  i: number | null;
  start: number;
  end: number;
  word: string;
  spk: string | null;
  status: "sure" | "maybe" | "manual";
  why: string;
  score: number;
  bleep: boolean;
  /** deep check (1.2.21): passes that heard it ("3/4"), what they heard, exact times */
  votes?: string | null;
  heard?: string[] | null;
  aligned?: boolean;
}

export interface SwearScanItem {
  start: number;
  end: number;
  word: string;
  heard: string[] | null;
  spk: string | null;
  status: "sure" | "maybe";
  score: number;
  votes: string | null;
  why: string;
  bleep: [number, number] | null;
  aligned: boolean | null;
  leak: string | null;
  leak_first: string | null;
  rounds: number | null;
}

export interface SwearScanView {
  done: boolean;
  aligner_ready: boolean;
  created_at?: string;
  model?: string;
  aligned?: boolean;
  seconds?: number;
  windows?: number;
  stale?: boolean;
  count?: { normal: number; strict: number; paranoid: number };
  items?: SwearScanItem[];
}

export interface SwearLabels {
  version: number;
  items: Record<string, { start: number; end: number; word: string; heard?: string[]; label?: "yes" | "no" | "unsure"; note?: string; by?: string }>;
}

export interface LearnedWord {
  word: string;
  n: number;
  spk: Record<string, number>;
  last: string | null;
}

export interface VoiceTrack {
  pos: number;
  title: string;
  codec: string | null;
  channels: number | null;
  label: TrackLabel;
}
export type TrackLabel = "me" | "friends" | "mixed" | "game" | "music" | "ignore";

export interface VoicesView {
  tracks: VoiceTrack[];
  labels_from: "project" | "remembered" | "guess";
  labels: TrackLabel[];
  models: { sherpa: boolean; models: Record<string, { ready: boolean; size_mb: number }> };
  done: boolean;
  mode?: "tracks" | "separate";
  whole?: boolean;
  ranges?: [number, number][];
  speakers?: Record<string, { seconds: number }>;
  names?: Record<string, string>;
  separated?: boolean;
  diarized?: boolean;
  words?: number;
  hints?: number;
  created_at?: string;
  seconds?: number;
  stale?: boolean;
}

export interface FacecamCandidate {
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number;
  presence: number;
  liveness: number;
  border: number;
  face: { x: number; y: number; w: number; h: number };
}

export interface FacecamAnalysis {
  candidates: FacecamCandidate[];
  ask: boolean;
  confidence: number | null;
  frame: boolean;
  frame_time: number | null;
  detector: string | null;
  created_at: string | null;
  layout: { channel: string; width: number; height: number; game: string; confirmed: boolean;
    box: { x: number; y: number; w: number; h: number } } | null;
  low: number;
}

export interface PlanWord extends Word {
  removed?: boolean;
  bleep?: boolean;
  filler?: boolean;
  /** a "maybe" swear that is not bleeped */
  maybe?: boolean;
}

export interface ZoomPulse {
  t0: number;
  t1: number;
  target: "scene" | "cam";
  code: string;
}

export interface PlanMusic {
  name: string;
  title: string;
  artist: string;
  best_start: number | null;
  duration: number | null;
  why: "manual" | "ai" | "signals" | "mode";
  mood?: string;
  credit?: string;
}

/** What the render does to a clip (source times), for the live preview. */
export interface EditPlanView {
  clip_id: string;
  start: number;
  end: number;
  fps: number;
  keep: [number, number][];
  removed: { a: number; b: number; kind: "deleted" | "silence" | "filler" }[];
  duration: number;
  words: PlanWord[];
  bleep_mode: "bleep" | "mute" | "off";
  bleep_sound: BleepSound;
  bleeps: [number, number][];
  swears: SwearItem[];
  /** speaker ids of the voice pass -> custom name ("" = default label) */
  speakers: Record<string, string>;
  mask_captions: boolean;
  zoom_level: number;
  pulses: ZoomPulse[];
  music: PlanMusic | null;
  suggestion: { name: string; title: string; artist: string; mood: string; why: string; matched: boolean } | null;
  brand: boolean;
  brand_preset: BrandPreset | null;
  intro_s: number;
  outro_s: number;
  loop: LoopSeam | null;
  /** fun effects (1.2.17): what the render adds */
  fx?: {
    inserts: { kind: "replay" | "freeze"; code: string; dur: number; at: number; text: string }[];
    bubbles: { a: number; user: string; text: string }[];
    shakes: [number, number][];
    punches: [number, number][];
    smooth: "mci" | "blend";
    extra: number;
  } | null;
  /** 1.2.22: swear_check_failed | swear_safety_net */
  warnings?: string[];
}

export type Mood = "hype" | "chill" | "sad" | "funny";

export interface MusicTrack {
  name: string;
  title: string;
  artist: string;
  moods: Mood[];
  mood_guess: Mood | null;
  duration: number | null;
  bpm: number | null;
  best_start: number | null;
  lufs: number | null;
  analyzed: boolean;
  size_bytes: number;
}

export interface MusicLibrary {
  folder: string;
  tracks: MusicTrack[];
  moods: Mood[];
  credit_template: string;
  credit_enabled: boolean;
}

export type LogoPos = "tl" | "tr" | "bl" | "br";

export interface BrandCard {
  enabled: boolean;
  text: string;
  seconds: number;
}

export interface BrandPreset {
  id: string;
  name: string;
  channel: string;
  handle: string;
  logo: string | null;
  logo_pos: LogoPos;
  logo_size: number;
  logo_opacity: number;
  show_handle: boolean;
  intro: BrandCard;
  outro: BrandCard;
  card_color: string;
  caption_font: string;
  caption_color: string;
  caption_highlight: string;
  caption_outline: string;
  rev: number;
}

export interface BrandState {
  presets: BrandPreset[];
  active: string | null;
  positions: LogoPos[];
}

/** Brand kit > Channel text: the channel's hashtags (first one always first), tag names, socials block */
export interface ChannelText {
  hashtags: string[];
  names: string[];
  socials: { enabled: boolean; headings: Record<string, string>; lines: string[] };
  default_headings: Record<string, string>;
  preview: string;
  preview_lang: string;
}

/** Brand kit > My style: the creator's own titles / descriptions / hashtags / tags (in ~/.sharkyclips/style) */
export interface StyleExample {
  id?: string;
  format: "short" | "long";
  game: string;
  title: string;
  description: string;
  hashtags: string[];
  tags: string[];
  source?: string;
  views?: number | null;
}

export interface StyleProfile {
  enabled: boolean;
  lang: string;
  name: string;
  channel_tag: string;
  shorts_socials: boolean;
  learn_likes: boolean;
  templates: Record<string, string>;
  examples: StyleExample[];
}

export interface StyleGlossary {
  keep: string[];
  corrections: Record<string, string>;
  sounds: Record<string, string>;
  learned: { from: string; to: string; at: string }[];
}

export interface StyleState {
  profile: StyleProfile;
  exists: boolean;
  glossary: StyleGlossary;
  builtin_corrections: Record<string, string>;
  games: { id: string; name: string }[];
  folder: string;
}

/** Full-video (16:9) metadata in the creator's style */
export interface LongMetadata {
  titles: string[];
  description: string;
  hashtags: string[];
  tags: string[];
  profile: "my_style" | "sample";
  model: string;
  strong: boolean;
  at: string;
}

/** One game's bank (Studio > Games): hashtags, tags, names, key words... as editable JSON */
export interface GameBank {
  id: string;
  name: string;
  custom: boolean;
  builtin: boolean;
  bank: Record<string, unknown>;
}

export interface MetadataGame {
  id: string;
  name: string;
  known: boolean;
  why: string;
  source: "override" | "hud" | "detected" | "unknown";
  choice: string;
  choices: { id: string; name: string }[];
}

export interface WordLists {
  profanity: Record<string, { words: string[]; default: string[]; custom: boolean }>;
  fillers: Record<string, { sure: string[]; maybe: string[]; default: { sure: string[]; maybe: string[] }; custom: boolean }>;
  silence_ms: { light: number; strong: number };
  silence_default_ms: { light: number; strong: number };
  /** 1.2.21: swears learned from manual bleeps (add) and unbleeps (ignore), per language */
  learned?: Record<string, { add: LearnedWord[]; ignore: LearnedWord[] }>;
}

export interface RenderEdits {
  duration?: number;
  cut_seconds?: number;
  cuts?: number;
  bleeps?: number;
  zoom_pulses?: number;
  music?: (PlanMusic & { offset: number }) | null;
  lufs?: number | null;
  brand?: string | null;
  loop?: (LoopSeam & { duration: number; audio_seam: SeamMeasure | null; dissolve: boolean;
    video_seam: { seam_step: number; typical_step: number } | null }) | null;
}

export interface Facecam {
  x: number;
  y: number;
  w: number;
  h: number;
  source?: "auto" | "manual" | "remembered";
  confidence?: number | null;
}

export interface Review {
  accepted: string[];
  hooks: Record<string, string>;
  options: ClipOptions;
  facecam: Facecam | null;
  facecam_checked: boolean;
  rejected: string[];
  edits: Record<string, ClipEdit>;
  /** per clip: song file name, "" = no music (missing = the AI's suggestion) */
  music: Record<string, string>;
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
  edits?: RenderEdits | null;
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
  metadata_game?: null | MetadataGame;
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
  /** speaker id from "Hear every speaker": "me", "f1", "f2"... */
  spk?: string;
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
  ui_motion: "full" | "reduced" | "off";
  ui_theme?: "dark" | "light";
  youtube_daily_quota: number;
}

// ------------------------------------------------------------------ export + YouTube (1.2.2)

export type FormatId = "mp4_h264" | "mp4_hevc" | "mp4_av1" | "mov" | "webm_vp9" | "gif" | "mp3" | "m4a";
export type PresetId = "youtube_shorts" | "tiktok" | "instagram_reels" | "x" | "youtube_16x9";

export interface ExportFormat {
  id: FormatId;
  label: string;
  kind: "video" | "gif" | "audio";
  ext: string;
  available: boolean;
  encoder: string | null;
  hardware: boolean;
}

export interface ExportPreset {
  id: PresetId;
  label: string;
  frame: "vertical" | "wide";
  width: number;
  height: number;
  fps: number;
  bitrate_k: number;
  audio_k: number;
  max_seconds: number | null;
  safe: [number, number, number, number];
  format: FormatId;
  thumbnail: boolean;
}

export interface ExportOptions {
  formats: ExportFormat[];
  presets: ExportPreset[];
  gif_default_mb: number;
  subtitle_kinds: ("srt" | "vtt")[];
  editors: ("fcpxml" | "premiere")[];
}

export interface ExportRequest {
  format: FormatId | null;
  preset: PresetId | null;
  burn_captions: boolean;
  subtitles: ("srt" | "vtt")[];
  subtitle_lang: string;
  editors: ("fcpxml" | "premiere")[];
  gif_max_mb: number;
}

export interface ExportWarning {
  code: "too_long" | "gif_over_limit";
  max?: number;
  duration?: number;
  max_mb?: number;
}

export interface ExportEstimate {
  clips: { clip_id: string; bytes: number; seconds: number; warnings: ExportWarning[] }[];
  bytes: number;
  seconds: number;
}

export interface ExportFile {
  name: string;
  role: string; // media | srt | vtt | fcpxml | premiere
  mime: string;
  size_bytes: number;
  language?: string | null;
  editor?: boolean;
}

export interface ClipExport {
  id: string;
  clip_id: string;
  rank: number;
  format: FormatId | null;
  preset: PresetId | null;
  files: ExportFile[];
  duration: number;
  encoder: string | null;
  seconds: number;
  created_at: string;
  frame: "vertical" | "wide" | null;
  subtitle_language: string | null;
  warnings: ExportWarning[];
  /** the song used (editing tools), with its credit line when that setting is on */
  music?: (PlanMusic & { offset: number }) | null;
}

export interface YoutubeQuota {
  used: number;
  limit: number;
  uploads_left: number;
  uploads_left_with_thumbnail: number;
  resets_at: string;
}

export interface YoutubeStatus {
  client: boolean;
  client_id: string | null;
  project_id: string | null;
  connected: boolean;
  channel: { id: string; title: string; thumbnail: string | null } | null;
  connected_at: string | null;
  quota: YoutubeQuota;
  last_synced: number | null;
  analytics?: boolean;
  uploads_locked?: null | { at: string; video_id: string };
  /** the token may manage videos (scheduling, cancel, playlists): connected with 1.2.7+ */
  manage?: boolean;
  lock?: YoutubeLock;
  token_protection?: "dpapi" | "keychain" | "file" | null;
  /** 1.2.8: shared = SharkyClips' built-in Google client, own = the user's own project */
  mode: "shared" | "own" | null;
  /** a sign-in is possible (built-in client available or own client loaded) */
  ready: boolean;
  shared: { available: boolean; verification: "testing" | "production" | "in_review" | "verified"; user_cap: number; project_id: string | null };
  channels: { id: string; title: string; thumbnail: string | null }[];
  no_channel: boolean;
  create_channel_url: string;
  signed_out: YoutubeSignedOut | null;
}

export interface YoutubeSignedOut {
  at: string;
  channel: { id: string; title: string; thumbnail: string | null } | null;
  reason: string;
}

export interface ConnectFlow {
  id: string;
  status: "waiting" | "ok" | "no_channel" | "choose_channel" | "cancelled" | "error" | "expired" | "api_disabled";
  message: string | null;
  hint: string | null;
  reason: string | null;
  youtube: YoutubeStatus | null;
}

/** Are uploads forced to private (unaudited Google project)? unknown = no upload told us yet. */
export interface YoutubeLock {
  state: "locked" | "unlocked" | "unknown";
  at: string | null;
  video_id: string | null;
}

export type Privacy = "private" | "unlisted" | "public";

export interface YoutubeUpload {
  video_id: string;
  url: string;
  title: string;
  privacy: Privacy;
  publish_at: string | null;
  file: string;
  uploaded_at: string;
  views?: number;
  likes?: number | null;
  stats_at?: string;
  thumbnail_error?: string | null;
  hook_style?: HookStyle | null;
  hook_variant?: "A" | "B" | null;
  retention?: number;
  missing?: boolean;
}

// ------------------------------------------------------------- stories + A/B hooks (1.2.5)

export type StoryArc = "fail_comeback" | "setup_payoff" | "running_joke" | "escalation" | "other";

export interface StorySegment {
  cid: string;
  start: number;
  end: number;
  card: string;
  role: string;
  rank: number | null;
}

export interface StoryPublish {
  titles: string[];
  description: string;
  hashtags: string[];
  hook_text: string;
  cover_text: string;
  cover_prompt: string;
  language: string;
  source: "ai" | "clips";
}

export interface Story {
  id: string;
  title: string;
  arc: StoryArc;
  pitch: string;
  segments: StorySegment[];
  cards: boolean;
  duration: number;
  publish: StoryPublish | null;
  created_at: string;
  cut_text: { cid: string; card: string; text: string }[];
  render: null | {
    file: string;
    rendered_at: string;
    size_bytes: number;
    encoder: string;
    info: { duration: number; lufs: number; segment_lufs_before: number[]; segment_lufs_after: number[]; cards: number };
  };
}

export interface StoriesView {
  stories: Story[];
  reason: null | "too_few_moments" | "too_short" | "no_arc";
  none_reason?: string | null;
  good: number | null;
  created_at: string | null;
  source: "ai" | "rules" | null;
  llm: boolean;
  job: Job | null;
  limits: { min: number; max: number };
}

export type HookStyle = "flash" | "question" | "cold_open" | "statement";

export interface HookReason {
  code: string;
  points: number;
  value: number | string | null;
}

export interface HookVariant {
  style: HookStyle;
  hook_text: string;
  hook_flash: boolean;
  start: number;
  file: string;
  score: number;
  reasons: HookReason[];
  judge: { score: number; why: string } | null;
  rendered_at: string;
  duration: number;
}

export type RealTestReason = null | "not_connected" | "locked_private" | "no_analytics";

export interface HookTest {
  variants: Record<"A" | "B", HookVariant>;
  winner: "A" | "B";
  margin: number;
  created_at: string;
  stale: boolean;
  files_ok: boolean;
  upload_pick: { label: "A" | "B" | null; how: "bandit" | "pretest" | null };
  uploaded: null | { video_id: string; variant: "A" | "B" | null; style: HookStyle | null; url: string };
}

export interface HookTests {
  clips: Record<string, HookTest>;
  real_test: { active: boolean; reason: RealTestReason };
}

export interface HookStyleStats {
  style: HookStyle;
  n: number;
  mean_reward: number;
  ci90: [number, number];
  mean_retention: number | null;
  median_views: number | null;
  p_best: number;
}

export interface HookStats {
  styles: HookStyleStats[];
  observations: number;
  verdict: null | { style: HookStyle; confidence: number };
  min_samples: number;
  reward_cap: number;
  real_test: { active: boolean; reason: RealTestReason };
  youtube: { connected: boolean; analytics: boolean; locked: null | { at: string; video_id: string } };
  min_age_hours: number;
}

// ------------------------------------------------------------------ publishing (1.2.7)

export type CoverKind = "peak" | "action" | "face" | "ai" | "custom" | "none";

export interface PublishMeta {
  title: string;
  description: string;
  hashtags: string[];
  tags: string[];
  category: string;
  language: string | null;
  made_for_kids: boolean;
  privacy: Privacy;
  playlist: { id: string; title: string } | null;
  cover: { kind: CoverKind; text: string; burn: boolean };
  preset: PresetId;
  format: FormatId;
  burn_captions: boolean;
  source: "auto" | "export";
  /** 1.2.19: a dubbed clip adds "this voice is AI-generated" to the description */
  ai_voice_note: boolean;
  /** 1.2.19: a dubbed clip sets YouTube's altered / synthetic content flag */
  synthetic_media: boolean;
}

export type LibStatus = "draft" | "scheduled" | "published" | "failed" | "locked";
export type LibStep =
  | null
  | "uploaded"
  | "waiting"
  | "retrying"
  | "rendering"
  | "uploading"
  | "queued_rendering"
  | "queued_uploading"
  | "attention"
  | "checking";
export type PublishFix = "retry" | "reconnect" | "edit" | "rerender" | "reschedule" | "wait";

export interface LibraryRow {
  key: string;
  project_id: string;
  project_title: string;
  clip_id: string;
  rank: number;
  title: string;
  duration: number;
  viral_score: number | null;
  viral_label: string | null;
  accepted: boolean;
  rendered: boolean;
  status: LibStatus;
  step: LibStep;
  date: string | null;
  planned: boolean;
  publish_at: string | null;
  now: boolean;
  moved_from: string | null;
  error: { message: string; hint: string | null; fix: PublishFix; at: string } | null;
  next_try_at: string | null;
  upload: {
    video_id: string;
    url: string;
    privacy: Privacy;
    requested_privacy?: Privacy;
    publish_at: string | null;
    published_at?: string | null;
    uploaded_at: string;
    views?: number;
    likes?: number | null;
    stats_at?: string;
    thumbnail_error?: string | null;
    playlist_error?: string | null;
  } | null;
  job: { kind: string; stage: string | null; progress: number | null; paused: string | null } | null;
}

export interface PublishSettings {
  daily_limit: number;
  effective_limit: number;
  quota_capacity: number;
  times: string[];
  best_times: { times: string[]; source: "learned" | "default" | "custom"; samples: number; configured: string[] };
  learn_times: boolean;
  auto: boolean;
  quota: YoutubeQuota;
}

export interface LibraryView extends PublishSettings {
  rows: LibraryRow[];
  counts: Partial<Record<LibStatus, number>>;
  now: string;
  youtube: {
    connected: boolean;
    manage: boolean;
    client: boolean;
    channel: YoutubeStatus["channel"];
    lock: YoutubeLock;
  };
}

export interface PublishSetup {
  key: string;
  meta: PublishMeta;
  item: null | { publish_at: string | null; now: boolean; video_id: string | null; attention: boolean };
  ai: {
    titles: string[];
    description: string;
    hashtags: string[];
    tags: string[];
    cover_text: string | null;
    cover_prompt: string | null;
    available: boolean;
  };
  clip: { rank: number; duration: number; text: string; viral_score: number | null; has_facecam: boolean; has_custom_thumb: boolean };
  presets: { id: PresetId; label: string; frame: "vertical" | "wide"; max_seconds: number | null }[];
  warnings: ExportWarning[];
  categories: string[];
  ab: null | { labels: string[]; styles: Record<string, HookStyle>; pick: { label: string | null; how: string | null } };
  upload: LibraryRow["upload"];
  youtube: { connected: boolean; manage: boolean; channel: YoutubeStatus["channel"]; lock: YoutubeLock };
  limits: PublishSettings;
  ai_voice: { dub: string; line: string | null; note: boolean; synthetic: boolean };
}

export interface CoverInfo {
  /** t = source time, at = seconds into the clip */
  face: null | { t: number; at?: number; score: number; reasons: string[]; faces: number };
  moments: { peak: number; action: number };
  custom: boolean;
}

export interface Playlist {
  id: string;
  title: string;
  privacy: Privacy | null;
  count: number | null;
}

export interface ScheduleResult {
  planned: { key: string; publish_at: string; moved: boolean }[];
  skipped: { key: string; reason: "missing" | "on_youtube" | "uploading" | "no_time" }[];
}

export interface UploadBody {
  source: string; // "clip" or an export file name
  title: string;
  description: string;
  tags: string[];
  privacy: Privacy;
  publish_at: string | null;
  made_for_kids: boolean;
  thumbnail: "none" | "auto" | "custom";
  language?: string | null;
  /** an A/B variant upload ("ab:A" source): how it was chosen */
  ab_how?: "bandit" | "pretest" | "manual";
  /** 1.2.19, dubbed files: false = no AI-voice line in the description / no synthetic flag */
  ai_voice_note?: boolean;
  synthetic_media?: boolean;
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
  /** a machine-readable reason (e.g. "not_connected") when the server sends one */
  code: string | null;
  constructor(message: string, hint: string | null, status: number, code: string | null = null) {
    super(message);
    this.hint = hint;
    this.status = status;
    this.code = code;
  }
}

// Heavy jobs (GPU / long CPU work). While an update is being built ("under construction"
// banner), starting one asks first; DevBanner registers the dialog.
const HEAVY: [string, RegExp][] = [
  ["POST", /^\/api\/(easy\/)?projects$/],
  ["POST", /\/(transcribe|highlights|analyze|render|montage|export)$/],
  ["POST", /\/game\/rescan$/],
  ["PUT", /\/game$/],
  ["PUT", /\/metadata-game$/],
  ["POST", /^\/api\/(llm\/benchmark|queue\/render|update|music\/analyze)$/],
  ["POST", /\/candidates$/],
  ["PUT", /^\/api\/uploads/],
  ["POST", /\/(ai-covers|dub)$/],
  ["POST", /^\/api\/platforms\/(tiktok|reels)\/clips\//],
];
let heavyGuard: (() => Promise<void>) | null = null;
export function setHeavyGuard(guard: (() => Promise<void>) | null) {
  heavyGuard = guard;
}
async function guardHeavy(method: string, path: string) {
  const p = path.split("?")[0];
  if (heavyGuard && HEAVY.some(([m, re]) => m === method && re.test(p))) await heavyGuard();
}

/** Fired when the server says this device has to log in (LAN access PIN). */
export const AUTH_EVENT = "sharkyclips-auth-required";

export interface AuthStatus {
  enabled: boolean;
  kind: "pin" | "password" | null;
  is_local: boolean;
  required: boolean;
  authenticated: boolean;
  lan: boolean;
}

async function authLogin(secret: string): Promise<{ ok: boolean; code?: string; retry_after?: number | null }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret }),
  });
  if (res.ok) return { ok: true };
  const data = await res.json().catch(() => ({}));
  return { ok: false, code: data.code, retry_after: data.retry_after ?? null };
}

export async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  await guardHeavy(method, path);
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    let hint: string | null = null;
    let code: string | null = null;
    try {
      const data = await res.json();
      msg = data.error || data.detail || msg;
      hint = data.hint || null;
      code = typeof data.code === "string" ? data.code : null;
      if (res.status === 401 && data.code === "auth_required") window.dispatchEvent(new Event(AUTH_EVENT));
    } catch {
      /* not JSON */
    }
    throw new ApiError(msg, hint, res.status, code);
  }
  return res.json() as Promise<T>;
}

const P = (id: string) => `/api/projects/${encodeURIComponent(id)}`;
const L = (pid: string, cid: string) => `/api/library/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;

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
  /** Google ended the YouTube sign-in: reconnect banner on every screen */
  youtube_signed_out: YoutubeSignedOut | null;
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
  authStatus: () => req<AuthStatus>("GET", "/api/auth/status"),
  authLogin,
  authSetSecret: (secret: string) => req<AuthStatus>("PUT", "/api/auth/secret", { secret }),
  authClearSecret: () => req<AuthStatus>("DELETE", "/api/auth/secret"),
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
  detectFacecam: (id: string, fresh = false) => req<Job>("POST", `${P(id)}/facecam/detect`, { fresh }),
  facecamAnalysis: (id: string) => req<FacecamAnalysis>("GET", `${P(id)}/facecam/analysis`),
  setFacecam: (id: string, facecam: Facecam | null, opts: { remember?: boolean; forget?: boolean } = {}) =>
    req<Review>("PUT", `${P(id)}/facecam`, { facecam, ...opts }),
  voices: (id: string) => req<VoicesView>("GET", `${P(id)}/voices`),
  runVoices: (id: string, whole = false) => req<Job>("POST", `${P(id)}/voices/run`, { whole }),
  setTrackLabels: (id: string, labels: TrackLabel[]) => req<VoicesView>("PUT", `${P(id)}/voices/tracks`, { labels }),
  setSpeakerNames: (id: string, names: Record<string, string>) =>
    req<VoicesView>("PUT", `${P(id)}/voices/names`, { names }),
  mergeSpeakers: (id: string, from: string, into: string) =>
    req<VoicesView>("PUT", `${P(id)}/voices/merge`, { from, into }),
  proofread: (id: string, force = false) => req<Job>("POST", `${P(id)}/proofread`, { force }),
  peaks: (id: string, start: number, end: number, n = 400) =>
    req<{ start: number; end: number; peaks: number[] }>("GET", `${P(id)}/peaks?start=${start}&end=${end}&n=${n}`),
  bleepState: () => req<{ custom: boolean; size: number }>("GET", "/api/bleep"),
  deleteBleep: () => req<{ custom: boolean; size: number }>("DELETE", "/api/bleep/custom"),
  uploadBleep: async (file: File) => {
    const res = await fetch("/api/bleep/custom", { method: "PUT", body: file });
    if (!res.ok) {
      let msg = res.statusText;
      try {
        msg = (await res.json()).error || msg;
      } catch {
        /* not JSON */
      }
      throw new ApiError(msg, null, res.status);
    }
    return (await res.json()) as { custom: boolean; size: number };
  },
  render: (id: string, clip_ids: string[], options: ClipOptions, hooks: Record<string, string>) =>
    req<{ jobs: Job[] }>("POST", `${P(id)}/render`, { clip_ids, options, hooks }),
  regeneratePublish: (id: string, cid: string) => req<Job>("POST", `${P(id)}/candidates/${cid}/publish`),
  analyze: (id: string, lang?: string, force = false) => req<Job>("POST", `${P(id)}/analyze`, { lang, force }),
  analyzeMeta: (id: string) => req<Job>("POST", `${P(id)}/analyze`, { meta_only: true }),
  setMetadataGame: (id: string, choice: string, rerun = true) =>
    req<{ metadata_game: MetadataGame; job: Job | null }>("PUT", `${P(id)}/metadata-game`, { choice, rerun }),
  voteTitle: (id: string, cid: string, text: string, vote: -1 | 0 | 1) =>
    req<{ text: string; vote: number }>("POST", `${P(id)}/candidates/${cid}/titles/vote`, { text, vote }),
  llm: () => req<LlmInfo>("GET", "/api/llm"),
  importChat: async (id: string, file: File) => {
    const res = await fetch(`${P(id)}/chat?filename=${encodeURIComponent(file.name)}`, { method: "PUT", body: file });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || res.statusText, data.hint || null, res.status);
    return data as NonNullable<ProjectDetail["chat"]>;
  },
  exportOptions: () => req<ExportOptions>("GET", "/api/export/options"),
  exportEstimate: (id: string, body: { clip_ids: string[]; format: FormatId | null; preset: PresetId | null; gif_max_mb?: number }) =>
    req<ExportEstimate>("POST", `${P(id)}/export/estimate`, body),
  exportClips: (id: string, body: ExportRequest & { clip_ids: string[] }) => req<{ jobs: Job[] }>("POST", `${P(id)}/export`, body),
  clipExports: (id: string) => req<ClipExport[]>("GET", `${P(id)}/clip-exports`),
  deleteClipExport: (id: string, exportId: string) =>
    req<{ removed: boolean }>("DELETE", `${P(id)}/clip-exports/${encodeURIComponent(exportId)}`),
  youtube: () => req<YoutubeStatus>("GET", "/api/youtube"),
  youtubeClient: async (body: File | string) => {
    const res = await fetch("/api/youtube/client", { method: "PUT", body });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || data.detail || res.statusText, data.hint || null, res.status);
    return data as YoutubeStatus;
  },
  /** Validate a client JSON without saving it. A server that can't check (an older process still
   * running after an update answers 405) gives reason "unchecked": saving still decides. */
  youtubeClientCheck: async (text: string) => {
    type Check = { ok: boolean; error?: string; hint?: string | null; reason?: string | null; project_id?: string | null };
    const res = await fetch("/api/youtube/client/check", { method: "POST", body: text });
    const data = (await res.json().catch(() => null)) as Check | null;
    if (!res.ok || !data || typeof data.ok !== "boolean") return { ok: false, reason: "unchecked" } as Check;
    return data;
  },
  youtubeRemoveClient: () => req<YoutubeStatus>("DELETE", "/api/youtube/client"),
  youtubeConnect: (open = true) => req<{ id: string; url: string; opened: boolean; port: number }>("POST", "/api/youtube/connect", { open }),
  youtubeConnectState: (id: string) => req<ConnectFlow>("GET", `/api/youtube/connect/${encodeURIComponent(id)}`),
  youtubeConnectCancel: (id: string) => req<ConnectFlow>("DELETE", `/api/youtube/connect/${encodeURIComponent(id)}`),
  youtubeChannel: (id: string) => req<YoutubeStatus>("POST", "/api/youtube/channel", { id }),
  youtubeRecheck: () => req<YoutubeStatus>("POST", "/api/youtube/recheck"),
  youtubeDismissSignedOut: () => req<YoutubeStatus>("POST", "/api/youtube/signed-out/dismiss"),
  youtubeDisconnect: () => req<YoutubeStatus>("POST", "/api/youtube/disconnect"),
  youtubeStats: () => req<Job>("POST", "/api/youtube/stats"),
  uploads: (id: string) => req<Record<string, YoutubeUpload[]>>("GET", `${P(id)}/uploads`),
  uploadClip: (id: string, cid: string, body: UploadBody) => req<Job>("POST", `${P(id)}/clips/${cid}/upload`, body),
  uploadThumbnail: async (id: string, cid: string, file: File) => {
    const res = await fetch(`${P(id)}/clips/${cid}/thumbnail`, { method: "PUT", body: file });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || data.detail || res.statusText, data.hint || null, res.status);
    return data as { ok: boolean };
  },
  cancelJob: (jobId: string) => req<Job>("POST", `/api/jobs/${jobId}/cancel`),
  moveJob: (jobId: string, to: number) => req<Job>("POST", `/api/jobs/${jobId}/move`, { to }),
  retryJob: (jobId: string) => req<Job>("POST", `/api/jobs/${jobId}/retry`),
  forgetJob: (jobId: string) => req<{ removed: boolean }>("DELETE", `/api/jobs/${jobId}`),
  queue: () => req<QueueView>("GET", "/api/queue"),
  queuePause: (paused: boolean) => req<{ paused: boolean }>("POST", "/api/queue/pause", { paused }),
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
  // editing tools (1.2.4)
  plan: (id: string, cid: string, body: { options?: Partial<ClipOptions>; edit?: ClipEdit; music?: string | null } = {}) =>
    req<EditPlanView>("POST", `${P(id)}/candidates/${encodeURIComponent(cid)}/plan`, body),
  addManualClip: (id: string, start: number, end: number) =>
    req<{ candidate: Candidate; job: Job | null }>("POST", `${P(id)}/candidates`, { start, end }),
  deleteManualClip: (id: string, cid: string) =>
    req<{ removed: boolean }>("DELETE", `${P(id)}/candidates/${encodeURIComponent(cid)}`),
  music: () => req<MusicLibrary>("GET", "/api/music"),
  musicSettings: (body: { credit_template?: string; credit_enabled?: boolean }) =>
    req<MusicLibrary>("PUT", "/api/music/settings", body),
  updateTrack: (name: string, body: { moods?: Mood[]; title?: string; artist?: string }) =>
    req<MusicTrack>("PUT", `/api/music/${encodeURIComponent(name)}`, body),
  deleteTrack: (name: string) => req<{ removed: boolean }>("DELETE", `/api/music/${encodeURIComponent(name)}`),
  analyzeMusic: () => req<Job>("POST", "/api/music/analyze"),
  openMusicFolder: () => req<{ ok: boolean; folder: string }>("POST", "/api/music/open"),
  uploadTrack: async (file: File) => {
    const res = await fetch(`/api/music/upload?filename=${encodeURIComponent(file.name)}`, { method: "PUT", body: file });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || data.detail || res.statusText, data.hint || null, res.status);
    return data as MusicTrack;
  },
  brand: () => req<BrandState>("GET", "/api/brand"),
  channelText: () => req<ChannelText>("GET", "/api/brand/channel"),
  saveChannelText: (d: Partial<Pick<ChannelText, "hashtags" | "names">> & { socials?: Partial<ChannelText["socials"]> }) =>
    req<ChannelText>("PUT", "/api/brand/channel", d),
  myStyle: () => req<StyleState>("GET", "/api/brand/style"),
  saveMyStyle: (d: { profile?: Partial<StyleProfile>; glossary?: Partial<StyleGlossary> }) =>
    req<StyleState>("PUT", "/api/brand/style", d),
  startMyStyle: () => req<StyleState>("POST", "/api/brand/style/sample"),
  longMetadata: (id: string) => req<{ long_metadata: LongMetadata | null }>("GET", `${P(id)}/long-metadata`),
  makeLongMetadata: (id: string, force = false) => req<Job>("POST", `${P(id)}/long-metadata`, { force }),
  gameBanks: () => req<{ games: GameBank[] }>("GET", "/api/studio/games"),
  saveGameBank: (gid: string, bank: Record<string, unknown>) =>
    req<GameBank>("PUT", `/api/studio/games/${encodeURIComponent(gid)}`, { bank }),
  resetGameBank: (gid: string) => req<{ games: GameBank[] }>("DELETE", `/api/studio/games/${encodeURIComponent(gid)}`),
  saveBrand: (presets: Partial<BrandPreset>[], active: string | null) =>
    req<BrandState>("PUT", "/api/brand", { presets, active }),
  uploadLogo: async (pid: string, file: File) => {
    const res = await fetch(`/api/brand/${encodeURIComponent(pid)}/logo?filename=${encodeURIComponent(file.name)}`, {
      method: "PUT",
      body: file,
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.error || data.detail || res.statusText, data.hint || null, res.status);
    return data as BrandState;
  },
  removeLogo: (pid: string) => req<BrandState>("DELETE", `/api/brand/${encodeURIComponent(pid)}/logo`),
  wordLists: () => req<WordLists>("GET", "/api/wordlists"),
  saveWordLists: (body: {
    profanity?: Record<string, string[] | null>;
    fillers?: Record<string, { sure: string[]; maybe: string[] } | null>;
    silence_ms?: Partial<{ light: number; strong: number }>;
  }) => req<WordLists>("PUT", "/api/wordlists", body),
  forgetLearned: (lang: string, word: string, kind: "add" | "ignore") =>
    req<WordLists>("DELETE", `/api/wordlists/learned?lang=${encodeURIComponent(lang)}&word=${encodeURIComponent(word)}&kind=${kind}`),
  swearScan: (id: string) => req<SwearScanView>("GET", `${P(id)}/swearscan`),
  runSwearScan: (id: string, findAll = false) => req<Job>("POST", `${P(id)}/swearscan/run`, { find_all: findAll }),
  swearLabels: (id: string) => req<SwearLabels>("GET", `${P(id)}/swearscan/labels`),
  setSwearLabel: (id: string, key: string, label: "yes" | "no" | "unsure" | null, note?: string) =>
    req<SwearLabels>("PUT", `${P(id)}/swearscan/labels`, { key, label, note }),
  jobs: () => req<Job[]>("GET", "/api/jobs"),
  // stories, A/B hooks (1.2.5)
  stories: (id: string) => req<StoriesView>("GET", `${P(id)}/stories`),
  proposeStories: (id: string, lang?: string) => req<Job>("POST", `${P(id)}/stories`, { lang }),
  updateStory: (id: string, sid: string, body: { segments?: (string | { cid: string; card?: string })[]; cards?: boolean; title?: string }) =>
    req<Story>("PUT", `${P(id)}/stories/${sid}`, body),
  deleteStory: (id: string, sid: string) => req<{ removed: boolean }>("DELETE", `${P(id)}/stories/${sid}`),
  renderStory: (id: string, sid: string) => req<Job>("POST", `${P(id)}/stories/${sid}/render`),
  hookTests: (id: string) => req<HookTests>("GET", `${P(id)}/ab`),
  makeHookTest: (id: string, cid: string) => req<Job>("POST", `${P(id)}/clips/${cid}/ab`),
  // publishing (1.2.7)
  library: () => req<LibraryView>("GET", "/api/library"),
  libraryTick: () => req<{ actions: string[] }>("POST", "/api/library/tick"),
  publishSettings: () => req<PublishSettings>("GET", "/api/library/settings"),
  savePublishSettings: (body: Partial<{ daily_limit: number; times: string[]; learn_times: boolean; auto: boolean }>) =>
    req<PublishSettings>("PUT", "/api/library/settings", body),
  publishSetup: (pid: string, cid: string) => req<PublishSetup>("GET", `${L(pid, cid)}/setup`),
  savePublish: (pid: string, cid: string, meta: PublishMeta) =>
    req<{ ok: boolean; applied: "youtube" | null; meta: PublishMeta }>("PUT", L(pid, cid), { meta }),
  forgetPublish: (pid: string, cid: string) => req<{ ok: boolean }>("DELETE", L(pid, cid)),
  schedule: (body: { clips: { project_id: string; clip_id: string; publish_at?: string }[]; mode: "auto" | "manual"; dry_run?: boolean }) =>
    req<ScheduleResult>("POST", "/api/library/schedule", body),
  reschedule: (pid: string, cid: string, publish_at: string, strict = true) =>
    req<{ publish_at: string; moved: boolean }>("POST", `${L(pid, cid)}/reschedule`, { publish_at, strict }),
  publishNow: (pid: string, cid: string) => req<{ ok: boolean; queued?: boolean; privacy?: Privacy }>("POST", `${L(pid, cid)}/publish-now`),
  cancelPublish: (pid: string, cid: string) => req<{ ok: boolean; deleted: boolean }>("POST", `${L(pid, cid)}/cancel`),
  retryPublish: (pid: string, cid: string) => req<{ ok: boolean; publish_at: string | null }>("POST", `${L(pid, cid)}/retry`),
  covers: (pid: string, cid: string) => req<CoverInfo>("GET", `${L(pid, cid)}/covers`),
  playlists: (refresh = false) => req<{ items: Playlist[]; connected: boolean }>("GET", `/api/youtube/playlists${refresh ? "?refresh=true" : ""}`),
  createPlaylist: (title: string) => req<Playlist>("POST", "/api/youtube/playlists", { title }),
  verificationGuide: () => req<{ markdown: string; url: string }>("GET", "/api/youtube/verification"),
  deleteHookTest: (id: string, cid: string) => req<{ removed: boolean }>("DELETE", `${P(id)}/clips/${cid}/ab`),
  hookStats: () => req<HookStats>("GET", "/api/hooks"),
  fetchHookStats: () => req<Job>("POST", "/api/hooks/fetch"),
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
  clipExportFile: (id: string, name: string, download = false) =>
    `${P(id)}/clip-exports/file/${encodeURIComponent(name)}${download ? "?download=true" : ""}`,
  thumbnail: (id: string, cid: string, kind: "auto" | "custom", v = 0) => `${P(id)}/clips/${cid}/thumbnail.jpg?kind=${kind}&v=${v}`,
  story: (id: string, sid: string, stamp: string, download = false) =>
    `${P(id)}/stories/${sid}/video?v=${encodeURIComponent(stamp)}${download ? "&download=true" : ""}`,
  hookVariant: (id: string, cid: string, label: string, stamp: string, download = false) =>
    `${P(id)}/clips/${cid}/ab/${label}/video?v=${encodeURIComponent(stamp)}${download ? "&download=true" : ""}`,
  musicAudio: (name: string) => `/api/music/${encodeURIComponent(name)}/audio`,
  bleepPreview: (sound: BleepSound, v = 0) => `/api/bleep/preview?sound=${sound}&v=${v}`,
  facecamFrame: (id: string, v = "") => `${P(id)}/facecam/frame.jpg?v=${encodeURIComponent(v)}`,
  brandLogo: (pid: string, rev = 0) => `/api/brand/${encodeURIComponent(pid)}/logo?v=${rev}`,
  cover: (pid: string, cid: string, kind: CoverKind, frame: "wide" | "tall", text: string, lang: string | null, v = 0) =>
    `${L(pid, cid)}/cover.jpg?${new URLSearchParams({ kind, frame, text, ...(lang ? { lang } : {}), v: String(v) })}`,
  clipThumb: (pid: string, cid: string) => `${P(pid)}/clips/${encodeURIComponent(cid)}/thumbnail.jpg?kind=auto`,
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

// ---------------------------------------------------------------- Easy mode (1.2.16, web/easy.py)

export type UiMode = "easy" | "pro";
export type UploadWhen = "now" | "auto";

export interface EasySettings {
  mode: UiMode;
  tour_done: boolean;
  upload_when: UploadWhen;
  open_folder: boolean;
  downloads: string;
  /** 1.2.17: fun effects for new clips + auto clips after a stream */
  replay: boolean;
  bubbles: boolean;
  memes: MemeLevel;
  auto_clip: boolean;
  /** 1.2.18: the upload button's platform, remembered */
  platform: "youtube" | "tiktok" | "reels";
  study_cards: "off" | "auto";
  visualizer: "off" | "auto";
  /** 1.2.21 "Check swears strictly": auto (= Strict for vertical clips) or normal */
  swear_strict: "auto" | "normal";
}

// ---------------------------------------------------------------- automation + live (1.2.17)

export type WatchPublish = "off" | "plan" | "now";

export interface WatchRecent {
  path: string;
  name: string;
  status: "ready" | "importing" | "imported" | "skipped" | "error";
  reason?: "too_small" | "too_short" | "remuxed";
  project_id?: string;
  markers?: number;
  error?: string;
  at: number;
}

export interface LiveMarker {
  id: string;
  at: number;
  source: "hotkey" | "chat" | "button";
  by?: string;
  note?: string;
  rec_ms?: number;
}

export interface LiveView {
  watch: {
    enabled: boolean;
    folders: string[];
    custom_folders: boolean;
    detected: string | null;
    render_top: number;
    publish: WatchPublish;
    publish_top: number;
    min_minutes: number;
    recent: WatchRecent[];
  };
  markers: {
    hotkey: string;
    hotkey_enabled: boolean;
    command: string;
    twitch_channel: string;
    youtube_chat: boolean;
    obs_websocket: "auto" | "off";
    recent: LiveMarker[];
    hotkey_supported: boolean;
  };
  obs: { found: boolean; record_dir: string | null; format: string | null; websocket: { enabled: boolean; port: number } | null };
  service: {
    hotkey: "off" | "on" | "taken" | "unsupported" | "invalid";
    twitch: { status: string; error: string | null; channel: string } | null;
    youtube: { status: string; error: string | null } | null;
    last_scan: number | null;
    error: string | null;
  };
}

export const liveApi = {
  get: () => req<LiveView>("GET", "/api/live"),
  watch: (body: Partial<{ enabled: boolean; folders: string[]; render_top: number; publish: WatchPublish; publish_top: number; min_minutes: number }>) =>
    req<LiveView>("PUT", "/api/live/watch", body),
  scan: () => req<{ started: string[]; recent: WatchRecent[] }>("POST", "/api/live/watch/scan"),
  obsCheck: () => req<{ ok: boolean; reason?: "not_enabled" | "no_websocket" | "password" | "not_running"; obs?: string }>("GET", "/api/live/obs/check"),
  markers: (body: Partial<{ hotkey: string; hotkey_enabled: boolean; command: string; twitch_channel: string; youtube_chat: boolean; obs_websocket: "auto" | "off" }>) =>
    req<LiveView>("PUT", "/api/live/markers", body),
  mark: () => req<{ marker: LiveMarker | null; recent: LiveMarker[] }>("POST", "/api/live/markers", { source: "button" }),
  unmark: (id: string) => req<{ recent: LiveMarker[] }>("DELETE", `/api/live/markers/${encodeURIComponent(id)}`),
};

// ---------------------------------------------------------------- phone approval (1.2.17)

export interface PhoneStatus {
  configured: boolean;
  paired: boolean;
  bot: string | null;
  chat: string | null;
  link: string | null;
  send: boolean;
  send_top: number;
}

export interface LanView {
  enabled: boolean;
  active: boolean;
  pin: boolean;
  url: string | null;
  approve_url: string | null;
  busy: boolean;
}

export interface ApproveClip {
  project_id: string;
  project_title: string;
  clip_id: string;
  title: string;
  viral_score: number | null;
  viral_label: string | null;
  duration: number | null;
  marked: boolean;
  video: string;
}

export interface ActResult {
  status: "uploading" | "scheduled" | "published" | "skipped";
  text: string;
  publish_at?: string;
  clips: ApproveClip[];
}

export interface PhoneView extends PhoneStatus {
  lan: LanView;
  poller: { status: string; error: string | null } | null;
}

export const phoneApi = {
  get: () => req<PhoneView>("GET", "/api/phone"),
  tgToken: (token: string) => req<PhoneStatus>("POST", "/api/phone/telegram", { token }),
  tgPair: () => req<PhoneStatus>("POST", "/api/phone/telegram/pair"),
  tgDisconnect: () => req<PhoneStatus>("DELETE", "/api/phone/telegram"),
  tgTest: () => req<{ ok: boolean }>("POST", "/api/phone/test"),
  set: (body: Partial<{ send: boolean; send_top: number; lan: boolean }>) => req<PhoneView>("PUT", "/api/phone", body),
  restart: () => req<{ restarting: boolean }>("POST", "/api/update/restart"),
  approve: () => req<{ clips: ApproveClip[]; youtube: boolean }>("GET", "/api/approve"),
  act: (pid: string, cid: string, action: "upload" | "plan" | "skip") =>
    req<ActResult>("POST", `/api/approve/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`, { action }),
};

export type EasyStepKey = "download" | "transcribe" | "find" | "titles" | "render";

export interface EasyStep {
  key: EasyStepKey;
  status: "done" | "active" | "todo";
  progress: number | null;
}

export interface EasyClip {
  id: string;
  rank: number;
  title: string;
  titles: string[];
  text: string;
  viral_score: number | null;
  viral_label: "very_high" | "high" | "medium" | "low" | null;
  start: number;
  end: number;
  duration: number;
  found: { start: number; end: number };
  bounds: { start: number; end: number };
  prefs: { title: string | null; subtitles: boolean; music: boolean };
  render: {
    status: "ready" | "waiting" | "queued" | "rendering" | "error";
    progress: number | null;
    stamp: string | null;
    has_video: boolean;
    error: string | null;
  };
  upload: {
    status: LibStatus;
    step: string | null;
    date: string | null;
    url: string | null;
    views: number | null;
    publish_at: string | null;
    progress: number | null;
    error: { message: string; hint: string | null } | null;
  };
  /** 1.2.18: TikTok / Reels posts of this clip */
  platforms?: Record<"tiktok" | "reels", PlatformClipState>;
}

export interface PlatformClipState {
  status: "exporting" | "uploading" | "exported" | "published" | "processing" | "error" | null;
  mode: "semi" | "api" | null;
  file: string | null;
  url: string | null;
  privacy: string | null;
  error: { message: string; hint: string | null } | null;
  progress: number | null;
  job: string | null;
  /** 1.2.20: the last export of a dubbed clip (label = AI label set / reminder wanted) */
  ai_voice?: { dub: string; line: string | null; note: boolean; label: boolean } | null;
}

export interface EasyView {
  id: string;
  title: string;
  mode: Mode;
  mode_auto: boolean;
  duration: number;
  easy: boolean;
  state: "working" | "ready" | "error" | "empty";
  steps: EasyStep[];
  eta_seconds: number | null;
  error: { kind: string; message: string; hint: string | null } | null;
  clips: EasyClip[];
  total: number;
  shown: number;
  music_available: boolean;
  youtube: { connected: boolean; lock: "locked" | "unlocked" | "unknown"; channel: { title: string } | null };
  settings: EasySettings;
  daily_limit: number;
}

export interface EasyProjectRow {
  id: string;
  title: string;
  created_at: string | null;
  duration: number | null;
  mode: Mode | null;
  easy: boolean;
  clips: number;
  busy: boolean;
}

export interface EasyUploadResult {
  status: "uploading" | "scheduled" | "published" | "error";
  publish_at?: string | null;
  url?: string | null;
  today_full?: boolean;
  error?: string;
}

export interface EasyDownload {
  folder: string;
  files: string[];
  count?: number;
  zip?: string | null;
  opened?: boolean;
  cover_error?: string | null;
}

export interface EasyLibRow {
  key: string;
  project_id: string;
  project_title: string;
  clip_id: string;
  title: string;
  duration: number;
  viral_label: string | null;
  status: LibStatus;
  step: string | null;
  date: string | null;
  publish_at: string | null;
  url: string | null;
  views: number | null;
  error: { message: string; hint: string | null } | null;
  job: { kind: string; stage: string | null; progress: number | null } | null;
}

const EZ = (pid: string, cid: string) => `/api/easy/clips/${encodeURIComponent(pid)}/${encodeURIComponent(cid)}`;
const EP = (pid: string) => `/api/easy/projects/${encodeURIComponent(pid)}`;

export const easyApi = {
  settings: () => req<EasySettings>("GET", "/api/easy/settings"),
  saveSettings: (s: Partial<Omit<EasySettings, "downloads">>) => req<EasySettings>("PUT", "/api/easy/settings", s),
  create: (body: { url?: string; path?: string; mode: Mode | "auto"; language: string }) =>
    req<Job>("POST", "/api/easy/projects", body),
  projects: () => req<EasyProjectRow[]>("GET", "/api/easy/projects"),
  view: (pid: string) => req<EasyView>("GET", EP(pid)),
  prepare: (pid: string) => req<EasyView & { queued: string[] }>("POST", `${EP(pid)}/prepare`),
  more: (pid: string) => req<EasyView>("POST", `${EP(pid)}/more`),
  setMode: (pid: string, mode: Mode) => req<EasyView>("POST", `${EP(pid)}/mode`, { mode }),
  retry: (pid: string) => req<EasyView>("POST", `${EP(pid)}/retry`),
  edit: (pid: string, cid: string, body: { title?: string; subtitles?: boolean; music?: boolean; start?: number; end?: number }) =>
    req<EasyView>("POST", `${EZ(pid, cid)}/edit`, body),
  discard: (pid: string, cid: string) => req<EasyView>("POST", `${EZ(pid, cid)}/discard`),
  upload: (pid: string, cid: string, when: UploadWhen) => req<EasyUploadResult>("POST", `${EZ(pid, cid)}/upload`, { when }),
  uploadMany: (clips: { project_id: string; clip_id: string }[], when: UploadWhen) =>
    req<{ results: (EasyUploadResult & { project_id: string; clip_id: string })[] }>("POST", "/api/easy/upload", { clips, when }),
  download: (pid: string, cid: string) => req<EasyDownload>("POST", `${EZ(pid, cid)}/download`),
  downloadAll: (pid: string, zip: boolean) => req<EasyDownload>("POST", `${EP(pid)}/download`, { zip }),
  library: () => req<{ tabs: { ready: EasyLibRow[]; planned: EasyLibRow[]; live: EasyLibRow[] }; youtube: { connected: boolean } }>("GET", "/api/easy/library"),
};

/** An upload with progress for Easy mode (mode "auto" = detect the content type). */
export function uploadEasyFile(
  file: File,
  mode: Mode | "auto",
  onProgress: (fraction: number) => void,
): { promise: Promise<Job>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const q = new URLSearchParams({ filename: file.name, mode, language: "auto", easy: "true" });
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
