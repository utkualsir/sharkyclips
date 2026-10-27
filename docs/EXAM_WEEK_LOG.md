# Exam week log

Autonomous work session started 2026-10-27 (base version 1.2.5). Every decision and open question
is written down here so it can be reviewed later. Nothing was published; the repo stays private.

Ground rules followed: headless browser only, no Whisper/LLM/render runs on real videos, no GPU
stress, one commit per task, one version bump at the end.

## Task 1: public release readiness

**Sweep** (`git grep` over everything except `frontend/dist` and the lockfile, plus the full git
history for keys/tokens):

- No secrets, API keys, OAuth client files, tokens or local paths in the tree or in the history.
- No `TODO` / `FIXME` / `console.log` / `breakpoint()` / stray `print()` in the app code.
- Your full name was used as test data in `backend/tests/test_welcome.py` (channel-name hashtag
  test). Replaced with a made-up channel name.
- `welcome.py` mentioned "Claude Code" in a docstring; made it neutral ("a development session").
- The GitHub user name `utkualsir` only appears in repo URLs (README, installers, updater, bundle
  id `io.github.utkualsir.sharkyclips`). That is expected for a public repo, so it stays.
- "Measured on an RTX 5070 Laptop" in README / how-it-works is a benchmark statement, not a
  hardcoded setting. Kept, but phrased as "a mid-range laptop GPU (RTX 5070 Laptop, 8 GB)".
- Screenshots and the demo GIF only show your own Delta Force project (unchanged).

**Docs fixes:**

- README said "Nothing is uploaded" and the FAQ said "SharkyClips never uploads anything", which
  contradicts the optional YouTube upload. Rewritten (English and Turkish) to: nothing leaves the
  PC unless *you* press Upload, and then only to your own YouTube channel.
- New `CONTRIBUTING.md` (setup, checks, project rules like the VERSION file and the 7 locales,
  no console windows) and `SECURITY.md` (how to report, what the LAN mode exposes).
  README's Contributing section now points to it.

**Open questions for you:**

- **Commit author email.** All 19 commits are authored as `utkualsir <utkualsir@gmail.com>`. When
  the repo goes public, that address is visible in the history. Rewriting history is destructive,
  so I didn't. If you mind: set `git config user.email <id>+utkualsir@users.noreply.github.com`
  for future commits, and decide yourself whether to rewrite old ones before going public.
- `CLAUDE.md` is committed and mentions the dev PC's GPU. Harmless, but you may want to keep it
  out of the public repo (or keep it: it doubles as contributor notes).
- The UI still stores the theme / language in `localStorage` keys `cf-theme` / `cf-lang` (old
  ClipForge prefix). Renaming them would reset every user's choice, so they stay.

## Task 2: Google verification prep

- `docs/site/`: static project site in the app's look (navy/gold, Instrument Serif + Geist, dark
  and light from the OS setting): `index.html` (what the app does + a table of exactly what it
  does with YouTube data, per scope), `privacy.html`, `terms.html`. Checked headless at 1280 px
  and 390 px in both color schemes (no horizontal scroll).
- `.github/workflows/pages.yml`: deploys `docs/site` to GitHub Pages, **manual trigger only**
  (`workflow_dispatch`). Nothing is published; Pages isn't enabled.
- `docs/google-verification.md`: checklist, scope justifications, demo-video script and answers
  for the YouTube API audit / quota form.
- The app's Settings → YouTube card now shows "SharkyClips uses YouTube API Services..." with links
  to the YouTube Terms, Google Privacy Policy, the SharkyClips privacy policy and Google's
  permissions page (required by the YouTube API policies; 7 languages).
- The policy text was checked against the code: scopes (`youtube.SCOPES`), what is read
  (`channels.list mine`, `videos.list` of own IDs, Analytics `averageViewPercentage` for hook-test
  uploads only), timing (views sync about twice a day, retention 48 h after publishing), storage
  paths.

**Decisions:**

- Contact on the site = GitHub issues + the private security advisory form, so your email isn't
  published. Google's consent screen still needs a support email (your choice, in the checklist).
- Google Fonts on the site (to match the app); disclosed in the privacy policy.
- The privacy-policy link in the app points to `https://utkualsir.github.io/sharkyclips/privacy.html`
  (`PRIVACY_URL` in `Publish.tsx`). It 404s until the repo is public and the Pages workflow ran.

**Open questions for you (important):**

- **Verification only helps with a shared OAuth client.** Today each user brings their own Google
  Cloud project, and each such project stays "unaudited" (uploads forced private). Shipping one
  SharkyClips client is a product decision (shared quota pool), so I didn't change it. Details
  at the top of `docs/google-verification.md`.
- **`github.io` as the verified domain** usually works (it's on the Public Suffix List), but if
  Google rejects it you need a custom domain.
- **Stored statistics after Disconnect** stay in the project files. Google's policies want them
  deleted on revocation; suggested follow-up in the verification doc.
