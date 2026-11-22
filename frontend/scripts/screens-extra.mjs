// Screenshots of the screens that are not pages: the launch animation, the first-run welcome,
// the waiting mini game, the What's new dialog and an empty state.
//
//   node frontend/scripts/screens-extra.mjs <fixture-server> <fresh-server> <project-id> <out-dir>
//
// <fresh-server>: a server on an empty settings folder (onboarding not done) for the welcome.
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
const [base, fresh, pid, outDir] = process.argv.slice(2);
if (!base || !fresh || !pid || !outDir) throw new Error("usage: screens-extra.mjs <base> <fresh> <pid> <out-dir>");
mkdirSync(outDir, { recursive: true });
const THEMES = process.env.SHOT_THEMES ? process.env.SHOT_THEMES.split(",") : ["light", "dark"];
const LANG = process.env.SHOT_LANG || "en";
const H = await apiHeaders(base);
const browser = await chromium.launch({ channel: process.env.SHOT_CHANNEL || "msedge" });

async function ctxFor(theme, { splash = true, motion = "off" } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(([t, l, s, m]) => {
    localStorage.setItem("cf-lang", l);
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("cf-theme", t);
    localStorage.setItem("sc-motion", m);
    if (s) sessionStorage.setItem("sc-splash-shown", "1");
  }, [theme, LANG, splash, motion]);
  return ctx;
}
async function shot(page, name, theme) {
  await page.evaluate(() => document.fonts.ready);
  const file = join(outDir, `${name}-${theme}.png`);
  await page.screenshot({ path: file });
  console.log("saved", file);
}

// welcome (first run) on the fresh server, both themes first
for (const theme of THEMES) {
  {
    const ctx = await ctxFor(theme);
    const page = await ctx.newPage();
    await page.goto(`${fresh}/#/`);
    try {
      await page.waitForSelector(".welcome", { timeout: 20000 });
      await page.waitForTimeout(600);
      await shot(page, "welcome", theme);
      const next = page.locator(".welcome-btn-primary").first();
      if (await next.count()) {
        await next.click();
        await page.waitForTimeout(800);
        await shot(page, "welcome-2", theme);
      }
    } catch (e) {
      console.log("FAILED welcome", String(e).split("\n")[0]);
    }
    await ctx.close();
  }
}

for (const theme of THEMES) {
  // launch: the last frame (motion off paints it at once)
  {
    const ctx = await ctxFor(theme, { splash: false, motion: "reduced" });
    const page = await ctx.newPage();
    await page.goto(`${base}/#/`);
    await page.waitForSelector(".launch-word-text", { timeout: 15000 });
    await page.waitForTimeout(250);
    await shot(page, "launch", theme);
    await ctx.close();
  }
  // empty states of the fresh home (after the welcome shots: Escape there finishes the onboarding)
  {
    const ctx = await ctxFor(theme);
    const page = await ctx.newPage();
    await page.goto(`${fresh}/#/library`);
    await page.waitForTimeout(800);
    for (let k = 0; k < 4 && (await page.locator(".modal-backdrop, .welcome").count()); k++) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(250);
    }
    await shot(page, "empty-library", theme);
    await ctx.close();
  }
  // mini game, toast, what's new on the fixture server
  {
    const ctx = await ctxFor(theme);
    const page = await ctx.newPage();
    await page.request.put(`${base}/api/easy/settings`, { data: { mode: "pro" }, headers: H });
    await page.goto(`${base}/#/p/${pid}`);
    await page.waitForSelector(".side-tabs", { timeout: 30000 });
    await page.waitForTimeout(600);
    await page.evaluate(() => window.dispatchEvent(new Event("sc-minigame-open")));
    await page.waitForTimeout(1500);
    await shot(page, "minigame", theme);
    await page.keyboard.press("Escape");
    await page.goto(`${base}/#/updates`);
    await page.waitForTimeout(800);
    const wn = page.locator("text=What's new").first();
    if (await wn.count()) {
      await wn.click().catch(() => {});
      await page.waitForTimeout(800);
      await shot(page, "whatsnew", theme);
      await page.keyboard.press("Escape");
    }
    await ctx.close();
  }
}
await browser.close();
