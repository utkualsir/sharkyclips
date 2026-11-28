// node shots.mjs <base> <outdir> path1 path2 ...  (run from frontend/ so playwright resolves)
import { createRequire } from "node:module";
import { join } from "node:path";
const { chromium } = createRequire(join(process.cwd(), "index.js"))("playwright");
const [base, out, ...paths] = process.argv.slice(2);
const b = await chromium.launch({ channel: "msedge" });
for (const [w, h, tag] of [[1366, 768, "laptop"], [390, 844, "phone"]]) {
  for (const theme of ["dark", "light"]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: theme });
    for (const p of paths) {
      const page = await ctx.newPage();
      await page.goto(base + "/" + p, { waitUntil: "load" });
      await page.waitForTimeout(600);
      const name = (p.replace(/[\/.]/g, "_") || "index") + `-${tag}-${theme}`;
      await page.screenshot({ path: join(out, name + "-fold.png") });
      if (theme === "dark" && tag === "laptop") await page.screenshot({ path: join(out, name + "-full.png"), fullPage: true });
      await page.close();
    }
    await ctx.close();
  }
}
await b.close();
