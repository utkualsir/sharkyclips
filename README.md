# ClipForge

**ClipForge** is a local, 100% free and open-source highlight clipper for streams and videos.
Point it at a Twitch/Kick/YouTube VOD or a video file and it finds the best moments for you.
Everything runs on your own computer: no paid APIs, no cloud, no account.

> Status: **Phase 1** (foundation, ingest, multilingual transcription). The CLI works today;
> a web UI comes in a later phase.

## Features & roadmap

| Phase | What | Status |
|---|---|---|
| 1 | Hardware detection, `doctor`, ingest from URL or file, 16 kHz audio, multilingual transcription with word timestamps, resumable for 3-6 h streams | ✅ done |
| 2 | Highlight detection (audio energy, chat/keywords, per-mode rules: gaming / study / music) | planned |
| 3 | Local LLM (on the same GPU, never loaded at the same time as Whisper) to rank and title clips | planned |
| 4 | Clip rendering: vertical 9:16 crops, burned-in subtitles (incl. RTL Arabic), export presets | planned |
| 5 | FastAPI web UI (Turkish by default, all 7 languages) | planned |

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
  cache/            per-chunk results (lets long runs resume)
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
`download_max_height` (default 1080), `ui_language` / `output_language` (default `tr`).

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg was not found` | Windows: `winget install --id Gyan.FFmpeg -e`, macOS: `brew install ffmpeg`, then open a new terminal |
| YouTube download fails | `python -m pip install -U "yt-dlp[default]"` and install Deno or Node.js |
| GPU test fails | Update your NVIDIA driver, then `python cli.py doctor` again |
| Slow transcription | You're on CPU mode; check `doctor` output. `--model small` is faster |
| First run is slow | The Whisper model (~1.6 GB) is downloaded once and cached in `~/.cache/huggingface` |

## License

MIT — see [LICENSE](LICENSE). Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[mlx-whisper](https://github.com/ml-explore/mlx-examples), [yt-dlp](https://github.com/yt-dlp/yt-dlp)
and [FFmpeg](https://ffmpeg.org/).
