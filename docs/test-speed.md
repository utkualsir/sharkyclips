# Test speed (1.2.75)

Goal: a fast loop while working, everything still checked before a release.

- **Local** = quick checks + the tests of the changed files + a small layout smoke set.
- **CI** = everything: the whole pytest suite (parallel + a short serial pass) and the full layout
  matrix, split into parallel shards.

## Before / after

Measured on the dev PC (24 threads, 16 GB RAM, Windows 11) and on GitHub Actions.

| What | Before | After |
|---|---|---|
| Full pytest, local | 24 min 28 s (1468 s, serial) | 9 min 26 s (261 s parallel with 6 workers + 305 s serial pass) |
| Local check of one change (`scripts/quick-check.py`) | full suite only: 24 min 28 s | 3 s (one module, e.g. `uploadstats.py`) to 31 s (`slideshow.py`); a change to core modules like `youtube.py` + `web/app.py` picks ~60 files: 4 min 20 s |
| Layout smoke, local (2 screens, 2 sizes, tr/ar, light/dark = 32 views) | full matrix only (thousands of views, CI) | 30 s (fixture server start included) |
| CI wall time (slowest job) | 31 min (Layout, 30:51) | __CI_AFTER__ |
| CI Backend (windows / ubuntu) | 20:21 / 16:32 | __CI_BACKEND__ |

"Before" CI numbers: run 46056863474 (commit 2ef3630, 2026-11-27).

## What changed

1. **`scripts/quick-check.py`** (local):
   - `ruff` over backend + installer + scripts (about 1 s);
   - pytest only for the changed test files and the test files that import a changed backend module
     (`sharkyclips/foo.py` -> tests that mention `foo`), plus `test_preview_math.py` for
     `previewMath.ts` and `test_updates_page.py` for VERSION / CHANGELOG / `frontend/dist`;
   - `npm run typecheck` when `frontend/src` changed, the i18n check when a locale changed;
   - `--layout [--screens a,b]`: a throwaway fixture server (mkdtemp, `SHARKYCLIPS_DOWNLOADS` set,
     nothing real touched) and `layout-check.mjs` on 1280x720 + 390x844 x tr/ar x light/dark (Classic);
   - `--full`: the whole suite the CI way.
2. **pytest-xdist**. `-n auto --dist loadfile` in CI; locally at most 6 workers: with 24 workers every
   worker imports the whole backend and the 16 GB dev PC ran out of memory (`MemoryError` while
   collecting). `QUICK_WORKERS=n` overrides.
3. **Serial pass.** Eight files start real browsers, servers or child processes and wait for them
   with short timeouts (`conftest.SERIAL_FILES`, marker `serial`). Under parallel load they timed
   out (the first parallel try took 30 min because one hung assisted-upload job blocked the rest).
   The parallel pass runs `-m "not serial"`, then `-m serial` runs them one at a time. Plain
   `pytest` still runs everything.
4. **Layout matrix in 4 CI shards.** `LAYOUT_SHARD=i/n` checks every n-th (preset, language, theme,
   size) combination; four jobs, each with its own fixture server. The preview / mini game / axe /
   browser checks got their own job; the presets job keeps axe + personalization.
5. **CI caching.** pip and npm were already cached; the Playwright browsers are now cached too
   (`actions/cache`, key = `package-lock.json` + browser list; on a hit only the system packages
   are installed). The shared setup lives in `.github/actions/fixture-server`.

## Rules of thumb

- While working: `quick-check.py` (add `--layout --screens <the screens you touched>` for UI work).
- Before a release: `quick-check.py --full`, `npm run build`, `check-i18n.mjs`; the full layout
  matrix and the three browsers run in CI.
- A new test that starts a browser / server / child process and waits with a timeout: add its file
  to `SERIAL_FILES` in `conftest.py` and in `scripts/quick-check.py` (`test_quick_check.py` keeps
  them equal).
