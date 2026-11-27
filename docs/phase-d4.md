# Phase D4 (1.2.74): logo, website, feedback, extension stores, full test

<!-- The short Turkish report for the owner goes at the top when the release is done. -->

## Decisions log

### 1. Logo
- `installer/make_icons.py` now draws the Classic look (themes.css `--mark-*`): navy rounded tile
  `#0E1A33` with a thin `#2B3E66` border, white fin, blue `#5B9BFF` water line; light version = white
  tile, blue fin. The tile proportions copy the header logo (30 px tile, 20 px mark, 8 px radius). At
  16-32 px the mark is drawn bigger (GLYPH_SMALL) so the favicon / tray icon stays readable.
- Regenerated: app icon (.ico/.icns/.png), tray icon, PWA icons, favicons, Inno wizard images, the
  website's icons, and the photo slideshow's logo outro (slideshow.py, same constants, test checks).
- The launcher splash already followed the theme (welcome.SPLASH_DEFAULT is Classic): no change.
- `docs/logo-120.png` (Google brand review) is untouched: only `--google` redraws it (md5 checked).

### 2. Website (docs/sitegen -> docs/site)
- One Python generator (`docs/sitegen/build.py`) + one JSON text file per language. The build fails on a
  missing key or a changed `{placeholder}` in any language, so a half-translated site can't ship.
- English at the site root (so `privacy.html` / `terms.html` keep the URLs Google knows), the other 10
  languages in `/<lang>/`. No automatic redirect by browser language (search engines crawl in English);
  a small dismissable "this page is also in X" bar instead. The choice is remembered in localStorage.
- Pages: Home (one-sentence promise, big Download button, 3 steps, demo video, screenshots, features,
  the reviewed "How SharkyClips uses YouTube" section), Features, Download (requirements, SmartScreen
  help, SHA-256), FAQ (FAQPage data), Updates (last 12 versions from CHANGELOG.md in that language),
  Contact, Privacy, Terms, 404.
- Legal pages: the English text Google reviewed stays as it is. Only facts that changed were fixed:
  projects folder (Videos\SharkyClips with the installer), photos/slideshows, first-run component
  downloads, channel monitoring, the SharkyClips Helper (fills the page, never posts, talks only to
  127.0.0.1), Instagram automation switched off, the feedback button, the site's localStorage, a missing
  ")" and the "last updated" date. Other languages show a translated summary plus the full English text
  marked `lang="en"` as the binding version (no machine-translated legal text).
- One language-neutral Open Graph image (logo, name, English line, screenshot) for every language;
  titles/descriptions are translated per page.
- Screenshots and the demo video come from a throwaway SharkyClips on a fresh settings folder with the
  synthetic demo stream (docs/demo/make_demo.py) and the drawn slideshow photos: no real person, game or
  account. `docs/sitegen/capture-site.mjs` retakes them.
- No external fonts, scripts or trackers (test_website.py checks). No personal e-mail on the site or in
  the app (privacy): contact goes through GitHub issues and GitHub's private security reporting.
- Checks: `docs/sitegen/check-site.mjs` = axe (WCAG 2.1 A/AA + best practices) on all 88 pages in dark
  and light, sideways scroll at 360 px, console errors, broken internal links: all clean. Phones at
  320 px: no sideways scroll on any page. Lighthouse (headless Edge, local server): 96-100 in
  performance, accessibility, best practices and SEO on mobile and desktop for every tested page; the
  only remaining hints are compression/caching, which GitHub Pages provides.

### 3. Feedback
- `frontend/src/feedback.ts` builds a pre-filled GitHub issue URL: app version + a short OS label from
  the server (`feedback.system_label()`, e.g. "Windows 11 (AMD64, build 26300)"; no user/computer name,
  no paths). For an error, the message is added after scrubbing paths, e-mails, links and long ids.
  Nothing is sent by the app: the person submits the form on GitHub.
- Buttons: Settings → About (Easy and Pro) "Report a bug" / "Suggest an idea"; every error toast gets a
  "Report" button. The website's Contact page links the same forms (`source=website`).
- Issue templates: bug (what, steps, version, os, mode, hardware, logs, source) and feature (area list
  updated), config links to the FAQ and private security reporting. The `os` field is now a text input
  so the app can fill it in.
- E-mail link: not added (the only address available is the owner's private one).

### 4. Extension store packages
- A store copy can't carry the per-install key (`config.js`). It pairs once: Settings → Helper guide →
  "Show connection code" (6 digits, 10 minutes, 5 tries, one use). `/api/assist/ext/pair` is the only
  key-less path and only answers an extension origin (`chrome-extension://`, `moz-extension://`).
- bg.js works as a service worker (Edge/Chrome) and as a Firefox background script; the key comes from
  config.js (SharkyClips' own copy) or from storage (paired store copy). New toolbar popup with status
  and the code field, 11 `_locales`.
- Two copies in one browser: only the first copy that has its key fills the page (DOM mark).
- Firefox fills once the store add-on has spoken to SharkyClips from there (`can_fill`).
- `installer/build_extension.py` makes reproducible Edge / Firefox / source zips and refuses a package
  with config.js, remote code or a host permission beyond 127.0.0.1/localhost. Firefox: gecko id
  `sharkyclips-helper@utkualsir.github.io`, `data_collection_permissions: none`, min Firefox 142;
  `web-ext lint`: 0 errors, 0 warnings. Real headless Edge: the Edge package paired (wrong code refused,
  right code connected).
- Store texts, images and the step-by-step guide: `docs/extension-stores.md`, `docs/extension-store/`.

### 5. Full test (in progress)
- Bug found and fixed: dialogs on a scrolled page opened off-screen under the top bar. `.page-fx` (the
  page-enter animation) kept an identity transform (`animation-fill-mode: both`), which made it the
  containing block of every `position: fixed` dialog. Now `backwards` (also on the top bar items and the
  welcome body). Regression test: test_dialog_position.py.
- Bug found (introduced in this session, never shipped) and fixed: SharkyClips' own unpacked copy of the
  Helper got a `_locales/` folder but its manifest had no `default_locale`, so Chromium refused to load
  it and every assisted upload would have waited forever (the 4 real-Edge tests timed out). Manifest now
  has `default_locale: "en"`; test_extension_store.py checks it, and a direct headless-Edge load
  confirmed the service worker starts.

## Resume point (paused again 2026-11-27, user shut the PC down)
Done and verified: tasks 1-4 (logo, site in 11 languages + checks, feedback, extension packages + pairing),
two bugs fixed (dialog position, Helper manifest), test_assisted_upload.py 18/18 green (real Edge).
Next, in order:
1. DONE: full pytest suite green (all ~1290 tests; assisted upload 18/18 separately).
   DONE: layout-check Classic 1530 views (tr/ar/en, 9 sizes, light/dark) and Ocean/Sign/Contrast 1224 views.
   (A first run crashed only because the PC went to sleep.)
2. Still to run: layout-check quick pass in es,pt,de,fr,hu,ru,zh,ja (interrupted, rerun:
   LAYOUT_CHANNEL=msedge LAYOUT_PRESETS=classic LAYOUT_QUICK=1 LAYOUT_LANGS=es,pt,de,fr,hu,ru,zh,ja),
   then preview-check, axe-check (all presets), browser-check. Fixture server: scratchpad fixserve.sh
   (if the scratchpad is gone: CI's commands from .github/workflows/ci.yml with SHARKYCLIPS_DOWNLOADS,
   SHARKYCLIPS_QUEUE_HOME and APPDATA pointed into a temp folder). UI checks on a fixture (`frontend/scripts/layout-fixture.py`, server on 8799 with SHARKYCLIPS_DOWNLOADS set):
   layout-check (all presets, extra langs), preview-check, axe-check, browser-check, handoff-check.
3. CHANGELOG: insert the drafted 1.2.74 entry (docs/changelog-1.2.74-draft.md, delete that file after inserting;
   again from this log) above 1.2.73; VERSION 1.2.74; README badge; `npm run build` AFTER the bump;
   rebuild the site (`docs/sitegen/build.py`) and extension zips (`installer/build_extension.py`).
4. Commit, tag v1.2.74, push, gh release (attach the extension zips), wait for CI + installer workflow green.
5. Publish the site (`bash docs/publish-site.sh "..."`) once the 1.2.74 setup .exe exists on the release.
6. Remove dev_in_progress.json, restart the user's app if idle, write the Turkish report at the top.
