// Takes the README screenshots (dark + light), the demo GIF and the social preview image from a
// running SharkyClips with the synthetic demo project (docs/demo/make_demo.py). No real user data.
//
//   1. python docs/demo/make_demo.py <dir>      -> a 6-minute synthetic stream + its chat log
//   2. Start SharkyClips on a FRESH settings folder (no accounts, nothing personal in the shots):
//        SHARKYCLIPS_HOME=<empty dir> python backend/cli.py serve --no-browser --port 8131
//      Import the video in Easy mode, import the chat log (Project -> Chat) before the highlights
//      run, and wait until Easy mode has rendered the clips.
//   3. From frontend/ (it has Playwright):  node ../docs/capture.mjs http://127.0.0.1:8131 <project-id> ../docs
//
// Uses Microsoft Edge ("msedge" channel, headless): Playwright's own Chromium can't play H.264.
// Needs ffmpeg on PATH for the GIF.
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const { chromium } = createRequire(join(process.cwd(), "index.js"))("playwright");

const [base = "http://127.0.0.1:8131", pid, outDir = "docs"] = process.argv.slice(2);
if (!pid) throw new Error("usage: node capture.mjs <base-url> <project-id> <out-dir>");
const shots = join(outDir, "screenshots");
mkdirSync(shots, { recursive: true });
const api = (method, path, body) =>
  fetch(base + path, { method, headers: { "content-type": "application/json" }, body: body && JSON.stringify(body) }).then((r) =>
    r.json(),
  );
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge" });

async function context(theme, extra = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...extra });
  await ctx.addInitScript((t) => {
    localStorage.setItem("cf-theme", t);
    localStorage.setItem("cf-lang", "en");
    sessionStorage.setItem("sc-splash-shown", "1"); // no start-up splash in the shots
  }, theme);
  return ctx;
}

async function settle(page, ms = 1800) {
  // (no "networkidle": the live job stream keeps a connection open)
  await page.waitForLoadState("load");
  await page.evaluate(() => document.fonts.ready);
  await sleep(ms);
}

const mode = (m) => api("PUT", "/api/easy/settings", { mode: m, tour_done: true });
const app = await api("GET", "/api/app");
await api("POST", "/api/app/whats-new-seen", { version: app.version }); // no "What's new" popup

// ------------------------------------------------------------- Easy mode (the default UI)
await mode("easy");
for (const theme of ["dark", "light"]) {
  const ctx = await context(theme);
  const page = await ctx.newPage();
  const shot = (name) => page.screenshot({ path: join(shots, `${name}-${theme}.png`) });
  await page.goto(`${base}/#/`);
  await settle(page);
  await shot("easy-home");
  await page.goto(`${base}/#/p/${pid}`);
  await settle(page, 3500);
  await shot("easy-project");
  await page.getByRole("button", { name: /^Publish/ }).first().click();
  await settle(page, 2500);
  await shot("publish");
  await ctx.close();
}

// ------------------------------------------------------------- Pro mode
await mode("pro");
for (const theme of ["dark", "light"]) {
  const ctx = await context(theme);
  const page = await ctx.newPage();
  const shot = (name) => page.screenshot({ path: join(shots, `${name}-${theme}.png`) });
  await page.goto(`${base}/#/`);
  await settle(page);
  await shot("library");
  await page.goto(`${base}/#/p/${pid}`);
  await settle(page, 3500);
  await shot("project");
  await page.getByRole("tab", { name: /Clips/ }).click();
  await settle(page, 2500);
  await shot("clips");
  await page.goto(`${base}/#/settings`);
  await settle(page);
  await shot("settings");
  await ctx.close();
}
await mode("easy");

// ------------------------------------------------------------- demo GIF: Easy mode, home -> clips -> publish
const videoDir = join(outDir, ".video");
rmSync(videoDir, { recursive: true, force: true });
const W = 1280, H = 760;
const ctx = await context("dark", { viewport: { width: W, height: H }, recordVideo: { dir: videoDir, size: { width: W, height: H } } });
const page = await ctx.newPage();
const t0 = Date.now();
await page.goto(`${base}/#/`);
await settle(page, 1200);
const tStart = (Date.now() - t0) / 1000;
await sleep(1500);
await page.goto(`${base}/#/p/${pid}`); // open the stream: its clips, already rendered
await settle(page, 3500);
const card = page.locator("video").first();
await card.scrollIntoViewIfNeeded().catch(() => {});
await card.hover().catch(() => {});
await sleep(2500);
await page.getByRole("button", { name: /^Publish/ }).first().click();
await sleep(3500);
await page.mouse.wheel(0, 400);
await sleep(2000);
await ctx.close();
const webm = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
renameSync(join(videoDir, webm), join(videoDir, "demo.webm"));
const filter = [
  `[0:v]trim=start=${tStart.toFixed(2)},setpts=PTS-STARTPTS,fps=10,scale=960:-1:flags=lanczos,split[x][y]`,
  "[x]palettegen=max_colors=128:stats_mode=diff[p]",
  "[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
].join(";");
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", join(videoDir, "demo.webm"), "-filter_complex", filter, join(outDir, "demo.gif")]);
rmSync(videoDir, { recursive: true, force: true });

// ------------------------------------------------------------- social preview (1280x640)
const sp = await browser.newContext({ viewport: { width: 1280, height: 640 } });
const spPage = await sp.newPage();
await spPage.goto(pathToFileURL(resolve(outDir, "demo", "social-preview.html")).href);
await settle(spPage, 800);
await spPage.screenshot({ path: join(outDir, "social-preview.png") });
await sp.close();

await browser.close();
console.log("done ->", outDir);
