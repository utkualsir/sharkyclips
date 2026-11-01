#!/usr/bin/env python3
"""SharkyClips command line.

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
    python cli.py lan-pin [--clear]      (access PIN / password other devices need in --lan mode)
    python cli.py launch [--tray]        (desktop shortcut: reuse a running server or start one)

Started with pythonw.exe (the Windows shortcut), there is no console: output goes to
~/.sharkyclips/logs/sharkyclips.log and a tray icon opens or quits SharkyClips.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"SharkyClips needs Python 3.11 or newer (you have {sys.version.split()[0]}).\n"
             "Windows: winget install --id Python.Python.3.12 -e\n"
             "macOS:   brew install python@3.12")



def _log_without_console() -> None:
    """pythonw has no stdout/stderr: write them to a log file instead of losing them."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    home = Path(os.environ.get("SHARKYCLIPS_HOME") or os.environ.get("CLIPFORGE_HOME")
                or Path.home() / ".sharkyclips")
    log = home / "logs" / "sharkyclips.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        if os.environ.get("SHARKYCLIPS_SUPERVISED") != "1" and log.is_file() and log.stat().st_size > 5_000_000:
            log.replace(log.with_suffix(".old.log"))
        f = open(log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the process
    except OSError:
        f = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    sys.stdout = sys.stdout or f
    sys.stderr = sys.stderr or f


_log_without_console()
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")  # hide "unauthenticated requests" notice

try:
    from sharkyclips import __version__, config, languages
    from sharkyclips.errors import SharkyClipsError
    from sharkyclips.hardware import MODEL_CHOICES
    from sharkyclips.project import MODES
    from sharkyclips.ui import console, fmt_time
except ImportError as exc:  # dependencies not installed yet
    req = Path(__file__).resolve().parent / "requirements.txt"
    sys.exit(f"Missing Python package: {exc.name or exc}\n"
             f"Install the requirements (inside your venv):\n"
             f'  python -m pip install -r "{req}"')


def cmd_doctor(args) -> int:
    from sharkyclips.doctor import run_doctor

    return run_doctor(fix=not args.no_fix, download_models=args.download_models)


def cmd_ingest(args) -> int:
    from rich.table import Table

    from sharkyclips.ingest import ingest

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
    from sharkyclips.project import get_project
    from sharkyclips.transcribe import summary_line, transcribe_project

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
                      f"SharkyClips's languages ({', '.join(languages.codes())}); later steps may "
                      "not fully support it.[/]")
    return 0


def cmd_highlights(args) -> int:
    from rich.table import Table

    from sharkyclips.highlights import run_highlights
    from sharkyclips.project import get_project

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

    from sharkyclips.errors import SharkyClipsError
    from sharkyclips.project import get_project, read_json
    from sharkyclips.render import export_preview, pick_encoder, preview_name
    from sharkyclips.ui import time_progress

    project = get_project(args.id)
    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise SharkyClipsError("No highlights yet for this project.",
                               f"Run: python cli.py highlights {project.id}")
    cands = read_json(hl_path)["candidates"]
    if args.all:
        chosen = cands
    elif args.rank is not None:
        chosen = [c for c in cands if c["rank"] == args.rank]
        if not chosen:
            raise SharkyClipsError(f"No candidate with rank {args.rank}.",
                                   f"Ranks available: 1-{len(cands)}")
    else:
        raise SharkyClipsError("Tell me which clip to cut.", "Pass a rank (e.g. 1) or --all.")
    source = project.source_path
    if source is None:
        raise SharkyClipsError("The project's source video is missing.",
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
    from sharkyclips import chat
    from sharkyclips.project import get_project

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

    from sharkyclips.analyze import analyze_project
    from sharkyclips.project import get_project

    project = get_project(args.id)

    def progress(i: int, n: int, c: dict) -> None:
        p = c["publish"]
        console.print(f"[dim]{i}/{n}[/] #{c['rank']:02d} viral [bold]{p['viral_score']}[/] "
                      f"({p['viral_label']})  {escape((p['titles'] or ['-'])[0])}")

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
                  escape((p["titles"] or ["-"])[0]), escape(p["hook_text"]),
                  "cache" if x["cached"] else f"{x['seconds']:.1f}")
    console.print(t)
    console.print(f"{len(res['candidates'])} clips in {res['total_seconds']}s "
                  f"(model load {res['load_seconds']}s, {res['calls']} LLM calls, "
                  f"{res['retries']} retries, {res['tokens_per_second']} tokens/s). LLM unloaded from the GPU.")
    return 0


def cmd_render(args) -> int:
    from rich.table import Table

    from sharkyclips.clips import ClipOptions, Facecam, render_clip
    from sharkyclips.project import get_project
    from sharkyclips.ui import time_progress
    from sharkyclips.web import state

    project = get_project(args.id)
    hl = state.load_highlights(project)
    if not hl:
        raise SharkyClipsError("No highlights yet.", f"Run: python cli.py highlights {project.id}")
    review = state.load_review(project, hl)
    cands = hl["candidates"]
    if args.all:
        chosen = cands
    elif args.accepted:
        chosen = [c for c in cands if c["id"] in review["accepted"]]
    else:
        chosen = [c for c in cands if c["rank"] in (args.ranks or [])]
    if not chosen:
        raise SharkyClipsError("No clips selected.", "Pass ranks (e.g. 1 2 3), --accepted or --all.")
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

    from sharkyclips.project import list_projects

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
        raise SharkyClipsError("The web UI isn't built and Node.js isn't installed.",
                               "Install Node.js (Windows: winget install OpenJS.NodeJS.LTS, "
                               "macOS: brew install node), then run serve again.")
    from sharkyclips import procs

    console.print("Building the web UI (first run only) ...")
    steps = [[npm, "run", "build"]]
    if not (root / "node_modules").is_dir():
        steps.insert(0, [npm, "install", "--no-audit", "--no-fund"])
    for step in steps:
        if procs.run_streamed(step, cwd=root) != 0:
            raise subprocess.CalledProcessError(1, step)


def _sharkyclips_version_at(port: int, timeout: float = 0.8) -> str | None:
    """Version of the SharkyClips server answering on this port, or None."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return str(data["version"]) if isinstance(data, dict) and "reason_codes" in data else None
    except Exception:  # noqa: BLE001 - nothing there, or another app
        return None


def _restart_if_outdated(port: int, running: str, wait: float = 40.0) -> bool:
    """An older SharkyClips is still running after an update (e.g. it sat in the tray while the
    files changed): it would serve the new UI with the old API. Restart it onto the new code if
    it's idle. Busy: leave it alone (the UI shows a "restart to finish the update" bar).
    Returns True when the server now runs this version."""
    import json
    import urllib.request

    from sharkyclips.updater import version_tuple

    try:
        if version_tuple(running) >= version_tuple(__version__):
            return False
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/api/jobs", timeout=3) as r:
            if any(j.get("status") in ("queued", "running") for j in json.loads(r.read().decode("utf-8"))):
                return False
        req = urllib.request.Request(f"{base}/api/update/restart", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            if not json.loads(r.read().decode("utf-8")).get("restarting"):
                return False
    except Exception:  # noqa: BLE001 - can't tell: keep using the running server
        return False
    end = time.time() + wait
    while time.time() < end:
        time.sleep(0.5)
        if _sharkyclips_version_at(port, timeout=0.5) == __version__:
            return True
    return False


def _wait_for_running(info: dict, wait: float = 30.0) -> tuple[int | None, str | None]:
    """The SharkyClips that holds the server lock (it may be restarting): its port and version."""
    port = info.get("port")
    end = time.time() + wait
    while isinstance(port, int):
        v = _sharkyclips_version_at(port, timeout=0.5)
        if v or time.time() >= end:
            return port, v
        time.sleep(0.5)
    return None, None


def _port_free(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False  # something is listening
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _open_browser_when_ready(url: str, port: int, timeout: float = 90) -> None:
    import threading
    import webbrowser

    def wait() -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _sharkyclips_version_at(port):
                webbrowser.open(url)
                return
            time.sleep(0.4)

    threading.Thread(target=wait, daemon=True).start()


def _open_splash_or_wait(url: str, port: int) -> None:
    """Open the splash page right away (it waits for the server and then opens the app), so the
    start-up time is spent looking at the splash, not at nothing. Falls back to opening the app
    when the server is ready."""
    import webbrowser

    from sharkyclips import welcome

    splash = welcome.write_splash(url)
    if splash is not None:
        try:
            if webbrowser.open(splash.resolve().as_uri()):
                return
        except Exception:  # noqa: BLE001 - no browser registered for files: use the old way
            pass
    _open_browser_when_ready(url, port)


def _run_server(args) -> int:
    """The real web server (a child process of `serve`, which restarts it after updates)."""
    from sharkyclips import governor, procs

    governor.limit_thread_pools()  # before numpy & co. create their thread pools
    procs.contain_server()  # Windows Job Object: priority/affinity for all children, no orphans
    procs.hide_child_windows()  # no console window ever flashes up (ffmpeg, ollama, git, ...)

    import uvicorn

    from sharkyclips.web.app import app

    app.state.lan_url = os.environ.get("SHARKYCLIPS_LAN_URL") or None
    uvicorn.run(app, host="0.0.0.0" if args.lan else "127.0.0.1", port=args.port, log_level="warning")
    return 0


def _signal_group(pgid: int, name: str) -> None:
    import signal

    try:
        os.killpg(pgid, getattr(signal, name))
    except (OSError, AttributeError):
        pass


def cmd_lan_pin(args) -> int:
    """Set or remove the access PIN / password other devices need in --lan mode."""
    import getpass

    from sharkyclips import lanauth

    if args.clear:
        lanauth.clear_secret()
        console.print("Access PIN removed. In --lan mode anyone on your network can use SharkyClips.")
        return 0
    first = getpass.getpass(f"New PIN or password ({lanauth.MIN_LEN}+ characters): ")
    if getpass.getpass("Repeat it: ") != first:
        console.print("[red]The two entries don't match.[/] Nothing changed.")
        return 1
    kind = lanauth.set_secret(first)
    console.print(f"Access {'PIN' if kind == 'pin' else 'password'} saved (only a salted hash is stored). "
                  "Every device has to log in again.")
    return 0


def cmd_serve(args) -> int:
    from sharkyclips.updater import RESTART_CODE

    if os.environ.get("SHARKYCLIPS_SUPERVISED") == "1":
        return _run_server(args)

    from sharkyclips import instance

    # One server per settings folder: a second one would run the publish scheduler and the job
    # queue a second time (the same clip exported / uploaded twice).
    lock = instance.acquire()
    if lock is None:
        port, version = _wait_for_running(instance.running() or {})
        url = f"http://localhost:{port}" if port else None
        console.print(f"SharkyClips {version or ''} is already running".replace("  ", " ")
                      + (f": [cyan]{url}[/]" if url else " (starting up)."))
        if url and version:
            _restart_if_outdated(port, version)
        if url and not args.no_browser:
            import webbrowser

            webbrowser.open(url)
        return 0
    try:
        instance.note(args.port)
        return _serve_locked(args, RESTART_CODE)
    finally:
        instance.release(lock)


def _serve_locked(args, RESTART_CODE: int) -> int:  # noqa: N803 - the updater's constant
    import subprocess

    local_url = f"http://localhost:{args.port}"
    running = _sharkyclips_version_at(args.port)
    if running:
        if _restart_if_outdated(args.port, running):
            console.print(f"[green]Restarted the running SharkyClips {running} as {__version__}.[/]")
            running = __version__
        console.print(f"SharkyClips {running} is already running: [cyan]{local_url}[/]")
        if not args.no_browser:
            import webbrowser

            webbrowser.open(local_url)
        return 0
    if not _port_free(args.port):
        raise SharkyClipsError(f"Port {args.port} is used by another program.",
                               f"Pick another one, e.g. python cli.py serve --port {args.port + 1} "
                               "(or use `python cli.py launch`, which finds a free port).")
    _ensure_frontend()

    lan_url = ""
    console.print(f"[bold]SharkyClips {__version__}[/] web UI: [cyan]{local_url}[/]")
    if args.lan:
        ip = _lan_ip()
        if ip:
            lan_url = f"http://{ip}:{args.port}"
            console.print(f"On your phone / other computers (same Wi-Fi): [cyan]{lan_url}[/]")
            from sharkyclips import lanauth

            if lanauth.enabled():
                console.print("[dim]Other devices log in with your access PIN. Windows may ask to allow "
                              "Python through the firewall: allow it for private networks.[/]")
            else:
                console.print("[yellow]No access PIN set: anyone on this network can use SharkyClips.[/] "
                              "Set one in Settings > Network access, or run [bold]python cli.py lan-pin[/].")
                console.print("[dim]Windows may ask to allow Python through the firewall: allow it for "
                              "private networks.[/]")
        else:
            console.print("[yellow]Couldn't find this computer's network address.[/]")
    use_tray = bool(getattr(args, "tray", False))
    if use_tray:
        from sharkyclips import tray

        use_tray = tray.available()
    if not use_tray:
        console.print(f"[dim]{_launch_text('stop')}[/]")
    if not args.no_browser:
        _open_splash_or_wait(local_url, args.port)

    # The server runs in a child process so an update can restart it (exit code RESTART_CODE).
    env = {**os.environ, "SHARKYCLIPS_SUPERVISED": "1", "SHARKYCLIPS_LAN_URL": lan_url}
    cmd = [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(args.port), "--no-browser"]
    if args.lan:
        cmd.append("--lan")
    from sharkyclips import procs

    # Windows: the server and everything below it live in a kill-on-close job held by this
    # process, so closing the window (or a crash) never leaves a server, ffmpeg or OCR worker
    # behind. (This process stays outside: the browser it opens must survive SharkyClips.)
    # macOS/Linux: the server gets its own process group, which is killed when it ends.
    guard = procs.Job(kill_on_close=True)
    posix = os.name != "nt"
    state: dict = {"proc": None, "quit": False}

    def supervise() -> int:
        while True:
            # pythonw parent: the server child gets a hidden console, never a window
            if guard.ok:  # start suspended so even its first child is inside the job
                proc = subprocess.Popen(cmd, env=env, **procs.no_window(0x4))  # CREATE_SUSPENDED
                guard.assign(proc.pid)
                procs.resume_pid(proc.pid)
            else:
                proc = subprocess.Popen(cmd, env=env, start_new_session=posix, **procs.no_window())
            state["proc"] = proc
            try:
                rc = proc.wait()
            except KeyboardInterrupt:  # Ctrl+C reaches the child too; give it time to stop cleanly
                if posix:
                    _signal_group(proc.pid, "SIGINT")
                try:
                    proc.wait(timeout=10)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    proc.kill()
                if posix:
                    _signal_group(proc.pid, "SIGKILL")
                console.print("SharkyClips stopped.")
                return 0
            if posix:
                _signal_group(proc.pid, "SIGKILL")  # leftovers of a crashed server
            if state["quit"]:
                console.print("SharkyClips stopped.")
                return 0
            if rc != RESTART_CODE:
                return rc
            console.print("[green]SharkyClips was updated.[/] Restarting ...")
            for _ in range(50):  # wait until the old server has released the port
                if _port_free(args.port):
                    break
                time.sleep(0.2)

    if not use_tray:
        return supervise()

    import threading

    from sharkyclips import tray

    stopped = threading.Event()
    result = {"rc": 0}

    def run_supervisor() -> None:
        try:
            result["rc"] = supervise()
        finally:
            stopped.set()

    def quit_all() -> None:
        state["quit"] = True
        _quit_server(args.port, state["proc"])

    threading.Thread(target=run_supervisor, name="sharkyclips-supervisor", daemon=True).start()
    tray.run(local_url, quit_all, stopped)  # blocks until Quit (or the server is gone)
    stopped.wait(15)
    return result["rc"]


def _quit_server(port: int, proc) -> None:
    """Tray "Quit": let the server unload its models and stop; kill it if it doesn't."""
    import subprocess
    import urllib.request

    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/quit", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json", "X-SharkyClips": "quit"})
        urllib.request.urlopen(req, timeout=10).close()
    except Exception:  # noqa: BLE001
        pass
    if proc is None:
        return
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()  # the job object takes its children with it


_LAUNCH_TEXT = {
    "tr": {"running": "SharkyClips çalışıyor: {url}",
           "already": "SharkyClips zaten açık, tarayıcıda açılıyor: {url}",
           "stop": "Bu pencere açık kaldığı sürece SharkyClips çalışır. Kapatmak için pencereyi kapatın "
                   "(veya Ctrl+C)."},
    "en": {"running": "SharkyClips is running: {url}",
           "already": "SharkyClips is already running, opening it in your browser: {url}",
           "stop": "SharkyClips runs while this window is open. Close the window (or press Ctrl+C) to stop it."},
}


def _launch_text(key: str, **kw) -> str:
    lang = str(config.get("ui_language") or "en")
    return _LAUNCH_TEXT.get(lang, _LAUNCH_TEXT["en"])[key].format(**kw)


def _migrate_windows_shortcuts() -> None:
    """Old installs: the SharkyClips shortcuts ran SharkyClips.bat (a console window that had to
    stay open). Point them at pythonw (no window, tray icon) - once."""
    if os.name != "nt" or config.get("launcher_version") == 2:
        return
    import subprocess

    from sharkyclips import procs

    root = Path(__file__).resolve().parents[1]
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        return
    script = (
        "$sh = New-Object -ComObject WScript.Shell; "
        "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { "
        "$p = Join-Path $d 'SharkyClips.lnk'; if (-not (Test-Path $p)) { continue }; "
        "$s = $sh.CreateShortcut($p); if ($s.TargetPath -notlike '*SharkyClips.bat') { continue }; "
        f"$s.TargetPath = '{pythonw}'; $s.Arguments = '\"{root / 'backend' / 'cli.py'}\" launch --tray'; "
        f"$s.WorkingDirectory = '{root}'; $s.WindowStyle = 1; $s.Save() }}"
    )
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=30, **procs.no_window())
        config.update(launcher_version=2)
    except (OSError, subprocess.SubprocessError):
        pass


def cmd_launch(args) -> int:
    """What the desktop shortcut runs: reuse a running SharkyClips, else start one on a free port."""
    import webbrowser

    _migrate_windows_shortcuts()

    from sharkyclips import instance

    info = instance.running()
    if info is not None:  # it holds the lock: open it, even while it restarts after an update
        port, version = _wait_for_running(info)
        if port and version:
            _restart_if_outdated(port, version)
            url = f"http://localhost:{port}"
            console.print(_launch_text("already", url=url))
            webbrowser.open(url)
        return 0
    for port in range(8000, 8011):  # a running SharkyClips older than 1.2.11 holds no lock
        running = _sharkyclips_version_at(port, timeout=0.5)
        if running:
            _restart_if_outdated(port, running)  # an update happened while it ran
            url = f"http://localhost:{port}"
            console.print(_launch_text("already", url=url))
            webbrowser.open(url)
            return 0
    port = next((p for p in range(8000, 8100) if _port_free(p)), None)
    if port is None:
        raise SharkyClipsError("No free network port between 8000 and 8099.")
    console.print(f"[bold]{_launch_text('running', url=f'http://localhost:{port}')}[/]")
    args.port, args.lan, args.no_browser = port, False, False
    args.tray = getattr(args, "tray", False) or sys.stdin is None or not sys.stdout.isatty()
    return cmd_serve(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sharkyclips",
                                description=f"SharkyClips {__version__} - local stream & video highlight clipper")
    p.add_argument("--version", action="version", version=f"SharkyClips {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check dependencies, GPU and run a real smoke test")
    d.add_argument("--no-fix", action="store_true", help="don't install/upgrade anything")
    d.add_argument("--download-models", action="store_true",
                   help="also download the Whisper model now (else on the first transcription)")
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
    s.add_argument("--tray", action="store_true", help="show a tray icon (Open / mode / Quit)")
    s.set_defaults(func=cmd_serve)

    lp = sub.add_parser("lan-pin", help="set the access PIN other devices need in --lan mode")
    lp.add_argument("--clear", action="store_true", help="remove the PIN")
    lp.set_defaults(func=cmd_lan_pin)

    la = sub.add_parser("launch", help="open SharkyClips (what the desktop shortcut runs): reuses a running "
                                       "server or starts one on a free port")
    la.add_argument("--tray", action="store_true", help="show a tray icon (automatic without a console)")
    la.set_defaults(func=cmd_launch)

    sub.add_parser("list", help="list projects").set_defaults(func=cmd_list)
    sub.add_parser("languages", help="show supported languages").set_defaults(func=cmd_languages)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from sharkyclips import migrate

    done = migrate.run_all()  # ClipForge -> SharkyClips (settings folder, shortcuts); once
    if done.get("home"):
        console.print(f"[dim]Settings moved to {done['home'].get('to')}[/]")
    try:
        return args.func(args)
    except SharkyClipsError as exc:
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
