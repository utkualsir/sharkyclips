// Browser test of "Connect with Google" against the fake Google server (headless Edge).
//
//   1. python backend/tests/e2e/serve_fake_google.py 8131      (prints the app + fake Google URLs)
//   2. npm i playwright@1.56.0 (in any folder), then from there:
//        node <repo>/backend/tests/e2e/youtube-connect.mjs http://127.0.0.1:8131 <google-url> [screenshot-dir]
//
// Covers: onboarding step, the warning tip, allow, cancel on Google, cancel in the app, no channel,
// several channels, revoked access (banner + one-click reconnect), the Advanced wizard with a
// pasted client JSON, phone width and both themes (no sideways scrolling).
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const { chromium } = createRequire(join(process.cwd(), "index.js"))("playwright");
const [base, google, shots = "e2e-shots"] = process.argv.slice(2);
if (!base || !google) throw new Error("usage: node youtube-connect.mjs <app-url> <fake-google-url> [shots]");
mkdirSync(shots, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (method, path, body, root = base) =>
  fetch(root + path, { method, headers: { "content-type": "application/json" }, body: body && JSON.stringify(body) }).then((r) => r.json());
const fakeSet = (o) => api("POST", "/_set", o, google);
let failures = 0;
const check = (ok, what) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failures++;
};

const browser = await chromium.launch({ channel: "msedge" });

async function newPage(theme, viewport = { width: 1280, height: 900 }) {
  const ctx = await browser.newContext({ viewport, locale: "en-US" });
  await ctx.addInitScript((t) => {
    localStorage.setItem("cf-theme", t);
    localStorage.setItem("cf-lang", "en");
    localStorage.setItem("cf-lang-set", "1");
    sessionStorage.setItem("sc-splash-shown", "1");
  }, theme);
  return { ctx, page: await ctx.newPage() };
}

/** Click a connect button; in Google's (fake) page click Allow / Cancel; return the result tab. */
async function signIn(page, ctx, trigger, choice = "allow") {
  const popupP = ctx.waitForEvent("page", { timeout: 15000 });
  await trigger();
  const popup = await popupP;
  await popup.waitForLoadState("load");
  await popup.click(choice === "allow" ? "#allow" : "#deny");
  await popup.waitForSelector("main h1", { timeout: 15000 });
  return popup;
}

// ------------------------------------------------------------------ 1. onboarding
{
  const { ctx, page } = await newPage("light");
  await page.goto(`${base}/#/`);
  await page.waitForSelector(".welcome", { timeout: 20000 });
  for (let i = 0; i < 3; i++) await page.click(".welcome-btn-primary");
  await page.waitForSelector("text=Connect YouTube (optional)");
  await page.screenshot({ path: join(shots, "01-onboarding-step.png") });
  await page.click(".welcome .gbtn");
  await page.waitForSelector("text=Google will show a warning");
  await page.screenshot({ path: join(shots, "02-warning-tip.png") });
  const popup = await signIn(page, ctx, () => page.click("text=Got it, open Google"));
  const title = await popup.textContent("main h1");
  check(title === "Connected!", "result page says Connected!");
  await popup.screenshot({ path: join(shots, "03-result-page.png") });
  await page.waitForSelector("text=Connected: Fake Channel", { timeout: 10000 });
  check(true, "onboarding shows the channel");
  await page.screenshot({ path: join(shots, "04-onboarding-connected.png") });
  await page.click(".welcome-btn-primary"); // Finish
  await page.waitForSelector(".welcome", { state: "detached" });
  await ctx.close();
}

// ------------------------------------------------------------------ 2. settings: cancel paths, no channel, several channels
for (const theme of ["dark", "light"]) {
  const { ctx, page } = await newPage(theme);
  await page.goto(`${base}/#/settings`);
  await page.waitForSelector("#youtube .yt-account, #youtube .gbtn", { timeout: 20000 });
  await sleep(800); // the page fade-in
  if (theme === "dark") {
    check((await page.textContent("#youtube")).includes("Fake Channel"), "settings shows the connected channel");
    check((await page.textContent("#youtube")).includes("up to 100 people"), "settings shows the 100-user limit");
    await page.locator("#youtube").screenshot({ path: join(shots, `05-settings-connected-${theme}.png`) });
    await page.click("#youtube >> text=Disconnect");
    await page.waitForSelector("#youtube .gbtn-big");

    // cancel on Google's screen (tip: tick "don't show again")
    await page.click("#youtube .gbtn-big");
    await page.check(".ytc-check input");
    let popup = await signIn(page, ctx, () => page.click("text=Got it, open Google"), "deny");
    check((await popup.textContent("main h1")) === "Connection cancelled", "result page says cancelled");
    await page.waitForSelector("text=Connection cancelled. Nothing was changed.");
    check(true, "app says cancelled, nothing changed");
    await popup.close();

    // cancel in the app while waiting (no tip this time)
    const popupP = ctx.waitForEvent("page");
    await page.click("#youtube .gbtn-big");
    const waiting = await popupP;
    await page.waitForSelector("text=Finish in your browser");
    await page.locator("#youtube").screenshot({ path: join(shots, `06-waiting-${theme}.png`) });
    await page.click(".ytc-wait >> text=Cancel");
    await page.waitForSelector("#youtube .gbtn-big");
    await waiting.close();
    check(true, "cancel in the app returns to the button");

    // an account without a channel, then "Check again"
    await fakeSet({ channel_count: 0 });
    popup = await signIn(page, ctx, () => page.click("#youtube .gbtn-big"));
    check((await popup.textContent("main h1")).includes("no YouTube channel"), "result page: no channel");
    await popup.close();
    await page.waitForSelector("text=This Google account has no YouTube channel yet");
    await page.locator("#youtube").screenshot({ path: join(shots, `07-no-channel-${theme}.png`) });
    await fakeSet({ channel_count: 1 });
    await page.click("button:has-text(\"Check again\")");
    await page.waitForSelector("#youtube .ytc-name:has-text('Fake Channel')");
    check(true, "check again finds the new channel");

    // several channels: pick one
    await page.click("#youtube >> text=Disconnect");
    await fakeSet({ channel_count: 2 });
    popup = await signIn(page, ctx, () => page.click("#youtube .gbtn-big"));
    await popup.close();
    await page.waitForSelector(".ytc-channels");
    await page.click(".ytc-channel:has-text('Second Channel')");
    await page.waitForSelector("#youtube .ytc-name:has-text('Second Channel')");
    check(true, "picked the second channel");
    await page.locator("#youtube").screenshot({ path: join(shots, `08-channels-${theme}.png`) });
    await fakeSet({ channel_count: 1 });
  } else {
    await page.locator("#youtube").screenshot({ path: join(shots, `05-settings-connected-${theme}.png`) });
  }
  await ctx.close();
}

// ------------------------------------------------------------------ 3. revoked: banner on every screen + reconnect
{
  await fakeSet({ revoke_refresh: true, expire_next: 1 });
  await fetch(`${base}/api/youtube/playlists?refresh=true`); // the 401 -> refresh -> invalid_grant
  const yt = await api("GET", "/api/youtube");
  check(!yt.connected && yt.signed_out?.reason === "invalid_grant", "revoked access is noticed");
  await fakeSet({ revoke_refresh: false });
  const { ctx, page } = await newPage("dark");
  await page.goto(`${base}/#/`);
  await page.waitForSelector(".yt-banner", { timeout: 20000 });
  check((await page.textContent(".yt-banner")).includes("Second Channel"), "banner names the channel");
  await page.screenshot({ path: join(shots, "09-signed-out-banner.png") });
  await page.click(".yt-banner button:has-text(\"Reconnect\")");
  await page.waitForSelector("text=Google will show a warning"); // a new browser: the tip first
  const popup = await signIn(page, ctx, () => page.click("text=Got it, open Google"));
  await popup.close();
  await page.waitForSelector(".yt-banner", { state: "detached", timeout: 10000 });
  check(true, "one-click reconnect removes the banner");
  await ctx.close();
}

// ------------------------------------------------------------------ 4. advanced wizard (own project)
{
  const { ctx, page } = await newPage("dark");
  await page.goto(`${base}/#/settings`);
  await page.waitForSelector("#youtube .yt-account");
  await page.click("#youtube >> text=Disconnect");
  await page.click("text=Advanced: use your own Google project");
  await page.waitForSelector(".ytw");
  for (let i = 1; i <= 4; i++) {
    check((await page.textContent(".ytw-count")) === `Step ${i} of 5`, `wizard step ${i} of 5`);
    check((await page.locator(".ytw a[href*='console.cloud.google.com']").count()) > 0, `step ${i} links to the Console`);
    if (i === 3) await page.locator(".ytw").screenshot({ path: join(shots, "10-wizard-step3.png") });
    await page.click("text=Done, next");
  }
  await page.fill(".ytw textarea", "AIzaSyFAKEKEY");
  await page.waitForSelector("text=That's an API key, not an OAuth client.");
  check(true, "a pasted API key is explained");
  await page.locator(".ytw").screenshot({ path: join(shots, "11-wizard-bad-json.png") });
  await page.fill(".ytw textarea", JSON.stringify({ installed: { client_id: "9-own.apps.googleusercontent.com", client_secret: "s", project_id: "my-sharky" } }));
  await page.waitForSelector("text=Looks right: project my-sharky");
  const popup = await signIn(page, ctx, () => page.click("text=Save and connect"));
  await popup.close();
  await page.waitForSelector("text=Using your own Google project: my-sharky");
  check((await api("GET", "/api/youtube")).mode === "own", "connected with the own client");
  await page.click("text=Back to the one-click connection");
  await page.waitForSelector("#youtube .gbtn-big");
  check((await api("GET", "/api/youtube")).mode === "shared", "back to the built-in client");
  await ctx.close();
}

// ------------------------------------------------------------------ 5. phone width, both themes, Turkish + Arabic
for (const [theme, lang] of [["dark", "en"], ["light", "tr"], ["dark", "ar"]]) {
  const { ctx, page } = await newPage(theme, { width: 390, height: 844 });
  await ctx.addInitScript((l) => localStorage.setItem("cf-lang", l), lang);
  await page.goto(`${base}/#/settings`);
  await page.waitForSelector("#youtube .gbtn-big", { timeout: 20000 });
  await page.locator("#youtube").scrollIntoViewIfNeeded();
  await sleep(800);
  await page.click("#youtube .ytc-adv > summary");
  await page.waitForSelector(".ytw");
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(over <= 0, `phone ${theme}/${lang}: no sideways scrolling (${over}px)`);
  const unnamed = await page.evaluate(() =>
    [...document.querySelectorAll("#youtube button, #youtube a")].filter((b) => !(b.textContent.trim() || b.getAttribute("aria-label"))).length,
  );
  check(unnamed === 0, `phone ${theme}/${lang}: every button has a name`);
  await page.locator("#youtube").screenshot({ path: join(shots, `12-phone-${theme}-${lang}.png`) });
  await ctx.close();
}

await browser.close();
console.log(failures ? `${failures} FAILED` : "all passed");
process.exit(failures ? 1 : 0);
