// 1.2.39: the "post it yourself" flow in a real browser, against a layout-fixture server.
// node frontend/scripts/handoff-check.mjs http://127.0.0.1:8799 <project-id> [shots-dir]
// Publish with Instagram + TikTok (semi-automatic, the default) -> the guide opens -> "Copy & open"
// copies the caption and opens the upload page -> "Copied, paste and share" -> "I shared it" moves
// on to TikTok -> both shared.
import { mkdirSync } from "node:fs";

const [base, pid, shots] = process.argv.slice(2);
if (!base || !pid) {
  console.error("usage: handoff-check.mjs <base-url> <project-id> [shots-dir]");
  process.exit(2);
}
const { chromium } = await import("playwright");
const browser = await chromium.launch(process.env.LAYOUT_CHANNEL ? { channel: process.env.LAYOUT_CHANNEL } : {});
const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, permissions: ["clipboard-read", "clipboard-write"] });
await ctx.addInitScript(() => {
  localStorage.setItem("cf-lang", "tr");
  localStorage.setItem("cf-lang-set", "1");
  localStorage.setItem("sc-motion", "off");
});
const page = await ctx.newPage();
const pages = [];
ctx.on("page", (p) => pages.push(p));
const opened = [];
const urls = async () => {
  for (const p of pages) await p.waitForLoadState("domcontentloaded").catch(() => {});
  opened.push(...pages.map((p) => p.url()));
  for (const p of pages.splice(0)) await p.close().catch(() => {});
  await page.bringToFront();
};
await ctx.route(/instagram\.com|tiktok\.com/, (r) => r.fulfill({ status: 200, contentType: "text/html", body: "<title>upload</title>" }));
const fail = (m) => {
  console.error("FAIL:", m);
  process.exit(1);
};
const shot = async (name) => {
  if (!shots) return;
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: `${shots}/${name}.png` });
};

await page.request.put(`${base}/api/publish/targets`, { data: { targets: ["tiktok", "reels"] } });
await page.goto(`${base}/#/p/${encodeURIComponent(pid)}`);
// HANDOFF_RESUME=1: the files were made already (POST /api/publish): reopen the guide from the card
const go = process.env.HANDOFF_RESUME
  ? page.locator(".mp-resume").first()
  : page.locator(".mp-go .btn-primary:not([disabled])").first();
await go.waitFor({ timeout: 240000 });
// "What's new" (once per version) may cover the page: close it
if (await page.locator(".modal-backdrop").count()) {
  await page.keyboard.press("Escape");
  await page.locator(".modal-backdrop").first().waitFor({ state: "detached", timeout: 5000 }).catch(() => {});
}
await go.click();
const dialog = page.locator(".modal", { has: page.locator(".ho-track") });
await dialog.waitFor({ timeout: 20000 });
await shot("1-preparing");
const copyOpen = dialog.locator(".ho-go");
await copyOpen.waitFor({ timeout: 60000 });
if (!(await dialog.locator(".ho-card-head").innerText()).includes("Instagram")) fail("Instagram should come first");
await shot("2-ready");
await copyOpen.click();
await dialog.locator(".ho-copied").waitFor({ timeout: 5000 });
const text = await dialog.locator(".ho-copied b").innerText();
if (!text.includes("Kopyalandı, yapıştır ve paylaş")) fail(`copied line: ${text}`);
const clip = await page.evaluate(() => navigator.clipboard.readText());
if (!clip || !clip.includes("#")) fail(`clipboard: ${clip}`);
await page.waitForTimeout(500);
await urls();
if (!opened.some((u) => u.includes("instagram.com"))) fail(`upload page not opened: ${opened}`);
await shot("3-copied");
await dialog.locator(".ho-ready .btn-primary").click(); // "I shared it, next: TikTok"
await page.waitForFunction(() => document.querySelector(".ho-card-head")?.textContent?.includes("TikTok"), null, { timeout: 10000 });
await dialog.locator(".ho-go").click();
await dialog.locator(".ho-copied").waitFor({ timeout: 5000 });
await page.waitForTimeout(500);
await urls();
if (!opened.some((u) => u.includes("tiktok.com"))) fail(`TikTok upload page not opened: ${opened}`);
await dialog.locator(".ho-ready .btn-primary").click(); // "I shared it"
await dialog.locator(".ho-all").waitFor({ timeout: 10000 });
await shot("4-done");
// phone width: the guide fits without sideways scroll
await page.setViewportSize({ width: 390, height: 800 });
const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
if (wide) fail("sideways scroll at phone width");
await shot("5-phone");
console.log("handoff OK:", opened.join(" , "));
await browser.close();
