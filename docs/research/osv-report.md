# OSV-Scanner report

- Date: 2026-11-21 · Tool: OSV-Scanner v2.7.0 (osv-scalibr 0.5.3), database: osv.dev (live)
- Scanned: `backend/requirements.txt`, `backend/requirements-dev.txt`,
  `backend/requirements-nvidia.txt`, `frontend/package-lock.json`
- Result after the fix: **No issues found** (both scan modes below). CI job "OSV-Scanner" repeats
  the transitive scan on every push (non-blocking).

## Two ways of scanning, two different answers

The Python requirement files use minimum versions (`>=`), not a lockfile. OSV-Scanner therefore
**resolves** them itself (deps.dev), and for indirect dependencies it may pick an old version that
pip would never install today. Both views matter:

| Mode | What it answers | Before | After |
|---|---|---|---|
| Exact: `pip freeze --all` of the dev `.venv` (115 packages) + `package-lock.json` (78 packages), `--no-resolve` | What is really installed now | 0 | 0 |
| Transitive: the requirement files as written (`osv-scanner scan source -L ...`) | What the declared ranges *allow* | 7 packages, ~110 advisories | 0 |

So no installed package was vulnerable (installers and the updater use `pip install --upgrade`),
but nothing in the requirement files *prevented* an old, vulnerable indirect dependency from being
kept. That gap is now closed.

## Findings (transitive mode) and fixes

| Package | Pulled in by | Lowest allowed before | Advisories | Fixed in | Fix |
|---|---|---|---|---|---|
| pillow | matplotlib, pystray, rapidocr | 9.5.0 | 87 (e.g. PYSEC-2026-4330, -4332, CVSS 9.8) | 13.0.0 | floor `pillow>=13.0.0` |
| pycryptodomex | yt-dlp[default] | 3.9.9 | 2 (PYSEC-2024-3) | 3.19.1 | floor `>=3.19.1` |
| httpx2 | huggingface_hub (faster-whisper) | 2.9.1 | 10 | 2.12.0 | floor `>=2.12.0` |
| httpcore2 | httpx2 | 2.9.1 | 2 | 2.10.0 | floor `>=2.10.0` |
| anyio | fastapi/starlette, httpx | 4.9.0 | 4 (PYSEC-2026-4024, -4025) | 4.14.2 | floor `>=4.14.2` |
| certifi | requests, httpx | 2026.7.22 | 2 (PYSEC-2026-4320) | 2026.10.18 | floor `>=2026.10.18` |
| idna | requests, anyio | 3.9.0 | 2 (PYSEC-2026-215) | 3.15 | floor `>=3.15` |

Floors were added at the end of `backend/requirements.txt` (runtime) and, for anyio / certifi /
idna, also `backend/requirements-dev.txt` (the dev file is resolved on its own through httpx).
Every floor is at or below the version already installed in the dev environment, so nothing
changes for a current install; `pip install --dry-run` resolves cleanly. Shipped as 1.2.61
because the updater re-runs pip when the requirement files change.

npm (`frontend/package-lock.json`): no advisories.

## Not fixed / notes

- Nothing left open.
- The one-click Windows installer (`installer/windows/build_installer.py`) builds from
  `requirements.txt`, so the next installer build picks up the floors automatically. The 1.2.56
  installer in `installer/dist` was built before this change (its bundled packages are newer than
  the floors anyway; Defender found nothing, see docs/tooling.md).
- OSV results change as advisories are published. Re-run (see docs/tooling.md) before releases.

## Re-run

```sh
# exact (what is installed)
.venv/Scripts/python -m pip freeze --all > "$TEMP/osv/requirements.txt"
osv-scanner scan source --no-resolve -L "$TEMP/osv/requirements.txt" -L frontend/package-lock.json
# transitive (what the files allow) - same as CI
osv-scanner scan source -L backend/requirements.txt -L backend/requirements-dev.txt \
  -L backend/requirements-nvidia.txt -L frontend/package-lock.json
```
