#!/usr/bin/env python3
"""ClipForge command line.

    python cli.py doctor
    python cli.py ingest <url-or-path> [--mode gaming|study|music]
    python cli.py transcribe <id> [--lang auto|tr|en|ru|hu|de|ar|zh] [--model auto|large-v3-turbo|medium|small]
    python cli.py highlights <id> [--mode gaming|study|music] [--top N]
    python cli.py cut <id> <rank> | --all
    python cli.py chat <id> [--file chat.json] [--force]
    python cli.py analyze <id> [--lang tr|en|...] [--force] [--no-refine]
    python cli.py render <id> <rank...> | --accepted | --all [--layout ..] [--subs ..] [--hook flash]
    python cli.py list
    python cli.py languages
    python cli.py serve [--lan] [--port 8000]
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


def cmd_highlights(args) -> int:
    from rich.table import Table

    from clipforge.highlights import run_highlights
    from clipforge.project import get_project

    project = get_project(args.id)
    res = run_highlights(project, mode=args.mode, top=args.top, force=args.force)
    cands = res["candidates"]
    if not cands:
        console.print("[yellow]No highlight candidates found.[/]")
        return 0
    t = Table(title=f"Highlights - {res['mode']} mode - clips: {len(cands)}")
    t.add_column("#", justify="right")
    t.add_column("time")
    t.add_column("len", justify="right")
    t.add_column("hype", justify="right")
    t.add_column("reasons")
    t.add_column("text", overflow="fold", max_width=48)
    for c in cands:
        reasons = ", ".join(r["code"] + (f" {r['value']}" if r.get("value") else "")
                            for r in c["reasons"][:4])
        t.add_row(str(c["rank"]), f"{fmt_time(c['start'])}-{fmt_time(c['end'])}",
                  f"{c['duration']:.0f}s", str(c["hype_score"]), reasons, c["text"][:120])
    console.print(t)
    skipped = [f"{k} ({v['reason']})" for k, v in res["signals"].items() if v["status"] != "ok"]
    if skipped:
        console.print(f"[yellow]Skipped signals:[/] {'; '.join(skipped)}")
    console.print(f"Done in {res['elapsed_seconds']}s -> {project.dir / 'highlights.json'}")
    return 0


def cmd_cut(args) -> int:
    from rich.table import Table

    from clipforge.errors import ClipForgeError
    from clipforge.project import get_project, read_json
    from clipforge.render import export_preview, pick_encoder, preview_name
    from clipforge.ui import time_progress

    project = get_project(args.id)
    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise ClipForgeError("No highlights yet for this project.",
                             f"Run: python cli.py highlights {project.id}")
    cands = read_json(hl_path)["candidates"]
    if args.all:
        chosen = cands
    elif args.rank is not None:
        chosen = [c for c in cands if c["rank"] == args.rank]
        if not chosen:
            raise ClipForgeError(f"No candidate with rank {args.rank}.",
                                 f"Ranks available: 1-{len(cands)}")
    else:
        raise ClipForgeError("Tell me which clip to cut.", "Pass a rank (e.g. 1) or --all.")
    source = project.source_path
    if source is None:
        raise ClipForgeError("The project's source video is missing.",
                             "Re-run: python cli.py ingest <url-or-path>")

    enc, notes = pick_encoder()
    for note in notes:
        console.print(f"[dim]{note}[/]")
    console.print(f"Encoder: [bold]{enc.label}[/]")
    out_dir = project.dir / "previews"
    t = Table(title=f"Previews -> {out_dir}")
    for col in ("#", "file", "length", "size", "render", "speed", "encoder"):
        t.add_column(col)
    total = 0.0
    for c in chosen:
        dest = out_dir / preview_name(c["rank"], c["hype_score"], c["start"])
        with time_progress() as prog:
            task = prog.add_task(f"Clip {c['rank']:02d}", total=c["duration"])
            r = export_preview(source, c["start"], c["end"], dest,
                               on_progress=lambda s: prog.update(task, completed=s))
            prog.update(task, completed=c["duration"])
        total += r.seconds
        t.add_row(str(c["rank"]), dest.name, f"{c['duration']:.1f}s",
                  f"{r.size_bytes / 1024**2:.1f} MB", f"{r.seconds:.1f}s",
                  f"{c['duration'] / r.seconds:.0f}x", r.encoder)
    console.print(t)
    console.print(f"[green]Done:[/] {len(chosen)} preview(s) in {total:.1f}s")
    return 0


def cmd_chat(args) -> int:
    from clipforge import chat
    from clipforge.project import get_project

    project = get_project(args.id)
    if args.file:
        data = chat.import_file(project, Path(args.file).expanduser())
    else:
        data = chat.ensure_chat(project, force=args.force)
    if data["status"] != "ok":
        console.print(f"[yellow]No chat:[/] {data.get('reason')}")
        return 0
    console.print(f"[green]Chat:[/] {data['count']} messages from {data['authors']} people "
                  f"({data['source']}) -> {chat.chat_path(project)}")
    console.print(f"Next: [bold]python cli.py highlights {project.id}[/] to use it.")
    return 0


def cmd_analyze(args) -> int:
    from rich.markup import escape
    from rich.table import Table

    from clipforge.analyze import analyze_project
    from clipforge.project import get_project

    project = get_project(args.id)

    def progress(i: int, n: int, c: dict) -> None:
        p = c["publish"]
        console.print(f"[dim]{i}/{n}[/] #{c['rank']:02d} viral [bold]{p['viral_score']}[/] "
                      f"({p['viral_label']})  {escape(p['titles'][0])}")

    res = analyze_project(project, out_lang=args.lang, force=args.force, refine=not args.no_refine,
                          ranks=args.ranks, translate=not args.no_translate, on_progress=progress)
    t = Table(title=f"LLM analysis - {res['model']} - output: {res['language']}")
    for col in ("#", "viral", "hook/ret/trend/len", "cut", "title", "hook text", "s"):
        t.add_column(col, overflow="fold")
    tm = {x["rank"]: x for x in res["timings"]}
    for c in res["candidates"]:
        p, j = c["publish"], c["llm"]
        ss = p["sub_scores"]
        o = j["original"]
        cut = f"{c['start'] - o['start']:+.1f}/{c['end'] - o['end']:+.1f}s" if j["refined"] else "="
        x = tm[c["rank"]]
        t.add_row(str(c["rank"]), f"{p['viral_score']} {p['viral_label']}",
                  f"{ss['hook']}/{ss['retention']}/{ss['trend_fit']}/{ss['length_fit']}", cut,
                  escape(p["titles"][0]), escape(p["hook_text"]),
                  "cache" if x["cached"] else f"{x['seconds']:.1f}")
    console.print(t)
    console.print(f"{len(res['candidates'])} clips in {res['total_seconds']}s "
                  f"(model load {res['load_seconds']}s, {res['calls']} LLM calls, "
                  f"{res['retries']} retries, {res['tokens_per_second']} tokens/s). LLM unloaded from the GPU.")
    return 0


def cmd_render(args) -> int:
    from rich.table import Table

    from clipforge.clips import ClipOptions, Facecam, render_clip
    from clipforge.project import get_project
    from clipforge.ui import time_progress
    from clipforge.web import state

    project = get_project(args.id)
    hl = state.load_highlights(project)
    if not hl:
        raise ClipForgeError("No highlights yet.", f"Run: python cli.py highlights {project.id}")
    review = state.load_review(project, hl)
    cands = hl["candidates"]
    if args.all:
        chosen = cands
    elif args.accepted:
        chosen = [c for c in cands if c["id"] in review["accepted"]]
    else:
        chosen = [c for c in cands if c["rank"] in (args.ranks or [])]
    if not chosen:
        raise ClipForgeError("No clips selected.", "Pass ranks (e.g. 1 2 3), --accepted or --all.")
    opts = {**review["options"], **{k: v for k, v in {
        "layout": args.layout, "subtitles": args.subs, "subtitle_lang": args.sub_lang}.items() if v}}
    if args.hook:
        opts["hook_flash"] = "flash" in args.hook
        opts["hook"] = "text" in args.hook
    facecam = Facecam.from_dict(review.get("facecam"))
    t = Table(title=f"Clips -> {project.dir / 'clips'}")
    for col in ("#", "file", "length", "size", "render"):
        t.add_column(col)
    for c in chosen:
        o = ClipOptions.from_dict({**opts, "hook_text": review["hooks"].get(c["id"], "")})
        name = f"{c['rank']:02d}_{c['id']}.mp4"
        with time_progress() as prog:
            task = prog.add_task(f"Clip {c['rank']:02d}", total=c["duration"])
            r = render_clip(project, c, o, facecam, project.dir / "clips" / name,
                            on_progress=lambda s: prog.update(task, completed=s))
        state.save_clip(project, c["id"], {
            "file": name, "id": c["id"], "rank": c["rank"], "start": c["start"], "end": c["end"],
            "duration": c["duration"], "options": o.to_dict(),
            "facecam": facecam.to_dict() if facecam else None, "rendered_at": state.now_iso(),
            "size_bytes": r.size_bytes, "render_seconds": round(r.seconds, 2), "encoder": r.encoder})
        t.add_row(str(c["rank"]), name, f"{c['duration']:.1f}s", f"{r.size_bytes / 1024**2:.1f} MB",
                  f"{r.seconds:.1f}s ({r.encoder})")
    console.print(t)
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


def _lan_ip() -> str | None:
    import socket

    try:  # no packet is sent; this just asks the OS which interface would be used
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.255.255", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def _ensure_frontend() -> None:
    """Build the React app if it's missing or older than its sources (needs Node.js)."""
    import shutil
    import subprocess

    root = Path(__file__).resolve().parent.parent / "frontend"
    index = root / "dist" / "index.html"
    sources = [p for p in (root / "src").rglob("*") if p.is_file()] +               [root / n for n in ("index.html", "package.json", "vite.config.ts") if (root / n).is_file()]
    newest = max((p.stat().st_mtime for p in sources), default=0)
    if index.is_file() and index.stat().st_mtime >= newest:
        return
    npm = shutil.which("npm")
    if npm is None:
        if index.is_file():
            return  # the shipped build is fine; sources only matter to developers
        raise ClipForgeError("The web UI isn't built and Node.js isn't installed.",
                             "Install Node.js (Windows: winget install OpenJS.NodeJS.LTS, "
                             "macOS: brew install node), then run serve again.")
    console.print("Building the web UI (first run only) ...")
    if not (root / "node_modules").is_dir():
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=root, check=True)
    subprocess.run([npm, "run", "build"], cwd=root, check=True)


def cmd_serve(args) -> int:
    import threading
    import webbrowser

    import uvicorn

    _ensure_frontend()
    from clipforge.web.app import app

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    local_url = f"http://localhost:{args.port}"
    console.print(f"[bold]ClipForge[/] web UI: [cyan]{local_url}[/]")
    if args.lan:
        ip = _lan_ip()
        if ip:
            app.state.lan_url = f"http://{ip}:{args.port}"
            console.print(f"On your phone / other computers (same Wi-Fi): [cyan]{app.state.lan_url}[/]")
            console.print("[dim]Anyone on this network can open it. Windows may ask to allow "
                          "Python through the firewall: allow it for private networks.[/]")
        else:
            console.print("[yellow]Couldn't find this computer's network address.[/]")
    console.print("[dim]Press Ctrl+C to stop.[/]")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(local_url)).start()
    uvicorn.run(app, host=host, port=args.port, log_level="warning")
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

    h = sub.add_parser("highlights", help="find the best moments (clip candidates)")
    h.add_argument("id", help="project id (a unique prefix is enough)")
    h.add_argument("--mode", choices=MODES, help="override the project's mode")
    h.add_argument("--top", type=int, help="max number of clips (default: ~1 per 4 minutes)")
    h.add_argument("--force", action="store_true", help="recompute cached signals")
    h.set_defaults(func=cmd_highlights)

    c = sub.add_parser("cut", help="export quick preview MP4s of highlight candidates")
    c.add_argument("id", help="project id (a unique prefix is enough)")
    c.add_argument("rank", nargs="?", type=int, help="candidate rank from `highlights` (e.g. 1)")
    c.add_argument("--all", action="store_true", help="export every candidate")
    c.set_defaults(func=cmd_cut)

    ch = sub.add_parser("chat", help="download the chat replay, or import a chat log file")
    ch.add_argument("id", help="project id (a unique prefix is enough)")
    ch.add_argument("--file", help="chat log: chat-downloader / yt-dlp / TwitchDownloader JSON or text")
    ch.add_argument("--force", action="store_true", help="download again")
    ch.set_defaults(func=cmd_chat)

    a = sub.add_parser("analyze", help="local LLM: judge clips, viral score, titles, hashtags, cover prompt")
    a.add_argument("id", help="project id (a unique prefix is enough)")
    a.add_argument("--lang", choices=languages.codes(), help="output language (default: config, tr)")
    a.add_argument("--ranks", type=int, nargs="+", help="only these candidates (e.g. --ranks 1 2 3)")
    a.add_argument("--force", action="store_true", help="ignore cached LLM answers")
    a.add_argument("--no-refine", action="store_true", help="keep the original clip boundaries")
    a.add_argument("--no-translate", action="store_true", help="don't translate subtitles")
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("render", help="render vertical 9:16 clips with subtitles")
    r.add_argument("id", help="project id (a unique prefix is enough)")
    r.add_argument("ranks", type=int, nargs="*", help="candidate ranks (e.g. 1 2 3)")
    r.add_argument("--accepted", action="store_true", help="the clips accepted in the web UI")
    r.add_argument("--all", action="store_true")
    r.add_argument("--layout", choices=["auto", "split", "fit", "crop"])
    r.add_argument("--subs", choices=["bold", "clean", "minimal", "none"])
    r.add_argument("--sub-lang", choices=languages.codes(),
                   help="subtitle language (translated by `analyze --lang`)")
    r.add_argument("--hook", choices=["text", "flash", "flash+text", "none"],
                   help="flash = the peak moment for ~1 s first; text = hook text on screen")
    r.set_defaults(func=cmd_render)

    s = sub.add_parser("serve", help="start the web UI in your browser")
    s.add_argument("--lan", action="store_true",
                   help="also allow other devices on your network (phone, laptop)")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true", help="don't open the browser")
    s.set_defaults(func=cmd_serve)

    sub.add_parser("list", help="list projects").set_defaults(func=cmd_list)
    sub.add_parser("languages", help="show supported languages").set_defaults(func=cmd_languages)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ClipForgeError as exc:
        from rich.markup import escape  # messages may contain [brackets], e.g. "yt-dlp[default]"

        console.print(f"[bold red]Error:[/] {escape(exc.message)}")
        if exc.hint:
            console.print(f"[yellow]Fix:[/] {escape(exc.hint)}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/] Finished work is saved - run the same command "
                      "again to resume.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
