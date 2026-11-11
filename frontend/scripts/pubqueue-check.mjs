// 1.2.40: the publish queue in a real browser, against a layout-fixture server.
// node frontend/scripts/pubqueue-check.mjs http://127.0.0.1:8799 [shots-dir] [n-clips]
// Picks the first n clips, "Prepare for Chrome" -> files under 10 MB + queue.json + calendar,
// copies the brief, imports a status answer, checks the calendar table; also at phone width.
import { mkdirSync } from "node:fs";

const [base, shots, nArg] = process.argv.slice(2);
const n = Number(nArg || 2);
if (!base) {
  console.error("usage: pubqueue-check.mjs <base-url> [shots-dir] [n-clips]");
  process.exit(2);
}
const { chromium } = await import("playwright");
const browser = await chromium.launch(process.env.LAYOUT_CHANNEL ? { channel: process.env.LAYOUT_CHANNEL } : {});
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["clipboard-read", "clipboard-write"] });
await ctx.addInitScript(() => {
  localStorage.setItem("cf-lang", "tr");
  localStorage.setItem("cf-lang-set", "1");
  localStorage.setItem("sc-motion", "off");
});
const page = await ctx.newPage();
const fail = (m) => {
  console.error("FAIL:", m);
  process.exit(1);
};
const shot = async (name, full = false) => {
  if (!shots) return;
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: full });
};

await page.goto(`${base}/#/publish-queue`);
await page.locator(".pq-actions").waitFor({ timeout: 30000 });
if (await page.locator(".modal-backdrop").count()) {
  await page.keyboard.press("Escape"); // "What's new"
  await page.locator(".modal-backdrop").first().waitFor({ state: "detached", timeout: 5000 }).catch(() => {});
}
const rows = page.locator(".pq-row");
await rows.first().waitFor({ timeout: 20000 });
if (!(await page.locator(".pq-row-title").first().innerText()).trim()) fail("no AI title");
// PQ_RESUME=1: the batch was prepared already (the job finished while this script waited)
if (!process.env.PQ_RESUME) {
// pick exactly the first n clips
await page.getByRole("button", { name: /Hiçbirini seçme/ }).click();
for (let i = 0; i < n; i++) await rows.nth(i).locator(".pq-pick input").check();
await page.locator(".pq-chip.pq-plan").first().waitFor({ timeout: 10000 }); // the automatic times
// open the editor of the first clip: the AI texts are filled in and #utkualsirr is there
await rows.first().getByRole("button", { name: /Düzenle/ }).click();
const tags = await rows.first().locator(".pq-editor input.input").nth(2).inputValue();
if (!tags.includes("#utkualsirr")) fail(`hashtags: ${tags}`);
await shot("1-picked");
await page.locator(".pq-actions .btn-primary").click();
}
await page.locator(".pq-result").waitFor({ timeout: 3600000 });
const sizes = await page.locator(".pq-result-list li .mono").allInnerTexts();
if (sizes.length !== n) fail(`result rows: ${sizes}`);
for (const s of sizes) if (!(parseFloat(s) < 10)) fail(`size ${s}`);
await shot("2-ready", true);
// the brief for Claude in Chrome
await page.locator(".pq-result .btn-primary").click();
await page.waitForTimeout(400);
const brief = await page.evaluate(() => navigator.clipboard.readText());
if (!brief.includes("queue.json") || !brief.includes("Europe/Budapest")) fail("brief");
const ids = [...brief.matchAll(/"id": "([^"<]+)"/g)].map((m) => m[1]);
// Claude in Chrome answers
const answer = JSON.stringify({ results: [
  { id: ids[0], platform: "youtube", status: "scheduled", url: "https://youtube.com/shorts/demo" },
  { id: ids[0], platform: "instagram", status: "scheduled" },
  { id: ids[1] ?? ids[0], platform: "tiktok", status: "failed", note: "upload error" },
] });
await page.locator(".pq-actions").getByRole("button", { name: /Durumu içe aktar/ }).click();
await page.locator(".pq-import").fill("```json\n" + answer + "\n```");
await page.locator(".modal .btn-primary").click();
await page.locator(".pq-table").waitFor({ timeout: 10000 });
await page.waitForTimeout(500);
const table = await page.locator(".pq-table").innerText();
if (!/planlandı/.test(table) || !/başarısız/.test(table)) fail(`calendar: ${table.slice(0, 300)}`);
await page.locator(".pq-table").scrollIntoViewIfNeeded();
await shot("3-calendar");
await page.setViewportSize({ width: 390, height: 820 });
await page.waitForTimeout(300);
if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)) fail("sideways scroll at phone width");
await page.evaluate(() => window.scrollTo(0, 0));
await shot("4-phone");
console.log("pubqueue OK:", sizes.join(", "));
await browser.close();
