# ClipForge

**ClipForge** is a local, 100% free and open-source highlight clipper for streams and videos.
Point it at a Twitch/Kick/YouTube VOD or a video file and it finds the best moments for you.
Everything runs on your own computer: no paid APIs, no cloud, no account.

> Status: phases 1, 2, 3A, 3B and 5 done: transcription, highlight engine, chat signal, local LLM
> (viral score, natural titles that learn your style, hashtags, cover prompt, subtitle translation),
> 9:16 rendering, web UI.

## Features & roadmap

| Phase | What | Status |
|---|---|---|
| 1 | Hardware detection, `doctor`, ingest from URL or file, 16 kHz audio, multilingual transcription with word timestamps, resumable for 3-6 h streams | ✅ done |
| 2 | Highlight engine: pluggable signals (loudness, keywords, laughter/shouting, speech rhythm, music chorus/drop) → hype curve → non-overlapping clip candidates with reasons | ✅ done |
| 3A | Chat replay signal (YouTube, Twitch, or a log file) + local LLM via Ollama: judges clips, refines cuts, viral score, titles, hashtags, cover prompt, hook text, subtitle translation, study-mode explanations | ✅ done |
| 3B | Title quality (few-shot examples per language, glossary, proofread pass, dictionary check, variety rules, thumbs up/down that teach your style) + UI: viral score on cards, output language, model picker, chat stats, hook modes | ✅ done |
| 4 | Clip rendering: vertical 9:16 (facecam + game / fit / fill), burned-in word-timed subtitles (incl. RTL Arabic), hook text + peak flash, facecam detection | ✅ core done |
| 5 | Local web UI: library, timeline with Hype Map, review & render, 7 languages, dark/light | ✅ done |
| 6 | Batch render queue (reorder, ETA, retry, survives restarts, optional shutdown), 16:9 best-of video (title cards, crossfades, loudness, AI titles/description/chapters), channel calibration from real YouTube views, Fast analysis | ✅ done |

**Languages:** Turkish (tr, default), English (en), Russian (ru), Hungarian (hu), German (de),
Arabic (ar, right-to-left), Chinese (zh). Run `python cli.py languages` to see the registry.

## Supported hardware

ClipForge detects your hardware every time it runs and adapts. Nothing is tied to one machine.

| Your computer | Backend | Model picked automatically |
|---|---|---|
| NVIDIA GPU, 6 GB+ VRAM (any series, incl. RTX 50) | faster-whisper on CUDA | large-v3-turbo, float16 |
| NVIDIA GPU, 4-6 GB VRAM | faster-whisper on CUDA | large-v3-turbo, int8_float16 |
| NVIDIA GPU, 1.5-4 GB VRAM | faster-whisper on CUDA | medium / small, int8_float16 |
| Apple Silicon Mac (M1/M2/M3/M4...) | mlx-whisper | large-v3-turbo (small if < 8 GB RAM) |
| AMD / Intel GPU, Intel Mac, or no GPU | faster-whisper on CPU (int8) — **slower** | medium (12 GB+ RAM) or small |

- No CUDA Toolkit install needed: the CUDA libraries (cuBLAS, cuDNN) come from pip and ClipForge
  loads them at runtime.
- If a model doesn't fit in memory, ClipForge automatically steps down
  (float16 → int8 → medium → small → CPU).
- `doctor` runs a real transcription test. If the GPU test fails (e.g. a brand-new GPU needs newer
  libraries), it upgrades ctranslate2 and the NVIDIA libraries, re-tests, and if it still fails it
  switches to CPU and tells you why.

## Setup

You need **Python 3.11+**, **ffmpeg** and **git**. For YouTube downloads, also a JavaScript
runtime (**Deno** recommended, Node.js also works).

### Windows 10 / 11

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Gyan.FFmpeg -e
winget install --id Git.Git -e
winget install --id DenoLand.Deno -e
# close and reopen the terminal so the new tools are on PATH

git clone <this-repo-url> ClipForge
cd ClipForge
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
# NVIDIA GPU only (doctor also does this for you):
python -m pip install -r backend\requirements-nvidia.txt
```

### macOS

```bash
brew install python@3.12 ffmpeg git deno

git clone <this-repo-url> ClipForge
cd ClipForge
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt   # installs mlx-whisper on Apple Silicon
```

### Web UI

```bash
cd backend
python cli.py serve          # opens http://localhost:8000 in your browser
python cli.py serve --lan    # also reachable from your phone / Mac on the same Wi-Fi
```

`--lan` prints the address to open on the other device (e.g. `http://192.168.1.20:8000`).
Anyone on that network can use it, so only do this on a network you trust. Windows may ask to
allow Python through the firewall: allow it for private networks.

The built UI ships in `frontend/dist`, so Node.js isn't needed to use it. If you change the
frontend sources and Node.js is installed, `serve` rebuilds it automatically
(or run `cd frontend && npm install && npm run dev` for live reloading on port 5173).

What you can do in the browser:

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
  glossary), custom trigger words per language, video encoder, default mode.
- Keyboard: up/down (or j/k) moves through candidates, `a` accepts/unaccepts.

Heavy work (transcription, analysis, rendering) runs one job at a time on the GPU lane;
downloads run alongside. Progress streams live to every open browser tab.

### Check everything

```bash
cd backend
python cli.py doctor
```

`doctor` prints an OK / MISSING table (OS, Python, RAM, ffmpeg, yt-dlp, GPU, VRAM, CUDA, the
chosen backend) and the exact install command for anything missing.

## Usage

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

### Local LLM (Ollama)

`python cli.py doctor` installs [Ollama](https://ollama.com) (winget / brew) and downloads the model.
The model is picked by hardware: **qwen3.5:9b** (6.6 GB, 4-bit) with 8 GB+ VRAM or Apple Silicon
with 16 GB+, otherwise **qwen3.5:4b** (3.3 GB). Set `llm_model` to any Ollama model to override.
If Ollama's own download keeps failing (seen with broken IPv6), ClipForge downloads the model
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

#### Titles (`clipforge/titles/`)

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

**Your style**: thumbs up / down in the web UI are saved in `~/.clipforge/title_feedback.json`.
The next "Analyze with AI" rewrites the titles with your liked ones as examples (the scores and
cuts stay cached).

Measured on an RTX 5070 Laptop (8 GB), qwen3.5:9b, 15 clips of a 19 min stream: ~10 min in total
(~40 s per clip: ~12 s judging, the rest drafting + proofreading titles; ~37 tokens/s with ~85% of the model on the GPU, unloaded
afterwards). Re-running after a thumbs up only redoes the titles. A 7 min study video: the LLM
reads the transcript in ~30 s.

**Your own trigger words** go in `~/.clipforge/config.json`:

```json
"custom_triggers": {"tr": ["kral", "efsane an"], "en": {"reaction": ["poggers"], "study": ["mnemonic"]}}
```

**Adding a signal** (e.g. chat activity): subclass `Signal` in `highlights/signals/`, decorate it
with `@register`, import it in `signals/__init__.py`, and give it a weight in `modes.py`.
The scorer and candidate picker don't change.

### Queue, best-of videos and calibration (Phase 6)

* **Queue** (top bar → Queue): renders and best-of videos run one at a time on the GPU. Each clip is
  its own entry, so you can drag to reorder, cancel or retry it. "Render all accepted" queues every
  accepted clip of the projects you tick (already rendered clips with the same settings are
  skipped). The queue is saved in `<workspace>/_queue.json`: after a restart unfinished jobs
  continue. "Shut down the PC when the queue is finished" (Windows/macOS) shows a 60 s countdown
  with a Cancel button first; set `CLIPFORGE_DRY_SHUTDOWN=1` to test it without shutting down.
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
  `~/.clipforge/calibration.json`.
* **Fast analysis** (Settings → Local AI): `llm_fallback_model` (qwen3.5:4b) and 6 instead of 9
  title drafts. "Run speed test" measures both setups on your newest project's best clip
  (RTX 5070 Laptop: 28 s vs 15 s per clip).

### Long streams (3-6 hours)

Audio is processed in ~10-minute chunks, split at quiet moments so words aren't cut. Only one
chunk is in memory at a time, and each finished chunk is saved immediately. If you stop
(Ctrl+C) or the computer sleeps, run the same command again and it continues where it stopped.
After transcription the model is fully unloaded from GPU memory, so later phases can load a local
LLM on the same GPU.

## Settings

Stored in `~/.clipforge/config.json` (Windows: `C:\Users\<you>\.clipforge\config.json`).
Set the `CLIPFORGE_HOME` environment variable to use another folder. Useful keys:
`workspace_dir`, `default_mode`, `transcribe_language`, `transcribe_model`,
`download_max_height` (default 1080), `ui_language` / `output_language` (default `tr`),
`custom_triggers`, `video_encoder` (`auto` or `h264_nvenc`, `h264_videotoolbox`, `h264_qsv`,
`h264_amf`, `libx264`), `llm_enabled`, `llm_model` (`auto` or an Ollama tag),
`llm_fallback_model` (`qwen3.5:4b`), `llm_num_ctx` (8192), `ollama_url`, `chat_delay` (5 s),
`auto_analyze` (true), `glossary` (names AI titles must spell exactly), `fast_analysis` (false).

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg was not found` | Windows: `winget install --id Gyan.FFmpeg -e`, macOS: `brew install ffmpeg`, then open a new terminal |
| YouTube download fails | `python -m pip install -U "yt-dlp[default]"` and install Deno or Node.js |
| GPU test fails | Update your NVIDIA driver, then `python cli.py doctor` again |
| Slow transcription | You're on CPU mode; check `doctor` output. `--model small` is faster |
| First run is slow | The Whisper model (~1.6 GB) is downloaded once and cached in `~/.cache/huggingface` |
| LLM is slow or runs out of memory | Set `"llm_model": "qwen3.5:4b"` in the config (or any smaller Ollama model) |
| No titles / viral score | Ollama isn't installed or running: `python cli.py doctor` |
| Titles misspell a name | Add it to the glossary in Settings, then "Analyze with AI" again |

## License

MIT — see [LICENSE](LICENSE). Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[mlx-whisper](https://github.com/ml-explore/mlx-examples), [yt-dlp](https://github.com/yt-dlp/yt-dlp)
and [FFmpeg](https://ffmpeg.org/).
