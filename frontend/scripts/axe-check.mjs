// Accessibility check (axe-core, WCAG 2.1 A/AA + best practices) of the screens and dialogs, both
// themes, plus the 1.2.41 delete flow end to end (select a clip -> delete -> undo toast -> back).
// Same server as layout-check.mjs (python frontend/scripts/layout-fixture.py <dir>, then serve).
//   node scripts/axe-check.mjs http://127.0.0.1:8799 <project-id>
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const req = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = req("playwright"));
} catch {
  ({ chromium } = req("@playwright/test"));
}
const AXE = readFileSync(req.resolve("axe-core/axe.min.js"), "utf8");
/** Switch Easy / Pro on the server; a slow CI runner may stall one request: wait longer, try again. */
async function putMode(request, url, mode) {
  for (let i = 1; ; i++) {
    try {
      return await request.put(url, { data: { mode }, timeout: 60000 });
    } catch (e) {
      if (i >= 3) throw e;
    }
  }
}

const [base, pid] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node axe-check.mjs <base-url> <project-id>");
const P = encodeURIComponent(pid);
const LANG = process.env.AXE_LANG || "tr";

// [name, mode, hash, ready selector, optional action that opens a dialog / state]
const SCREENS = [
  ["library", "pro", "#/", ".pcard-wrap"],
  ["library-delete-dialog", "pro", "#/", ".pcard-wrap", async (page) => {
    await page.locator(".pcard-wrap").first().hover();
    await page.locator(".pcard-del").first().click();
    await page.waitForSelector(".trash-dialog");
  }],
  ["project", "pro", `#/p/${P}`, ".side-tabs"],
  ["project-picking", "pro", `#/p/${P}`, ".side-tabs", async (page) => {
    await page.locator('[data-testid="pick-toggle"]').click();
    await page.waitForSelector(".pick-bar");
    await page.locator(".cand-pick input").nth(1).check();
  }],
  ["trash", "pro", "#/trash", ".trash-usage"],
  ["trash-empty-dialog", "pro", "#/trash", ".trash-usage", async (page) => {
    await page.locator(".trash-page .page-head .btn-danger").click();
    await page.waitForSelector('[data-testid="trash-empty-confirm"]');
  }],
  ["pubqueue", "pro", "#/publish-queue", ".pq-actions"],
  ["settings", "pro", "#/settings", "main"],
  ["easy-home", "easy", "#/", ".ez-create"],
  ["easy-project", "easy", `#/p/${P}`, ".ez-title"],
  ["easy-trash", "easy", "#/trash", ".trash-usage"],
];

const browser = await chromium.launch(process.env.AXE_CHANNEL ? { channel: process.env.AXE_CHANNEL } : {});
const failures = [];
for (const theme of ["dark", "light"]) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript(([l, t]) => {
    localStorage.setItem("cf-lang", l);
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("cf-theme", t);
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("sc-splash-shown", "1");
  }, [LANG, theme]);
  const page = await ctx.newPage();
  let mode = null;
  for (const [name, m, hash, ready, act] of SCREENS) {
    if (m !== mode) {
      await putMode(page.request, `${base}/api/easy/settings`, m);
      await page.goto("about:blank");
      mode = m;
    }
    await page.goto(`${base}/${hash}`, { waitUntil: "load" });
    await page.waitForSelector(ready, { timeout: 20000 });
    await page.waitForTimeout(600);
    for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) await page.keyboard.press("Escape");
    if (act) await act(page);
    await page.waitForTimeout(300);
    await page.addScriptTag({ content: AXE });
    const res = await page.evaluate(async () => {
      // eslint-disable-next-line no-undef
      const r = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] } });
      return r.violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, target: v.nodes.slice(0, 3).map((x) => x.target.join(" ")), why: v.nodes[0]?.failureSummary?.slice(0, 300) }));
    });
    // region / landmark rules: toasts and dialogs live outside <main> by design (checked in 1.2.6 too)
    const bad = res.filter((v) => !["region"].includes(v.id));
    if (bad.length) failures.push({ screen: `${name} ${theme}`, bad });
    process.stdout.write(bad.length ? "x" : ".");
  }
  await ctx.close();
}

// ---- the delete flow: pick a clip, delete it, undo from the toast
{
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript((l) => {
    localStorage.setItem("cf-lang", l);
    localStorage.setItem("cf-lang-set", "1");
    sessionStorage.setItem("sc-splash-shown", "1");
  }, LANG);
  const page = await ctx.newPage();
  await putMode(page.request, `${base}/api/easy/settings`, "pro");
  await page.goto(`${base}/#/p/${P}`, { waitUntil: "load" });
  await page.waitForSelector(".side-tabs", { timeout: 20000 });
  for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) await page.keyboard.press("Escape");
  const before = await page.locator("[data-cand]").count();
  const last = await page.locator("[data-cand]").last().getAttribute("data-cand");
  await page.locator(`[data-cand="${last}"] .cand-accept .icon-btn`).click();
  await page.waitForSelector('[data-testid="trash-confirm"]:not([disabled])');
  await page.locator('[data-testid="trash-confirm"]').click();
  await page.waitForFunction((n) => document.querySelectorAll("[data-cand]").length === n - 1, before, { timeout: 10000 });
  const trash = await (await page.request.get(`${base}/api/trash`)).json();
  if (!trash.items.some((i) => i.clip_ids.includes(last))) failures.push({ screen: "flow", bad: ["deleted clip not in the trash"] });
  await page.locator(".toast .btn").last().click(); // Undo
  await page.waitForFunction((n) => document.querySelectorAll("[data-cand]").length === n, before, { timeout: 10000 }).catch(() => {
    failures.push({ screen: "flow", bad: ["undo did not bring the clip back"] });
  });
  process.stdout.write(".");
  await ctx.close();
}
await browser.close();
console.log("");
if (failures.length) {
  for (const f of failures) console.log(f.screen, JSON.stringify(f.bad, null, 1));
  console.log(`AXE PROBLEMS on ${failures.length} views`);
  process.exit(1);
}
console.log(`Axe OK: ${SCREENS.length * 2} views (${LANG}, dark/light) + the delete / undo flow.`);
