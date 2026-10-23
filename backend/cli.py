#!/usr/bin/env python3
"""ClipForge command line.

    python cli.py doctor
    python cli.py ingest <url-or-path> [--mode gaming|study|music]
    python cli.py transcribe <id> [--lang auto|tr|en|ru|hu|de|ar|zh] [--model auto|large-v3-turbo|medium|small]
    python cli.py list
    python cli.py languages
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"ClipForge needs Python 3.11 or newer (you have {sys.version.split()[0]}).\n"
             "Windows: winget install --id Python.Python.3.12 -e\n"
             "macOS:   brew install python@3.12")

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")  # hide "unauthenticated requests" notice

try:
    from clipforge import __version__, config, languages
    from clipforge.errors import ClipForgeError
    from clipforge.hardware import MODEL_CHOICES
    from clipforge.project import MODES
    from clipforge.ui import console, fmt_time
except ImportError as exc:  # dependencies not installed yet
    req = Path(__file__).resolve().parent / "requirements.txt"
    sys.exit(f"Missing Python package: {exc.name or exc}\n"
             f"Install the requirements (inside your venv):\n"
             f'  python -m pip install -r "{req}"')


def cmd_doctor(args) -> int:
    from clipforge.doctor import run_doctor

    return run_doctor(fix=not args.no_fix)


def cmd_ingest(args) -> int:
    from rich.table import Table

    from clipforge.ingest import ingest

    mode = args.mode or config.get("default_mode")
    project = ingest(args.source, mode=mode)
    meta = project.load_meta()
    t = Table(show_header=False, box=None)
    for k in ("id", "title", "mode", "duration", "resolution", "fps"):
        v = meta.get(k)
        t.add_row(f"[bold]{k}[/]", fmt_time(v) if k == "duration" else str(v))
    t.add_row("[bold]folder[/]", str(project.dir))
    console.print(t)
    console.print(f"[green]Ingested.[/] Next: [bold]python cli.py transcribe {project.id}[/]")
    return 0


def cmd_transcribe(args) -> int:
    from clipforge.project import get_project
    from clipforge.transcribe import summary_line, transcribe_project

    project = get_project(args.id)
    lang = args.lang or config.get("transcribe_language") or "auto"
    model = args.model or config.get("transcribe_model") or "auto"
    console.print(f"Project [bold]{project.id}[/]  language={lang}  model={model}")
    t0 = time.perf_counter()
    transcript = transcribe_project(project, lang=lang, model=model, force=args.force)
    console.print(f"[green]Done[/] in {fmt_time(time.perf_counter() - t0)} (wall clock): "
                  f"{summary_line(transcript)}")
    console.print(f"Transcript: {project.transcript_path}")
    if transcript.get("language") and not transcript.get("language_supported"):
        console.print(f"[yellow]Detected language '{transcript['language']}' isn't one of "
                      f"ClipForge's languages ({', '.join(languages.codes())}); later steps may "
                      "not fully support it.[/]")
    return 0


def cmd_list(args) -> int:
    from rich.table import Table

    from clipforge.project import list_projects

    projects = list_projects()
    if not projects:
        console.print("No projects yet. Try: python cli.py ingest <url-or-path>")
        return 0
    t = Table(title=str(config.workspace_dir()))
    for col in ("id", "title", "mode", "duration", "transcript"):
        t.add_column(col)
    for p in projects:
        m = p.load_meta()
        tr = m.get("transcript")
        t.add_row(p.id, str(m.get("title", ""))[:50], m.get("mode", ""), fmt_time(m.get("duration")),
                  f"{tr['language']} / {tr['model']}" if tr else "-")
    console.print(t)
    return 0


def cmd_languages(args) -> int:
    from rich.table import Table

    t = Table(title="Supported languages")
    for col in ("code", "native", "english", "RTL", "whisper"):
        t.add_column(col)
    for lang in languages.LANGUAGES.values():
        default = " (default)" if lang.code == languages.DEFAULT_UI_LANGUAGE else ""
        t.add_row(lang.code + default, lang.native_name, lang.english_name,
                  "yes" if lang.is_rtl else "", lang.whisper_code)
    console.print(t)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clipforge",
                                description=f"ClipForge {__version__} - local stream & video highlight clipper")
    p.add_argument("--version", action="version", version=f"ClipForge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check dependencies, GPU and run a real smoke test")
    d.add_argument("--no-fix", action="store_true", help="don't install/upgrade anything")
    d.set_defaults(func=cmd_doctor)

    i = sub.add_parser("ingest", help="import a video from a URL or a local file")
    i.add_argument("source", help="URL (YouTube, Twitch, Kick, ...) or path to a video file")
    i.add_argument("--mode", choices=MODES, help="content type (default: gaming)")
    i.set_defaults(func=cmd_ingest)

    t = sub.add_parser("transcribe", help="transcribe a project with word-level timestamps")
    t.add_argument("id", help="project id (from ingest or `list`; a unique prefix is enough)")
    t.add_argument("--lang", choices=[languages.AUTO, *languages.codes()],
                   help="spoken language (default: auto-detect)")
    t.add_argument("--model", choices=MODEL_CHOICES, help="Whisper model (default: auto)")
    t.add_argument("--force", action="store_true", help="redo even if a transcript exists")
    t.set_defaults(func=cmd_transcribe)

    sub.add_parser("list", help="list projects").set_defaults(func=cmd_list)
    sub.add_parser("languages", help="show supported languages").set_defaults(func=cmd_languages)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ClipForgeError as exc:
        console.print(f"[bold red]Error:[/] {exc.message}")
        if exc.hint:
            console.print(f"[yellow]Fix:[/] {exc.hint}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/] Finished work is saved - run the same command "
                      "again to resume.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
