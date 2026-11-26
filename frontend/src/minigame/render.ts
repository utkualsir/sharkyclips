// The waiting mini game (1.2.59): drawing. Everything is drawn in code on a 2D canvas (no image
// files, no fonts to download), so the game adds only a few KB to the app.
import { edible, H, sharkR, W, type Fish, type Game, type Hazard, type Power } from "./engine";
import { ART, FISH_COLORS, POWER_COLORS, SEA_DEFAULT, SKINS, TONES, glow, type Skin } from "./art";

export { SKINS, type Skin };

/** The water follows the app theme (--mg-* in themes.css); read once per theme change. */
let seaCache: typeof SEA_DEFAULT | null = null;
if (typeof window !== "undefined") window.addEventListener("cf-theme", () => (seaCache = null));
function seaColours(): typeof SEA_DEFAULT {
  if (seaCache) return seaCache;
  const cs = typeof document !== "undefined" ? getComputedStyle(document.documentElement) : null;
  const pick = (name: string, d: string) => cs?.getPropertyValue(name).trim() || d;
  seaCache = { a: pick("--mg-water-a", SEA_DEFAULT.a), b: pick("--mg-water-b", SEA_DEFAULT.b), c: pick("--mg-water-c", SEA_DEFAULT.c), floor: pick("--mg-floor", SEA_DEFAULT.floor), dark: pick("--mg-dark", SEA_DEFAULT.dark) };
  return seaCache;
}



export interface View {
  /** canvas pixels per world unit */
  scale: number;
  skin: Skin;
  /** full = shake and flashes; reduced / off = none (OS or app "reduce motion") */
  motion: "full" | "reduced" | "off";
  /** 1 = everything, 0 = the cheapest picture (render time too high) */
  quality: number;
}

// ------------------------------------------------------------------ the sea

function background(ctx: CanvasRenderingContext2D, g: Game, v: View): void {
  const sea = seaColours();
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, sea.a);
  grad.addColorStop(0.55, sea.b);
  grad.addColorStop(1, sea.c);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
  const t = g.t;
  if (v.quality > 0.5) {
    // light rays from the surface, swaying slowly
    ctx.globalAlpha = 0.07;
    ctx.fillStyle = ART.ray;
    for (let i = 0; i < 4; i++) {
      const x = 60 + i * 120 + Math.sin(t * 0.3 + i * 1.7) * 26;
      ctx.beginPath();
      ctx.moveTo(x - 18, 0);
      ctx.lineTo(x + 18, 0);
      ctx.lineTo(x + 70, H);
      ctx.lineTo(x - 10, H);
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  // far kelp
  ctx.strokeStyle = ART.kelp;
  ctx.lineWidth = 5;
  ctx.lineCap = "round";
  for (let i = 0; i < 7; i++) {
    const x = 20 + i * 74;
    const h = 60 + ((i * 37) % 50);
    ctx.beginPath();
    ctx.moveTo(x, H);
    ctx.quadraticCurveTo(x + Math.sin(t * 0.8 + i) * 14, H - h * 0.6, x + Math.sin(t * 0.8 + i + 1) * 10, H - h);
    ctx.stroke();
  }
  // ambient bubbles (positions from time: nothing stored, nothing to update)
  ctx.fillStyle = ART.bubble;
  const n = v.quality > 0.5 ? 14 : 6;
  for (let i = 0; i < n; i++) {
    const speed = 12 + (i % 5) * 5;
    const x = ((i * 97) % W) + Math.sin(t + i) * 4;
    const y = H - ((t * speed + i * 53) % (H + 20));
    ctx.beginPath();
    ctx.arc(x, y, 1 + (i % 3), 0, Math.PI * 2);
    ctx.fill();
  }
  // the sea floor
  ctx.fillStyle = sea.floor;
  ctx.beginPath();
  ctx.moveTo(0, H);
  for (let x = 0; x <= W; x += 40) ctx.lineTo(x, H - 14 - Math.sin(x * 0.03) * 5);
  ctx.lineTo(W, H);
  ctx.closePath();
  ctx.fill();
}

// ------------------------------------------------------------------ creatures

function fish(ctx: CanvasRenderingContext2D, g: Game, f: Fish): void {
  const dir = f.vx >= 0 ? 1 : -1;
  const wag = Math.sin(f.phase) * 0.35;
  const ok = edible(g, f);
  ctx.save();
  ctx.translate(f.x, f.y);
  ctx.scale(dir, 1);
  if (f.kind === "predator") {
    // a long, dark barracuda-like hunter (an original shape)
    const r = f.r;
    ctx.fillStyle = ok ? ART.predatorSafe : ART.predator;
    ctx.beginPath();
    ctx.moveTo(r * 1.5, 0);
    ctx.quadraticCurveTo(r * 0.6, -r * 0.5, -r * 1.1, -r * 0.22);
    ctx.lineTo(-r * 1.1, r * 0.22);
    ctx.quadraticCurveTo(r * 0.6, r * 0.5, r * 1.5, 0);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-r * 1.0, 0);
    ctx.lineTo(-r * 1.6, -r * 0.5 + wag * r * 0.3);
    ctx.lineTo(-r * 1.45, 0);
    ctx.lineTo(-r * 1.6, r * 0.5 + wag * r * 0.3);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = ok ? ART.white : ART.dangerEye; // a red eye: dangerous
    ctx.beginPath();
    ctx.arc(r * 0.95, -r * 0.1, r * 0.11, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = ART.white55;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      ctx.moveTo(r * (1.25 - i * 0.07), r * 0.05);
      ctx.lineTo(r * (1.21 - i * 0.07), r * 0.14);
    }
    ctx.stroke();
  } else {
    const r = f.r;
    const col = f.kind === "gold" ? ART.goldFish : FISH_COLORS[f.hue % FISH_COLORS.length];
    ctx.fillStyle = col;
    ctx.globalAlpha = ok ? 1 : 0.75;
    ctx.beginPath();
    ctx.ellipse(0, 0, r, r * 0.62, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-r * 0.8, 0);
    ctx.lineTo(-r * 1.5, -r * 0.55 + wag * r);
    ctx.lineTo(-r * 1.5, r * 0.55 + wag * r);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
    if (f.kind === "gold") {
      const glint = 0.5 + 0.5 * Math.sin(g.t * 8 + f.phase);
      ctx.fillStyle = glow(0.35 + 0.5 * glint);
      ctx.beginPath();
      ctx.ellipse(r * 0.1, -r * 0.25, r * 0.35, r * 0.12, -0.3, 0, Math.PI * 2);
      ctx.fill();
    } else if (f.kind !== "small") {
      ctx.fillStyle = ART.white35;
      ctx.fillRect(-r * 0.15, -r * 0.55, r * 0.18, r * 1.1);
    }
    if (!ok) {
      ctx.strokeStyle = ART.dangerRing;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.ellipse(0, 0, r, r * 0.62, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = seaColours().dark;
    ctx.beginPath();
    ctx.arc(r * 0.5, -r * 0.12, Math.max(1.2, r * 0.13), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function hazard(ctx: CanvasRenderingContext2D, h: Hazard): void {
  ctx.save();
  ctx.translate(h.x, h.y);
  if (h.kind === "jelly") {
    const pulse = 1 + Math.sin(h.phase * 1.3) * 0.12;
    ctx.fillStyle = ART.jelly;
    ctx.beginPath();
    ctx.ellipse(0, 0, h.r * pulse, h.r * 0.75 / pulse, 0, Math.PI, 0);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = ART.jellyLine;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = -2; i <= 2; i++) {
      const x = i * h.r * 0.35;
      ctx.moveTo(x, 0);
      ctx.quadraticCurveTo(x + Math.sin(h.phase * 2 + i) * 4, h.r * 0.9, x, h.r * 1.7);
    }
    ctx.stroke();
  } else {
    ctx.rotate(h.phase * 0.5);
    ctx.fillStyle = ART.urchin;
    ctx.strokeStyle = ART.urchinLine;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      ctx.moveTo(Math.cos(a) * h.r * 0.7, Math.sin(a) * h.r * 0.7);
      ctx.lineTo(Math.cos(a) * h.r * 1.45, Math.sin(a) * h.r * 1.45);
    }
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, h.r * 0.8, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}


function power(ctx: CanvasRenderingContext2D, p: Power): void {
  const c = POWER_COLORS[p.kind];
  const r = 10 + Math.sin(p.phase * 2) * 0.8;
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.globalAlpha = p.life < 2 ? 0.4 + 0.6 * Math.abs(Math.sin(p.life * 8)) : 1;
  ctx.fillStyle = ART.white12;
  ctx.strokeStyle = c;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = c;
  ctx.strokeStyle = c;
  ctx.lineWidth = 2;
  ctx.beginPath();
  if (p.kind === "magnet") {
    ctx.arc(0, 0, 4.5, Math.PI, 0);
    ctx.moveTo(-4.5, 0);
    ctx.lineTo(-4.5, 4);
    ctx.moveTo(4.5, 0);
    ctx.lineTo(4.5, 4);
    ctx.stroke();
  } else if (p.kind === "frenzy") {
    ctx.moveTo(1.5, -6);
    ctx.lineTo(-3.5, 1);
    ctx.lineTo(0, 1);
    ctx.lineTo(-1.5, 6);
    ctx.lineTo(3.5, -1);
    ctx.lineTo(0, -1);
    ctx.closePath();
    ctx.fill();
  } else if (p.kind === "shield") {
    ctx.moveTo(0, -6);
    ctx.lineTo(5, -3.5);
    ctx.quadraticCurveTo(5, 3.5, 0, 6);
    ctx.quadraticCurveTo(-5, 3.5, -5, -3.5);
    ctx.closePath();
    ctx.fill();
  } else {
    ctx.arc(0, 0, 5, 0, Math.PI * 2);
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -3.5);
    ctx.moveTo(0, 0);
    ctx.lineTo(2.5, 1.5);
    ctx.stroke();
  }
  ctx.restore();
}

function shark(ctx: CanvasRenderingContext2D, g: Game, v: View): void {
  const s = g.shark;
  const sk = v.skin;
  const r = sharkR(g);
  if (s.inv > 0 && Math.floor(s.inv * 12) % 2 === 0) return; // blink after a hit
  ctx.save();
  ctx.translate(s.x, s.y);
  ctx.rotate(s.angle);
  // facing left: flip so the belly stays down
  if (Math.cos(s.angle) < 0) ctx.scale(1, -1);
  const sq = s.squash * 0.12;
  ctx.scale(1 + sq, 1 - sq);
  const L = r * 1.9;
  const wag = Math.sin(s.tail) * 0.28;
  if (sk.pattern === "ghost") ctx.globalAlpha = 0.72;
  if (g.shield) {
    ctx.strokeStyle = ART.shield;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(0, 0, L * 0.95, r * 1.1, 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  // tail fin
  ctx.fillStyle = sk.fin;
  ctx.beginPath();
  ctx.moveTo(-L * 0.72, 0);
  ctx.lineTo(-L * 1.12, -r * 0.85 + wag * r);
  ctx.lineTo(-L * 0.98, wag * r * 0.4);
  ctx.lineTo(-L * 1.08, r * 0.6 + wag * r);
  ctx.closePath();
  ctx.fill();
  // dorsal fin
  ctx.beginPath();
  ctx.moveTo(-r * 0.25, -r * 0.55);
  ctx.lineTo(-r * 0.62, -r * 1.25);
  ctx.lineTo(r * 0.35, -r * 0.52);
  ctx.closePath();
  ctx.fill();
  // body
  const open = s.chomp;
  ctx.fillStyle = sk.body;
  ctx.beginPath();
  ctx.moveTo(L * 0.62, -open * r * 0.12);
  ctx.bezierCurveTo(L * 0.45, -r * 0.78, -L * 0.3, -r * 0.7, -L * 0.78, -r * 0.08);
  ctx.lineTo(-L * 0.78, r * 0.12);
  ctx.bezierCurveTo(-L * 0.3, r * 0.62, L * 0.4, r * 0.62, L * 0.6, r * 0.1 + open * r * 0.28);
  ctx.closePath();
  ctx.fill();
  // a soft light outline: the shark always stands out from the water
  ctx.strokeStyle = ART.trail;
  ctx.lineWidth = 1.2;
  ctx.stroke();
  // belly
  ctx.fillStyle = sk.belly;
  ctx.beginPath();
  ctx.moveTo(L * 0.5, r * 0.18 + open * r * 0.22);
  ctx.bezierCurveTo(L * 0.25, r * 0.55, -L * 0.3, r * 0.5, -L * 0.62, r * 0.12);
  ctx.bezierCurveTo(-L * 0.2, r * 0.22, L * 0.2, r * 0.15, L * 0.5, r * 0.18 + open * r * 0.22);
  ctx.fill();
  // patterns
  if (sk.pattern === "stripes") {
    ctx.strokeStyle = sk.accent;
    ctx.lineWidth = Math.max(1.5, r * 0.12);
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      const x = -L * 0.45 + i * L * 0.22;
      ctx.moveTo(x, -r * 0.55);
      ctx.lineTo(x - r * 0.12, -r * 0.12);
    }
    ctx.stroke();
  } else if (sk.pattern === "spots" || sk.pattern === "dots") {
    ctx.fillStyle = sk.accent;
    for (let i = 0; i < 5; i++) {
      const glow = sk.pattern === "dots" ? 0.55 + 0.45 * Math.sin(g.t * 3 + i) : 0.9;
      ctx.globalAlpha = glow * (sk.pattern === "dots" ? 1 : 0.8);
      ctx.beginPath();
      ctx.arc(-L * 0.5 + i * L * 0.2, -r * (0.25 + (i % 2) * 0.15), r * (sk.pattern === "dots" ? 0.07 : 0.1), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  } else if (sk.pattern === "glow") {
    ctx.strokeStyle = sk.accent;
    ctx.globalAlpha = 0.6 + 0.3 * Math.sin(g.t * 4);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(L * 0.55, -r * 0.1);
    ctx.bezierCurveTo(L * 0.4, -r * 0.7, -L * 0.3, -r * 0.62, -L * 0.75, -r * 0.05);
    ctx.stroke();
    ctx.globalAlpha = 1;
  } else if (sk.pattern === "shine") {
    const x = ((g.t * 0.8) % 2) * L * 1.6 - L * 0.8;
    ctx.fillStyle = ART.white35;
    ctx.beginPath();
    ctx.moveTo(x, -r * 0.7);
    ctx.lineTo(x + r * 0.3, -r * 0.7);
    ctx.lineTo(x + r * 0.05, r * 0.5);
    ctx.lineTo(x - r * 0.25, r * 0.5);
    ctx.closePath();
    ctx.fill();
  }
  // pectoral fin
  ctx.fillStyle = sk.fin;
  ctx.beginPath();
  ctx.moveTo(r * 0.2, r * 0.3);
  ctx.lineTo(-r * 0.35, r * 0.95 + Math.sin(s.tail * 0.7) * r * 0.1);
  ctx.lineTo(-r * 0.05, r * 0.3);
  ctx.closePath();
  ctx.fill();
  // gills
  ctx.strokeStyle = ART.shade;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i < 3; i++) {
    ctx.moveTo(L * 0.18 - i * r * 0.14, -r * 0.18);
    ctx.lineTo(L * 0.12 - i * r * 0.14, r * 0.12);
  }
  ctx.stroke();
  // eye
  ctx.fillStyle = sk.eye;
  ctx.beginPath();
  ctx.arc(L * 0.38, -r * 0.22, Math.max(1.4, r * 0.1), 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = ART.white80;
  ctx.beginPath();
  ctx.arc(L * 0.38 + r * 0.03, -r * 0.25, Math.max(0.5, r * 0.035), 0, Math.PI * 2);
  ctx.fill();
  // teeth while chomping
  if (open > 0.15) {
    ctx.fillStyle = ART.white;
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const x = L * (0.56 - i * 0.07);
      ctx.moveTo(x, r * 0.02);
      ctx.lineTo(x - r * 0.05, r * 0.14 * open + r * 0.04);
      ctx.lineTo(x - r * 0.1, r * 0.02);
    }
    ctx.fill();
  }
  ctx.restore();
}

// ------------------------------------------------------------------ the frame

export function draw(ctx: CanvasRenderingContext2D, g: Game, v: View): void {
  ctx.setTransform(v.scale, 0, 0, v.scale, 0, 0);
  if (v.motion === "full" && g.shake > 0) {
    const a = g.shake * 0.5;
    ctx.translate((Math.sin(g.t * 91) * a) | 0, (Math.cos(g.t * 77) * a) | 0);
  }
  background(ctx, g, v);
  for (const p of g.powers) power(ctx, p);
  for (const f of g.fish) fish(ctx, g, f);
  for (const h of g.hazards) hazard(ctx, h);
  shark(ctx, g, v);
  // particles
  for (const p of g.particles) {
    const a = Math.max(0, p.life / p.max);
    ctx.globalAlpha = a;
    if (p.kind === 0) {
      ctx.strokeStyle = ART.pop;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.stroke();
    } else {
      ctx.fillStyle = p.kind === 1 ? ART.spark : FISH_COLORS[p.hue % FISH_COLORS.length];
      ctx.fillRect(p.x - p.size, p.y - p.size, p.size * 2, p.size * 2);
    }
  }
  ctx.globalAlpha = 1;
  // floating texts
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const p of g.popups) {
    ctx.globalAlpha = Math.min(1, p.life * 2.5);
    ctx.font = `700 ${p.tone === 2 ? 15 : 12}px Archivo, "Segoe UI", system-ui, sans-serif`;
    ctx.lineWidth = 3;
    ctx.strokeStyle = ART.textEdge;
    ctx.strokeText(p.text, p.x, p.y);
    ctx.fillStyle = TONES[p.tone] ?? ART.white;
    ctx.fillText(p.text, p.x, p.y);
  }
  ctx.globalAlpha = 1;
  // a short flash on a hit / power-up (never with reduced motion)
  if (v.motion === "full" && g.flash > 0) {
    ctx.fillStyle = glow(Math.min(0.18, g.flash * 0.7));
    ctx.fillRect(-10, -10, W + 20, H + 20);
  }
  // frenzy / magnet: a soft coloured edge
  if (g.frenzy > 0 || g.magnet > 0) {
    ctx.strokeStyle = g.frenzy > 0 ? ART.frenzyEdge : ART.hurtEdge;
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, W - 4, H - 4);
  }
}

/** A still shark for the skin picker. */
export function drawPreview(ctx: CanvasRenderingContext2D, g: Game, skin: Skin, px: number): void {
  const s = g.shark;
  Object.assign(s, { x: W / 2, y: H / 2, angle: 0, size: 1, inv: 0, chomp: 0, squash: 0, tail: 0.6 });
  const k = px / 60; // the shark (about 46 world units long) fills the preview
  ctx.setTransform(k, 0, 0, k, -W / 2 * k + px / 2, -H / 2 * k + (px * 0.62) / 2);
  ctx.clearRect(W / 2 - 40, H / 2 - 30, 80, 60);
  shark(ctx, g, { scale: k, skin, motion: "off", quality: 1 });
}
