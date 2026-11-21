// Public site check (1.2.63): every page of docs/site at phone / laptop / desktop width, light + dark:
// console errors, broken internal links / anchors / images, sideways scroll, keyboard skip link, axe.
//
//   python -m http.server 8790 --directory docs/site      (or any static server)
//   node frontend/scripts/site-check.mjs http://127.0.0.1:8790
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const req = createRequire(join(process.cwd(), "index.js"));
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  ({ chromium } = req("playwright"));
}
const AXE = readFileSync(req.resolve("axe-core/axe.min.js"), "utf8");
const base = (process.argv[2] || "http://127.0.0.1:8790").replace(/\/$/, "");
const PAGES = ["index.html", "privacy.html", "terms.html"];
const SIZES = [[390, 844], [1280, 720], [1920, 1080]];
const problems = [];
const fail = (where, msg) => problems.push(`${where}: ${msg}`);

const browser = await chromium.launch({ channel: process.env.LAYOUT_CHANNEL || undefined, headless: true });
for (const scheme of ["light", "dark"]) {
  for (const [w, h] of SIZES) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("requestfailed", (r) => {
      if (r.url().startsWith(base)) errors.push(`failed: ${r.url()}`);
    });
    for (const p of PAGES) {
      const where = `${p} ${w}x${h} ${scheme}`;
      const res = await page.goto(`${base}/${p}`, { waitUntil: "load" });
      if (!res || !res.ok()) fail(where, `HTTP ${res?.status()}`);
      await page.waitForTimeout(300);
      const info = await page.evaluate(() => {
        const out = { overflow: document.documentElement.scrollWidth - window.innerWidth, links: [], anchors: [], imgs: [] };
        for (const a of document.querySelectorAll("a[href]")) {
          const href = a.getAttribute("href");
          if (href.startsWith("#") && href.length > 1 && !document.getElementById(href.slice(1))) out.anchors.push(href);
          else if (!/^(https?:|mailto:|#)/.test(href)) out.links.push(href);
          if (!a.innerText.trim() && !a.getAttribute("aria-label") && !a.querySelector("img[alt]")) out.anchors.push(`empty link ${href}`);
        }
        for (const i of document.images) if (!i.complete || i.naturalWidth === 0) out.imgs.push(i.getAttribute("src"));
        return out;
      });
      if (info.overflow > 1) fail(where, `page scrolls sideways by ${info.overflow}px`);
      info.anchors.forEach((a) => fail(where, `broken anchor / link text: ${a}`));
      info.imgs.forEach((s) => fail(where, `image did not load: ${s}`));
      for (const l of info.links) {
        const [file, hash] = l.split("#");
        const r = await ctx.request.get(`${base}/${file}`);
        if (!r.ok()) fail(where, `broken link ${l} (${r.status()})`);
        else if (hash && !(await r.text()).includes(`id="${hash}"`)) fail(where, `missing anchor ${l}`);
      }
      // keyboard: the first Tab lands on the skip link
      await page.keyboard.press("Tab");
      const first = await page.evaluate(() => document.activeElement?.getAttribute("href"));
      if (first !== "#main") fail(where, `first Tab goes to ${first}, not the skip link`);
      if (w === 1280) {
        await page.addScriptTag({ content: AXE });
        const r = await page.evaluate(async () =>
          (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] })).violations.map(
            (v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target?.join(" ")}`,
          ),
        );
        r.forEach((v) => fail(where, `axe ${v}`));
      }
    }
    errors.forEach((e) => fail(`${w}x${h} ${scheme}`, `console: ${e}`));
    await ctx.close();
  }
}
await browser.close();
if (problems.length) {
  console.log([...new Set(problems)].join("\n"));
  process.exit(1);
}
console.log(`site OK: ${PAGES.length} pages x ${SIZES.length} sizes x 2 themes`);
