// 1.2.53 issue #5: the UI must work the same in Chromium (Chrome / Edge / Opera GX), Firefox and
// WebKit. Same server as layout-check.mjs (python frontend/scripts/layout-fixture.py <dir>, serve).
//   node scripts/browser-check.mjs http://127.0.0.1:8799 <project-id>
//   BROWSERS=chromium,firefox,webkit (default: all that are installed)
// Checks: edit a clip title (select + Backspace / Delete + type) while the page keeps polling,
// scroll the edit window (it must not jump back to the top), switch the UI language (incl. RTL),
// change the content language, start a render, and the publish dialog's title field.
import { apiHeaders } from "./api-token.mjs";
import { createRequire } from "node:module";

const req = createRequire(import.meta.url);
const pw = req("playwright");
const [base, pid] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node browser-check.mjs <base-url> <project-id>");
const H = await apiHeaders(base);
const P = encodeURIComponent(pid);
const wanted = (process.env.BROWSERS || "chromium,firefox,webkit").split(",").map((s) => s.trim()).filter(Boolean);
const failures = [];
const fail = (b, msg) => {
  failures.push(`[${b}] ${msg}`);
  console.log(`  FAIL ${msg}`);
};

async function setMode(request, mode) {
  await request.put(`${base}/api/easy/settings`, { data: { mode }, headers: H, timeout: 60000 });
}


/** goto that says which requests were still open when a page load hangs (seen in WebKit on CI). */
function tracked(page) {
  const open = new Map();
  page.on("request", (r) => open.set(r, Date.now()));
  page.on("requestfinished", (r) => open.delete(r));
  page.on("requestfailed", (r) => open.delete(r));
  return async (url) => {
    try {
      await page.goto(url, { timeout: 45000 });
    } catch (e) {
      const now = Date.now();
      const list = [...open].map(([r, t]) => `${r.resourceType()} ${r.url().replace(base, "")} (${Math.round((now - t) / 1000)} s)`);
      throw new Error(`${e.message.split(/\r?\n/)[0]} | still open: ${list.join(" ; ") || "nothing"}`);
    }
  };
}

for (const name of wanted) {
  let browser;
  try {
    browser = await pw[name].launch(name === "chromium" && process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {});
  } catch (e) {
    if (process.env.BROWSERS) throw e; // asked for it explicitly: a missing browser is a failure
    console.log(`${name}: not installed, skipped (${String(e.message).split("\n")[0]})`);
    continue;
  }
  console.log(`${name}:`);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  await ctx.addInitScript(() => {
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("sc-splash-shown", "1");
  });
  const page = await ctx.newPage();
  const go = tracked(page);
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await setMode(page.request, "easy");

  // 1. edit the title: select all, Backspace, Delete, type - also after the page polled again
  await go(`${base}/#/p/${P}`);
  await page.waitForSelector('[data-testid="ez-edit"]', { timeout: 30000 });
  await page.locator('[data-testid="ez-edit"]').first().click();
  const input = page.locator('[data-testid="ez-title-input"]');
  await input.waitFor();
  await input.click();
  await input.press(process.platform === "darwin" ? "Meta+A" : "Control+A");
  await input.press("Backspace");
  if ((await input.inputValue()) !== "") fail(name, "Backspace did not clear the selected title");
  await input.type("Hello world", { delay: 20 });
  await input.press("Backspace");
  await input.press("Home");
  await input.press("Delete");
  if ((await input.inputValue()) !== "ello worl") fail(name, `Backspace/Delete in the title field: got "${await input.inputValue()}"`);
  await page.waitForTimeout(4500); // the Easy page polls every few seconds: focus and text must stay
  const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-testid"));
  if (focused !== "ez-title-input") fail(name, `focus moved away from the title field while typing (now: ${focused})`);
  await input.press("End");
  await input.type("!");
  if ((await input.inputValue()) !== "ello worl!") fail(name, `typing after a poll went elsewhere ("${await input.inputValue()}")`);

  // 2. scroll the edit window: it must stay where the user scrolled
  const modal = page.locator(".modal").last();
  const scrolled = await modal.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return el.scrollTop;
  });
  await page.mouse.move(640, 400);
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(4500);
  const after = await modal.evaluate((el) => el.scrollTop);
  if (scrolled > 20 && after < scrolled - 40) fail(name, `the edit window jumped back up (${scrolled} -> ${after})`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  if (await page.locator(".modal").count()) fail(name, "Escape did not close the edit window");

  // 3. UI language switcher (flag + name), incl. Arabic right-to-left
  await go(`${base}/#/`);
  await page.waitForSelector(".lang-btn");
  for (const [code, dir] of [["es", "ltr"], ["ar", "rtl"], ["ja", "ltr"], ["en", "ltr"]]) {
    await page.locator(".lang-btn").first().click();
    await page.locator(`.lang-menu button[lang="${code}"]`).click();
    await page.waitForFunction((c) => document.documentElement.lang === c, code, { timeout: 30000 }).catch(() => {});
    const got = await page.evaluate(() => [document.documentElement.lang, document.documentElement.dir]);
    if (got[0] !== code || got[1] !== dir) fail(name, `language ${code}: html lang/dir = ${got.join("/")}`);
  }

  // 4. content language is separate from the UI language and reaches the server
  // (Easy mode's Settings has the same card: the default UI must reach it too)
  await go(`${base}/#/settings`);
  await page.reload({ waitUntil: "domcontentloaded" });
  const sel = page.locator('#content-language select');
  await sel.waitFor();
  await sel.selectOption("es");
  await page.waitForTimeout(800);
  const s = await (await page.request.get(`${base}/api/settings`)).json();
  if (s.output_language !== "es") fail(name, `content language not saved (got ${s.output_language})`);
  if (s.ui_language === "es") fail(name, "changing the content language changed the UI language");
  await page.request.put(`${base}/api/settings`, { data: { output_language: "en" }, headers: H });

  // 5. publish dialog (Pro mode): the title field takes Backspace too
  await setMode(page.request, "pro");
  await go(`${base}/#/p/${P}`);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector(".side-tabs", { timeout: 30000 });
  const pubBtn = page.locator('[data-testid="publish-btn"]').first();
  if ((await pubBtn.count()) && (await pubBtn.isEnabled())) {
    await pubBtn.click();
    const t = page.locator('.modal input[type="text"], .modal input:not([type])').first();
    await t.waitFor({ timeout: 10000 });
    await t.click();
    await t.press("End");
    const before = await t.inputValue();
    await t.press("Backspace");
    if (before && (await t.inputValue()) !== before.slice(0, -1)) fail(name, "Backspace in the publish dialog's title did nothing");
    await page.keyboard.press("Escape");
  }

  if (errors.length) fail(name, `page errors: ${errors.slice(0, 3).join(" | ")}`);
  await setMode(page.request, "easy");
  await browser.close();
}

// 6. render: the button starts a job. Once, in the first browser, after every other check: a real
//    render keeps a small CI runner busy until its next safe point, even when cancelled at once,
//    and that made the next browser's checks time out.
if (wanted.length) {
  const name = wanted[0];
  const browser = await pw[name].launch(name === "chromium" && process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {});
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  await ctx.addInitScript(() => {
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    sessionStorage.setItem("sc-splash-shown", "1");
  });
  const page = await ctx.newPage();
  const go = tracked(page);
  console.log(`${name} (render):`);
  await setMode(page.request, "pro");
  await go(`${base}/#/p/${P}`);
  await page.waitForSelector(".side-tabs", { timeout: 30000 });
  const renderBtn = page.locator('[data-testid="render-btn"]').first();
  if ((await renderBtn.count()) && (await renderBtn.isEnabled())) {
    await renderBtn.click();
    let job = null;
    for (let i = 0; i < 40 && !job; i++) {
      const j = await (await page.request.get(`${base}/api/jobs`)).json();
      job = (j.jobs || j).find((x) => x.kind === "render" && x.project_id === pid && ["queued", "running"].includes(x.status));
      if (!job) await page.waitForTimeout(500);
    }
    if (!job) fail(name, "the render button started no render job");
    else await page.request.post(`${base}/api/jobs/${job.id}/cancel`, { headers: H });
  }
  await setMode(page.request, "easy");
  await browser.close();
}

if (failures.length) {
  console.log(`\n${failures.length} browser check(s) failed:\n` + failures.join("\n"));
  process.exit(1);
}
console.log("browser checks OK");
