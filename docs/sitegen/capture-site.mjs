// Screenshots + the short demo video for the website (docs/site), from a SharkyClips that runs on a
// FRESH settings folder with the synthetic demo stream (docs/demo/make_demo.py) and the drawn
// slideshow sample (docs/demo/make_slideshow_sample.py photos). No real person, game or account.
//
//   cd frontend && node ../docs/sitegen/capture-site.mjs http://127.0.0.1:8131 <project-id> <slideshow-id> <out-dir>
//   python docs/sitegen/build.py --shots <out-dir>/shots --og
//
// Writes <out-dir>/shots/*.png (1440 x 900, Classic dark), <out-dir>/demo.mp4 + demo-poster.webp
// (needs ffmpeg). Microsoft Edge headless (Playwright's Chromium can't play H.264).
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { apiHeaders } from "../../frontend/scripts/api-token.mjs";

const { chromium } = createRequire(join(process.cwd(), "index.js"))("playwright");
const [base, pid, sid, out] = process.argv.slice(2);
if (!out) throw new Error("usage: node capture-site.mjs <base> <project-id> <slideshow-id> <out-dir>");
const shots = join(out, "shots");
mkdirSync(shots, { recursive: true });
const H = await apiHeaders(base);
const api = (method, path, body) =>
  fetch(base + path, { method, headers: { "content-type": "application/json", ...H }, body: body && JSON.stringify(body) }).then((r) => r.json());
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const app = await api("GET", "/api/app");
await api("POST", "/api/app/whats-new-seen", { version: app.version });
const browser = await chromium.launch({ channel: "msedge" });

async function context(extra = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...extra });
  await ctx.addInitScript(() => {
    localStorage.setItem("cf-theme", "dark");
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    sessionStorage.setItem("sc-splash-shown", "1");
  });
  return ctx;
}
async function settle(page, sel, ms = 1500) {
  await page.waitForLoadState("load");
  if (sel) await page.waitForSelector(sel, { timeout: 30000 });
  await page.evaluate(() => document.fonts.ready);
  await sleep(ms);
}
const mode = (m) => api("PUT", "/api/easy/settings", { mode: m, tour_done: true });

const SHOTS = [
  ["easy-home", "easy", "#/", ".ez-create"],
  ["easy-project", "easy", `#/p/${pid}`, ".share-grid", null, 3500],
  ["share", "easy", `#/p/${pid}/share`, ".share-grid", async (page) => {
    await page.locator(".share-selbtns .btn").first().click();
    await page.locator('[data-testid="share-review"]').click();
    await page.waitForSelector(".share-plats");
  }],
  ["pro-project", "pro", `#/p/${pid}`, ".proj-main", null, 3500],
  ["slideshow", "easy", `#/slideshow/${sid}`, ".ss-grid", null, 3000],
  ["looks", "easy", "#/settings", "#personalization", async (page) => {
    await page.locator("#personalization").scrollIntoViewIfNeeded();
    await page.evaluate(() => {
      const el = document.querySelector("#personalization");
      window.scrollBy(0, el.getBoundingClientRect().top - 90);
    });
  }],
];
for (const [name, m, hash, sel, act, ms] of SHOTS) {
  await mode(m);
  const ctx = await context();
  const page = await ctx.newPage();
  await page.goto(`${base}/${hash}`);
  await settle(page, sel, ms ?? 1500);
  if (act) {
    await act(page);
    await sleep(1500);
  }
  await page.screenshot({ path: join(shots, `${name}.png`) });
  console.log("shot", name);
  await ctx.close();
}

// ---- demo video: Easy mode, home -> a stream with its clips -> play one -> Share window
await mode("easy");
const vdir = join(out, ".video");
rmSync(vdir, { recursive: true, force: true });
const W = 1280, Hh = 760;
const ctx = await context({ viewport: { width: W, height: Hh }, recordVideo: { dir: vdir, size: { width: W, height: Hh } } });
const page = await ctx.newPage();
const t0 = Date.now();
await page.goto(`${base}/#/`);
await settle(page, ".ez-create", 800);
const tStart = (Date.now() - t0) / 1000;
await sleep(1800);
await page.goto(`${base}/#/p/${pid}`);
await settle(page, ".share-grid", 2500);
// play the first clip (short timeouts: a missed click must not leave a minute of still picture)
await page.locator(".sh-card button[aria-label]").first().click({ timeout: 3000 }).catch(() => {});
await sleep(3500);
await page.goto(`${base}/#/p/${pid}/share`);
await settle(page, ".share-grid", 1000);
await page.locator(".share-selbtns .btn").first().click();
await sleep(900);
await page.locator('[data-testid="share-review"]').click();
await page.waitForSelector(".share-plats");
await sleep(3500);
await ctx.close();
const webm = readdirSync(vdir).find((f) => f.endsWith(".webm"));
renameSync(join(vdir, webm), join(vdir, "demo.webm"));
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", tStart.toFixed(2), "-i", join(vdir, "demo.webm"),
  "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-movflags", "+faststart", "-an",
  join(out, "demo.mp4")]);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", "4", "-i", join(out, "demo.mp4"), "-frames:v", "1",
  "-c:v", "libwebp", "-quality", "78", join(out, "demo-poster.webp")]);
rmSync(vdir, { recursive: true, force: true });
await browser.close();
console.log("done ->", out);
