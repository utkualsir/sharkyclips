# SharkyClips - notes for Claude Code

SharkyClips (called ClipForge before 1.2.1) is a free, local stream-highlight clipper: Python backend
(`backend/`, package `sharkyclips`, CLI `backend/cli.py`), React/Vite UI (`frontend/`, the built
`frontend/dist` is committed), installers in `installer/`. GitHub: `utkualsir/sharkyclips`.

## Permanent rules

### 1. Versioning (every update / phase)

- Every update or phase bumps the **patch** version by 0.0.1 (1.2.0 -> 1.2.1 -> 1.2.2 ...), unless
  the user asks for a different bump.
- The version lives in **one place: `VERSION`** at the repo root. The backend (`sharkyclips.__version__`,
  the UI via `/api/meta` and `/api/app`), the CLI, the updater and both installers read it. Never
  write the version anywhere else by hand (the README badge is the one exception: update it too).
- Every bump gets a **CHANGELOG.md** entry `## [x.y.z] - YYYY-MM-DD`: English first, then Turkish
  after `<!-- lang:tr -->`, then short summaries for de / hu / ru / ar / zh, each after
  `<!-- lang:xx -->` inside `<details><summary>Language</summary> ... </details>`. The app's
  "What's new in x.y.z" popup shows the block of the UI language (English fallback), once per
  version (config `seen_version`), so write it for users, not developers.
- Then: commit, `git tag vX.Y.Z`, `git push` and `git push origin vX.Y.Z`.

### 2. "Under construction" flag (every work session)

- At the **start** of every work session, create `~/.sharkyclips/dev_in_progress.json`:
  `{"started_at": "<UTC ISO time>", "task": "<short task description>"}`
  (on Windows: `%USERPROFILE%\.sharkyclips\dev_in_progress.json`; honour `SHARKYCLIPS_HOME`).
- While it exists, the running app shows a slim "Update in progress - under construction" banner on
  every screen (task + start time), and starting heavy jobs asks first.
- **Remove it** when the work is committed and pushed, **and also when the session fails or is
  abandoned**. A flag older than 12 hours counts as stale: the banner hides and Settings shows a
  small note with a Remove button (`welcome.py`, `STALE_HOURS`).

### 3. Restart the running app after a release

- After the push, the user's running SharkyClips still runs the OLD Python code behind the new
  UI files (1.2.9 and 1.2.22 "bugs" were exactly that). So after every release: find the servers
  on ports 8000-8010 (`/api/app` shows `version`), and for each one still on the old version
  check `/api/jobs`: if nothing is queued / running, `POST /api/update/restart` (the supervisor
  restarts it on the new code) and wait until `/api/app` reports the new version. If jobs are
  running, don't interrupt them: tell the user (the UI shows a "restart to finish the update"
  bar). Only then test on the user's app or report the release as done.

## Working here

- Tests: `.venv/Scripts/python -m pytest -q` (from the repo root; tests use a throwaway
  `SHARKYCLIPS_HOME` and set `SHARKYCLIPS_NO_MIGRATE=1`). Lint: `.venv/Scripts/python -m ruff check backend`.
- Frontend: `cd frontend && npm run build` (also typechecks), `node scripts/check-i18n.mjs` (every
  key in all 7 locales: en, tr, de, hu, ru, ar, zh). Commit the rebuilt `frontend/dist`.
- Layout check (CI job "Layout"): `python frontend/scripts/layout-fixture.py <dir>`, serve with
  `SHARKYCLIPS_HOME=<dir>/home ... --port 8799`, then `LAYOUT_CHANNEL=msedge node
  frontend/scripts/layout-check.mjs http://127.0.0.1:8799 <project-id> [shots]` (`LAYOUT_QUICK=1`
  for a fast pass). It fails on overlapping panels, squeezed lists, cut-off content and sideways
  page scroll on every screen at 1024-1920 px, 700-1080 px high and phone width.
- Preview check (same CI job, same server): `node frontend/scripts/preview-check.mjs
  http://127.0.0.1:8799 <project-id>` compares the 9:16 live preview's pixels with the server's
  render plan (crop rects + zoom / shake samples) for split / crop / fit. The preview's cut and
  zoom math lives in `frontend/src/previewMath.ts`, a copy of `clips.split_rects`,
  `zoom.factor_out` and `fx.shake_at`: change both sides together (`test_preview_math.py`).
- Icons/logo come from `installer/make_icons.py` (one geometry; `frontend/src/components/Brand.tsx`
  and `backend/sharkyclips/web/splash.html` copy the same paths).
- Settings folder: `~/.sharkyclips` (`config.config_dir()`); `migrate.py` moves an old `~/.clipforge`
  over on start and renames old Windows shortcuts / the Apps & features entry.
- The dev PC (RTX 5070 Laptop, 8 GB) is a test machine only: never hardcode it. Whisper and the LLM
  never share the GPU. Browser tests: Playwright with `channel: "msedge"`, headless.
- README media show only the user's own Delta Force project; `docs/capture.mjs` retakes them (on a
  copy of the settings folder).
- Never make the GitHub repo public; the user does that.
