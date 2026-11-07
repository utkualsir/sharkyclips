import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { api, type Candidate, type ClipEdit, type ClipOptions, type EditPlanView } from "./api";

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

/** Source-time ranges that are bleeped / muted (the review list's "on" items, every speaker). */
export function bleepRanges(plan: EditPlanView | null): [number, number][] {
  if (!plan || plan.bleep_mode === "off") return [];
  const removed = plan.removed ?? [];
  return (plan.swears ?? [])
    .filter((s) => s.bleep && !removed.some((r) => (s.start + s.end) / 2 >= r.a && (s.start + s.end) / 2 <= r.b))
    .map((s) => [s.start - 0.03, s.end + 0.03] as [number, number]);
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

/** While a clip plays in the preview: jump over cut parts, bleep / mute swear words, stop at
 * the clip's end - or, in a loop preview, jump from the end back to `loopStart` and keep going.
 * Runs every frame (timeupdate only fires ~4x a second). */
export function usePreviewPlayback(
  video: RefObject<HTMLVideoElement>,
  active: boolean,
  plan: EditPlanView | null,
  end: number | null,
  onEnd: () => void,
  loopStart: number | null = null,
) {
  const audio = useRef<{ ctx: AudioContext; osc: OscillatorNode; gain: GainNode } | null>(null);
  useEffect(() => {
    const v = video.current;
    if (!v || !active) return;
    const removed = plan?.removed ?? [];
    const bleeps = bleepRanges(plan);
    const mode = plan?.bleep_mode ?? "off";
    let raf = 0;
    let wasMuted = v.muted;
    let inBleep = false;
    const beep = (on: boolean) => {
      if (mode !== "bleep") return;
      try {
        if (!audio.current) {
          const ctx = new AudioContext();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.frequency.value = 1000;
          gain.gain.value = 0;
          osc.connect(gain).connect(ctx.destination);
          osc.start();
          audio.current = { ctx, osc, gain };
        }
        const a = audio.current;
        a.gain.gain.setTargetAtTime(on ? 0.12 * v.volume : 0, a.ctx.currentTime, 0.005);
      } catch {
        /* no Web Audio: muting is enough */
      }
    };
    const tick = () => {
      const t = v.currentTime;
      const cut = removed.find((r) => t >= r.a - 0.02 && t < r.b - 0.02);
      if (cut) v.currentTime = cut.b;
      const b = bleeps.some(([a, bb]) => t >= a && t <= bb);
      if (b !== inBleep) {
        inBleep = b;
        if (b) {
          wasMuted = v.muted;
          v.muted = true;
        } else v.muted = wasMuted;
        beep(b);
      }
      if (end != null && t >= end) {
        if (loopStart != null) {
          v.currentTime = loopStart; // the end flows into the start, again and again
        } else {
          v.pause();
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
      if (inBleep) {
        v.muted = wasMuted;
        beep(false);
      }
    };
  }, [video, active, plan, end, loopStart]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(
    () => () => {
      audio.current?.ctx.close().catch(() => {});
      audio.current = null;
    },
    [],
  );
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

/** Is the keyboard event aimed at a text field (then shortcuts stay off)? */
export function typing(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
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
