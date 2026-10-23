// Checks that every locale has the same keys as en.ts and that the code only uses
// keys that exist.  Run: node scripts/check-i18n.mjs
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const PLURAL = /_(zero|one|two|few|many|other)$/;
const keysOf = (file) =>
  new Set([...readFileSync(join(root, "i18n/locales", file), "utf8").matchAll(/^\s*"([^"]+)":/gm)].map((m) =>
    m[1].replace(PLURAL, ""),
  ));

const en = keysOf("en.ts");
let bad = 0;
for (const f of readdirSync(join(root, "i18n/locales"))) {
  if (f === "en.ts") continue;
  const ks = keysOf(f);
  const missing = [...en].filter((k) => !ks.has(k));
  const extra = [...ks].filter((k) => !en.has(k));
  if (missing.length || extra.length) {
    bad++;
    console.log(`${f}: missing ${missing.join(", ") || "-"} | extra ${extra.join(", ") || "-"}`);
  }
}

const files = [];
const walk = (d) => {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.tsx?$/.test(n) && !p.includes("locales")) files.push(p);
  }
};
walk(root);
const used = new Set();
for (const f of files) for (const m of readFileSync(f, "utf8").matchAll(/\bt\("([a-z_]+\.[a-z_.]+)"/g)) used.add(m[1]);
const undef = [...used].filter((k) => !en.has(k));
if (undef.length) {
  bad++;
  console.log("used but not defined:", undef.join(", "));
}
console.log(bad ? "i18n check FAILED" : `i18n OK: ${en.size} keys, ${used.size} used literally`);
process.exit(bad ? 1 : 0);
