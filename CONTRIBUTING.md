# Contributing to SharkyClips

Thanks for helping! Bug reports, translations, title examples and pull requests are all welcome.

## Reporting bugs

Open an [issue](https://github.com/utkualsir/sharkyclips/issues/new/choose) and paste the output
of `python cli.py doctor` (run it in the `backend` folder). Please **don't attach private videos**
or your `~/.sharkyclips` folder: a short description of the video is enough. Security problems go
to [SECURITY.md](SECURITY.md) instead of a public issue.

## Setting up

You need Python 3.11-3.13, FFmpeg, Git and Node.js 20+ (only for UI work).

```bash
git clone https://github.com/utkualsir/sharkyclips.git SharkyClips
cd SharkyClips
python -m venv .venv
.venv\Scripts\activate                      # macOS / Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd frontend && npm ci && cd ..
python backend/cli.py serve                 # http://localhost:8000
```

For UI work, `npm run dev` in `frontend/` serves the UI with live reload on port 5173 and talks to
the backend on port 8000.

## Before a pull request

Run the same checks CI runs:

```bash
python -m ruff check backend installer
python -m pytest -q                     # from the repo root
cd frontend
npm run build                           # also type-checks
node scripts/check-i18n.mjs             # every key in all 7 languages
```

- **Commit the rebuilt `frontend/dist`** with UI changes: the installer and the updater ship it
  as-is, so users don't need Node.js.
- Tests run with a throwaway `SHARKYCLIPS_HOME` and never touch your real settings. Tests that
  encode video are marked `requires_ffmpeg` and are skipped when FFmpeg is missing.
- Keep pull requests small and focused; describe what you tested by hand.

## House rules

- **Version:** only in the `VERSION` file at the repo root. Everything else reads it. A release
  bumps the patch number and adds a `CHANGELOG.md` entry (English first, then Turkish after
  `<!-- lang:tr -->`, then short summaries for de / hu / ru / ar / zh). Maintainers do this; you
  don't need to bump the version in a pull request.
- **Translations:** the UI has 7 languages (en, tr, de, hu, ru, ar, zh) in
  `frontend/src/i18n/locales/`. A new key goes into all of them; `check-i18n.mjs` fails otherwise.
  Arabic is right-to-left: use logical CSS properties (`margin-inline-start`, not `margin-left`).
- **No console windows.** Every subprocess is started with `**procs.no_window()`
  (`backend/tests/test_no_window.py` checks this). Never use `DETACHED_PROCESS` on Windows.
- **The GPU is shared with games.** Whisper and the local LLM never run on the GPU at the same
  time, and long work goes through the resource governor (`governor.py`) so it can pause.
- **Never hardcode a machine.** Pick models, encoders and limits from the detected hardware
  (`hardware.py`), not from one test PC.
- **Local first.** No telemetry, no accounts, no paid APIs. Network access only for what the user
  asks for (downloads, model pulls, updates, their own YouTube channel).

## Where things are

| Path | What |
|---|---|
| `backend/cli.py` | Command line (`serve`, `ingest`, `transcribe`, `highlights`, `analyze`, `render`, `doctor`...) |
| `backend/sharkyclips/highlights/` | Highlight engine. New signal: subclass `Signal` in `signals/`, `@register` it, give it a weight in `modes.py` |
| `backend/sharkyclips/titles/` | AI titles: per-language examples, glossary, spell checks |
| `backend/sharkyclips/edit/` | Editing tools (bleeps, silence cuts, zoom, music, loudness, loops) |
| `backend/sharkyclips/web/` | FastAPI server and job queue |
| `frontend/src/` | React UI (`pages/`, `components/`, `i18n/locales/`) |
| `installer/` | Windows and macOS installers, icon generator |
| `docs/how-it-works.md` | Detailed technical reference |

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
