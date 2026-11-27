// Checks the built website (docs/site) the way a visitor sees it:
//   every page of every language, dark and light: axe-core (WCAG 2.1 A/AA + best practices),
//   no sideways scroll at 360 px, no console errors, every internal link and image resolves.
//
//   python -m http.server 8790 --directory docs/site      (any static server)
//   cd frontend && node ../docs/sitegen/check-site.mjs http://127.0.0.1:8790
//
// Exits 1 on any problem. Microsoft Edge headless (CHECK_CHANNEL=chromium for Playwright's Chromium).
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const req = createRequire(join(process.cwd(), "index.js"));
const { chromium } = req("playwright");
const AXE = readFileSync(req.resolve("axe-core/axe.min.js"), "utf8");
const base = (process.argv[2] || "http://127.0.0.1:8790").replace(/\/$/, "");
const LANGS = ["", "tr/", "es/", "pt/", "de/", "fr/", "hu/", "ru/", "ar/", "zh/", "ja/"];
const PAGES = ["", "features.html", "download.html", "faq.html", "updates.html", "contact.html", "privacy.html", "terms.html"];
const browser = await chromium.launch({ channel: process.env.CHECK_CHANNEL || "msedge" });
const problems = [];
const seen = new Set();
const internal = new Set();

for (const theme of ["dark", "light"]) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: theme, bypassCSP: true });
  const phone = await browser.newContext({ viewport: { width: 360, height: 780 }, colorScheme: theme });
  for (const l of LANGS) {
    for (const p of PAGES) {
      const url = `${base}/${l}${p}`;
      const page = await ctx.newPage();
      const errs = [];
      page.on("pageerror", (e) => errs.push(String(e)));
      page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
      const res = await page.goto(url);
      if (!res || res.status() !== 200) problems.push(`${url}: HTTP ${res && res.status()}`);
      await page.addScriptTag({ content: AXE });
      // open every FAQ / details so their content is checked too
      await page.evaluate(() => document.querySelectorAll("main details").forEach((d) => (d.open = true)));
      const r = await page.evaluate(async () => {
        // eslint-disable-next-line no-undef
        const out = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] } });
        return out.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0].target.join(" ")}`);
      });
      for (const v of r) problems.push(`${l}${p || "index"} [${theme}] axe ${v}`);
      if (errs.length) problems.push(`${url} [${theme}] console: ${errs.join(" | ")}`);
      if (theme === "dark") {
        const links = await page.evaluate(() => [...document.querySelectorAll("a[href], img[src], link[href], source[src], video[poster]")]
          .map((e) => e.href || e.src || e.poster).filter(Boolean));
        for (const h of links) if (h.startsWith(base)) internal.add(h.split("#")[0]);
      }
      await page.close();
      const ph = await phone.newPage();
      await ph.goto(url);
      if (await ph.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) problems.push(`${url} [${theme}] scrolls sideways at 360 px`);
      await ph.close();
      seen.add(url);
    }
  }
  await ctx.close();
  await phone.close();
}
const rq = await browser.newContext();
for (const u of internal) {
  const r = await rq.request.head(u).catch(() => null);
  if (!r || r.status() !== 200) problems.push(`broken link: ${u} (${r ? r.status() : "no answer"})`);
}
await rq.close();
await browser.close();
console.log(`${seen.size} pages x 2 themes, ${internal.size} internal links/files checked`);
if (problems.length) {
  console.log(problems.join("\n"));
  process.exit(1);
}
console.log("site check OK");
