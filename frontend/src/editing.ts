import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { api, type Candidate, type ClipEdit, type ClipOptions, type EditPlanView } from "./api";
import { attachBleeps } from "./previewAudio";

// Editing tools (1.2.4): helpers shared by the project page, the transcript editor, the live
// 9:16 preview and fast review. The preview's zoom / crop math is in previewMath.ts.

/** The range the render uses: a seamless loop may move the start out of a word and the end to its seam. */
export function renderRange(
  range: { start: number; end: number } | null,
  options: ClipOptions,
  plan: EditPlanView | null,
): { start: number; end: number } | null {
  if (range && options.loop && plan?.loop) return { start: plan.loop.start, end: plan.loop.end };
  return range;
}

export function effectiveRange(c: Candidate, edit: ClipEdit | undefined): { start: number; end: number } {
  const start = edit?.start ?? c.start;
  const end = edit?.end ?? c.end;
  return end - start >= 1 ? { start, end } : { start: c.start, end: c.end };
}

/** Source-time ranges the render bleeps / mutes (1.2.45: the plan's own bleep_src, the exact
 * moments audiomix uses - padding, the deep check's ranges, your edges and the post-render
 * widening included; no second calculation here). */
export function bleepRanges(plan: EditPlanView | null): [number, number][] {
  if (!plan || plan.bleep_mode === "off") return [];
  return plan.bleep_src ?? [];
}

/** 1.2.45: the preview's bleeps, live, whenever the video plays (not only with "Play clip"):
 * the sound ducks and the tone plays in exactly the render's ranges (previewAudio.ts). */
export function useLiveBleeps(video: RefObject<HTMLVideoElement | null>, plan: EditPlanView | null) {
  const ranges = bleepRanges(plan);
  const key = JSON.stringify([plan?.bleep_mode ?? "off", plan?.bleep_sound ?? "", ranges, plan?.bleep_fade ?? 0.012]);
  useEffect(() => {
    const v = video.current;
    if (!v || !plan) return;
    return attachBleeps(v, { ranges, mode: plan.bleep_mode, sound: plan.bleep_sound, fade: plan.bleep_fade });
  }, [video, key]); // eslint-disable-line react-hooks/exhaustive-deps
}

export function mergeRanges(r: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const [a, b] of [...r].sort((x, y) => x[0] - y[0])) {
    if (b <= a) continue;
    if (out.length && a <= out[out.length - 1][1] + 0.001) out[out.length - 1][1] = Math.max(out[out.length - 1][1], b);
    else out.push([a, b]);
  }
  return out.map(([a, b]) => [Math.round(a * 1000) / 1000, Math.round(b * 1000) / 1000]);
}

export function subtractRange(r: [number, number][], a: number, b: number): [number, number][] {
  const out: [number, number][] = [];
  for (const [x, y] of r) {
    if (y <= a || x >= b) out.push([x, y]);
    else {
      if (x < a) out.push([x, a]);
      if (y > b) out.push([b, y]);
    }
  }
  return out.filter(([x, y]) => y - x > 0.01);
}

/** "Me" / "Friend 2" / the name the user gave a voice. */
export function speakerLabel(
  spk: string,
  names: Record<string, string> | undefined,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  const custom = names?.[spk];
  if (custom) return custom;
  if (spk === "me") return t("spk.me");
  const n = Number(spk.replace(/^f/, "")) || 1;
  return n === 1 ? t("spk.friend") : t("spk.friend_n", { n });
}

/** Fetch the edit plan of the selected clip (debounced; stale answers ignored). */
export function usePlan(
  projectId: string,
  cid: string | null,
  deps: { options: ClipOptions; edit?: ClipEdit; music?: string | null; rev: number },
): EditPlanView | null {
  const [plan, setPlan] = useState<EditPlanView | null>(null);
  const seq = useRef(0);
  const key = JSON.stringify([cid, deps.options, deps.edit ?? null, deps.music ?? null, deps.rev]);
  useEffect(() => {
    if (!cid) {
      setPlan(null);
      return;
    }
    const n = ++seq.current;
    const timer = window.setTimeout(() => {
      const body: Parameters<typeof api.plan>[2] = { options: deps.options, edit: deps.edit ?? {} };
      if (deps.music !== undefined) body.music = deps.music;
      api
        .plan(projectId, cid, body)
        .then((p) => n === seq.current && setPlan(p))
        .catch(() => n === seq.current && setPlan(null));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [projectId, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return plan && plan.clip_id === cid ? plan : null;
}

/** While a clip plays in the preview: jump over cut parts, stop at the clip's end - or, in a
 * loop preview, jump from the end back to `loopStart` and keep going. Runs every frame
 * (timeupdate only fires ~4x a second). Bleeps: useLiveBleeps (always on, on the audio clock). */
export function usePreviewPlayback(
  video: RefObject<HTMLVideoElement | null>,
  active: boolean,
  plan: EditPlanView | null,
  end: number | null,
  onEnd: () => void,
  loopStart: number | null = null,
  onLoop?: () => void,
) {
  useEffect(() => {
    const v = video.current;
    if (!v || !active) return;
    const removed = plan?.removed ?? [];
    let raf = 0;
    const tick = () => {
      const t = v.currentTime;
      const cut = removed.find((r) => t >= r.a - 0.02 && t < r.b - 0.02);
      if (cut) v.currentTime = cut.b;
      if (end != null && t >= end - 1 / 60) {
        if (loopStart != null) {
          v.currentTime = loopStart; // the end flows into the start, again and again
          onLoop?.();
        } else {
          v.pause();
          v.currentTime = end; // 1.2.63: stop ON the clip's last frame, not a frame or two after it
          onEnd();
          return;
        }
      }
      if (!v.paused) raf = requestAnimationFrame(tick);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };
    v.addEventListener("play", start);
    if (!v.paused) start();
    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("play", start);
    };
  }, [video, active, plan, end, loopStart]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** Undo / redo of review snapshots (accept, reject, transcript edits). */
export function useHistory<T>() {
  const past = useRef<T[]>([]);
  const future = useRef<T[]>([]);
  const [, setTick] = useState(0);
  const push = useCallback((before: T) => {
    past.current.push(before);
    if (past.current.length > 100) past.current.shift();
    future.current = [];
    setTick((n) => n + 1);
  }, []);
  const undo = useCallback((current: T): T | null => {
    const prev = past.current.pop();
    if (prev === undefined) return null;
    future.current.push(current);
    setTick((n) => n + 1);
    return prev;
  }, []);
  const redo = useCallback((current: T): T | null => {
    const next = future.current.pop();
    if (next === undefined) return null;
    past.current.push(current);
    setTick((n) => n + 1);
    return next;
  }, []);
  return { push, undo, redo, canUndo: past.current.length > 0, canRedo: future.current.length > 0 };
}

/** Is this element a place where the user types (or picks with the keyboard)? */
export function isEditable(el: Element | null | undefined): boolean {
  if (!el || !(el as HTMLElement).tagName) return false;
  const h = el as HTMLElement;
  const tag = h.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag === "INPUT") return (h as HTMLInputElement).type !== "button" && (h as HTMLInputElement).type !== "submit";
  if (h.isContentEditable) return true;
  const role = h.getAttribute?.("role");
  return role === "textbox" || role === "combobox" || role === "searchbox" || role === "spinbutton";
}

/**
 * Is the keyboard event aimed at a text field (then shortcuts stay off)?
 * Issue #5: checks the whole composed path (shadow DOM, Firefox/Opera retargeting) and the
 * focused element, and an IME composition, so Backspace / Delete always reach the field.
 */
export function typing(e: KeyboardEvent): boolean {
  if (e.isComposing || e.keyCode === 229) return true;
  const path = typeof e.composedPath === "function" ? e.composedPath() : [];
  for (const n of path) if (n instanceof Element && isEditable(n)) return true;
  if (isEditable(e.target as Element | null)) return true;
  return typeof document !== "undefined" && isEditable(document.activeElement);
}

/** Page-level shortcuts stay off while a dialog is open, unless the key event comes from inside it. */
export function blockedByDialog(e: KeyboardEvent, own?: Element | null): boolean {
  if (typeof document === "undefined") return false;
  const open = document.querySelector('[aria-modal="true"]');
  if (!open) return false;
  const t = e.target as Node | null;
  return !(own && t && own.contains(t));
}

export const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ["A"], label: "keys.accept" },
  { keys: ["X"], label: "keys.reject" },
  { keys: ["Space"], label: "keys.play" },
  { keys: ["J", "L"], label: "keys.seek" },
  { keys: ["K"], label: "keys.pause" },
  { keys: ["←", "→"], label: "keys.prev_next" },
  { keys: ["I", "O"], label: "keys.in_out" },
  { keys: ["Ctrl", "Z"], label: "keys.undo" },
  { keys: ["Ctrl", "Shift", "Z"], label: "keys.redo" },
  { keys: ["Del"], label: "keys.delete_words" },
  { keys: ["F"], label: "keys.fast" },
  { keys: ["?"], label: "keys.help" },
];

/** "ass" -> "a**" (first letter and punctuation kept, CJK fully starred), like the renderer. */
export function maskWord(word: string): string {
  const m = word.match(/^([\p{P}\p{S}\s]*)(.*?)([\p{P}\p{S}\s]*)$/u);
  if (!m || !m[2]) return word;
  const [, lead, core, trail] = m;
  const chars = [...core];
  if (/[　-鿿가-힯＀-￯]/.test(core)) return lead + "*".repeat(chars.length) + trail;
  return lead + chars[0] + "*".repeat(chars.length - 1) + trail;
}
