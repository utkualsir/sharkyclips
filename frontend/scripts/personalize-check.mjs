// 1.2.69 Settings > Personalization, end to end in a real browser:
//   presets switch <html data-preset>, the accent reaches buttons / tabs / progress bars, a colour
//   that makes text unreadable is fixed (and the panel says so), the choice survives a reload with
//   no flash (pre-paint script), a theme file round-trips, Reset brings Classic back.
//
//   node frontend/scripts/personalize-check.mjs http://127.0.0.1:8799 [shot-dir]
// env: PZ_CHANNEL=msedge (Windows dev PC); CI uses Playwright's Chromium.
import { createRequire } from "node:module";
import { join } from "node:path";
import { mkdirSync, readFileSync } from "node:fs";
import { apiHeaders } from "./api-token.mjs";

const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = req("playwright"));
} catch {
  ({ chromium } = req("./frontend/node_modules/playwright"));
}
const [base, shotDir] = process.argv.slice(2);
if (!base) throw new Error("usage: personalize-check.mjs <base> [shot-dir]");
if (shotDir) mkdirSync(shotDir, { recursive: true });
const H = await apiHeaders(base);

const fails = [];
const ok = (cond, what) => {
  if (!cond) fails.push(what);
  process.stdout.write(cond ? "." : "x");
};

const browser = await chromium.launch(process.env.PZ_CHANNEL ? { channel: process.env.PZ_CHANNEL } : {});
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
await ctx.addInitScript(() => {
  if (!sessionStorage.getItem("pz-init")) {
    localStorage.clear();
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    localStorage.setItem("cf-theme", "dark");
    localStorage.setItem("sc-motion", "off");
    sessionStorage.setItem("pz-init", "1");
  }
  sessionStorage.setItem("sc-splash-shown", "1");
});
const page = await ctx.newPage();
await page.request.put(`${base}/api/easy/settings`, { data: { mode: "pro" }, headers: H });
await page.request.put(`${base}/api/settings`, { data: { ui_personal: { preset: "classic", mode: "dark", at: 1 } }, headers: H });
await page.goto(`${base}/#/settings`, { waitUntil: "load" });
await page.waitForSelector("#personalization");
for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) await page.keyboard.press("Escape");
const attr = (n) => page.evaluate((a) => document.documentElement.getAttribute(a), n);
const token = (n) => page.evaluate((v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim(), n);
const bgOf = (sel) => page.evaluate((s) => getComputedStyle(document.querySelector(s)).backgroundColor, sel);

ok((await attr("data-preset")) === "classic", "default preset is classic");

// presets
for (const id of ["ocean", "sign", "contrast", "classic"]) {
  await page.locator(".pz-preset").nth(["classic", "ocean", "sign", "contrast"].indexOf(id)).click();
  ok((await attr("data-preset")) === id, `preset ${id} applied`);
}
// mode
await page.locator("#personalization .segmented button").filter({ hasText: /^Light$/ }).first().click();
ok((await attr("data-theme")) === "light", "light mode applied");

// accent: palette swatch -> buttons, the open tab, the progress bar
await page.locator(".pz-swatch").nth(7).click(); // --accent-7 #0078d4
const accent = await token("--gold");
ok(accent === "#0078d4", `accent token set (${accent})`);
ok((await bgOf(".pz-pv-btns .btn-primary")) === "rgb(0, 120, 212)", "primary button takes the accent");
ok((await bgOf(".progress > span")) === "rgb(0, 120, 212)", "progress bar takes the accent");
// title bar toggle
await page.locator(".pz-block .toggle-line").filter({ hasText: /title bar/ }).locator("button[role=switch]").click();
ok((await page.locator('meta[name="theme-color"]').getAttribute("content")) === "#0078d4", "title bar colour = accent");

// detailed colours: text almost the colour of the background -> fixed automatically
await page.locator(".pz-details > summary").click();
const setColor = async (label, value) => {
  const input = page.locator(".pz-color").filter({ hasText: label }).locator("input[type=color]");
  await input.evaluate((el, v) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
};
await setColor("Background", "#f4f4f4");
await setColor(/^Text/, "#eeeeee");
await page.waitForTimeout(300);
const fixedText = await token("--text");
ok(fixedText !== "#eeeeee" && fixedText !== "", `unreadable text was fixed (${fixedText})`);
ok((await page.locator(".pz-problems li").count()) > 0, "the panel lists the fix");
if (shotDir) await page.screenshot({ path: join(shotDir, "personalize-fixed.png"), fullPage: true });

// reload: same look before the app runs (pre-paint) and after
await page.reload({ waitUntil: "domcontentloaded" });
ok((await attr("data-theme")) === "light" && (await attr("data-preset")) === "classic", "kept after reload");
ok((await token("--gold")) === "#0078d4", "accent kept after reload");

// export -> reset -> import
await page.waitForSelector("#personalization");
for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) await page.keyboard.press("Escape");
const [dl] = await Promise.all([page.waitForEvent("download"), page.locator(".pz-actions .btn").nth(1).click()]);
const file = await dl.path();
const theme = JSON.parse(readFileSync(file, "utf8"));
ok(theme.kind === "sharkyclips-theme" && theme.accent === "#0078d4" && theme.colors.light.bg === "#f4f4f4", "theme file content");
await page.locator(".pz-actions .btn").nth(0).click(); // reset
await page.waitForTimeout(300);
ok((await attr("data-preset")) === "classic" && (await token("--gold")) !== "#0078d4", "reset to Classic");
await page.locator('.pz-actions input[type=file]').setInputFiles(file);
await page.waitForTimeout(500);
ok((await token("--gold")) === "#0078d4", "imported theme applied");
await page.locator('.pz-actions input[type=file]').setInputFiles({ name: "x.json", mimeType: "application/json", buffer: Buffer.from('{"kind":"sharkyclips-theme","preset":"neon"}') });
await page.waitForTimeout(400);
ok((await token("--gold")) === "#0078d4", "a bad theme file changes nothing");

// the server keeps the choice (other browsers, the splash page)
await page.waitForTimeout(800);
const s = await (await page.request.get(`${base}/api/settings`, { headers: H })).json();
ok(s.ui_personal && s.ui_personal.accent === "#0078d4", "saved on the server");

// leave the fixture as it was (no theme on the server: later checks set their own per browser)
await page.locator(".pz-actions .btn").nth(0).click();
await page.waitForTimeout(800);
await page.request.put(`${base}/api/settings`, { data: { ui_personal: null }, headers: H });
await browser.close();
console.log();
if (fails.length) {
  console.log("PERSONALIZATION PROBLEMS:\n  " + fails.join("\n  "));
  process.exit(1);
}
console.log("Personalization OK.");
