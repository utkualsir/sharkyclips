// 1.2.59 waiting mini game, in a real browser (same server as layout-check.mjs):
//   node scripts/minigame-check.mjs http://127.0.0.1:8799 <project-id>
// 1. keys typed in the game never reach the app's shortcuts (Project page: "?" opens the shortcut
//    sheet, A / X decide a clip, Space plays) and keys typed elsewhere never reach the game
// 2. performance budget while playing: frame cost (simulation + drawing) and main-thread CPU
// 3. pauses when the window loses focus / the panel is hidden; nearly no CPU while paused
// 4. the panel fits the screen at laptop / desktop / phone sizes and leaves the top bar free
import { apiHeaders } from "./api-token.mjs";
import { createRequire } from "node:module";

const req = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = req("playwright"));
} catch {
  ({ chromium } = req("@playwright/test"));
}
const [base, pid] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node minigame-check.mjs <base-url> <project-id>");
const H = await apiHeaders(base);
const P = encodeURIComponent(pid);
// budgets (CI runners are slow and draw on the CPU: generous, but they catch a runaway loop)
const FRAME_MS = Number(process.env.MG_FRAME_MS || 6);
const CPU_PLAY = Number(process.env.MG_CPU_PLAY || 0.5);
const CPU_PAUSED = Number(process.env.MG_CPU_PAUSED || 0.06);

const fails = [];
const check = (ok, what) => {
  process.stdout.write(ok ? "." : "x");
  if (!ok) fails.push(what);
};

const browser = await chromium.launch(process.env.LAYOUT_CHANNEL ? { channel: process.env.LAYOUT_CHANNEL } : {});
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => {
  localStorage.setItem("cf-lang", "en");
  localStorage.setItem("cf-lang-set", "1");
  localStorage.setItem("sc-motion", "full");
  sessionStorage.setItem("sc-splash-shown", "1");
});
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.request.put(`${base}/api/easy/settings`, { data: { mode: "pro", minigame: true }, headers: H });
await page.request.put(`${base}/api/minigame`, { data: { howto_seen: false, today: "2000-01-01" }, headers: H });
const outside = [];
page.on("request", (r) => {
  const u = r.url();
  // the app's UI fonts (index.html, not the game) are the only outside files the app itself loads
  if (/^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(u)) return;
  if (!u.startsWith(base) && !u.startsWith("data:") && !u.startsWith("blob:")) outside.push(u);
});

await page.goto(`${base}/#/p/${P}`, { waitUntil: "load" });
await page.waitForSelector(".side-tabs", { timeout: 20000 });
for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) await page.keyboard.press("Escape");

const screen = () => page.locator(".mg-stage").getAttribute("data-screen");
const dialogs = () => page.locator(".modal-backdrop, [role=dialog]").count();
const projectState = async () => {
  const p = await (await page.request.get(`${base}/api/projects/${P}`)).json();
  return JSON.stringify([p.review?.accepted, p.review?.rejected, p.candidates]); // the decisions (jobs change on their own)
};

// ---- open: the first time shows how to play
await page.evaluate(() => window.dispatchEvent(new CustomEvent("sc-minigame-open")));
await page.waitForSelector(".mg-panel:not([hidden])", { timeout: 10000 });
await page.waitForSelector('.mg-stage[data-screen="howto"]', { timeout: 5000 }).catch(() => {});
check((await screen()) === "howto", "the how-to shows on the first open");
await page.locator(".mg-card .btn-primary").click(); // Got it
await page.waitForSelector('.mg-stage[data-screen="start"]');
await page.locator(".mg-stage").focus();
await page.keyboard.press("Enter");
await page.waitForSelector('.mg-stage[data-screen="play"]');
check(true, "");

// ---- 1. keys inside the game stay in the game
const before = await projectState();
const d0 = await dialogs();
await page.locator(".mg-stage").focus();
for (const k of ["?", "a", "x", "Space", "j", "k", "l", "f", "i", "o"]) await page.keyboard.press(k);
await page.waitForTimeout(400);
check((await dialogs()) === d0, "a key in the game opened an app dialog");
check((await projectState()) === before, "a key in the game changed the project (A / X shortcuts)");
check((await screen()) === "play", "the game stopped on its own keys");
await page.keyboard.press("p");
check((await screen()) === "paused", "P in the game pauses it (the game hears its keys)");
await page.keyboard.press("p");
check((await screen()) === "play", "P again resumes");
// keys outside the game never reach it, and the app's shortcuts still work there
await page.locator(".page h1, .side-tabs").first().click({ position: { x: 2, y: 2 } }).catch(() => {});
await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
await page.keyboard.press("p");
await page.waitForTimeout(150);
check((await screen()) === "play", "a key outside the game reached it");
await page.keyboard.press("?");
await page.waitForTimeout(300);
check((await dialogs()) > d0, "the app's own shortcut (?) stopped working outside the game");
await page.keyboard.press("Escape");
await page.waitForTimeout(200);

// ---- 2. performance budget while playing
const cdp = await ctx.newCDPSession(page);
await cdp.send("Performance.enable");
const cpu = async (ms) => {
  const m0 = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));
  await page.waitForTimeout(ms);
  const m1 = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));
  return (m1.TaskDuration - m0.TaskDuration) / ((m1.Timestamp - m0.Timestamp) || ms / 1000);
};
await page.locator(".mg-stage").focus();
await page.keyboard.down("ArrowRight");
const playCpu = await cpu(5000);
await page.keyboard.up("ArrowRight");
const frameMs = Number(await page.locator(".mg-stage").getAttribute("data-frame-ms"));
const fps = Number(await page.locator(".mg-stage").getAttribute("data-fps"));
console.log(`\n  playing: ${frameMs.toFixed(2)} ms per frame, ${fps} fps, main thread ${(playCpu * 100).toFixed(1)} %`);
check(frameMs > 0 && frameMs < FRAME_MS, `frame cost ${frameMs} ms >= ${FRAME_MS} ms`);
check(fps > 0 && fps <= 62, `fps ${fps} (must be capped at 60)`);
check(playCpu < CPU_PLAY, `main thread ${playCpu} while playing >= ${CPU_PLAY}`);

// ---- 3. pauses: window blur, panel hidden; idle CPU while paused
if ((await screen()) !== "play") await page.locator(".mg-stage").press("p");
await page.evaluate(() => window.dispatchEvent(new Event("blur")));
await page.waitForTimeout(100);
check((await screen()) === "paused", "losing the window focus did not pause");
await page.evaluate(() => window.dispatchEvent(new Event("focus")));
await page.locator(".mg-card .btn-primary").click(); // Resume
check((await screen()) === "play", "resume");
await page.locator('.mg-head button[aria-label="Hide the game (the round is kept)"]').click();
check(await page.locator(".mg-panel[hidden]").count() === 1, "the hide button hides the panel");
const pausedCpu = await cpu(3000);
console.log(`  hidden + paused: main thread ${(pausedCpu * 100).toFixed(1)} %`);
check(pausedCpu < CPU_PAUSED, `main thread ${pausedCpu} while hidden >= ${CPU_PAUSED}`);
await page.evaluate(() => window.dispatchEvent(new CustomEvent("sc-minigame-open")));
await page.waitForSelector(".mg-panel:not([hidden])");
check((await screen()) === "paused", "the round is kept (paused) after hiding the panel");

// ---- 4. layout: inside the window, never over the top bar
for (const [w, h] of [[1024, 700], [1366, 768], [1920, 1080], [390, 844]]) {
  await page.setViewportSize({ width: w, height: h });
  await page.waitForTimeout(250);
  const r = await page.evaluate(() => {
    const p = document.querySelector(".mg-panel").getBoundingClientRect();
    const top = document.querySelector(".topbar")?.getBoundingClientRect();
    const st = document.querySelector(".mg-stage").getBoundingClientRect();
    return { p: [p.left, p.top, p.right, p.bottom], top: top ? top.bottom : 0, stage: [st.width, st.height],
             scroll: document.documentElement.scrollWidth > window.innerWidth + 1 };
  });
  check(r.p[0] >= 0 && r.p[2] <= w && r.p[1] >= r.top && r.p[3] <= h, `panel outside the window / over the top bar at ${w}x${h}: ${r.p}`);
  check(r.stage[0] >= 200 && r.stage[1] >= 120, `game area too small at ${w}x${h}: ${r.stage}`);
  check(!r.scroll, `sideways scroll at ${w}x${h}`);
}

// ---- turning it off in Settings: no game, Escape closes it
await page.setViewportSize({ width: 1366, height: 768 });
await page.locator(".mg-stage").focus();
await page.keyboard.press("Escape");
check(await page.locator(".mg-panel[hidden]").count() === 1, "Escape on a paused game hides the panel");
check(outside.length === 0, `requests outside the app: ${outside.slice(0, 3)}`);
check(errors.length === 0, `page errors: ${errors.slice(0, 3)}`);
await page.request.put(`${base}/api/minigame`, { data: { howto_seen: false, today: "2000-01-01" }, headers: H });
await browser.close();
console.log("");
if (fails.length) {
  for (const f of fails) console.log("FAIL:", f);
  process.exit(1);
}
console.log("Mini game OK: keys isolated both ways, budget, pausing, layout at 4 sizes, no outside requests.");
