// Copies the launch-sequence CSS (styles.css, between /* splash:begin */ and /* splash:end */)
// into the launcher's splash page (backend/sharkyclips/web/splash.html), so both look the same.
// Runs before every build (npm run build). Use --check to only report a difference.
import { readFileSync, writeFileSync } from "node:fs";

const css = new URL("../src/styles.css", import.meta.url);
const html = new URL("../../backend/sharkyclips/web/splash.html", import.meta.url);
const BEGIN = "/* splash:begin */";
const END = "/* splash:end */";

const src = readFileSync(css, "utf8");
const a = src.indexOf(BEGIN);
const b = src.indexOf(END);
if (a < 0 || b < a) throw new Error("styles.css: splash markers missing");
const block = src.slice(a, b + END.length);

const page = readFileSync(html, "utf8");
const pa = page.indexOf(BEGIN);
const pb = page.indexOf(END);
if (pa < 0 || pb < pa) throw new Error("splash.html: splash markers missing");
const next = page.slice(0, pa) + block + page.slice(pb + END.length);
if (next === page) {
  console.log("splash.html is in sync");
} else if (process.argv.includes("--check")) {
  console.log("splash.html is out of date: run node scripts/sync-splash.mjs");
  process.exit(1);
} else {
  writeFileSync(html, next);
  console.log("splash.html updated");
}
