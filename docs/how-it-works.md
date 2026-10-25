# How SharkyClips works

The [README](../README.md) covers installing and everyday use. This page is the detailed
reference: the web UI's features, the command line, the files SharkyClips writes, and how the
highlight engine, the local AI and the titles work.

## The web UI in detail

- **Library**: all projects with live status ("Transcribing 60%", "12 candidates ready").
  New project: paste a URL, a local file path (on this computer only), or drop a file.
  Download -> transcription -> highlight analysis -> facecam detection run by themselves.
- **Project**: 16:9 player with a live 9:16 preview of the selected clip (layout, subtitles,
  hook), the Hype Map (click to jump), per-clip signal stats, the candidate list with
  translated reasons and Accept toggles, render options and "Render N clips". Finished clips
  play inline and download as MP4 (1080x1920, H.264/AAC).
  - Candidate cards show the **viral score /100** with its label (Low / Medium / High / Very
    high); the hype score is the smaller bar underneath.
  - **Analyze with AI**: pick the output language (7 languages) for titles, hashtags and
    subtitles next to the button; progress shows live ("AI analysis 3/15"). It also runs by
    itself after highlights are found (switch it off in Settings).
  - **Publish package**: titles with thumbs up / down (liked titles become examples for the
    next run, so titles learn your style), "New suggestions", hashtags, cover prompt.
  - **Chat** (when the stream has a chat replay): messages, people, messages per minute
    compared with the usual rate, "Chat exploded 5.2x" spikes and the most spammed reaction.
  - **Hook**: Off / Text / Flash / Both. The text is the AI hook, prefilled and editable
    (reset button brings the AI text back).
- **Facecam editor**: drag/resize the detected webcam box on a real frame.
- **Settings**: UI language (Turkish default, English, Russian, Hungarian, German, Arabic RTL,
  Chinese), local AI (model picker with the installed Ollama models, auto-analyze switch,
  Fast analysis, glossary), custom trigger words per language, video encoder, default mode,
  and **Updates** (check for a new version and install it; SharkyClips restarts by itself).
- **Queue**, **Best-of video** and **Stats**: see [below](#queue-best-of-videos-and-calibration).
- Keyboard: up/down (or j/k) moves through candidates, `a` accepts/unaccepts.

Heavy work (transcription, analysis, rendering) runs one job at a time on the GPU lane;
downloads run alongside. Progress streams live to every open browser tab.

## Development

```bash
python -m pip install -r backend/requirements-dev.txt   # pytest, ruff, httpx, pillow
python -m ruff check backend installer
python -m pytest
cd frontend && npm install && npm run dev                # UI with live reload on :5173
node scripts/check-i18n.mjs                             # all 7 languages have every key
python installer/make_icons.py                          # regenerate the app icons
```

`python cli.py serve` rebuilds `frontend/dist` by itself when the sources are newer and Node.js is
installed. `docs/capture.mjs` retakes the README screenshots and the demo GIF (see its header).

The server runs as a child of `serve`: after an update (Settings -> Updates: `git pull --ff-only`,
then `pip install` if the requirements changed) it exits with code 75 and `serve` starts it again.

## Command line

All commands run from the `backend` folder with the venv activated.

```bash
# 1. Import a video (URL or local file). Mode: gaming (default), study, music
python cli.py ingest "https://www.twitch.tv/videos/1234567890"
python cli.py ingest "https://www.youtube.com/watch?v=jNQXAC9IVRw" --mode study
python cli.py ingest "D:\Videos\My Stream 2026.mp4"          # paths with spaces: use quotes
python cli.py ingest ~/Movies/stream.mkv --mode music

# 2. Transcribe (auto language + auto model by default)
python cli.py transcribe me-at-the-zoo-829e083e
python cli.py transcribe me-at --lang tr --model medium      # a unique id prefix is enough
python cli.py transcribe me-at --force                       # redo from scratch

# 3. Find highlights (uses the project's mode unless you pass --mode)
python cli.py highlights me-at
python cli.py highlights me-at --mode study --top 5
python cli.py highlights me-at --force                       # recompute cached signals

# 4. Check results by eye: quick horizontal 720p previews (NVENC/VideoToolbox/QSV/AMF, else CPU)
python cli.py cut me-at 1          # one candidate by rank
python cli.py cut me-at --all      # -> workspace/<id>/previews/01_s94_02-14-37.mp4 ...

# 5. Chat replay (optional; `highlights` fetches it by itself for YouTube/Twitch streams)
python cli.py chat me-at                                    # download it again: --force
python cli.py chat me-at --file chat.json                   # or import a chat log

# 6. Local LLM: judge every clip, viral score, titles, hashtags, cover prompt, hook text
python cli.py analyze me-at                  # output language from config (default tr)
python cli.py analyze me-at --lang en        # English titles + English subtitles
python cli.py analyze me-at --ranks 1 2 3    # only some clips; --no-refine keeps the cuts

# 7. Render vertical 9:16 clips (the web UI does the same)
python cli.py render me-at 1 2 3 --hook flash+text --subs bold
python cli.py render me-at --accepted --sub-lang en          # clips accepted in the web UI

# Other
python cli.py list         # projects in the workspace
python cli.py languages    # supported languages
python cli.py doctor       # check everything; --download-models also fetches Whisper now
python cli.py serve        # web UI on :8000 (--lan for phones, --port, --no-browser)
python cli.py launch       # what the desktop shortcut runs: reuse a running SharkyClips or
                           # start one on a free port, then open the browser
```

### What you get

```
workspace/<id>/
  source.mp4        the video (hard-linked when imported from the same drive, so no extra space)
  audio.wav         16 kHz mono audio
  meta.json         title, duration, resolution, fps, source, mode
  transcript.json   language + segments with word-level timestamps
  highlights.json   clip candidates + the whole-video hype curve (1 value/second)
  hype_curve.json   small Hype Map file for the UI: combined + per-signal curves (max 1500
                    points, values 0-100, peaks kept) + clip markers
  previews/         quick preview MP4s from `cut` (rank_score_start-time.mp4)
  chat.json         chat replay: [[seconds, "message", author_index], ...] (no names stored)
  review.json       web UI choices: accepted clips, hook texts, render options, facecam box
  clips/            rendered 9:16 clips (01_c01.mp4 ...), listed in clips.json
  cache/            per-chunk / per-signal results (lets long runs resume)
```

`transcript.json` (shortened):

```json
{
  "language": "en", "language_probability": 0.9995, "is_rtl": false,
  "model": "large-v3-turbo", "device": "cuda", "compute_type": "float16",
  "segments": [
    {"id": 0, "start": 0.98, "end": 16.5, "text": "Alright, so here we are...",
     "words": [{"start": 0.98, "end": 1.42, "word": " Alright,", "probability": 0.62}]}
  ]
}
```

### Highlight engine

Each **signal** scores every second of the video from 0 to 1 and records *reason events*.
The **scorer** combines them with mode-specific weights into a hype curve; **candidates**
are picked from its peaks, with boundaries snapped to word timestamps (never mid-word,
sentence edges preferred) and no overlaps.

| Signal | What it detects |
|---|---|
| `loudness` | Volume jumps against a rolling 60 s baseline (works for loud and quiet streamers) |
| `keywords` | Reaction / study trigger phrases per language (`highlights/triggers/*.json`) + your own |
| `laughter` | Laughter, shouting, cheering, using a free 10 MB AudioSet model (CED-mini via sherpa-onnx, CPU) |
| `speech` | Excited fast talk, and a pause followed by a burst (setup → punchline) |
| `steady_speech` | Calm, continuous explanation (study mode) |
| `music` | Repeated chorus (chroma self-similarity) and drops (energy rise); first strong chorus preferred |
| `chat` | Chat speed vs. its usual speed (rolling 2 min median) + reaction spam (KEKW, LUL, ahahah, ????, emotes, copy-paste waves; per language in `triggers/chat_reactions.json`). Shifted ~5 s earlier, because chat reacts late. Bots and poll votes are ignored |
| `llm` | Study mode: the local LLM reads the transcript in overlapping 2.5 min windows and marks self-contained explanations |

| Mode | Main signals | Clip length |
|---|---|---|
| gaming | loudness, laughter, keywords, speech, chat | 15-60 s (ideal ~38 s), 6-10 s pre-roll |
| study | LLM explanations, study keywords, steady speech; loud/laugh nearly off | 30-60 s, sentence-complete |
| music | music, chat | 15-30 s around the chorus/drop |

Signals that can't run (no chat replay, no Ollama) are skipped and the other weights re-normalized.

A candidate in `highlights.json`:

```json
{"rank": 1, "start": 1027.7, "end": 1056.65, "duration": 28.95, "peak": 1035.0,
 "hype_score": 100, "hype_raw": 0.2158,
 "reasons": [{"code": "keyword", "value": "allah allah", "t": 1035.2, "strength": 0.6, "signal": "keywords"},
             {"code": "laughter", "t": 1040.0, "strength": 0.71, "signal": "laughter"}],
 "signal_scores": {"loudness": 0.4, "laughter": 0.71, "keywords": 0.8, "speech": 0.14},
 "text": "..."}
```

`hype_score` is relative within the video (best clip = 100); `hype_raw` is the absolute value,
kept for later calibration. Reason `code`s are stable identifiers (`loudness_spike`, `keyword`,
`laughter`, `shouting`, `cheering`, `fast_speech`, `pause_then_burst`, `steady_explanation`,
`chorus`, `drop`, `chat_spike` (value e.g. `"5.2x"`), `chat_reactions` (e.g. `"KEKW"`),
`llm_explanation`) so the UI can translate them.

### Chat replay

| Source | How |
|---|---|
| YouTube (videos that were live streams) | yt-dlp's live chat replay. YouTube sends it in small pieces, so a long stream takes a few minutes |
| Twitch VODs | Twitch's public chat API, 8 parts of the VOD in parallel (a 5 h VOD: ~30 s) |
| Anything else | `python cli.py chat <id> --file ...` or "Import chat" in the web UI: chat-downloader / yt-dlp `.live_chat.json` / TwitchDownloader JSON, or text lines like `[1:02:03] name: message` |

No chat replay is fine: the signal is skipped. Twitch only keeps the chat of VODs that still exist.

### Game awareness (Delta Force, League of Legends)

The `game` signal (`backend/sharkyclips/game/`, weight 0.6 in gaming mode) reads the game's HUD.
The game comes from the video title, from game words in the transcript ("lane", "minyon", champion
names...), or from the per-project picker (Auto / Delta Force / League of Legends / Other).

**Sampling.** ffmpeg decodes only reference frames (`-skip_frame noref`) at 2 fps, on NVDEC when there
is an NVIDIA GPU, in 3 parallel segments, and hands over raw NV12 (luma = free grayscale, chroma =
colour tests). Measured on an RTX 5070 Laptop: decoding alone ~35x realtime for 1080p60; a full scan
20-45x realtime depending on how much text there is to read, so a 4 h stream takes roughly 6-12 min.
Without NVDEC (CPU decode) expect about 6-10x.

**Reading.** Each HUD box (1920x1080 coordinates, scaled; presets in `game/presets.py`) has a cheap
pixel test, and OCR (PaddleOCR PP-OCR models via RapidOCR/onnxruntime, CPU, in worker processes) runs
only when that test fires:

| Game | Box | Test -> reading | Events |
|---|---|---|---|
| LoL | Team score, K/D/A (top right) | pixels changed -> one-line OCR | kills, deaths, assists; multikills from kill timing (10 s, 30 s for the 5th); first blood |
| LoL | Announcements (top centre) | after a kill or a bright-text jump -> line OCR | shutdown ("Buraya kadar!"), ace, baron/dragon (steal or secure, not the enemy's, not "spawned") |
| LoL | Ability bar | edges vanish -> read the result box for 8 s | victory / defeat ("ZAFER" / "BOZGUN") |
| LoL | Champion portrait | template match vs Data Dragon icons | champion, only used when its name is also said or in the title (skins fool the match) |
| DF | Icons above the score counter | template match: skull / revive / assist | kills, revives, assists; multikills (kills within 10 s) |
| DF | Score lines | while a skull shows -> line OCR | how many kills at once ("Öldürme" x2, "Çifte Öldürme"), revenge ("İntikam", "Göze Göz") |
| DF | Killer card | after the screen turns grey -> red "ÖLDÜREN" label | own death (being downed is not a death) |
| DF | Result box | still screen after a cut -> OCR | extraction success / failure (unverified texts, Operations mode) |

English and Turkish client texts are in `TEXT_RULES`; matching is accent-free and fuzzy (OCR noise).
Banners the game shows for everyone (first blood, shutdown, multikills) only count when the
streamer's own K/D/A shows a kill at that moment.

**Scoring.** Event strengths are in `game/events.py` (pentakill 1.0, quadra 0.9, triple 0.75, double
0.55, kill 0.4...; DF multikill x2 0.65, x3 0.85, x4 0.95). The curve ramps up 6 s before an event and
stays high over its whole span. Events of strength >= 0.8 always become a candidate, and
`candidates.fit_spans` grows a clip so the whole event (every kill of a multikill) plus 4 s of
build-up fits. The LLM prompt gets the events as facts ("3 kills in a row (multikill) at +11s").

**Sounds.** Optional reference clips in `~/.sharkyclips/game_sounds/<lol|delta_force>/<event>.mp3`
(e.g. `lol_pentakill.mp3`, several per event allowed) are found in the audio with log-mel
cross-correlation; a hit confirms a screen event or adds one.

**Calibration.** The project's "Game detection" page (gamepad button) shows sampled frames with the
boxes drawn on them, every event, the OCR text around each moment and "Read this frame". Boxes can be
edited; they are saved per computer in `~/.sharkyclips/game_regions.json`, then "Read the HUD again".
The scan is cached in `<project>/cache/game/scan.json` (rules can change without a rescan).

### Local LLM (Ollama)

`python cli.py doctor` installs [Ollama](https://ollama.com) (winget / brew) and downloads the model.
The model is picked by hardware: **qwen3.5:9b** (6.6 GB, 4-bit) with 8 GB+ VRAM or Apple Silicon
with 16 GB+, otherwise **qwen3.5:4b** (3.3 GB). Set `llm_model` to any Ollama model to override.
If Ollama's own download keeps failing (seen with broken IPv6), SharkyClips downloads the model
files directly from the same registry over IPv4 and resumes where it stopped.

- The LLM and Whisper are **never on the GPU at the same time**: loading one unloads the other,
  and the LLM is unloaded (`keep_alive 0`) when a batch ends.
- Answers use Ollama's structured JSON output with a schema, are validated, and retried with the
  problems listed.
- Results are cached per clip in `cache/llm/`, so re-running is instant and an interrupted run
  resumes.

`analyze` writes, per candidate in `highlights.json`:

```json
"publish": {"viral_score": 62, "viral_label": "medium",
            "sub_scores": {"hook": 56, "retention": 64, "trend_fit": 70, "length_fit": 100},
            "titles": ["KONTROLÜ ÇALDIK!", "..."], "hashtags": ["#shorts", "#DeltaForce", "..."],
            "description": "Lobiye tek başıma daldım ... Sizce nasıldı?\n\n#shorts #DeltaForce ...",
            "hook_text": "KONTROLÜ ALDIK!", "cover_prompt": "... 9:16 thumbnail, navy and gold ...",
            "language": "tr", "model": "qwen3.5:9b"},
"llm": {"what_happens": "...", "self_contained": true, "moment_type": "exciting",
        "original": {"start": 1068.0, "end": 1083.4}, "refined": true},
"translations": {"en": [{"start": 1065.2, "end": 1067.9, "text": "So good, so good."}]}
```

- **Viral score** = signals (22%) + hook (22%) + retention (22%) + trend fit (10%) + length fit (6%)
  + how funny/exciting/useful the moment is (18%); x0.85 if it isn't self-contained.
  Labels: Low < 40, Medium 40-64, High 65-84, Very high 85+. Small local models rate almost
  everything 70-85, so their sub-scores are spread out (75 -> 50) before they're combined.
- **Cuts**: the LLM may move the start/end by up to 10 s (setup / payoff); the new edges are
  snapped to word boundaries and never overlap other clips. `--no-refine` keeps the original cut.
- **Subtitles**: when the output language differs from the spoken one, the clip's sentences are
  translated with their timing kept; render with `--sub-lang <code>` (or pick it in the web UI).
- **Cover prompt**: English, describes what really happens in the clip, always in the same style
  (dramatic, high contrast, navy & gold grade, short bold text, no logos/watermarks).
- **YouTube description**: a separate short call after the titles (own cache, `desc_*.json`):
  2-3 sentences in the creator's voice in the output language, spelling fixed like the titles,
  then the hashtags. Channel names never become hashtags.
- **Re-running the highlights** keeps a clip's AI results when its original cut didn't change
  (`highlights/pipeline.py: carry_over_ai`); the analysis job is saved in the queue, so a pause or a
  restart continues it instead of losing it.

#### Titles (`sharkyclips/titles/`)

Small local models like to write generic, over-hyped titles ("İnanılmaz Bir Durum!") and make
spelling mistakes. Titles are therefore written in their own steps:

1. **Draft**: the LLM writes 9 ideas, shown 10-15 natural example titles for the language and
   content type (`titles/examples/<lang>.json`, casual, mostly without "!"; edit them freely),
   your liked titles, and the glossary.
2. **Local checks**: emoji and Title Case removed, accents repaired ("olmasin" -> "olmasın",
   "schoner" -> "schöner"), Turkish question particles follow vowel harmony ("pompalı mi" ->
   "pompalı mı"), names spelled the glossary way. Words that are neither in the transcript, the
   glossary nor the offline dictionary ([wordfreq](https://github.com/rspeer/wordfreq), with
   suffix stripping for Turkish and Hungarian) are flagged.
3. **Proofread**: a second, short LLM pass fixes spelling and grammar in the output language,
   gets the flagged words, and drops duplicates and repeated patterns.
4. **Pick**: titles that still contain unknown words, swearing or rude fillers ("lan"), copy an
   example, or repeat another clip's title are rejected (see `title_checks` in
   `highlights.json`). Six are picked: at most 2 with "!", at least one question, at least one
   calm statement, and the streamer's own words in at most two.

**Glossary**: the game is detected from the video title / topic; its built-in names
(`titles/games.json`: Delta Force, LoL, Valorant, CS2, ...) are used only when the streamer
actually says them (fuzzy match, so Whisper's misspellings still count). Add your own in
Settings or in the config: `"glossary": ["Zero Dam", "kanka"]` (or `{"all": [...], "tr": [...]}`).
Words the streamer says far more often than usual ("kanka", nicknames) are added automatically.

**Your style**: thumbs up / down in the web UI are saved in `~/.sharkyclips/title_feedback.json`.
The next "Analyze with AI" rewrites the titles with your liked ones as examples (the scores and
cuts stay cached).

Measured on an RTX 5070 Laptop (8 GB), qwen3.5:9b, 15 clips of a 19 min stream: ~10 min in total
(~40 s per clip: ~12 s judging, the rest drafting + proofreading titles; ~37 tokens/s with ~85% of the model on the GPU, unloaded
afterwards). Re-running after a thumbs up only redoes the titles. A 7 min study video: the LLM
reads the transcript in ~30 s.

**Your own trigger words** go in `~/.sharkyclips/config.json`:

```json
"custom_triggers": {"tr": ["kral", "efsane an"], "en": {"reaction": ["poggers"], "study": ["mnemonic"]}}
```

**Adding a signal** (e.g. chat activity): subclass `Signal` in `highlights/signals/`, decorate it
with `@register`, import it in `signals/__init__.py`, and give it a weight in `modes.py`.
The scorer and candidate picker don't change.

### Queue, best-of videos and calibration

* **Queue** (top bar → Queue): renders and best-of videos run one at a time on the GPU. Each clip is
  its own entry, so you can drag to reorder, cancel or retry it. "Render all accepted" queues every
  accepted clip of the projects you tick (already rendered clips with the same settings are
  skipped). The queue is saved in `<workspace>/_queue.json`: after a restart unfinished jobs
  continue. "Shut down the PC when the queue is finished" (Windows/macOS) shows a 60 s countdown
  with a Cancel button first; set `SHARKYCLIPS_DRY_SHUTDOWN=1` to test it without shutting down.
* **Best-of video** (project page → Best-of video): pick clips (default: best accepted by viral
  score, calibrated score once available), drag to order, optional intro/outro cards. Output is
  1920x1080 at 60 fps with Instrument Serif title cards (navy/gold), 0.5 s crossfades and every
  clip normalized to -14 LUFS, saved in `workspace/<id>/exports/`. The local LLM writes title
  options, a description and chapter names; chapter timestamps follow YouTube's rules (first at
  00:00, each at least 10 s; a short intro is merged into the first clip).
* **Calibration** (Clips tab → "Add YouTube views", overview under Stats): after 10 clips with real
  views a ridge regression on log views (numpy, penalty chosen by leave-one-out) learns how the
  clip's signals and scores relate to your channel's views. Calibrated score =
  default + n/(n+10) × (model score − default). Stats shows predicted vs real views (leave-one-out),
  and the best content type, publish time, length and kind of moment. Data:
  `~/.sharkyclips/calibration.json`.
* **Fast analysis** (Settings → Local AI): `llm_fallback_model` (qwen3.5:4b) and 6 instead of 9
  title drafts. "Run speed test" measures both setups on your newest project's best clip
  (RTX 5070 Laptop: 28 s vs 15 s per clip).

### Long streams (3-6 hours)

Audio is processed in ~10-minute chunks, split at quiet moments so words aren't cut. Only one
chunk is in memory at a time, and each finished chunk is saved immediately. If you stop
(Ctrl+C) or the computer sleeps, run the same command again and it continues where it stopped.
After transcription the model is fully unloaded from GPU memory, so later phases can load a local
LLM on the same GPU.

### Staying out of the way (resource governor)

`sharkyclips/governor.py` decides every ~2 s how hard SharkyClips may work; `sysmon.py` provides the
measurements in-process (psutil, NVML via `nvml.dll` / `libnvidia-ml`, Windows performance
counters for per-process GPU load / VRAM / video decode+encode, the foreground window,
`GetLastInputInfo`, the lock screen). No helper program is started per sample. With no job and
no visible UI tab (the UI sends a heartbeat only while it's visible) it samples only CPU/RAM every
10 s and doesn't touch the GPU: idle cost measured at ~0.002 % CPU.

| Mode | Priority | CPU | Pauses for |
|---|---|---|---|
| Silent (default) | Windows IDLE, low I/O; macOS background QoS | half the threads + throttling | listed games (in front, or rendering behind other windows), OBS & co. while encoding, fullscreen apps, playing videos, other apps keeping CPU/GPU busy |
| Balanced | BELOW_NORMAL | half + throttling | nothing |
| Turbo | normal | all | nothing |

Away (no input for `perf_idle_minutes`, or the screen is locked) = full speed in Silent and
Balanced, back to the limits on the next tick after you return. Every mode pauses when the GPU
reaches `perf_gpu_temp_limit` until it's 10 °C cooler. VRAM: `perf_vram_headroom_mb` (auto = 25 %,
2 GB on an 8 GB card) always stays free: Whisper steps down to a smaller setup or the CPU and
Ollama gets fewer GPU layers (`num_gpu`) instead. Silent uses `llm_fallback_model` (qwen3.5:4b)
unless you're away.

How limits reach every process: the server sits in a Windows Job Object (`procs.py`), so priority
and CPU affinity apply to all its children (ffmpeg, OCR workers, an Ollama server it started) and
everything dies with it (kill-on-close; macOS/Linux: process group). An Ollama server started by
the user gets the same priority only while a job runs. Pausing happens at safe points: progress
updates, between Whisper chunks (the model is unloaded first), before every LLM request (unloaded
too, right when the pause starts), in frame-decoding and laughter loops; long ffmpeg processes are
suspended and resumed. Nothing is redone. After every GPU job Ollama gets `keep_alive 0`.

Windows: the shortcut runs `pythonw.exe cli.py launch --tray` (no console; log in
`~/.sharkyclips/logs/sharkyclips.log`), every child process is started with `CREATE_NO_WINDOW`, and
the tray icon opens the UI, switches the mode or quits. Ollama's Startup-folder shortcut is moved
to `~/.sharkyclips/disabled-startup/` unless `ollama_autostart` is on.

## Settings

Stored in `~/.sharkyclips/config.json` (Windows: `C:\Users\<you>\.sharkyclips\config.json`).
Set the `SHARKYCLIPS_HOME` environment variable to use another folder. Useful keys:
`workspace_dir`, `default_mode`, `transcribe_language`, `transcribe_model`,
`download_max_height` (default 1080), `ui_language` / `output_language` (default `tr`),
`custom_triggers`, `video_encoder` (`auto` or `h264_nvenc`, `h264_videotoolbox`, `h264_qsv`,
`h264_amf`, `libx264`), `llm_enabled`, `llm_model` (`auto` or an Ollama tag),
`llm_fallback_model` (`qwen3.5:4b`), `llm_num_ctx` (8192), `ollama_url`, `chat_delay` (5 s),
`auto_analyze` (true), `glossary` (names AI titles must spell exactly), `fast_analysis` (false).
Set by the app: `onboarding_done`, `content_types`, `seen_version` (the last "What's new" shown).

Before 1.2.1 the folder was `~/.clipforge` (ClipForge). `sharkyclips/migrate.py` moves it over on the
first start (existing files in the new folder win, paths inside config.json are rewritten) and
renames old shortcuts and the Apps & features entry; `CLIPFORGE_HOME` is still honoured.

## Version, welcome screen, "What's new"

- The version is only in `VERSION` (repo root); every update bumps the patch number and adds a
  CHANGELOG.md entry (English, Turkish, then `<!-- lang:xx -->` summaries for the other languages).
- `sharkyclips/welcome.py`: the launcher writes `~/.sharkyclips/splash.html` and opens it at once;
  it waits for the server and hands over to the app (`?splash=done`), so the splash costs no time.
  First start: 3-step onboarding (language, content types, performance mode + hardware check).
  After an update: the CHANGELOG entry of the new version in the UI language, once.
- `~/.sharkyclips/dev_in_progress.json` (`{"started_at", "task"}`) shows an "Update in progress"
  banner while a new version is being built; heavy jobs ask first. Older than 12 hours = stale.
