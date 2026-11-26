// Screenshots of the main screens (docs/redesign.md before / after, design reviews).
//
//   python frontend/scripts/layout-fixture.py <dir>       (prints the project id)
//   SHARKYCLIPS_HOME=<dir>/home python backend/cli.py serve --port 8799 --no-browser
//   node frontend/scripts/screens.mjs http://127.0.0.1:8799 <project-id> <out-dir>
//
// env: SHOT_W / SHOT_H (1440x900), SHOT_THEMES (light,dark), SHOT_LANG (en), SHOT_ONLY (names),
//      SHOT_PRESETS (1.2.69: classic,ocean,sign,contrast; files get a -<preset> suffix when set).
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { apiHeaders } from "./api-token.mjs";

const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = req("playwright"));
} catch {
  ({ chromium } = req("./frontend/node_modules/playwright"));
}

const [base, pid, outDir] = process.argv.slice(2);
if (!base || !pid || !outDir) throw new Error("usage: screens.mjs <base> <pid> <out-dir>");
mkdirSync(outDir, { recursive: true });
const H = await apiHeaders(base);
const W = Number(process.env.SHOT_W || 1440);
const HGT = Number(process.env.SHOT_H || 900);
const LANG = process.env.SHOT_LANG || "en";
const ONLY = process.env.SHOT_ONLY ? process.env.SHOT_ONLY.split(",") : null;
const THEMES = process.env.SHOT_THEMES ? process.env.SHOT_THEMES.split(",") : ["light", "dark"];
const PRESETS = process.env.SHOT_PRESETS ? process.env.SHOT_PRESETS.split(",") : [null];

const SCREENS = [
  { name: "home", mode: "easy", hash: "#/", ready: ".ez-create" },
  { name: "easy", mode: "easy", hash: `#/p/${pid}`, ready: ".ez-card-title" },
  { name: "easy-library", mode: "easy", hash: "#/library", ready: "main" },
  { name: "easy-settings", mode: "easy", hash: "#/settings", ready: "main" },
  { name: "pro-library", mode: "pro", hash: "#/", ready: "main" },
  { name: "pro-editor", mode: "pro", hash: `#/p/${pid}`, ready: ".side-tabs" },
  { name: "preview", mode: "pro", hash: `#/p/${pid}`, ready: ".side-tabs", open: 'button[title$="(F)"]', openReady: ".fast-card" },
  { name: "publish", mode: "pro", hash: "#/library", ready: "main", open: "button:has(.mp-mini-icons)", openReady: ".modal" },
  { name: "publish-queue", mode: "pro", hash: "#/publish-queue", ready: "main" },
  { name: "queue", mode: "pro", hash: "#/queue", ready: "main" },
  { name: "stats", mode: "pro", hash: "#/stats", ready: "main" },
  { name: "settings", mode: "pro", hash: "#/settings", ready: "main" },
  { name: "updates", mode: "pro", hash: "#/updates", ready: "main" },
  { name: "trash", mode: "pro", hash: "#/trash", ready: "main" },
  { name: "studio", mode: "pro", hash: "#/studio/brand", ready: "main" },
];

const browser = await chromium.launch({ channel: process.env.SHOT_CHANNEL || "msedge" });
for (const preset of PRESETS)
for (const theme of THEMES) {
  const ctx = await browser.newContext({ viewport: { width: W, height: HGT }, deviceScaleFactor: 1 });
  await ctx.addInitScript(([t, l, pr]) => {
    localStorage.setItem("cf-lang", l);
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("cf-theme", t);
    if (pr) localStorage.setItem("sc-personal", JSON.stringify({ p: { v: 1, preset: pr, mode: t, accent: null, titlebar: false, autofix: true, colors: { dark: {}, light: {} }, at: 0 } }));
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("sc-splash-shown", "1");
  }, [theme, LANG, preset]);
  const page = await ctx.newPage();
  let mode = null;
  for (const s of SCREENS) {
    if (ONLY && !ONLY.includes(s.name)) continue;
    if (s.mode !== mode) {
      await page.request.put(`${base}/api/easy/settings`, { data: { mode: s.mode }, headers: H });
      await page.goto("about:blank");
      mode = s.mode;
    }
    try {
      await page.goto(`${base}/${s.hash}`, { waitUntil: "load" });
      await page.waitForSelector(s.ready, { timeout: 30000 });
      await page.waitForTimeout(900);
      for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) {
        await page.keyboard.press("Escape");
        await page.waitForTimeout(250);
      }
      if (s.open) {
        await page.locator(s.open).first().click();
        await page.waitForSelector(s.openReady, { timeout: 15000 });
        await page.waitForTimeout(900);
      }
      await page.evaluate(() => document.fonts.ready);
      const file = join(outDir, `${s.name}-${theme}${preset ? `-${preset}` : ""}.png`);
      await page.screenshot({ path: file, fullPage: !!process.env.SHOT_FULL });
      console.log("saved", file);
    } catch (e) {
      console.log("FAILED", s.name, theme, String(e).split("\n")[0]);
    }
  }
  await ctx.close();
}
await browser.close();
