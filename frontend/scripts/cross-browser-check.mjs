// Cross-browser smoke check (1.2.63): Chrome, Edge and Firefox; every main screen in Easy and Pro
// mode, light + dark, 1280x720 and a 13" laptop (1366x768 / 1440x900), all 11 UI languages on the
// main screens: no page errors, no console errors, no sideways scroll; and the clip end point: Play
// clip stops exactly at the clip's end and shows "End of clip".
//
//   node frontend/scripts/cross-browser-check.mjs http://127.0.0.1:8799 <project-id>
//   CB_BROWSERS=firefox  (default: chrome,msedge,firefox)   CB_QUICK=1 (fewer combinations)
import { apiHeaders } from "./api-token.mjs";
import { createRequire } from "node:module";
import { join } from "node:path";

const req = createRequire(join(process.cwd(), "index.js"));
let pw;
try {
  pw = await import("playwright");
} catch {
  pw = req("playwright");
}
const [base, pid] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node cross-browser-check.mjs <base-url> <project-id>");
const H = await apiHeaders(base);
const P = encodeURIComponent(pid);
const quick = process.env.CB_QUICK === "1";
const BROWSERS = (process.env.CB_BROWSERS || "chrome,msedge,firefox").split(",");
const LANGS = ["en", "tr", "es", "pt", "de", "fr", "hu", "ru", "ar", "zh", "ja"];
const SIZES = quick ? [[1280, 720]] : [[1280, 720], [1366, 768], [1440, 900]];
const SCREENS = [
  ["easy", "#/"], ["easy", `#/p/${P}`], ["easy", "#/library"], ["easy", "#/settings"], ["easy", "#/publish-queue"],
  ["easy", "#/trash"], ["easy", "#/updates"],
  ["pro", "#/"], ["pro", `#/p/${P}`], ["pro", "#/library"], ["pro", "#/queue"], ["pro", "#/publish-queue"],
  ["pro", "#/studio/brand"], ["pro", "#/stats"], ["pro", "#/settings"], ["pro", "#/trash"], ["pro", "#/updates"],
];
// known noise that is not an app error (the fixture has no YouTube / LLM / network)
const IGNORE = [/Failed to load resource: the server responded with a status of (404|409|503)/, /favicon/, /net::ERR_/, /NetworkError/];
const problems = [];
const fail = (w, m) => problems.push(`${w}: ${m}`);

async function setMode(request, mode) {
  for (let i = 0; i < 3; i++) {
    try {
      return await request.put(`${base}/api/easy/settings`, { data: { mode }, headers: H, timeout: 60000 });
    } catch (e) {
      if (i === 2) throw e;
    }
  }
}

function launcher(name) {
  if (name === "firefox") return pw.firefox.launch({ headless: true });
  return pw.chromium.launch({ channel: name, headless: true });
}

for (const bname of BROWSERS) {
  const browser = await launcher(bname);
  const combos = [];
  for (const [w, h] of SIZES) for (const theme of ["light", "dark"]) combos.push({ w, h, theme, langs: w === 1280 && theme === "dark" && !quick ? LANGS : ["en", "ar"] });
  for (const c of combos) {
    for (const lang of c.langs) {
      const ctx = await browser.newContext({ viewport: { width: c.w, height: c.h } });
      await ctx.addInitScript(([l, t]) => {
        localStorage.setItem("cf-lang", l);
        localStorage.setItem("cf-lang-set", "1");
        localStorage.setItem("cf-theme", t);
        localStorage.setItem("sc-motion", "off");
        sessionStorage.setItem("sc-splash-shown", "1");
      }, [lang, c.theme]);
      const page = await ctx.newPage();
      const errs = [];
      page.on("pageerror", (e) => errs.push(`pageerror ${String(e).slice(0, 200)}`));
      page.on("console", (m) => m.type() === "error" && !IGNORE.some((r) => r.test(m.text())) && errs.push(m.text().slice(0, 200)));
      let mode = null;
      const screens = process.env.CB_ONLY_END === "1" ? [] : lang === "en" || lang === "ar" ? SCREENS : SCREENS.filter(([, h]) => h === "#/" || h.startsWith("#/p/") || h === "#/settings");
      for (const [m, hash] of screens) {
        if (m !== mode) {
          await setMode(page.request, m);
          mode = m;
        }
        const where = `${bname} ${c.w}x${c.h} ${c.theme} ${lang} ${m} ${hash.replace(P, "<p>")}`;
        await page.goto(`${base}/${hash}`, { waitUntil: "load" });
        await page.waitForSelector("main", { timeout: 20000 }).catch(() => fail(where, "no <main>"));
        await page.waitForTimeout(900);
        const o = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        if (o > 1) fail(where, `sideways scroll ${o}px`);
        if (m === "pro") {
          const hidden = await page.evaluate(() => {
            const nav = document.querySelector(".nav");
            return nav ? nav.scrollWidth - nav.clientWidth : 0;
          });
          if (hidden > 2 && c.w >= 1280 && (lang === "en" || lang === "tr")) fail(where, `top bar links cut off (${hidden}px hidden)`);
        }
        errs.splice(0).forEach((e) => fail(where, e));
      }
      // the clip end point (Pro, the selected clip): Play clip -> stops at the end, badge shows
      if (lang === "en" && c.theme === "dark" && c.w === SIZES[0][0]) {
        await setMode(page.request, "pro");
        await page.goto(`${base}/#/p/${P}`, { waitUntil: "load" });
        await page.waitForSelector('[data-testid="clipbar"]', { timeout: 20000 }).catch(() => fail(`${bname} clip end`, "no clip bar"));
        const r = await page.evaluate(async () => {
          const v = document.querySelector(".player video");
          const btn = document.querySelector(".player-bar .btn-primary");
          if (!v || !btn) return { err: "no player / play button" };
          v.muted = true;
          btn.click();
          const t0 = performance.now();
          while (performance.now() - t0 < 12000 && !v.paused) await new Promise((r) => setTimeout(r, 50));
          await new Promise((r) => setTimeout(r, 120));
          const left = document.querySelector('[data-testid="clip-left"]')?.textContent || "";
          const badge = document.querySelector('[data-testid="clip-end-badge"]')?.classList.contains("on");
          return { paused: v.paused, t: v.currentTime, left, badge };
        });
        if (r.err) fail(`${bname} clip end`, r.err);
        else {
          const range = await page.evaluate(() => document.querySelector(".clipbar-range-text")?.textContent || "");
          const m = range.match(/(\d+):(\d+(?:\.\d+)?)\s*[–-]\s*(\d+):(\d+(?:\.\d+)?)/);
          const end = m ? +m[3] * 60 + +m[4] : null;
          if (!r.paused) fail(`${bname} clip end`, "did not stop at the clip end");
          if (end != null && Math.abs(r.t - end) > 0.12) fail(`${bname} clip end`, `stopped at ${r.t.toFixed(3)} s, the clip ends at ${end} s`);
          if (!r.badge) fail(`${bname} clip end`, '"End of clip" not shown');
        }
      }
      await ctx.close();
    }
  }
  await browser.close();
  console.log(`${bname}: done`);
}
if (problems.length) {
  console.log([...new Set(problems)].join("\n"));
  process.exit(1);
}
console.log("cross-browser OK");
