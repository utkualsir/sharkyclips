// The waiting mini game (1.2.59): the simulation. Pure TypeScript, no DOM, no network, seeded
// random numbers - so backend/tests/test_minigame.py can run it with Node (performance budget,
// fairness, rules). render.ts draws a Game; Panel.tsx feeds it input and time.
//
// The shark swims after the mouse / finger or the arrow keys, eats fish smaller than itself to
// grow, avoids bigger fish, jellyfish and spiky urchins, builds combos by eating quickly and picks
// up bubble power-ups. A round lasts 60 s (golden fish and the clock bubble add time, 90 s at
// most) or ends when the three lives are gone. It gets a bit harder every second.

export const W = 480;
export const H = 300;
export const ROUND_S = 60;
export const MAX_ROUND_S = 90;
export const LIVES = 3;
const COMBO_S = 1.6;
const MAX_SIZE = 2.4;
const BASE_R = 12;
const SEABED = H - 18;

export type FishKind = "small" | "mid" | "big" | "gold" | "predator";
export type HazardKind = "jelly" | "urchin";
export type PowerKind = "magnet" | "frenzy" | "shield" | "time";
export type Phase = "ready" | "playing" | "over";

export interface Input {
  /** pointer target in world units (null = no pointer steering) */
  tx: number | null;
  ty: number | null;
  /** keyboard direction, -1..1 each */
  dx: number;
  dy: number;
  dash: boolean;
}

export const NO_INPUT: Input = { tx: null, ty: null, dx: 0, dy: 0, dash: false };

export interface Shark {
  x: number;
  y: number;
  vx: number;
  vy: number;
  angle: number;
  size: number;
  /** seconds of blinking after a hit (no damage) */
  inv: number;
  stun: number;
  dashT: number;
  dashCd: number;
  /** chomp animation, 1 -> 0 */
  chomp: number;
  tail: number;
  /** grows with a short squash after eating */
  squash: number;
}

export interface Fish {
  kind: FishKind;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  phase: number;
  hue: number;
}

export interface Hazard {
  kind: HazardKind;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  phase: number;
}

export interface Power {
  kind: PowerKind;
  x: number;
  y: number;
  vy: number;
  life: number;
  phase: number;
}

export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  max: number;
  size: number;
  /** 0 bubble, 1 spark, 2 bit (tinted with hue) */
  kind: number;
  hue: number;
}

export interface Popup {
  x: number;
  y: number;
  text: string;
  life: number;
  /** 0 points, 1 gold / power, 2 combo, 3 bad */
  tone: number;
}

export type GameEvent =
  | { type: "eat"; kind: FishKind; points: number; combo: number }
  | { type: "hit" }
  | { type: "blocked" }
  | { type: "power"; kind: PowerKind }
  | { type: "dash" }
  | { type: "combo"; combo: number }
  | { type: "grow" }
  | { type: "over"; score: number };

export interface Stats {
  score: number;
  fish: number;
  bestCombo: number;
}

export interface Game {
  phase: Phase;
  seed: number;
  rnd: () => number;
  t: number;
  /** seconds played this round (difficulty) */
  elapsed: number;
  timeLeft: number;
  lives: number;
  score: number;
  fishEaten: number;
  combo: number;
  comboT: number;
  bestCombo: number;
  shark: Shark;
  fish: Fish[];
  hazards: Hazard[];
  powers: Power[];
  particles: Particle[];
  popups: Popup[];
  magnet: number;
  frenzy: number;
  shield: boolean;
  shake: number;
  flash: number;
  hitStop: number;
  spawnFish: number;
  spawnHazard: number;
  spawnPower: number;
  /** particle budget: render.ts lowers it when frames get slow (and for reduced motion) */
  maxParticles: number;
  events: GameEvent[];
}

/** Small fast seeded RNG (mulberry32). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FISH: Record<FishKind, { r: [number, number]; pts: number; speed: [number, number] }> = {
  small: { r: [5, 7], pts: 10, speed: [38, 62] },
  mid: { r: [9, 11], pts: 25, speed: [34, 54] },
  big: { r: [14, 17], pts: 50, speed: [28, 44] },
  gold: { r: [7, 8], pts: 100, speed: [80, 105] },
  predator: { r: [23, 28], pts: 150, speed: [42, 64] },
};

export const POWER_KINDS: PowerKind[] = ["magnet", "frenzy", "shield", "time"];

export function sharkR(g: Game): number {
  return BASE_R * g.shark.size;
}

export function edible(g: Game, f: Fish): boolean {
  return f.r < sharkR(g) * 0.95;
}

export function multiplier(g: Game): number {
  return (1 + Math.min(4, Math.floor(g.combo / 4))) * (g.frenzy > 0 ? 2 : 1);
}

export function difficulty(g: Game): number {
  return Math.min(1, g.elapsed / 60);
}

function newShark(): Shark {
  return { x: W * 0.35, y: H * 0.5, vx: 0, vy: 0, angle: 0, size: 1, inv: 0, stun: 0, dashT: 0, dashCd: 0, chomp: 0,
    tail: 0, squash: 0 };
}

export function createGame(seed = 1): Game {
  const g: Game = {
    phase: "ready", seed, rnd: rng(seed), t: 0, elapsed: 0, timeLeft: ROUND_S, lives: LIVES, score: 0, fishEaten: 0,
    combo: 0, comboT: 0, bestCombo: 0, shark: newShark(), fish: [], hazards: [], powers: [], particles: [], popups: [],
    magnet: 0, frenzy: 0, shield: false, shake: 0, flash: 0, hitStop: 0, spawnFish: 0, spawnHazard: 4, spawnPower: 7,
    maxParticles: 160, events: [],
  };
  // a calm sea on the start screen
  for (let i = 0; i < 6; i++) spawnFish(g, i < 4 ? "small" : "mid", g.rnd() * W);
  return g;
}

/** A fresh round (keeps the seed stream going, so every round is different). */
export function startRound(g: Game): void {
  const keep = g.maxParticles;
  Object.assign(g, {
    phase: "playing", t: 0, elapsed: 0, timeLeft: ROUND_S, lives: LIVES, score: 0, fishEaten: 0, combo: 0, comboT: 0,
    bestCombo: 0, shark: newShark(), fish: [], hazards: [], powers: [], particles: [], popups: [], magnet: 0, frenzy: 0,
    shield: false, shake: 0, flash: 0, hitStop: 0, spawnFish: 0, spawnHazard: 3.5, spawnPower: 6, maxParticles: keep,
    events: [],
  } satisfies Partial<Game>);
  for (let i = 0; i < 5; i++) spawnFish(g, "small", W * (0.55 + 0.4 * g.rnd()));
}

export function stats(g: Game): Stats {
  return { score: Math.round(g.score), fish: g.fishEaten, bestCombo: g.bestCombo };
}

const range = (g: Game, [a, b]: [number, number]) => a + (b - a) * g.rnd();

function pickFishKind(g: Game): FishKind {
  const d = difficulty(g);
  const s = g.shark.size;
  const x = g.rnd();
  if (x < 0.035 + 0.02 * d) return "gold";
  if (x < 0.1 + 0.12 * d + (s > 1.8 ? 0.05 : 0)) return "predator";
  if (x < 0.2 + 0.16 * d + (s > 1.3 ? 0.1 : 0)) return "big";
  if (x < 0.62) return "mid";
  return "small";
}

function spawnFish(g: Game, kind: FishKind, atX?: number): void {
  const spec = FISH[kind];
  const fromLeft = g.rnd() < 0.5;
  const r = range(g, spec.r);
  const speed = range(g, spec.speed) * (1 + 0.45 * difficulty(g));
  const x = atX ?? (fromLeft ? -r * 2 : W + r * 2);
  const dir = atX !== undefined ? (g.rnd() < 0.5 ? -1 : 1) : fromLeft ? 1 : -1;
  g.fish.push({ kind, x, y: 24 + g.rnd() * (SEABED - 48), vx: speed * dir, vy: 0, r, phase: g.rnd() * 6.28,
    hue: Math.floor(g.rnd() * 6) });
}

function spawnHazard(g: Game): void {
  if (g.rnd() < 0.55) {
    g.hazards.push({ kind: "jelly", x: 30 + g.rnd() * (W - 60), y: H + 16, vx: 0, vy: -(14 + 10 * g.rnd()), r: 10,
      phase: g.rnd() * 6.28 });
  } else {
    g.hazards.push({ kind: "urchin", x: 30 + g.rnd() * (W - 60), y: -14, vx: (g.rnd() - 0.5) * 12,
      vy: 16 + 16 * g.rnd() + 14 * difficulty(g), r: 9, phase: g.rnd() * 6.28 });
  }
}

function spawnPower(g: Game): void {
  const kind = POWER_KINDS[Math.floor(g.rnd() * POWER_KINDS.length)];
  g.powers.push({ kind, x: 40 + g.rnd() * (W - 80), y: H + 12, vy: -(20 + 8 * g.rnd()), life: 9, phase: g.rnd() * 6.28 });
}

function burst(g: Game, x: number, y: number, n: number, kind: number, hue: number, speed = 60): void {
  for (let i = 0; i < n && g.particles.length < g.maxParticles; i++) {
    const a = g.rnd() * Math.PI * 2;
    const v = speed * (0.35 + g.rnd());
    const max = 0.35 + g.rnd() * 0.45;
    g.particles.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - (kind === 0 ? 20 : 0), life: max, max,
      size: kind === 0 ? 1.5 + g.rnd() * 2.5 : 1 + g.rnd() * 1.6, kind, hue });
  }
}

function popup(g: Game, x: number, y: number, text: string, tone: number): void {
  if (g.popups.length > 8) g.popups.shift();
  g.popups.push({ x, y, text, life: 0.9, tone });
}

function hurt(g: Game, fromX: number, fromY: number): void {
  const s = g.shark;
  if (s.inv > 0) return;
  const dx = s.x - fromX;
  const dy = s.y - fromY;
  const d = Math.hypot(dx, dy) || 1;
  s.vx = (dx / d) * 190;
  s.vy = (dy / d) * 190;
  if (g.shield) {
    g.shield = false;
    s.inv = 0.8;
    g.events.push({ type: "blocked" });
    burst(g, s.x, s.y, 14, 1, 5, 90);
    return;
  }
  g.lives -= 1;
  s.inv = 1.3;
  s.size = Math.max(1, s.size * 0.92);
  g.combo = 0;
  g.comboT = 0;
  g.shake = Math.max(g.shake, 6);
  g.flash = 0.25;
  g.events.push({ type: "hit" });
  burst(g, s.x, s.y, 12, 2, 0, 80);
  popup(g, s.x, s.y - 18, "-1", 3);
  if (g.lives <= 0) endRound(g);
}

function endRound(g: Game): void {
  if (g.phase !== "playing") return;
  g.phase = "over";
  g.events.push({ type: "over", score: Math.round(g.score) });
}

function eat(g: Game, i: number): void {
  const f = g.fish[i];
  const s = g.shark;
  g.fish.splice(i, 1);
  g.combo += 1;
  g.comboT = COMBO_S;
  g.bestCombo = Math.max(g.bestCombo, g.combo);
  const pts = Math.round(FISH[f.kind].pts * multiplier(g));
  g.score += pts;
  g.fishEaten += 1;
  s.chomp = 1;
  s.squash = 1;
  const before = Math.floor(s.size * 5);
  s.size = Math.min(MAX_SIZE, s.size + FISH[f.kind].pts / 900 + 0.008);
  if (Math.floor(s.size * 5) > before) g.events.push({ type: "grow" });
  g.events.push({ type: "eat", kind: f.kind, points: pts, combo: g.combo });
  burst(g, f.x, f.y, f.kind === "small" ? 6 : 10, 2, f.hue, 55);
  burst(g, f.x, f.y, 4, 0, 0, 30);
  popup(g, f.x, f.y - 10, `+${pts}`, f.kind === "gold" ? 1 : 0);
  if (f.kind === "gold") {
    addTime(g, 2);
    burst(g, f.x, f.y, 12, 1, 7, 90);
  }
  if (f.kind === "predator" || f.kind === "big") {
    g.hitStop = f.kind === "predator" ? 0.08 : 0.04;
    g.shake = Math.max(g.shake, f.kind === "predator" ? 4 : 2);
  }
  if (g.combo >= 4 && g.combo % 4 === 0) {
    g.events.push({ type: "combo", combo: g.combo });
    popup(g, s.x, s.y - 26, `x${1 + Math.min(4, Math.floor(g.combo / 4))}`, 2);
  }
}

function addTime(g: Game, s: number): void {
  // never past MAX_ROUND_S in total
  g.timeLeft = Math.min(g.timeLeft + s, MAX_ROUND_S - g.elapsed);
}

function takePower(g: Game, i: number): void {
  const p = g.powers[i];
  g.powers.splice(i, 1);
  if (p.kind === "magnet") g.magnet = 6;
  else if (p.kind === "frenzy") g.frenzy = 6;
  else if (p.kind === "shield") g.shield = true;
  else addTime(g, 5);
  g.flash = Math.max(g.flash, 0.12);
  g.events.push({ type: "power", kind: p.kind });
  burst(g, p.x, p.y, 14, 1, 4, 80);
}

function steer(g: Game, dt: number, input: Input): void {
  const s = g.shark;
  const max = (150 - 16 * (s.size - 1)) * (s.dashT > 0 ? 2.3 : 1) * (s.stun > 0 ? 0.35 : 1);
  let wx = 0;
  let wy = 0;
  if (input.dx || input.dy) {
    const n = Math.hypot(input.dx, input.dy) || 1;
    wx = (input.dx / n) * max;
    wy = (input.dy / n) * max;
  } else if (input.tx !== null && input.ty !== null) {
    const dx = input.tx - s.x;
    const dy = input.ty - s.y;
    const d = Math.hypot(dx, dy);
    if (d > 3) {
      const k = Math.min(1, d / 60) * max;
      wx = (dx / d) * k;
      wy = (dy / d) * k;
    }
  }
  if (input.dash && s.dashCd <= 0 && s.stun <= 0) {
    s.dashT = 0.24;
    s.dashCd = 1.2;
    const a = Math.hypot(wx, wy) > 1 ? Math.atan2(wy, wx) : s.angle;
    s.vx = Math.cos(a) * max * 2.3;
    s.vy = Math.sin(a) * max * 2.3;
    g.events.push({ type: "dash" });
    burst(g, s.x, s.y, 6, 0, 0, 40);
  }
  const k = Math.min(1, dt * (s.dashT > 0 ? 2 : 5.5));
  s.vx += (wx - s.vx) * k;
  s.vy += (wy - s.vy) * k;
  s.x += s.vx * dt;
  s.y += s.vy * dt;
  const r = sharkR(g);
  if (s.x < r) (s.x = r), (s.vx = Math.abs(s.vx) * 0.3);
  if (s.x > W - r) (s.x = W - r), (s.vx = -Math.abs(s.vx) * 0.3);
  if (s.y < r * 0.7) (s.y = r * 0.7), (s.vy = Math.abs(s.vy) * 0.3);
  if (s.y > SEABED - r * 0.5) (s.y = SEABED - r * 0.5), (s.vy = -Math.abs(s.vy) * 0.3);
  const speed = Math.hypot(s.vx, s.vy);
  if (speed > 8) {
    const want = Math.atan2(s.vy, s.vx);
    let diff = want - s.angle;
    while (diff > Math.PI) diff -= Math.PI * 2;
    while (diff < -Math.PI) diff += Math.PI * 2;
    s.angle += diff * Math.min(1, dt * 9);
  }
  s.tail += dt * (4 + speed / 18);
}

/** Advance the game by dt seconds (call with dt <= 1/30; Panel.tsx uses fixed 1/60 steps). */
export function step(g: Game, dt: number, input: Input = NO_INPUT): void {
  g.t += dt;
  // particles and popups live on in every phase (the end screen fades them out)
  for (let i = g.particles.length - 1; i >= 0; i--) {
    const p = g.particles[i];
    p.life -= dt;
    if (p.life <= 0) {
      g.particles[i] = g.particles[g.particles.length - 1];
      g.particles.pop();
      continue;
    }
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    const drag = p.kind === 0 ? 1.5 : 3;
    p.vx -= p.vx * drag * dt;
    p.vy -= p.vy * drag * dt + (p.kind === 0 ? 30 * dt : 0);
  }
  for (let i = g.popups.length - 1; i >= 0; i--) {
    const p = g.popups[i];
    p.life -= dt;
    p.y -= 22 * dt;
    if (p.life <= 0) g.popups.splice(i, 1);
  }
  g.shake = Math.max(0, g.shake - dt * 30);
  g.flash = Math.max(0, g.flash - dt);
  if (g.phase !== "playing") {
    // the sea keeps moving gently behind the start / end screens
    for (const f of g.fish) {
      f.phase += dt * 3;
      f.x += f.vx * dt * 0.5;
      if (f.x < -40) f.x = W + 30;
      if (f.x > W + 40) f.x = -30;
    }
    return;
  }
  if (g.hitStop > 0) {
    g.hitStop -= dt;
    return;
  }
  g.elapsed += dt;
  g.timeLeft -= dt;
  if (g.timeLeft <= 0) {
    g.timeLeft = 0;
    endRound(g);
    return;
  }
  const s = g.shark;
  const d = difficulty(g);
  s.inv = Math.max(0, s.inv - dt);
  s.stun = Math.max(0, s.stun - dt);
  s.dashT = Math.max(0, s.dashT - dt);
  s.dashCd = Math.max(0, s.dashCd - dt);
  s.chomp = Math.max(0, s.chomp - dt * 5);
  s.squash = Math.max(0, s.squash - dt * 4);
  g.magnet = Math.max(0, g.magnet - dt);
  g.frenzy = Math.max(0, g.frenzy - dt);
  if (g.comboT > 0) {
    g.comboT -= dt;
    if (g.comboT <= 0) g.combo = 0;
  }
  steer(g, dt, input);

  // spawning: more and faster things as the round goes on, never more than the caps
  g.spawnFish -= dt;
  if (g.spawnFish <= 0 && g.fish.length < 22) {
    spawnFish(g, pickFishKind(g));
    g.spawnFish = 0.62 - 0.22 * d + g.rnd() * 0.25;
  }
  g.spawnHazard -= dt;
  if (g.spawnHazard <= 0 && g.hazards.length < 7) {
    spawnHazard(g);
    g.spawnHazard = 4.2 - 2.6 * d + g.rnd() * 1.4;
  }
  g.spawnPower -= dt;
  if (g.spawnPower <= 0 && g.powers.length < 2) {
    spawnPower(g);
    g.spawnPower = 7 + g.rnd() * 5;
  }

  const r = sharkR(g);
  const mx = s.x + Math.cos(s.angle) * r * 0.85;
  const my = s.y + Math.sin(s.angle) * r * 0.85;
  for (let i = g.fish.length - 1; i >= 0; i--) {
    const f = g.fish[i];
    f.phase += dt * (5 + Math.abs(f.vx) / 20);
    const canEat = edible(g, f);
    // a small fish near the shark gets nervous and swims away; a predator hunts a smaller shark
    const ddx = f.x - s.x;
    const ddy = f.y - s.y;
    const dist = Math.hypot(ddx, ddy) || 1;
    if (g.magnet > 0 && canEat && dist < 110) {
      f.vy += (-ddy / dist) * 260 * dt;
      f.x += (-ddx / dist) * 90 * dt;
    } else if (canEat && dist < 70) {
      f.vy += (ddy / dist) * 70 * dt;
    } else if (f.kind === "predator" && !canEat && dist < 160) {
      f.vy += (-ddy / dist) * (25 + 30 * d) * dt;
    }
    f.vy *= 1 - Math.min(1, dt * 1.8);
    f.x += f.vx * dt;
    f.y += f.vy * dt + Math.sin(f.phase * 0.5) * 6 * dt;
    if (f.y < f.r + 4) (f.y = f.r + 4), (f.vy = Math.abs(f.vy));
    if (f.y > SEABED - f.r) (f.y = SEABED - f.r), (f.vy = -Math.abs(f.vy));
    if ((f.vx > 0 && f.x > W + 50) || (f.vx < 0 && f.x < -50)) {
      g.fish.splice(i, 1);
      continue;
    }
    if (canEat) {
      if (Math.hypot(f.x - mx, f.y - my) < r * 0.75 + f.r) eat(g, i);
    } else if (dist < r * 0.8 + f.r * 0.85) {
      if (f.kind === "predator") hurt(g, f.x, f.y);
      else if (s.inv <= 0) {
        // too big to eat, harmless: a bump
        s.vx = (-ddx / dist) * 120;
        s.vy = (-ddy / dist) * 120;
        g.events.push({ type: "blocked" });
        s.inv = 0.25;
      }
    }
  }
  for (let i = g.hazards.length - 1; i >= 0; i--) {
    const h = g.hazards[i];
    h.phase += dt * 2;
    h.x += (h.vx + (h.kind === "jelly" ? Math.sin(h.phase) * 10 : 0)) * dt;
    h.y += h.vy * (h.kind === "jelly" ? 0.6 + 0.6 * Math.max(0, Math.sin(h.phase * 1.3)) : 1) * dt;
    if (h.y < -30 || h.y > H + 30) {
      g.hazards.splice(i, 1);
      continue;
    }
    if (Math.hypot(h.x - s.x, h.y - s.y) < r * 0.75 + h.r) {
      if (h.kind === "jelly") s.stun = 0.7;
      hurt(g, h.x, h.y);
      if (g.phase !== "playing") return;
    }
  }
  for (let i = g.powers.length - 1; i >= 0; i--) {
    const p = g.powers[i];
    p.phase += dt * 3;
    p.y += p.vy * dt;
    p.x += Math.sin(p.phase) * 8 * dt;
    p.life -= dt;
    if (p.life <= 0 || p.y < -20) {
      g.powers.splice(i, 1);
      continue;
    }
    if (Math.hypot(p.x - s.x, p.y - s.y) < r + 10) takePower(g, i);
  }
  // a bubble trail when swimming fast
  if (Math.hypot(s.vx, s.vy) > 120 && g.rnd() < dt * 18) {
    const tx = s.x - Math.cos(s.angle) * r * 1.4;
    const ty = s.y - Math.sin(s.angle) * r * 1.4;
    burst(g, tx, ty, 1, 0, 0, 12);
  }
}

/** A simple player for tests: chase the nearest fish it can eat, keep away from danger. */
export function botInput(g: Game): Input {
  const s = g.shark;
  let best: Fish | null = null;
  let bd = 1e9;
  for (const f of g.fish) {
    if (!edible(g, f)) continue;
    const d = Math.hypot(f.x - s.x, f.y - s.y);
    if (d < bd) (bd = d), (best = f);
  }
  let tx = best ? best.x : W / 2;
  let ty = best ? best.y : H / 2;
  const r = sharkR(g);
  for (const h of [...g.hazards, ...g.fish.filter((f) => f.kind === "predator" && !edible(g, f))]) {
    const d = Math.hypot(h.x - s.x, h.y - s.y);
    if (d < r + h.r + 40) {
      tx = s.x + (s.x - h.x) * 3;
      ty = s.y + (s.y - h.y) * 3;
    }
  }
  return { tx, ty, dx: 0, dy: 0, dash: !!best && bd < 70 && bd > 30 };
}
