// Where a clip ends, while you watch it (1.2.63). Pure math, no imports: the Python tests run this
// file with Node (backend/tests/test_clip_end.py).

export type ClipEndMode = "stop" | "loop";

export interface ClipState {
  /** the playhead is inside the clip (a frame of slack at both ends) */
  inClip: boolean;
  /** seconds until the clip ends (0 after the end) */
  left: number;
  /** 0..1 through the clip */
  progress: number;
  /** positions on a bar that shows `0..total` seconds, in % */
  startPct: number;
  endPct: number;
  playPct: number;
  /** at (or a hair before) the end */
  atEnd: boolean;
}

/** One frame at 30 fps: "exactly at the end" allows this much, never more. */
export const END_EPS = 1 / 30;

export function clipState(t: number, start: number, end: number, total?: number | null): ClipState {
  const s = Math.max(0, Math.min(start, end));
  const e = Math.max(s + 0.001, end);
  const tot = Math.max(e, total && isFinite(total) ? total : e);
  const clamp = (x: number) => Math.min(100, Math.max(0, x));
  return {
    inClip: t >= s - END_EPS && t <= e + END_EPS,
    left: Math.max(0, e - t),
    progress: Math.min(1, Math.max(0, (t - s) / (e - s))),
    startPct: clamp((s / tot) * 100),
    endPct: clamp((e / tot) * 100),
    playPct: clamp((t / tot) * 100),
    atEnd: t >= e - END_EPS,
  };
}

/** What to do at this playhead time while a clip plays: keep going, stop at the end, or go back
 *  to the start (loop). */
export function endAction(t: number, end: number, mode: ClipEndMode): "none" | "stop" | "loop" {
  if (t < end - END_EPS / 2) return "none";
  return mode === "loop" ? "loop" : "stop";
}

/** Did the playhead just wrap from the end back to the start (a native loop)? */
export function wrapped(prev: number, now: number, start: number, end: number): boolean {
  const len = end - start;
  return len > 0 && prev >= end - Math.max(0.35, len * 0.1) && now <= start + Math.max(0.35, len * 0.1) && now < prev;
}

/** "2.4" (one decimal under 10 s, whole seconds above, never negative). */
export function fmtLeft(s: number): string {
  const v = Math.max(0, s);
  return v < 10 ? (Math.floor(v * 10) / 10).toFixed(1) : String(Math.floor(v));
}

/** Seek target for a click at fraction `x` (0..1) of a bar that shows `0..total`. */
export function seekTarget(x: number, total: number): number {
  return Math.min(1, Math.max(0, x)) * Math.max(0, total);
}
