// The waiting mini game (1.2.59): sound effects, made with WebAudio oscillators (no sound files).
// Muted by default. The AudioContext is only created after the player turns the sound on (a
// click = a user gesture), and it is suspended again when muted or when the game pauses.
import type { GameEvent } from "./engine";

let ctx: AudioContext | null = null;
let master: GainNode | null = null;
let on = false;
let lastAt = 0;

function audio(): AudioContext | null {
  if (!on) return null;
  if (!ctx) {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return null;
    try {
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.16;
      master.connect(ctx.destination);
    } catch {
      return null;
    }
  }
  if (ctx.state === "suspended") void ctx.resume().catch(() => {});
  return ctx;
}

export function setSound(enabled: boolean): void {
  on = enabled;
  if (!enabled && ctx && ctx.state === "running") void ctx.suspend().catch(() => {});
  if (enabled) audio();
}

export function suspendSound(): void {
  if (ctx && ctx.state === "running") void ctx.suspend().catch(() => {});
}

function tone(freq: number, to: number, dur: number, type: OscillatorType, vol = 1, delay = 0): void {
  const a = audio();
  if (!a || !master) return;
  const t0 = a.currentTime + delay;
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t0);
  o.frequency.exponentialRampToValueAtTime(Math.max(30, to), t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.connect(g);
  g.connect(master);
  o.start(t0);
  o.stop(t0 + dur + 0.02);
}

/** Play the sounds for this frame's events (at most a few per frame, so a burst never gets loud). */
export function playEvents(events: GameEvent[]): void {
  if (!on || !events.length) return;
  const now = performance.now();
  let n = 0;
  for (const e of events) {
    if (n >= 2) break;
    if (e.type === "eat") {
      if (now - lastAt < 35) continue;
      lastAt = now;
      const up = Math.min(12, e.combo) * 0.045;
      if (e.kind === "gold") {
        tone(880, 1320, 0.09, "triangle", 0.8);
        tone(1320, 1760, 0.12, "triangle", 0.7, 0.07);
      } else if (e.kind === "predator" || e.kind === "big") {
        tone(220 * (1 + up), 90, 0.16, "sawtooth", 0.55);
      } else {
        tone(520 * (1 + up), 260 * (1 + up), 0.07, "square", 0.35);
      }
    } else if (e.type === "hit") tone(160, 60, 0.25, "sawtooth", 0.8);
    else if (e.type === "blocked") tone(300, 200, 0.06, "triangle", 0.4);
    else if (e.type === "power") {
      tone(440, 880, 0.14, "triangle", 0.7);
      tone(660, 1320, 0.14, "triangle", 0.5, 0.06);
    } else if (e.type === "dash") tone(240, 480, 0.08, "sine", 0.4);
    else if (e.type === "combo") tone(660 + e.combo * 20, 990 + e.combo * 20, 0.1, "square", 0.3);
    else if (e.type === "over") {
      tone(660, 600, 0.12, "triangle", 0.6);
      tone(520, 480, 0.12, "triangle", 0.6, 0.13);
      tone(392, 380, 0.25, "triangle", 0.6, 0.26);
    } else continue;
    n++;
  }
}
