// Preview-vs-render check (headless browser, 1.2.23).
//
// 1. Sizes: selecting a clip whose transcript has an endless Whisper "word" must not stretch the
//    player or the 9:16 preview (the 1.2.22 "zooms in and shifts" report) at laptop sizes.
// 2. Pixels: for the split, crop and fit layouts with smart zoom on, the 9:16 preview canvas is
//    compared with a picture drawn here from the SERVER's render plan only: the crop rects the
//    renderer cuts (plan "geometry") and the zoom / shake the render's filters apply at that
//    moment (plan "samples"). Any drift between the preview and the renderer fails the check.
//
//   python frontend/scripts/layout-fixture.py <dir>          (prints the project id)
//   SHARKYCLIPS_HOME=<dir>/home python backend/cli.py serve --port 8799 --no-browser
//   node frontend/scripts/preview-check.mjs http://127.0.0.1:8799 <project-id> [screenshot-dir]
//
// LAYOUT_CHANNEL=msedge uses the installed Edge; CI uses Playwright's Chromium (the fixture's
// source video is VP9 for it). Changes the fixture's render settings. Exit code 1 on failure.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  ({ chromium } = req("playwright"));
}

/** Switch Easy / Pro on the server; a slow CI runner may stall one request: wait longer, try again. */
async function putMode(request, url, mode) {
  for (let i = 1; ; i++) {
    try {
      return await request.put(url, { data: { mode }, timeout: 60000 });
    } catch (e) {
      if (i >= 3) throw e;
    }
  }
}

const [base, pid, shotDir] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node preview-check.mjs <base-url> <project-id> [screenshot-dir]");
if (shotDir) mkdirSync(shotDir, { recursive: true });
const P = encodeURIComponent(pid);
const CLIP = "c01"; // its transcript has the endless word (layout-fixture.py)
const SIZES = [[1280, 720], [1366, 768], [1536, 864], [1707, 960], [1707, 1067]];
const MAX_DIFF = 2.5; // mean |difference| per channel (0-255) the check accepts
const problems = [];

const browser = await chromium.launch({ channel: process.env.LAYOUT_CHANNEL || undefined, headless: true });
const api = (await browser.newContext()).request;
await putMode(api, `${base}/api/easy/settings`, "pro");

async function openProject(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await ctx.addInitScript(() => {
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("sc-splash-shown", "1");
  });
  const page = await ctx.newPage();
  await page.goto(`${base}/#/p/${P}`);
  await page.waitForSelector(`.cand[data-cand="${CLIP}"]`, { timeout: 30000 });
  await page.click(`.cand[data-cand="${CLIP}"]`);
  await page.waitForTimeout(1200); // plan + transcript load
  return { ctx, page };
}

// ------------------------------------------------------------------ 1. sizes

await api.put(`${base}/api/projects/${P}/review`, { data: { options: { layout: "auto", subtitles: "bold", hook: true, zoom: "strong" } } });
for (const [w, h] of SIZES) {
  const { ctx, page } = await openProject(w, h);
  await page.waitForSelector(".tx-words .tx-w", { timeout: 15000 }).catch(() => {});
  const m = await page.evaluate(() => {
    const r = (s) => document.querySelector(s)?.getBoundingClientRect();
    const words = [...document.querySelectorAll(".tx-words .tx-w")].map((e) => e.textContent.trim());
    return { iw: innerWidth, ih: innerHeight, sw: document.documentElement.scrollWidth, player: r(".player"),
      frame: r(".vprev-frame"), main: r(".proj-main"), longest: Math.max(0, ...words.map((x) => x.length)), n: words.length };
  });
  const tag = `${w}x${h}`;
  if (!m.n) problems.push(`${tag}: the transcript editor shows no words`);
  if (m.longest > 41) problems.push(`${tag}: a ${m.longest}-letter word reached the transcript (not cleaned)`);
  if (m.sw > m.iw + 1) problems.push(`${tag}: page scrolls sideways (${m.sw} > ${m.iw})`);
  if (m.player.right > m.main.right + 1) problems.push(`${tag}: player sticks out of its column (${Math.round(m.player.right)} > ${Math.round(m.main.right)})`);
  if (m.frame.height > m.ih * 0.8 + 2) problems.push(`${tag}: 9:16 preview taller than the window allows (${Math.round(m.frame.height)} px)`);
  if (Math.abs(m.frame.height - Math.min(m.player.height, m.ih * 0.8)) > 4) problems.push(`${tag}: preview ${Math.round(m.frame.height)} px vs player ${Math.round(m.player.height)} px high`);
  if (shotDir) await page.screenshot({ path: join(shotDir, `preview-size-${tag}.png`) });
  console.log(`${tag}: player ${Math.round(m.player.width)}x${Math.round(m.player.height)}, preview ${Math.round(m.frame.width)}x${Math.round(m.frame.height)}, longest word ${m.longest}`);
  await ctx.close();
}

// ------------------------------------------------------------------ 2. pixels

/** Runs in the page: seek, then compare the preview canvas with the server-plan reference. */
async function compareAt(page, t, plan) {
  await page.evaluate(async (t) => {
    const v = document.querySelector(".player video");
    v.pause();
    await new Promise((ok) => {
      v.addEventListener("seeked", ok, { once: true });
      v.currentTime = t;
    });
    await new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));
  }, t);
  const actual = await page.evaluate(() => document.querySelector(".player video").currentTime);
  const res = await page.request.post(`${base}/api/projects/${P}/candidates/${CLIP}/plan`, { data: { samples: [actual] } });
  const sample = (await res.json()).samples[0];
  return page.evaluate(([geo, s]) => {
    const v = document.querySelector(".player video");
    const pv = document.querySelector(".vprev-frame canvas");
    const W = 360;
    const H = 640;
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    const cover = ([x, y, w, h], dw, dh) => (w / h > dw / dh ? [x + (w - h * dw / dh) / 2, y, h * dw / dh, h] : [x, y + (h - w * dh / dw) / 2, w, w * dh / dw]);
    const zoom = ([x, y, w, h], z, cy = 0.5) => [x + (w - w / z) / 2, y + h * cy - h * cy / z, w / z, h / z];
    const draw = (z) => {
      const c = document.createElement("canvas");
      c.width = W;
      c.height = H;
      const g = c.getContext("2d");
      g.imageSmoothingEnabled = true;
      g.imageSmoothingQuality = "high";
      const [k, dx, dy] = s.shake;
      if (k > 1.0001) g.setTransform(k, 0, 0, k, -(0.5 - 0.5 / k + dx) * W * k, -(0.5 - 0.5 / k + dy) * H * k);
      const top = (geo.split_top / geo.out[0]) * W;
      const box = { x: 0, y: 0, w: W, h: H };
      if (geo.layout === "split") {
        const px = (r) => [r[0] * vw, r[1] * vh, r[2] * vw, r[3] * vh];
        g.drawImage(v, ...zoom(px(geo.cam), z ? s.cam : 1, 0.45), 0, 0, W, top);
        g.drawImage(v, ...zoom(cover(px(geo.game), W, H - top), z ? s.scene : 1), 0, top, W, H - top);
      } else if (geo.layout === "crop") {
        g.drawImage(v, ...zoom(cover([0, 0, vw, vh], W, H), z ? s.full : 1), 0, 0, W, H);
      } else {
        const sc = Math.min(W / vw, H / vh);
        Object.assign(box, { x: (W - vw * sc) / 2, y: (H - vh * sc) / 2, w: vw * sc, h: vh * sc });
        g.drawImage(v, ...zoom([0, 0, vw, vh], z ? s.full : 1), box.x, box.y, box.w, box.h);
      }
      return { c, box };
    };
    // the preview canvas at its real pixel size -> 360x640 for the comparison
    const pc = document.createElement("canvas");
    pc.width = W;
    pc.height = H;
    pc.getContext("2d").drawImage(pv, 0, 0, W, H);
    const diff = (a, b, box) => {
      const x = Math.ceil(box.x) + 2;
      const y = Math.ceil(box.y) + 2;
      const w = Math.floor(box.w) - 4;
      const h = Math.floor(box.h) - 4;
      const da = a.getContext("2d").getImageData(x, y, w, h).data;
      const db = b.getContext("2d").getImageData(x, y, w, h).data;
      let sum = 0;
      for (let i = 0; i < da.length; i += 4) sum += Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]);
      return sum / (da.length / 4) / 3;
    };
    const ref = draw(true);
    const flat = draw(false); // the same without any zoom: shows the check can see a zoom
    return { t: v.currentTime, diff: diff(pc, ref.c, ref.box), vsFlat: diff(pc, flat.c, ref.box), zoomed: Math.max(s.scene, s.cam, s.full, s.shake[0]) };
  }, [plan.geometry, sample]);
}

const TIMES = [1.2, 1.75, 2.1, 2.6, 3.4]; // c01 = 1.0-3.6 s, smart zoom pulse around 2.0 s
for (const layout of ["auto", "crop", "fit"]) {
  await api.put(`${base}/api/projects/${P}/review`, {
    data: { options: { layout, zoom: "strong", subtitles: "none", hook: false, brand: false, loop: false } },
  });
  const { ctx, page } = await openProject(1366, 768);
  const plan = await (await page.request.post(`${base}/api/projects/${P}/candidates/${CLIP}/plan`, { data: {} })).json();
  if (!plan.geometry) {
    problems.push(`${layout}: the plan has no geometry`);
    await ctx.close();
    continue;
  }
  if (!plan.pulses?.length || plan.zoom_level <= 1) problems.push(`${layout}: fixture clip has no smart zoom to check`);
  const ok = await page.evaluate(() => document.querySelector(".player video").readyState >= 2 || new Promise((r) => {
    const v = document.querySelector(".player video");
    v.addEventListener("loadeddata", () => r(true), { once: true });
    setTimeout(() => r(v.readyState >= 2), 8000);
  }));
  if (!ok) {
    problems.push(`${layout}: the browser can't play the fixture video`);
    await ctx.close();
    continue;
  }
  let sawZoom = false;
  for (const t of TIMES) {
    const r = await compareAt(page, t, plan);
    const line = `${plan.geometry.layout} t=${r.t.toFixed(2)} zoom ${r.zoomed.toFixed(3)}: diff ${r.diff.toFixed(2)} (unzoomed ${r.vsFlat.toFixed(2)})`;
    console.log(line);
    if (r.diff > MAX_DIFF) problems.push(`preview differs from the render plan: ${line}`);
    if (r.zoomed > 1.05) {
      sawZoom = true;
      if (r.vsFlat < r.diff + 1) problems.push(`check can't tell zoomed from unzoomed: ${line}`);
    }
    if (shotDir) await page.locator(".vprev-frame").screenshot({ path: join(shotDir, `preview-${plan.geometry.layout}-${t}.png`) });
  }
  if (!sawZoom) problems.push(`${layout}: no sampled moment was zoomed`);
  await ctx.close();
}

await browser.close();
if (problems.length) {
  console.log(`\n${problems.length} problem(s):\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log("\nPreview matches the render plan.");
