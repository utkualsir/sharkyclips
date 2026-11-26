// 1.2.66: screenshots of "Share clips" (board, selection, platform step, summary, progress) from the
// layout fixture server (python frontend/scripts/layout-fixture.py <dir>, then serve on 8799).
//   node scripts/share-shots.mjs http://127.0.0.1:8799 <project-id> <out-dir> [lang] [theme]
// The "progress" shot really publishes the picked clips on the fixture server (TikTok by hand).
import { apiHeaders } from "./api-token.mjs";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const req = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = req("playwright"));
} catch {
  ({ chromium } = req("@playwright/test"));
}
const [base, pid, out, lang = "en", theme = "dark"] = process.argv.slice(2);
if (!base || !pid || !out) throw new Error("usage: node share-shots.mjs <base-url> <project-id> <out-dir> [lang] [theme]");
mkdirSync(out, { recursive: true });
const H = await apiHeaders(base);
const P = encodeURIComponent(pid);
const browser = await chromium.launch({ channel: process.env.LAYOUT_CHANNEL || "msedge", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await ctx.addInitScript(([l, th]) => {
  localStorage.setItem("cf-lang", l);
  localStorage.setItem("cf-lang-set", "1");
  localStorage.setItem("cf-theme", th);
  sessionStorage.setItem("sc-splash-shown", "1");
}, [lang, theme]);
const page = await ctx.newPage();
await page.request.put(`${base}/api/easy/settings`, { data: { mode: process.env.SHOT_MODE || "easy" }, headers: H });
const shot = (name) => page.screenshot({ path: `${out}/${name}-${lang}-${theme}.png` });
await page.goto(`${base}/#/p/${P}/share`, { waitUntil: "load" });
await page.waitForSelector(".share-grid", { timeout: 20000 });
await page.waitForTimeout(1200);
await shot("1-board");
await page.locator(".share-selbtns .btn").nth(1).click(); // Select not shared
await page.waitForSelector(".share-bar.is-on");
await page.waitForTimeout(300);
await shot("2-selected");
await page.locator(".share-go").click();
await page.waitForSelector(".share-plats");
await page.waitForTimeout(300);
await shot("3-where");
await page.locator(".modal-foot .btn-primary").click();
await page.waitForSelector(".share-summary");
await page.waitForTimeout(400);
await shot("4-summary");
if (process.env.SHOT_PUBLISH === "1") {
  await page.locator(".modal-foot .btn-primary").click();
  await page.waitForSelector(".share-batch", { timeout: 20000 });
  await page.waitForTimeout(6000);
  await shot("5-progress");
}
await browser.close();
console.log("shots in", out);
