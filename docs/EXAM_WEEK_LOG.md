# Exam week log

Autonomous work sessions while the user studies. Newest first. Every decision and open question is
written down here so it can be reviewed later.

## Session 2: 2026-11-10 (base 1.2.37)

Ground rules: headless browser only, no visible windows, no heavy GPU jobs (Whisper ran on the CPU
on clips of 30 s to 2 min), Silent mode, no questions. One commit per task, one version bump at the
end.

### Task 2: stability sprint

**Test-order failures, both fixed at the root:**

1. `test_easy.py` then `test_welcome.py`: `test_onboarding_then_whats_new` simulates a brand-new
   user, but other test files leave projects in the shared test workspace, and a user with
   projects (correctly) skips onboarding. The test now says "no projects" explicitly; a new test
   covers the existing-user path (onboarding skipped, "What's new" shown).
2. `test_governor*.py` + `test_publishing.py` (an export hung): a test that ticks a real
   `Governor` reads this PC's real state. If the PC looked busy (a game, a fullscreen video), the
   governor decided to pause and `procs.suspend_all()` set a module-wide "paused" flag that was
   never cleared, so every ffmpeg a *later* test started was suspended at birth. Two tests already
   undid this by hand; `test_idle_governor_samples_cheaply_and_wakes_for_jobs` didn't. That's why
   it was rare and machine-dependent. Now an autouse fixture in `conftest.py` resumes any leaked
   pause and restores the installed governor after every test, so no test can leak it again.
3. Found by running the whole suite in **reverse file order**: `test_multipost` partial-failure
   retry read TikTok as "idle" right after it was published. Cause in the app (Windows only):
   `platforms.records()` and `multipost._store()` answered "no data" when they opened the file
   during another thread's atomic replace (WinError 5/32). In the UI that briefly showed a posted
   clip as unposted; for `save_clip_store` (read-modify-write) it could have wiped a clip's
   drafts. New `project.read_json_shared()` waits that moment out; both readers use it.

Both file orders now pass (613 tests, ~4.5 min each). There is no pytest-randomly in the venv, so
"reverse order" was done by passing the files in reverse; worth repeating after big test changes.

**v1.2.33 tag: left as it is (decision).** The tag points at `eb54d37`, one commit before the
changelog fix `eb33d5c` (the Chinese summary was under the 100-character test minimum), so CI on
the tag is red. Moving it would need a force-push of the tag, and the in-app updater runs
`git fetch --tags`: on every install that already has the old v1.2.33, a moved tag makes that
fetch fail ("would clobber existing tag"), which would stop updates for those users. A red CI
run on an old tag hurts no one; broken updates would. (The 1.2.35 / 1.2.36 runs that failed after
4-7 s were GitHub not starting jobs while the repo was private; nothing to fix.)

**Dead code removed** (vulture, then every name checked with `git grep` across backend, tests,
frontend scripts and CI; route handlers and test-only helpers kept): `audiomix._voice_rms`,
`swear_eval.falses` / `baseline_metrics`, `facecam.detect_facecam`, `llm.metadata_model`,
`publishing.split_key`, `taste.vote_of`, `style.socials_for_short`, `JobManager.tombstones`,
`youtube.clear_locked`.

### Task 4: Kick VOD / clip import

**What I found:** yt-dlp (2026.10.21, already a dependency) has working `kick:vod` and `kick:clip`
extractors, and every URL already went through yt-dlp, so a pasted Kick link half-worked before.
What was missing: the short `kick.com/video/<id>` links (yt-dlp needs the channel in the path), a
useful message for channel links (yt-dlp says "not currently live"), chat replay, and a plan B
for the next time Kick changes its site and yt-dlp's extractor breaks.

**What changed** (`backend/sharkyclips/kick.py`, `ingest.py`, `chat.py`, `game/__init__.py`):

- Every link shape: `kick.com/<ch>/videos/<id>`, `kick.com/video/<id>`, `kick.com/<ch>/clips/<id>`,
  `kick.com/<ch>?clip=<id>`. Channel links (`kick.com/<ch>`, `/videos`, `/clips`) get "That's a
  Kick channel, not a video" plus where to find a VOD, before anything downloads.
- yt-dlp first. If its Kick extractor fails, Kick's public endpoints (the same ones kick.com's
  own player uses, no login) give the title, channel, date and the HLS playlist, and yt-dlp
  downloads that. Subscriber-only VODs get a clear "can't download without an account" message
  (decision: no login support, like for YouTube members-only videos).
- **Chat replay** for VODs and clips: Kick's public messages endpoint answers ~5 s of chat per
  call, so it runs in 6 parallel parts (a 5 h VOD: a few minutes; Twitch's API is faster).
  `[emote:123:KEKW]` codes become `KEKW`, so emote spam counts as hype like on Twitch.
- The stream's **category** (Kick names the game) is saved as `source.category` and used as a
  game-detection hint next to the title.
- yt-dlp's "attempting impersonation" warning is hidden (Kick works without curl_cffi).
  Decision: no new dependency (`curl_cffi`); if Cloudflare starts blocking, adding
  `yt-dlp[default,curl-cffi]` to requirements is the fix.
- Easy mode's link placeholder and tour now say Kick (7 languages); docs updated.

**Tests:** `test_kick.py` (9 tests, fake Kick server, no network): link shapes, canonical links,
VOD/clip resolve, subscriber-only, chat windows (order, de-dup, emotes, clip offset), chat
dispatch, ingest fallback when yt-dlp's extractor fails, channel link refused before any
download, category -> game detection.

**Real test** (throwaway settings folder, Whisper `small` on the CPU, no GPU):

| Link | Result |
|---|---|
| xQc clip, `kick.com/xqc?clip=clip_01M6PNKW...` (30 s) | 1080p60 in 6 s; chat replay 161 messages / 119 people; transcript + highlights OK (1 candidate, hype 100) |
| Destiny VOD, `kick.com/video/01a1989d-...` (2:14, short link form) | resolved to `kick.com/destiny/videos/...`, 720p in 9 s, category "Just Chatting"; transcript + highlights OK (3 candidates). That stream had no chat; the same code read 31 messages in 20 s of a busy xQc VOD |

## Session 1: 2026-10-27 (1.2.5 -> 1.2.6)
### Summary (read this first)

All 7 tasks are done, each in its own commit, released as **1.2.6** (tag `v1.2.6`), CI green.
Nothing was published: the repo stays private and the GitHub Pages workflow is manual-only.
No heavy jobs ran (only a 20-second synthetic test video); all browser checks were headless.

| # | Task | Result |
|---|---|---|
| 1 | Release readiness | Repo clean of secrets/paths; README contradictions about uploading fixed; CONTRIBUTING.md + SECURITY.md |
| 2 | Google verification prep | `docs/site/` (home, privacy, terms), manual Pages workflow, `docs/google-verification.md` (form answers, demo script), YouTube legal links in the app |
| 3 | LAN security | Optional PIN/password, scrypt-hashed, rate-limited login, login screen, `cli.py lan-pin` |
| 4 | Code health | +60 tests; queue 30→90 %, YouTube 64→87 %, migration 51→84 % coverage; 2 event-loop stalls and 1 path issue fixed; dead code removed |
| 5 | Accessibility | 0 axe violations on 11 screens + dialogs, both themes; focus rings everywhere |
| 6 | Performance | Server import 1.2→0.5 s, start 3.2→2.7 s, −60 MB RAM, main JS bundle 743→380 KB |
| 7 | macOS | 3 real installer/launcher bugs fixed, macOS CI job (runs once the repo is public) |

**Your decisions needed** (details in the sections below):

1. Google verification only helps if SharkyClips ships **one shared OAuth client** (today every
   user brings their own). Product decision, see `docs/google-verification.md`.
2. Your **email is in the git history** (commit author). Decide before going public.
3. After the repo is public: run the **Project site** workflow, verify the domain in Search
   Console, and remove `continue-on-error` from the macOS CI job once it's green.
4. Test on a real Mac once (installer, launcher from the Dock, "shut down when finished").


Autonomous work session started 2026-10-27 (base version 1.2.5). Every decision and open question
is written down here so it can be reviewed later. Nothing was published; the repo stays private.

Ground rules followed: headless browser only, no Whisper/LLM/render runs on real videos, no GPU
stress, one commit per task, one version bump at the end.

### Task 1: public release readiness

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

### Task 2: Google verification prep

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
- The privacy-policy link in the app points to `https://utkualsir.github.io/sharkyclips-site/privacy.html`
  (`PRIVACY_URL` in `Publish.tsx`). Since 1.2.10 the site lives in the public repo
  `utkualsir/sharkyclips-site` (see docs/google-verification.md), so it works while this repo is private.

**Open questions for you (important):**

- **Verification only helps with a shared OAuth client.** Today each user brings their own Google
  Cloud project, and each such project stays "unaudited" (uploads forced private). Shipping one
  SharkyClips client is a product decision (shared quota pool), so I didn't change it. Details
  at the top of `docs/google-verification.md`.
- **`github.io` as the verified domain** usually works (it's on the Public Suffix List), but if
  Google rejects it you need a custom domain.
- **Stored statistics after Disconnect** stay in the project files. Google's policies want them
  deleted on revocation; suggested follow-up in the verification doc.

### Task 3: LAN access PIN

- `backend/sharkyclips/lanauth.py`: PIN or password (digits only = PIN, 4-128 chars), stored as a
  salted **scrypt** hash in `~/.sharkyclips/lan_auth.json` (separate from `config.json`, so the
  settings API can never return it). Sessions: random 256-bit token in an `HttpOnly`,
  `SameSite=Strict` cookie (30 days); only its SHA-256 is stored. A new PIN logs every device out.
- **Rate limit:** 5 misses per device within 15 min, then a lock of 30 s that doubles per miss (max
  15 min); plus at most 20 misses a minute from all devices together. While locked, even the right
  PIN gets HTTP 429 with `Retry-After`.
- `backend/sharkyclips/web/auth.py`: `/api/auth/status|login|logout|secret` and a pure-ASGI guard
  (doesn't buffer, so the live event stream is fine). Off by default; requests from this computer
  never need it; other devices need a session for every `/api/` path and `/openapi.json`. The UI
  shell stays public so the login screen can load. Only this computer can set/remove the PIN.
- UI: login screen for other devices (numeric keypad for PINs, countdown when locked), and a PIN
  box in Settings → Other devices; red warning when LAN mode runs without a PIN. CLI:
  `python cli.py lan-pin [--clear]`, and `serve --lan` prints a warning without a PIN.
- Tests: `backend/tests/test_lanauth.py` (10 tests). Headless E2E on a throwaway settings folder:
  login screen shown, API 401 before login, wrong PIN error, right PIN opens the app.

**Decisions:** "recommended on LAN" = warning, not forced, so existing LAN users aren't locked out
after the update. No HTTPS (would need certificates); SECURITY.md says to use LAN mode only on
trusted networks.

### Task 4: code health

**Coverage** (line coverage, measured locally with pytest-cov; total 49% → 52%):

| Module | Before | After | New tests |
|---|---|---|---|
| `web/jobs.py` (queue) | 30% | 90% | `test_jobs.py`: order, lanes, dedupe, move/front, cancel, errors, follow-ups, restart restore, broken queue files, trimming |
| `youtube.py` (uploads) | 64% | 87% | `test_youtube_flow.py`: PKCE sign-in, token refresh / sign-out, revoke offline, chunked + resumed upload, network errors, quota, stats/retention parsing (fake HTTP, no network) |
| `migrate.py` | 51% | 84% | `test_migrate_more.py`: config merge, log rename, copy fallback, path rewrite, hidden PowerShell call, macOS app rename |
| `web/power.py` | 44% | 96% | `test_power.py`: countdown, new work stops it, cancel, failed shutdown (real shutdown impossible in tests) |
| `governor.py` | 73% | 80% | `test_governor_gate.py`: hot-loop gate pause/stop/cancel, deferred, throttling |
| `export.py` | 63% | 68% | `test_export_registry.py`: request validation, registry, delete, SRT/VTT |

**Fixes found on the way:**

- The thumbnail upload ran ffmpeg (up to 60 s) and the chat import parsed up to 500 MB directly
  inside `async` handlers, which froze every other request (live progress, other tabs) meanwhile.
  Both now run in a worker thread.
- Export registry hardening: a hand-edited `exports/clips.json` with names like `../../x` could
  make "delete export" remove files outside the exports folder. Names with path parts are ignored.

**Dead code removed** (found with vulture, checked against every caller incl. tests):
`memory.current_model_name`, `montage.estimate_seconds`, `procs.tracked_count`, `procs.popen_flags`,
`editors.Timeline.joins`, unused `LEVELS` constants in `edit/fillers.py` and `edit/zoom.py`.
Route handlers, registered signals and serialized dataclass fields that vulture also lists are used.

**Lint / types:** `ruff check` was already clean with the project rules. Added type hints to the
public helpers that had none and to the risky modules (governor, jobs, migrate, youtube, lanauth,
errors, calibration, feedback, keywords). ~180 annotations are still missing, mostly private
helpers and FastAPI handlers that return files; not worth the churn.

**Decision:** pytest-cov and vulture were installed into the local venv only, not added to
`requirements-dev.txt` (CI doesn't need them).

### Task 5: accessibility audit

**How:** a throwaway SharkyClips with a tiny synthetic project (20 s test pattern, made with
ffmpeg `ultrafast`), headless Edge, [axe-core](https://github.com/dequelabs/axe-core) 4.10 with
the WCAG 2.1 A/AA + best-practice rules on all 11 screens (library, project, best-of, stories, game
detection, queue, stats, settings, studio music/brand/words) in dark and light, plus the What's
new, fast review and export dialogs. A keyboard walk (40 Tab stops per screen) checked that every
stop shows a focus ring.

**Result:** first run 11 issue types; now **0 violations** everywhere, focus ring on every stop.

Fixed:

- Contrast: dimmed transcript words (outside the clip) were 2.6:1 (light) / 3.9:1 (dark) → now the
  normal muted color (≥ 4.5:1). Light theme gold text `#86662a` → `#806027` (the "High" pill was
  4.44:1) and green `#1d7a52` → `#1a724c` (the "GPU" label in export was 4.31:1). Both are barely
  visible changes. The project site uses the same gold.
- Dialogs are named by their title (`aria-labelledby`); the fast review overlay now takes focus
  when it opens and gives it back when it closes.
- Clip candidates were `role="option"` items containing buttons (invalid for screen readers) →
  a list with `aria-current` on the selected clip. The candidates/clips tab bar no longer has a
  non-tab button inside its `tablist`.
- Headings: setting cards and library cards were `h3` right under the page `h1` → `h2`; What's new
  markdown headings `h4` → `h3` (same look).
- Names: three Settings dropdowns (UI language, output language, encoder), the swear-word list,
  progress bars, the main video player, back links while the title loads.
- The scrollable What's new text can be reached and scrolled with the keyboard.

Not automated: a real screen reader run (NVDA / VoiceOver). Worth doing once by hand.

### Task 6: performance

Measured headless on a throwaway settings folder (fake `APPDATA`, so the Ollama start-up
shortcut logic never touched the real Startup folder), old code vs new, warm caches, 2 runs each:

| | Before | After |
|---|---|---|
| `import sharkyclips.web.app` | 1.22 s | 0.53 s |
| `cli.py serve` start → `/api/meta` answers | 3.2 s | 2.7 s |
| Memory of the running server (all processes) | 220 MB | 162 MB |
| Idle CPU (no job, no open tab, 30-45 s) | 0.1-0.26 % of one core | 0.16 % of one core (same, noise) |
| Main JS bundle | 743 KB (251 KB gzip) | 380 KB (119 KB gzip) |

What changed:

- `highlights/__init__.py` loads the pipeline lazily. The server only needs the mode table at
  start, but importing it pulled in SciPy (~0.65 s, ~60 MB). SciPy now loads when highlights are
  really computed.
- The UI ships English (the fallback) in the main bundle and loads the other 6 languages on demand
  (~50 KB each, one per user). It renders nothing for the few ms the file takes on first start,
  instead of flashing English. Language switching still works instantly-ish (checked de, ar/RTL).
- Settings, Studio, Queue, Stats, Best-of, Stories and Game detection are separate chunks loaded
  when first opened. Library and Project (the main screens) stay in the main bundle.

Looked at, left alone: the remaining ~1.3 s before the server answers is the supervisor starting
a second Python (needed for in-place updates) plus FastAPI's own import (~0.2 s). The idle server
was already cheap (the governor does light ticks without GPU reads when nothing runs).

### Task 7: macOS readiness

Static review of every macOS path: `install.sh`, `installer/macos/*`, and the Python code behind
`platform.system() == "Darwin"` / `IS_MAC` (procs: background priority via `setpriority`,
sysmon: idle time + front app via CoreGraphics/CoreFoundation, hardware: Apple Silicon / Rosetta,
render: VideoToolbox, llm: Ollama paths + brew, power: `osascript` shutdown, migrate: app rename,
fonts per OS). No test Mac was available, so nothing here ran on real macOS.

**Bugs fixed:**

1. `uninstall.sh` runs with `set -u` but read `$SHARKYCLIPS_HOME` without a default when
   deciding about the old `~/.clipforge` folder. On a normal Mac (variable unset) the uninstaller
   would abort with "unbound variable" right after you said yes to deleting settings, leaving a
   half-uninstalled app.
2. The launcher (`SharkyClips.command`, also behind the Dock app) didn't load Homebrew's
   environment. On fresh Apple Silicon Macs `/opt/homebrew/bin` often isn't on a new Terminal
   window's PATH, so FFmpeg, Git and Deno installed by `install.sh` wouldn't be found when
   SharkyClips starts. It now runs `brew shellenv` first.
3. The uninstaller stops SharkyClips with `pkill -f "$APP_DIR/.venv/bin/python"`, but the
   launcher started Python with a relative path, so the running app was never stopped before its
   files were deleted. The launcher now uses absolute paths.
4. `SharkyClips.app` said macOS 11+ in Info.plist; the README (and mlx) need 13+. Now 13.0.

Existing installs get 2 and 3 with the next update (the Desktop/Dock launchers call the file in
the repo).

`backend/tests/test_installer_scripts.py` checks these as plain text on every OS (they fail on the
old scripts). shellcheck is clean.

**macOS CI:** new `Backend (macOS)` job in `ci.yml`: installs everything, runs `install.sh
--dry-run`, exercises the macOS-only code (idle time, front app, hardware detection, encoder pick,
background priority) and the full test suite. macOS runners are free only for public repos (10×
minutes on private ones), so the job has `if: !github.event.repository.private` and is skipped
until you make the repo public. It is `continue-on-error` until it has passed once: **after the
first green macOS run, remove that line** so it blocks merges like the others.

**Open questions:**

- "Shut down the PC when the queue is finished" on macOS uses `osascript ... System Events to shut
  down`. macOS asks for Automation permission the first time, which may be exactly when you're
  away, so the first shutdown can fail (the app reports it). Worth a real-Mac test.
- macOS has no fullscreen / video-playing detection in the governor (Windows only); Silent mode
  pauses on Mac only for listed games in front and when you're away/back.

### Release

- 1.2.6 committed, tagged `v1.2.6`, pushed. CI on the release commit and the tag: all green
  (Backend Windows + Ubuntu, Frontend, Installer scripts; macOS skipped while private).
- Two CI runs of earlier commits (task 6 and 7) hung for 15+ minutes in `apt-get install ffmpeg`
  on GitHub's Ubuntu runner (a mirror problem, not our code: the same code passed on the release
  commit). I cancelled them so they wouldn't burn up to 6 hours of private-repo minutes, and
  added `timeout-minutes` to every CI job (and 10 min for the ffmpeg install). That last change is
  CI-only and not user-visible, so it went in without a version bump (decision: the bump rule is
  for app updates).
- The "under construction" flag was removed at the end.
