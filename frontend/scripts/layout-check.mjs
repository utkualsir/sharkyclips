// Layout regression check (headless browser): no overlapping panels, lists scroll inside their own
// panel with a usable height, counts visible, nothing cut off, no sideways page scroll.
// Every screen x laptop / desktop / phone sizes x light + dark x tr / ar (RTL) / en.
//
//   python frontend/scripts/layout-fixture.py <dir>          (prints the project id)
//   SHARKYCLIPS_HOME=<dir>/home python backend/cli.py serve --port 8799 --no-browser
//   node frontend/scripts/layout-check.mjs http://127.0.0.1:8799 <project-id> [screenshot-dir]
//
// LAYOUT_CHANNEL=msedge uses the installed Edge (Windows dev PC); CI uses Playwright's Chromium.
// LAYOUT_QUICK=1 checks fewer combinations. Exit code 1 when anything overlaps.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// Playwright from frontend/node_modules, or from the folder you run this in.
const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  ({ chromium } = req("playwright"));
}

const [base, pid, shotDir] = process.argv.slice(2);
if (!base || !pid) throw new Error("usage: node layout-check.mjs <base-url> <project-id> [screenshot-dir]");
if (shotDir) mkdirSync(shotDir, { recursive: true });
const quick = process.env.LAYOUT_QUICK === "1";

const SIZES = quick
  ? [[1280, 720], [1536, 864], [390, 844]]
  : [[1024, 700], [1280, 720], [1280, 800], [1366, 768], [1536, 864], [1707, 960], [1920, 1080], [1280, 1000], [390, 844]];
// LAYOUT_SIZES=1024x700,390x844 and LAYOUT_LANGS=tr: one failing case again, fast (local use)
if (process.env.LAYOUT_SIZES)
  SIZES.splice(0, SIZES.length, ...process.env.LAYOUT_SIZES.split(",").map((s) => s.split("x").map(Number)));
const LANGS = process.env.LAYOUT_LANGS ? process.env.LAYOUT_LANGS.split(",") : quick ? ["tr", "ar"] : ["tr", "ar", "en"];
const THEMES = ["light", "dark"];
const P = encodeURIComponent(pid);
// mode: Easy (the default) or Pro; switched on the server before the screen loads
const SCREENS = [
  { name: "easy-home", mode: "easy", hash: "#/", ready: ".ez-create" },
  { name: "easy-project", mode: "easy", hash: `#/p/${P}`, ready: ".ez-grid" },
  { name: "easy-library", mode: "easy", hash: "#/library", ready: ".ez-tabs", tabs: [null, ".ez-tabs button:nth-child(3)"] },
  { name: "easy-settings", mode: "easy", hash: "#/settings", ready: ".ez-settings" },
  { name: "approve", mode: "easy", hash: "#/approve", ready: ".approve-card, .approve-empty" },
  { name: "project", mode: "pro", hash: `#/p/${P}`, ready: ".side-tabs", tabs: [null, ".side-tablist button:nth-child(2)"] },
  { name: "projects", mode: "pro", hash: "#/", ready: "main" },
  { name: "library", mode: "pro", hash: "#/library", ready: "main" },
  { name: "calendar", mode: "pro", hash: "#/library/calendar", ready: "main" },
  { name: "queue", mode: "pro", hash: "#/queue", ready: "main" },
  { name: "stories", mode: "pro", hash: `#/p/${P}/stories`, ready: "main" },
  { name: "bestof", mode: "pro", hash: `#/p/${P}/bestof`, ready: "main" },
  { name: "studio-music", mode: "pro", hash: "#/studio/music", ready: "main" },
  { name: "studio-brand", mode: "pro", hash: "#/studio/brand", ready: "main" },
  { name: "studio-words", mode: "pro", hash: "#/studio/words", ready: "main" },
  { name: "studio-games", mode: "pro", hash: "#/studio/games", ready: ".games-json" },
  { name: "settings", mode: "pro", hash: "#/settings", ready: "main" },
  { name: "stats", mode: "pro", hash: "#/stats", ready: "main" },
  { name: "pubqueue", mode: "pro", hash: "#/publish-queue", ready: ".pq-actions" },
  { name: "easy-pubqueue", mode: "easy", hash: "#/publish-queue", ready: ".pq-actions" },
];

/** Runs in the page. Returns a list of problems. */
function audit() {
  const issues = [];
  const shown = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 4 && r.height >= 4;
  };
  // sticky bars (top bar, panel headers) overlap content by design once the page scrolls
  const inFlow = (el) => !["absolute", "fixed", "sticky"].includes(getComputedStyle(el).position);
  const boxy = (el) => getComputedStyle(el).display !== "inline"; // wrapped inline text boxes always "overlap"
  scrollTo(0, 0);
  const name = (el) => {
    const c = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    return el.tagName.toLowerCase() + (c ? "." + c : "") + (el.textContent ? ` "${el.textContent.trim().slice(0, 18)}"` : "");
  };
  // 1. in-flow siblings never overlap (panels, tabs, chips, buttons, rows)
  const skip = (el) => el.closest("svg, video, canvas, select, .sr-only, [aria-hidden='true'], .skeleton, .modal-backdrop");
  for (const parent of document.querySelectorAll("body *")) {
    if (parent.children.length < 2 || skip(parent) || !shown(parent)) continue;
    const kids = [...parent.children].filter((k) => shown(k) && inFlow(k) && boxy(k) && !skip(k));
    if (kids.length < 2 || kids.length > 60) continue;
    const rects = kids.map((k) => k.getBoundingClientRect());
    for (let i = 0; i < kids.length; i++)
      for (let j = i + 1; j < kids.length; j++) {
        const a = rects[i], b = rects[j];
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > 2 && h > 2) issues.push(`overlap: ${name(kids[i])} / ${name(kids[j])} in ${name(parent)}`);
      }
  }
  // 2. scrolling lists keep a usable height
  for (const s of document.querySelectorAll(".side-scroll")) {
    if (shown(s) && s.getBoundingClientRect().height < 150) issues.push(`list squeezed: ${name(s)} ${Math.round(s.getBoundingClientRect().height)}px`);
  }
  // 3. a hidden overflow must not cut content off (scrolling containers are fine)
  for (const el of document.querySelectorAll("main *")) {
    const cs = getComputedStyle(el);
    if (cs.overflowY !== "hidden" || !shown(el) || skip(el)) continue;
    if (el.scrollHeight > el.clientHeight + 4 && el.clientHeight > 40 && !el.matches(".clamp, [class*='clamp'], .cand-title, .title, h1, h2, h3, p"))
      issues.push(`cut off: ${name(el)} (${el.scrollHeight} > ${el.clientHeight})`);
  }
  // 3b. nothing hides content sideways (button groups, rows); real scrollers (tables, the nav,
  //     calendars, chip strips) are fine, and so is single-line text with an ellipsis
  for (const el of document.querySelectorAll("main *")) {
    const cs = getComputedStyle(el);
    if (!["hidden", "auto", "scroll"].includes(cs.overflowX) || !shown(el) || skip(el)) continue;
    if (cs.textOverflow === "ellipsis" || (cs.whiteSpace === "nowrap" && el.children.length === 0)) continue;
    if (el.matches("table, .table-wrap, [class*='scroll'], [class*='strip'], [class*='cal'], [class*='timeline'], pre, code, textarea, .cand-reasons, .chips")) continue;
    if (el.scrollWidth > el.clientWidth + 4) issues.push(`cut off sideways: ${name(el)} (${el.scrollWidth} > ${el.clientWidth})`);
  }
  // 4. a sticky panel fits on screen once it sticks
  for (const el of document.querySelectorAll(".proj-side")) {
    if (getComputedStyle(el).position !== "sticky") continue;
    scrollTo(0, 600);
    const r = el.getBoundingClientRect();
    if (r.bottom > innerHeight + 1) issues.push(`sticky panel runs off screen: bottom ${Math.round(r.bottom)} > ${innerHeight}`);
    scrollTo(0, 0);
  }
  // 5. tab counts are visible and not covered
  for (const c of document.querySelectorAll(".side-tabs .count")) {
    c.scrollIntoView({ block: "center" });
    const r = c.getBoundingClientRect();
    const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!shown(c) || !at || !(at === c || c.contains(at))) issues.push(`count hidden or covered: ${name(c)}`);
  }
  scrollTo(0, 0);
  // 6. no sideways page scroll
  if (document.documentElement.scrollWidth > innerWidth + 1) {
    let worst = null;
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.right > innerWidth + 1 && inFlow(el) && (!worst || r.width < worst.getBoundingClientRect().width)) worst = el;
    }
    issues.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${innerWidth}), e.g. ${worst ? name(worst) : "?"}`);
  }
  return [...new Set(issues)];
}

const browser = await chromium.launch(process.env.LAYOUT_CHANNEL ? { channel: process.env.LAYOUT_CHANNEL } : {});
const failures = [];
let checked = 0;
for (const lang of LANGS)
  for (const theme of THEMES) {
    if (lang === "en" && theme === "dark") continue;
    for (const [w, h] of SIZES) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h } });
      await ctx.addInitScript(([l, t]) => {
        localStorage.setItem("cf-lang", l);
        localStorage.setItem("cf-lang-set", "1");
        localStorage.setItem("cf-theme", t);
        localStorage.setItem("sc-motion", "off");
        sessionStorage.setItem("sc-splash-shown", "1");
      }, [lang, theme]);
      const page = await ctx.newPage();
      let mode = null;
      for (const s of SCREENS) {
        if (s.mode !== mode) {
          // the app reads the mode once at start: switch it on the server, then load afresh
          await page.request.put(`${base}/api/easy/settings`, { data: { mode: s.mode } });
          await page.goto("about:blank");
          mode = s.mode;
        }
        for (let attempt = 1; ; attempt++) {
          try {
            await page.goto(`${base}/${s.hash}`, { waitUntil: "load" });
            await page.waitForSelector(s.ready, { timeout: 20000 });
            break;
          } catch (e) {
            if (attempt >= 2) throw new Error(`${s.name} ${lang} ${theme} ${w}x${h} never loaded: ${e.message.split(/\r?\n/)[0]}`);
            await page.reload({ waitUntil: "load" }); // a slow first load (server just started): once more
          }
        }
        await page.waitForTimeout(700);
        for (let k = 0; k < 3 && (await page.locator(".modal-backdrop").count()); k++) {
          await page.keyboard.press("Escape"); // "What's new" & co. would cover the page
          await page.waitForTimeout(250);
        }
        for (const tab of s.tabs ?? [null]) {
          if (tab) {
            await page.click(tab);
            await page.waitForTimeout(400);
          }
          const label = `${s.name}${tab ? "-tab" : ""} ${lang} ${theme} ${w}x${h}`;
          const issues = await page.evaluate(audit);
          checked++;
          if (issues.length) {
            failures.push(`${label}:\n    ${issues.slice(0, 8).join("\n    ")}`);
            if (shotDir) await page.screenshot({ path: join(shotDir, `${label.replace(/ /g, "_")}.png`) });
          }
        }
      }
      await ctx.close();
    }
  }
await browser.close();
if (failures.length) {
  console.log(`LAYOUT PROBLEMS (${failures.length} of ${checked} views):\n` + failures.join("\n"));
  process.exit(1);
}
console.log(`Layout OK: ${checked} views (${SCREENS.length} screens, ${SIZES.length} sizes, ${LANGS.join("/")}, light/dark).`);
