// Takes the README screenshots (dark + light) and the demo GIF from a running SharkyClips.
//
//   1. Start SharkyClips on a COPY of your workspace (the demo accepts and renders clips):
//        SHARKYCLIPS_HOME=<copy of ~/.sharkyclips with workspace_dir set> python backend/cli.py serve --no-browser --port 8130
//      (leave dev_in_progress.json out of the copy, or the "under construction" banner is in every shot)
//   2. npm i playwright@1.56.0 (in any folder), then from there:
//        node <repo>/docs/capture.mjs http://localhost:8130 <project-id> <repo>/docs
//
// Uses Microsoft Edge ("msedge" channel): Playwright's own Chromium can't play H.264 video.
// Needs ffmpeg on PATH for the GIF.
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, renameSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// Playwright is loaded from the folder you run this in (it isn't a SharkyClips dependency).
const { chromium } = createRequire(join(process.cwd(), "index.js"))("playwright");

const [base = "http://localhost:8130", pid, outDir = "docs"] = process.argv.slice(2);
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

// ------------------------------------------------------------- screenshots
const app = await api("GET", "/api/app");
await api("POST", "/api/app/whats-new-seen", { version: app.version }); // no "What's new" popup
const project = await api("GET", `/api/projects/${pid}`);
const firstThree = project.highlights.candidates.slice(0, 3).map((c) => c.id);
await api("PUT", `/api/projects/${pid}/review`, { accepted: firstThree });

for (const theme of ["dark", "light"]) {
  const ctx = await context(theme);
  const page = await ctx.newPage();
  const shot = (name) => page.screenshot({ path: join(shots, `${name}-${theme}.png`) });

  await page.goto(`${base}/#/`);
  await settle(page);
  await shot("library");

  await page.goto(`${base}/#/p/${pid}`);
  await settle(page, 3000);
  await shot("project");

  await page.getByRole("tab", { name: /Clips/ }).click();
  await settle(page, 2500);
  await shot("clips");

  await page.goto(`${base}/#/p/${pid}/bestof`);
  await settle(page, 2500);
  await shot("bestof");

  await page.goto(`${base}/#/settings`);
  await settle(page);
  await shot("settings");
  const updates = page.locator("#updates");
  await updates.scrollIntoViewIfNeeded();
  await updates.getByRole("button").click();
  await page.waitForFunction(() => !/Checking/.test(document.querySelector("#updates")?.textContent ?? ""), null, {
    timeout: 60000,
  });
  await sleep(400);
  await updates.screenshot({ path: join(shots, `updates-${theme}.png`) });
  await ctx.close();
}

// ------------------------------------------------------------- demo GIF: review -> accept -> render
await api("PUT", `/api/projects/${pid}/review`, { accepted: [] });
const videoDir = join(outDir, ".video");
rmSync(videoDir, { recursive: true, force: true });
const ctx = await context("dark", { viewport: { width: 1280, height: 760 }, recordVideo: { dir: videoDir, size: { width: 1280, height: 760 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const at = () => (Date.now() - t0) / 1000;
await page.goto(`${base}/#/p/${pid}`);
await settle(page, 1500);
const tStart = at();
const cards = page.locator(".cand");
for (const i of [1, 3]) {
  await cards.nth(i).click(); // review: the player jumps to the clip, the 9:16 preview updates
  await sleep(1800);
  await cards.nth(i).locator("[role=switch]").click(); // accept
  await sleep(900);
}
await page.getByRole("button", { name: /Render 2 clips/ }).click();
await sleep(1500);
const tRender = at();
await page.getByRole("tab", { name: /Clips/, selected: true }).waitFor({ timeout: 180000 }); // opens when done
const tDone = at();
await sleep(1200);
await page.locator(".clip-card video, video").last().scrollIntoViewIfNeeded().catch(() => {});
await sleep(2500);
await ctx.close();
await api("PUT", `/api/projects/${pid}/review`, { accepted: firstThree });

const webm = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
renameSync(join(videoDir, webm), join(videoDir, "demo.webm"));
// Normal speed for the clicks, 5x while the clips render, then the result.
const speedup = 5;
const filter = [
  `[0:v]trim=${tStart.toFixed(2)}:${tRender.toFixed(2)},setpts=PTS-STARTPTS[a]`,
  `[0:v]trim=${tRender.toFixed(2)}:${tDone.toFixed(2)},setpts=(PTS-STARTPTS)/${speedup}[b]`,
  `[0:v]trim=start=${tDone.toFixed(2)},setpts=PTS-STARTPTS[c]`,
  "[a][b][c]concat=n=3:v=1[v]",
  "[v]fps=10,scale=900:-1:flags=lanczos,split[x][y]",
  "[x]palettegen=max_colors=128:stats_mode=diff[p]",
  "[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
].join(";");
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", join(videoDir, "demo.webm"), "-filter_complex", filter, join(outDir, "demo.gif")]);
rmSync(videoDir, { recursive: true, force: true });

// ------------------------------------------------------------- queue (while the re-render runs)
await api("POST", "/api/queue/render", { project_ids: [pid], rerender: true });
for (const theme of ["dark", "light"]) {
  const c = await context(theme);
  const p = await c.newPage();
  await p.goto(`${base}/#/queue`);
  await settle(p, 2500);
  await p.screenshot({ path: join(shots, `queue-${theme}.png`) });
  await c.close();
}
await api("POST", "/api/queue/cancel", { project_id: pid });
await browser.close();
console.log("done ->", outDir);
