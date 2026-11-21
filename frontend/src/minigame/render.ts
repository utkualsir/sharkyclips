// The waiting mini game (1.2.59): drawing. Everything is drawn in code on a 2D canvas (no image
// files, no fonts to download), so the game adds only a few KB to the app.
import { edible, H, sharkR, W, type Fish, type Game, type Hazard, type Power } from "./engine";

export interface Skin {
  body: string;
  belly: string;
  fin: string;
  eye: string;
  /** "" | stripes | spots | glow | ghost | dots | shine */
  pattern: string;
  accent: string;
}

export const SKINS: Record<string, Skin> = {
  classic: { body: "#6f8fb8", belly: "#eef3fa", fin: "#5a7aa3", eye: "#0e1a33", pattern: "", accent: "#d9b56a" },
  reef: { body: "#3fa7a0", belly: "#e9fbf6", fin: "#2f8a84", eye: "#0e1a33", pattern: "spots", accent: "#ffcf5c" },
  tiger: { body: "#c98a3c", belly: "#fff2dc", fin: "#a86e2a", eye: "#1b1206", pattern: "stripes", accent: "#3b2410" },
  neon: { body: "#2a2f7a", belly: "#c9f7ff", fin: "#1f2463", eye: "#ffffff", pattern: "glow", accent: "#3ef0ff" },
  ghost: { body: "#cfd8ea", belly: "#ffffff", fin: "#b7c3dc", eye: "#4a5a80", pattern: "ghost", accent: "#ffffff" },
  deep: { body: "#1c2740", belly: "#40507a", fin: "#141d33", eye: "#9ff7d8", pattern: "dots", accent: "#7dffcf" },
  gold: { body: "#d9b56a", belly: "#fff6d8", fin: "#b8913f", eye: "#2a1d05", pattern: "shine", accent: "#ffffff" },
};

const FISH_COLORS = ["#ff8a5b", "#ffd35b", "#7fd36b", "#5bc8ff", "#c38bff", "#ff6fa8", "#5be0c8", "#ffe08a"];
const TONES = ["#ffffff", "#ffe08a", "#7df9ff", "#ff8a8a"];

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
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#1b5b8f");
  grad.addColorStop(0.55, "#0f3a66");
  grad.addColorStop(1, "#08203f");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
  const t = g.t;
  if (v.quality > 0.5) {
    // light rays from the surface, swaying slowly
    ctx.globalAlpha = 0.07;
    ctx.fillStyle = "#cfe9ff";
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
  ctx.strokeStyle = "rgba(40, 110, 110, 0.45)";
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
  ctx.fillStyle = "rgba(220, 240, 255, 0.25)";
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
  ctx.fillStyle = "#0a2a4a";
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
    ctx.fillStyle = ok ? "#7a8a99" : "#3d4a5c";
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
    ctx.fillStyle = ok ? "#ffffff" : "#ff5d5d"; // a red eye: dangerous
    ctx.beginPath();
    ctx.arc(r * 0.95, -r * 0.1, r * 0.11, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      ctx.moveTo(r * (1.25 - i * 0.07), r * 0.05);
      ctx.lineTo(r * (1.21 - i * 0.07), r * 0.14);
    }
    ctx.stroke();
  } else {
    const r = f.r;
    const col = f.kind === "gold" ? "#ffd44d" : FISH_COLORS[f.hue % FISH_COLORS.length];
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
      ctx.fillStyle = `rgba(255,255,255,${0.35 + 0.5 * glint})`;
      ctx.beginPath();
      ctx.ellipse(r * 0.1, -r * 0.25, r * 0.35, r * 0.12, -0.3, 0, Math.PI * 2);
      ctx.fill();
    } else if (f.kind !== "small") {
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.fillRect(-r * 0.15, -r * 0.55, r * 0.18, r * 1.1);
    }
    if (!ok) {
      ctx.strokeStyle = "rgba(255, 120, 120, 0.8)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.ellipse(0, 0, r, r * 0.62, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = "#0b1426";
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
    ctx.fillStyle = "rgba(214, 140, 255, 0.85)";
    ctx.beginPath();
    ctx.ellipse(0, 0, h.r * pulse, h.r * 0.75 / pulse, 0, Math.PI, 0);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "rgba(230, 180, 255, 0.8)";
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
    ctx.fillStyle = "#2b1d3a";
    ctx.strokeStyle = "#e05bff";
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

const POWER_COLORS: Record<string, string> = { magnet: "#ff6b6b", frenzy: "#ffd35b", shield: "#6bd6ff", time: "#8cff9e" };

function power(ctx: CanvasRenderingContext2D, p: Power): void {
  const c = POWER_COLORS[p.kind];
  const r = 10 + Math.sin(p.phase * 2) * 0.8;
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.globalAlpha = p.life < 2 ? 0.4 + 0.6 * Math.abs(Math.sin(p.life * 8)) : 1;
  ctx.fillStyle = "rgba(255,255,255,0.12)";
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
    ctx.strokeStyle = "rgba(120, 220, 255, 0.7)";
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
  ctx.strokeStyle = "rgba(235, 245, 255, 0.55)";
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
    ctx.fillStyle = "rgba(255,255,255,0.35)";
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
  ctx.strokeStyle = "rgba(0,0,0,0.25)";
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
  ctx.fillStyle = "rgba(255,255,255,0.8)";
  ctx.beginPath();
  ctx.arc(L * 0.38 + r * 0.03, -r * 0.25, Math.max(0.5, r * 0.035), 0, Math.PI * 2);
  ctx.fill();
  // teeth while chomping
  if (open > 0.15) {
    ctx.fillStyle = "#ffffff";
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
      ctx.strokeStyle = "rgba(220,240,255,0.9)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.stroke();
    } else {
      ctx.fillStyle = p.kind === 1 ? "#fff3b0" : FISH_COLORS[p.hue % FISH_COLORS.length];
      ctx.fillRect(p.x - p.size, p.y - p.size, p.size * 2, p.size * 2);
    }
  }
  ctx.globalAlpha = 1;
  // floating texts
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const p of g.popups) {
    ctx.globalAlpha = Math.min(1, p.life * 2.5);
    ctx.font = `700 ${p.tone === 2 ? 15 : 12}px system-ui, sans-serif`;
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(5, 15, 35, 0.8)";
    ctx.strokeText(p.text, p.x, p.y);
    ctx.fillStyle = TONES[p.tone] ?? "#fff";
    ctx.fillText(p.text, p.x, p.y);
  }
  ctx.globalAlpha = 1;
  // a short flash on a hit / power-up (never with reduced motion)
  if (v.motion === "full" && g.flash > 0) {
    ctx.fillStyle = `rgba(255,255,255,${Math.min(0.18, g.flash * 0.7)})`;
    ctx.fillRect(-10, -10, W + 20, H + 20);
  }
  // frenzy / magnet: a soft coloured edge
  if (g.frenzy > 0 || g.magnet > 0) {
    ctx.strokeStyle = g.frenzy > 0 ? "rgba(255, 211, 91, 0.55)" : "rgba(255, 107, 107, 0.45)";
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
