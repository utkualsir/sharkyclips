// Live-preview geometry (1.2.23): an exact copy of what the renderer cuts and zooms, so the
// 9:16 preview shows the same picture as the rendered file.
//   splitRects      <- backend/sharkyclips/clips.py split_rects
//   outPulses       <- backend/sharkyclips/edit/plan.py EditPlan.out_pulses
//   factorAt        <- backend/sharkyclips/edit/zoom.py factor_expr / perspective_filter (MAX_ZOOM cap)
//   shakeAt         <- backend/sharkyclips/edit/fx.py shake_filter / shake_zoom_at
// frontend/scripts/preview-check.mjs compares the drawn preview with the backend's render plan.
import type { Facecam, ZoomPulse } from "./api";

export const OUT_W = 1080;
export const OUT_H = 1920;
export const SPLIT_TOP = 768;
export const MAX_ZOOM = 1.25;
const RAMP_IN = 0.35;
const RAMP_OUT = 0.55;
const SHAKE_ZOOM = 0.07;
const PUNCH_ZOOM = 0.12;

export type Rect = [number, number, number, number];

const floorEven = (v: number) => Math.max(0, Math.floor(v / 2) * 2);

/** Facecam panel + gameplay source crops (source pixels) of the split layout. */
export function splitRects(srcW: number, srcH: number, fc: Facecam): { cam: Rect; game: Rect } {
  const bottomH = OUT_H - SPLIT_TOP;
  const bx = Math.min(Math.max(0, fc.x), 0.95);
  const by = Math.min(Math.max(0, fc.y), 0.95);
  const bw = Math.min(Math.max(0.05, fc.w), 1 - bx);
  const bh = Math.min(Math.max(0.05, fc.h), 1 - by);
  let fx = bx * srcW;
  let fy = by * srcH;
  let fw = bw * srcW;
  let fh = bh * srcH;
  const target = OUT_W / SPLIT_TOP;
  if (fw / fh > target) {
    const nw = fh * target;
    fx += (fw - nw) / 2;
    fw = nw;
  } else {
    const nh = fw / target;
    fy += (fh - nh) / 2;
    fh = nh;
  }
  fw = Math.min(fw, srcW);
  fh = Math.min(fh, srcH);
  fx = Math.min(Math.max(0, fx), srcW - fw);
  fy = Math.min(Math.max(0, fy), srcH - fh);
  const gw = Math.min(srcW, (srcH * OUT_W) / bottomH);
  let gx = (srcW - gw) / 2;
  const camL = fc.x * srcW;
  const camR = (fc.x + fc.w) * srcW;
  if (camR <= srcW / 2 && camR > gx) gx = camR - gx < gw * 0.25 ? Math.min(camR, srcW - gw) : gx;
  else if (camL >= srcW / 2 && camL < gx + gw) gx = gx + gw - camL < gw * 0.25 ? Math.max(camL - gw, 0) : gx;
  gx = Math.min(Math.max(0, gx), srcW - gw);
  return {
    cam: [floorEven(fx), floorEven(fy), floorEven(fw), floorEven(fh)],
    game: [floorEven(gx), 0, floorEven(gw), floorEven(srcH)],
  };
}

/** The renderer's "scale=WxH:force_original_aspect_ratio=increase,crop=WxH": centered crop of a
 * source rect to the destination's aspect ratio. */
export function coverRect([sx, sy, sw, sh]: Rect, dw: number, dh: number): Rect {
  const target = dw / dh;
  if (sw / sh > target) {
    const nw = sh * target;
    return [sx + (sw - nw) / 2, sy, nw, sh];
  }
  const nh = sw / target;
  return [sx, sy + (sh - nh) / 2, sw, nh];
}

/** zoom.perspective_filter: shrink a rect around (center x, cy) for a zoom factor z. */
export function zoomRect([sx, sy, sw, sh]: Rect, z: number, cy = 0.5): Rect {
  if (z <= 1.0001) return [sx, sy, sw, sh];
  const nw = sw / z;
  const nh = sh / z;
  return [sx + (sw - nw) / 2, sy + sh * cy - sh * cy / z, nw, nh];
}

/** plan.merge: overlapping ranges become one (crop / fit zoom both pictures' pulses at once). */
export function mergeRanges(r: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const [a, b] of [...r].sort((x, y) => x[0] - y[0] || x[1] - y[1])) {
    if (b <= a) continue;
    if (out.length && a <= out[out.length - 1][1]) out[out.length - 1][1] = Math.max(out[out.length - 1][1], b);
    else out.push([a, b]);
  }
  return out;
}

/** EditPlan.out_pulses: a picture's pulses on the main timeline (snapped past cuts; none across
 * a loop seam; at least 0.6 s). */
export function outPulses(pulses: ZoomPulse[], target: "scene" | "cam", keep: [number, number][],
  loop: boolean): [number, number][] {
  const total = keep.reduce((s, [a, b]) => s + b - a, 0);
  const out: [number, number][] = [];
  for (const p of pulses) {
    if (p.target !== target) continue;
    const a = toMain(p.t0, keep, "fwd");
    const b = toMain(p.t1, keep, "back");
    if (loop && a != null && b != null && (a < 0.35 || b > total - 0.35)) continue;
    if (a != null && b != null && b - a >= 0.6) out.push([a, b]);
  }
  return out;
}

/** zoom.factor_expr: smoothstep pulses (summed, like the ffmpeg expression) at main time tm. */
export function factorAt(tm: number, pulses: [number, number][], level: number): number {
  if (level <= 1 || !pulses.length) return 1;
  const z = Math.min(level, MAX_ZOOM);
  if (!pulses.some(([a, b]) => tm >= a && tm <= b)) return 1; // the filter's enable=between(...)
  let acc = 0;
  for (const [t0, t1] of pulses) {
    const ri = Math.min(RAMP_IN, (t1 - t0) / 3);
    const ro = Math.min(RAMP_OUT, (t1 - t0) / 3);
    const s = Math.min(Math.min(1, Math.max(0, (tm - t0) / ri)), Math.min(1, Math.max(0, (t1 - tm) / ro)));
    acc += s * s * (3 - 2 * s);
  }
  return 1 + (z - 1) * acc;
}

/** Source time -> the render's main timeline (cut parts removed): EditPlan.to_out. Inside a
 * cut: null, or the next ("fwd") / previous ("back") kept moment. */
export function toMain(t: number, keep: [number, number][], snap: "none" | "fwd" | "back" = "none"): number | null {
  let acc = 0;
  let prevEnd: number | null = null;
  for (const [a, b] of keep) {
    if (t < a) {
      if (snap === "fwd") return acc;
      if (snap === "back") return prevEnd;
      return null;
    }
    if (t <= b) return acc + (t - a);
    acc += b - a;
    prevEnd = acc;
  }
  return snap === "back" ? prevEnd : null;
}

/** Meme shake / punch on the whole picture at main time tm (fx.shake_filter): zoom + shift in
 * canvas fractions. base = the smart zoom level: the two together never pass MAX_ZOOM. */
export function shakeAt(tm: number, shakes: [number, number][], punches: [number, number][], base: number,
  fps: number): { z: number; dx: number; dy: number } {
  const none = { z: 1, dx: 0, dy: 0 };
  const on = [...shakes, ...punches].some(([a, b]) => tm >= a && tm <= b);
  if (!on) return none;
  const room = Math.max(0, MAX_ZOOM / Math.max(1, base) - 1);
  if (room <= 0.001) return none;
  const tt = Math.round(tm * fps) / fps; // the renderer evaluates per frame
  const amp = Math.min(1, shakes.reduce((s, [a, b]) => s + (tt >= a && tt <= b ? 1 - (tt - a) / Math.max(0.05, b - a) : 0), 0));
  const pun = Math.min(1, punches.reduce(
    (s, [a, b]) => s + (tt >= a && tt <= b ? Math.sin(Math.PI * Math.min(1, (tt - a) / Math.max(0.05, b - a))) : 0), 0));
  const z = 1 + Math.min(room, SHAKE_ZOOM * amp + PUNCH_ZOOM * pun);
  const mx = 0.5 - 0.5 / z;
  const my = 0.5 - 0.5 / z;
  const dx = Math.min(mx, Math.max(-mx, 0.018 * amp * Math.sin(tt * 71)));
  const dy = Math.min(my, Math.max(-my, 0.011 * amp * Math.cos(tt * 53)));
  return { z, dx, dy };
}

/** Everything the preview needs from the render plan to zoom like the renderer. */
export interface PreviewFx {
  level: number; // smart zoom level (0 = off)
  pulses: ZoomPulse[];
  keep: [number, number][];
  loop: boolean;
  shakes: [number, number][];
  punches: [number, number][];
  fps: number;
}

const NO_ZOOM = { scene: 1, cam: 1, full: 1, shake: { z: 1, dx: 0, dy: 0 } };

/** Zoom factors at source time t, all on the main timeline like the render: smart zoom per
 * picture (split: scene + cam; crop / fit: "full") and the meme shake / punch on top. */
export function zoomsAt(t: number, fx: PreviewFx | null) {
  if (!fx || !fx.keep.length) return NO_ZOOM;
  const tm = toMain(t, fx.keep);
  if (tm == null) return NO_ZOOM;
  const level = fx.level > 1 && fx.pulses.length ? fx.level : 0;
  let scene = 1;
  let cam = 1;
  let full = 1;
  if (level) {
    const ps = outPulses(fx.pulses, "scene", fx.keep, fx.loop);
    const pc = outPulses(fx.pulses, "cam", fx.keep, fx.loop);
    scene = factorAt(tm, ps, level);
    cam = factorAt(tm, pc, level);
    full = factorAt(tm, mergeRanges([...ps, ...pc]), level);
  }
  const shake = shakeAt(tm, fx.shakes, fx.punches, level || 1, fx.fps);
  return { scene, cam, full, shake };
}
