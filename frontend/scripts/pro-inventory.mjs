// Pro mode control inventory + screenshots (1.2.63): every button / link / field / switch on every
// Pro screen, and whether it is visible right away or tucked into a closed "Advanced" section.
//
//   node frontend/scripts/pro-inventory.mjs http://127.0.0.1:8799 <project-id> <out-dir>
//
// Writes <out-dir>/inventory.json, <out-dir>/inventory.md and one full-page PNG per screen.
import { apiHeaders } from "./api-token.mjs";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  ({ chromium } = req("playwright"));
}

const [base, pid, out] = process.argv.slice(2);
if (!base || !pid || !out) throw new Error("usage: node pro-inventory.mjs <base-url> <project-id> <out-dir>");
mkdirSync(out, { recursive: true });
const H = await apiHeaders(base);
const P = encodeURIComponent(pid);
const SCREENS = [
  ["projects", "#/"],
  ["project", `#/p/${P}`],
  ["project-edit-tab", `#/p/${P}`, ".side-tablist button:nth-child(2)"],
  ["library", "#/library"],
  ["calendar", "#/library/calendar"],
  ["queue", "#/queue"],
  ["publish-queue", "#/publish-queue"],
  ["stories", `#/p/${P}/stories`],
  ["bestof", `#/p/${P}/bestof`],
  ["studio-music", "#/studio/music"],
  ["studio-brand", "#/studio/brand"],
  ["studio-words", "#/studio/words"],
  ["studio-games", "#/studio/games"],
  ["stats", "#/stats"],
  ["settings", "#/settings"],
  ["trash", "#/trash"],
  ["updates", "#/updates"],
];

const browser = await chromium.launch({ channel: process.env.LAYOUT_CHANNEL || undefined, headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: "en-US" });
const r = await ctx.request.put(`${base}/api/easy/settings`, { data: { mode: "pro" }, headers: H, timeout: 60000 });
if (!r.ok()) throw new Error(`could not switch to Pro mode: ${r.status()}`);
await ctx.addInitScript(() => {
  try {
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("cf-theme", "dark");
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("sc-splash-shown", "1");
  } catch {}
});
const page = await ctx.newPage();
const all = {};
for (const [name, hash, click] of SCREENS) {
  await page.goto(`${base}/${hash}`, { waitUntil: "load" });
  await page.waitForSelector("main", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  if (click) {
    await page.click(click).catch(() => {});
    await page.waitForTimeout(600);
  }
  const items = await page.evaluate(() => {
    const sel = "button, a[href], input, select, textarea, [role=switch], [role=tab], summary";
    const main = document.querySelector("main") || document.body;
    const rows = [];
    for (const el of main.querySelectorAll(sel)) {
      if (el.closest("[aria-hidden=true]")) continue;
      const closed = el.closest("details:not([open])");
      const inSummary = el.tagName === "SUMMARY" || el.closest("summary");
      const r = el.getBoundingClientRect();
      const shown = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
      if (!shown && !(closed && !inSummary)) continue;
      const label =
        el.getAttribute("aria-label") ||
        (el.labels && el.labels[0] && el.labels[0].innerText) ||
        el.getAttribute("title") ||
        el.innerText ||
        el.getAttribute("placeholder") ||
        el.getAttribute("name") ||
        el.type ||
        "";
      const section = el.closest("section, .panel, .card")?.querySelector("h2, h3, .section-title")?.innerText || "";
      rows.push({
        kind: el.tagName.toLowerCase() + (el.type && el.tagName === "INPUT" ? `:${el.type}` : ""),
        label: label.replace(/\s+/g, " ").trim().slice(0, 80),
        section: section.replace(/\s+/g, " ").trim().slice(0, 60),
        place: closed && !inSummary ? "advanced" : "visible",
      });
    }
    return rows;
  });
  all[name] = items;
  await page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
}
await browser.close();
writeFileSync(join(out, "inventory.json"), JSON.stringify(all, null, 1));
let md = "# Pro mode controls\n\n| Screen | Visible | In Advanced |\n|---|---|---|\n";
for (const [k, v] of Object.entries(all))
  md += `| ${k} | ${v.filter((x) => x.place === "visible").length} | ${v.filter((x) => x.place === "advanced").length} |\n`;
for (const [k, v] of Object.entries(all)) {
  md += `\n## ${k}\n\n| Where | Section | Control | Label |\n|---|---|---|---|\n`;
  for (const x of v) md += `| ${x.place} | ${x.section.replace(/\|/g, "/")} | ${x.kind} | ${x.label.replace(/\|/g, "/")} |\n`;
}
writeFileSync(join(out, "inventory.md"), md);
console.log(Object.entries(all).map(([k, v]) => `${k}: ${v.length}`).join("\n"));
