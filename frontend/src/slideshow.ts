// 1.2.72 Photo slideshow: 2-20 photos -> one 9:16 video (backend/sharkyclips/slideshow.py).
import { ApiError, req, type Job } from "./api";

export type Transition = "crossfade" | "slide" | "zoom";

export interface SlidePhoto {
  id: string;
  name: string | null;
  width: number | null;
  height: number | null;
  taken_at: string | null;
  date_source: "exif" | "file" | null;
  /** the user's own text ("" = none) */
  text: string;
  /** what the video shows on it (own text, else the label when Labels is on), already in caps */
  shown_text: string;
  /** the Before / Progress / Result word for this place */
  label: string;
  start: number;
  shape: "portrait" | "landscape" | "square";
}

export interface SlideSettings {
  seconds: number;
  transition: Transition;
  labels: boolean;
  outro: boolean;
  order_mode: "date" | "manual";
  subject: string;
}

export interface SlideshowView {
  id: string;
  title: string;
  created_at: string | null;
  language: string;
  settings: SlideSettings;
  photos: SlidePhoto[];
  removed: { id: string; name: string | null }[];
  timeline: { seconds: number; xfade: number; photos_s: number; outro_at: number | null; total: number };
  limits: { min_photos: number; max_photos: number; seconds: [number, number]; text_max: number; outro_s: number; exts: string[]; max_bytes: number };
  transitions: Transition[];
  labels_words: [string, string, string];
  ready: boolean;
  preview: { stamp: string | null; fresh: boolean } | null;
  export: { stamp: number | null; size_bytes: number; duration: number; encoder: string | null; fresh: boolean; folder: string | null } | null;
  package: { titles: string[]; description: string; hashtags: string[]; language: string };
  share: { kind: string; shared: { platform: string; url: string | null }[] } | null;
  jobs: Partial<Record<"slideshow_preview" | "slideshow_export", Job>>;
}

export interface SlideshowRow {
  id: string;
  title: string;
  created_at: string | null;
  photos: number;
  first: string | null;
  duration: number;
  exported: boolean;
  share: { kind: string } | null;
}

const base = (id: string) => `/api/slideshow/${encodeURIComponent(id)}`;

export const slideshowApi = {
  list: () => req<SlideshowRow[]>("GET", "/api/slideshow"),
  create: (title = "") => req<SlideshowView>("POST", "/api/slideshow", { title }),
  get: (id: string) => req<SlideshowView>("GET", base(id)),
  update: (id: string, body: Partial<SlideSettings> & { order?: string[]; sort?: "date"; title?: string; texts?: Record<string, string> }) =>
    req<SlideshowView>("PUT", base(id), body),
  remove: (id: string, photo: string) => req<SlideshowView>("POST", `${base(id)}/photos/${photo}/remove`),
  restore: (id: string, photo: string) => req<SlideshowView>("POST", `${base(id)}/photos/${photo}/restore`),
  preview: (id: string) => req<Job>("POST", `${base(id)}/preview`),
  export: (id: string) => req<Job>("POST", `${base(id)}/export`),
  save: (id: string) => req<{ folder: string; files: string[] }>("POST", `${base(id)}/save`),
  openFolder: (id: string) => req<{ folder: string; opened: boolean }>("POST", `${base(id)}/open-folder`),
};

export const slideUrls = {
  thumb: (id: string, photo: string) => `${base(id)}/photos/${photo}/thumb`,
  preview: (id: string, stamp: string | null) => `${base(id)}/preview.mp4?v=${encodeURIComponent(stamp ?? "")}`,
  video: (id: string, stamp: number | null) => `${base(id)}/video.mp4?v=${stamp ?? ""}`,
};

export const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif";

export function isPhoto(f: File): boolean {
  return /\.(jpe?g|png|webp|heic|heif)$/i.test(f.name) || /^image\/(jpeg|png|webp|heic|heif)$/.test(f.type);
}

/** One photo, raw body (the photo's own date travels along: used when it has no EXIF date). */
export function uploadPhoto(id: string, file: File): Promise<SlideshowView> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const q = new URLSearchParams({ filename: file.name, modified: String(file.lastModified || "") });
    xhr.open("PUT", `${base(id)}/photos?${q}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.onload = () => {
      let data: any = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data.view as SlideshowView);
      else reject(new ApiError(data?.error || xhr.statusText, data?.hint || null, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Network error", null, 0));
    xhr.send(file);
  });
}

/** Photos dropped on the list screen: the new slideshow's editor picks them up and uploads them. */
let handoff: { id: string; files: File[] } | null = null;
export function handFiles(id: string, files: File[]) {
  handoff = { id, files };
}
export function takeFiles(id: string): File[] {
  if (!handoff || handoff.id !== id) return [];
  const f = handoff.files;
  handoff = null;
  return f;
}
