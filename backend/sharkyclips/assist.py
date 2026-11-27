"""Assisted upload (1.2.70): SharkyClips fills in the TikTok / Instagram upload page in the user's
own browser, the user checks it and clicks Post. The app never clicks Post / Share itself.

How the page gets filled (decided in docs/assisted-upload.md, "Decisions"):

  browser    the user's real installed browser (Chrome, Edge, Opera GX, Opera, Brave; their default
             one unless they pick another in Settings), started as a PLAIN program (procs.launch_app)
             on a dedicated SharkyClips profile: <settings>/browser/assist-<browser> (Chrome reuses the
             1.2.43 TikTok profile, so an earlier TikTok login is kept). No remote debugging port,
             no --enable-automation, nothing attached: navigator.webdriver stays false. (Measured on
             Chrome / Edge 158: --remote-debugging-port alone turns navigator.webdriver on, and the
             flag that hides it shows an "unsupported command-line flag" bar, so the debugging port
             is not used at all.)
  extension  a small companion extension, "SharkyClips Helper" (assist_ext/), written to
             <settings>/browser/assist-extension with this install's own token. Its content scripts
             fill the upload page (file, caption, visibility, "post now"), show a banner in the tab
             and report every step to the local SharkyClips server (web/assist_api.py). Edge, Opera
             and Brave load it by themselves (--load-extension); Google Chrome ignores that switch
             since Chrome 137, so the first time SharkyClips shows a 4-step guide (Developer mode >
             Load unpacked > this folder). Chrome keeps it in the profile after that.
  firefox    Firefox only runs signed extensions: the page opens there, and the clip goes the
             by-hand way (copy buttons, file, folder) with a clear note, unless the SharkyClips
             Helper from Firefox Add-ons is in that profile (1.2.74): then Firefox fills too.
  stores     1.2.74: the same extension can be installed from Microsoft Edge Add-ons / Firefox
             Add-ons (installer/build_extension.py makes the packages). A store copy has no
             config.js with this install's key, so it pairs once: Settings shows a 6-digit code
             (pair_code, 10 minutes, 5 tries), the Helper's popup sends it to
             /api/assist/ext/pair (only from an extension origin) and keeps the key it gets back.
  login      never automated: the user logs in once in that window (the extension only says "Log
             in here once"); a CAPTCHA / verification pauses everything ("Please complete this in
             the browser") until the page is clear again. SharkyClips never solves or skips them.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import config, procs
from .errors import SharkyClipsError

EXT_NAME = "SharkyClips Helper"
EXT_FILES = ("bg.js", "common.js", "tiktok.js", "instagram.js", "popup.html", "popup.js", "popup.css")
EXT_ICON_SIZES = (16, 32, 48, 128)
GECKO_ID = "sharkyclips-helper@utkualsir.github.io"  # Firefox Add-ons id (fixed forever once listed)
PAIR_TTL = 600  # seconds a pairing code works
PAIR_TRIES = 5  # wrong codes before it stops working
PORTS = tuple(range(8000, 8011))  # the server's port range (web server: 8000-8010)
PAUSE_DEFAULT = 60  # seconds between two assisted posts on one platform (a batch): no spam pattern
PAUSE_MIN, PAUSE_MAX = 20, 600

# key -> name, kind, how the extension gets in, Windows ProgIds of "default browser", exe paths
BROWSERS: dict[str, dict] = {
    "chrome": {"name": "Google Chrome", "kind": "chromium", "autoload": False, "progids": ("ChromeHTML",),
               "exe": "chrome.exe", "ext_page": "chrome://extensions",
               "win": (("PROGRAMFILES", "Google/Chrome/Application"), ("PROGRAMFILES(X86)", "Google/Chrome/Application"),
                       ("LOCALAPPDATA", "Google/Chrome/Application")),
               "mac": "Google Chrome", "linux": ("google-chrome-stable", "google-chrome")},
    "edge": {"name": "Microsoft Edge", "kind": "chromium", "autoload": True, "progids": ("MSEdgeHTM",),
             "exe": "msedge.exe", "ext_page": "edge://extensions",
             "win": (("PROGRAMFILES(X86)", "Microsoft/Edge/Application"), ("PROGRAMFILES", "Microsoft/Edge/Application"),
                     ("LOCALAPPDATA", "Microsoft/Edge/Application")),
             "mac": "Microsoft Edge", "linux": ("microsoft-edge-stable", "microsoft-edge")},
    "operagx": {"name": "Opera GX", "kind": "chromium", "autoload": True, "progids": ("OperaGXStable",),
                "exe": "opera.exe", "ext_page": "opera://extensions",
                "win": (("LOCALAPPDATA", "Programs/Opera GX"), ("PROGRAMFILES", "Opera GX")),
                "mac": "Opera GX", "linux": ()},
    "opera": {"name": "Opera", "kind": "chromium", "autoload": True, "progids": ("OperaStable",),
              "exe": "opera.exe", "ext_page": "opera://extensions",
              "win": (("LOCALAPPDATA", "Programs/Opera"), ("PROGRAMFILES", "Opera")),
              "mac": "Opera", "linux": ("opera",)},
    "brave": {"name": "Brave", "kind": "chromium", "autoload": True, "progids": ("BraveHTML",),
              "exe": "brave.exe", "ext_page": "brave://extensions",
              "win": (("PROGRAMFILES", "BraveSoftware/Brave-Browser/Application"),
                      ("LOCALAPPDATA", "BraveSoftware/Brave-Browser/Application")),
              "mac": "Brave Browser", "linux": ("brave-browser", "brave")},
    "firefox": {"name": "Firefox", "kind": "firefox", "autoload": False, "progids": ("FirefoxURL", "FirefoxHTML"),
                "exe": "firefox.exe", "ext_page": None,
                "win": (("PROGRAMFILES", "Mozilla Firefox"), ("PROGRAMFILES(X86)", "Mozilla Firefox")),
                "mac": "Firefox", "linux": ("firefox",)},
}
ORDER = ("chrome", "edge", "operagx", "opera", "brave", "firefox")

_lock = threading.RLock()


# ===================================================================== places


def root() -> Path:
    return config.config_dir() / "browser"


def ext_dir() -> Path:
    return root() / "assist-extension"


def _state_path() -> Path:
    return root() / "assist.json"


def load_state() -> dict:
    try:
        d = json.loads(_state_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(**changes) -> dict:
    from .project import write_json_atomic

    with _lock:
        d = {**load_state(), **changes}
        root().mkdir(parents=True, exist_ok=True)
        write_json_atomic(_state_path(), d)
        return d


def profile_dir(key: str) -> Path:
    """The SharkyClips profile of one browser (cookies of one browser can't be read by another).
    Chrome: the 1.2.43 TikTok profile (logged in by a plain Chrome, so the login is kept)."""
    if key == "chrome":
        from . import tiktok_browser as TB

        return TB.profile_dir()
    return root() / f"assist-{key}"


# ===================================================================== the token


def token() -> str:
    """The extension's own key (not the UI's API token): it only opens /api/assist/ext/*."""
    path = root() / "assist_token"
    with _lock:
        try:
            tok = path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            tok = ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", tok):
            tok = secrets.token_urlsafe(32)
            try:
                root().mkdir(parents=True, exist_ok=True)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="ascii") as f:
                    f.write(tok)
            except OSError:
                pass
        return tok


def token_ok(value: str | None) -> bool:
    import hmac

    return bool(value) and hmac.compare_digest(str(value).encode(), token().encode())


# ===================================================================== browsers


def _exe_candidates(key: str) -> list[str]:
    b = BROWSERS[key]
    out: list[str] = []
    if sys.platform == "win32":
        try:
            import winreg

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{b['exe']}") as k:
                        val = str(winreg.QueryValue(k, None))
                        if key not in ("opera", "operagx") or ("gx" in val.lower()) == (key == "operagx"):
                            out.append(val)
                except OSError:
                    pass
        except ImportError:
            pass
        for env, sub in b["win"]:
            base = os.environ.get(env)
            if base:
                out.append(str(Path(base) / sub / b["exe"]))
    elif sys.platform == "darwin":
        for base in ("/Applications", str(Path.home() / "Applications")):
            out.append(f"{base}/{b['mac']}.app/Contents/MacOS/{b['mac']}")
    else:
        for name in b["linux"]:
            w = shutil.which(name)
            if w:
                out.append(w)
    return out


_found: dict = {"at": 0.0, "val": None}


def installed() -> dict[str, str]:
    """{key: executable} of the supported browsers on this PC (looked up at most every 30 s).
    SHARKYCLIPS_ASSIST_BROWSER (tests: 'key=path') replaces the search."""
    import time

    raw = os.environ.get("SHARKYCLIPS_ASSIST_BROWSER")
    if raw and "=" in raw:
        k, path = raw.split("=", 1)
        return {k.strip(): path.strip()} if k.strip() in BROWSERS else {}
    if _found["val"] is not None and time.time() - _found["at"] < 30:
        return dict(_found["val"])
    found: dict[str, str] = {}
    for key in ORDER:
        for c in _exe_candidates(key):
            c = c.strip().strip('"')
            if c and Path(c).is_file():
                found[key] = c
                break
    _found.update(at=time.time(), val=dict(found))
    return found


def default_browser() -> str | None:
    """The user's default browser (Windows: the https handler they picked), if it is one we know."""
    if os.environ.get("SHARKYCLIPS_ASSIST_BROWSER"):
        return os.environ["SHARKYCLIPS_ASSIST_BROWSER"].split("=", 1)[0].strip() or None
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as k:
            prog = str(winreg.QueryValueEx(k, "ProgId")[0])
    except (OSError, ImportError):
        return None
    for key in ORDER:
        if any(prog == p or prog.startswith(p + "-") or prog.startswith(p) for p in BROWSERS[key]["progids"]):
            return key
    return None


def chosen() -> str:
    v = str(config.get("assist_browser") or "auto")
    return v if v in BROWSERS or v == "auto" else "auto"


def pick() -> tuple[str, str] | None:
    """(key, exe) of the browser to use: the one picked in Settings, else the default browser, else
    the first supported one installed (Chromium-based first: those can be filled in)."""
    inst = installed()
    if not inst:
        return None
    want = chosen()
    if want != "auto" and want in inst:
        return want, inst[want]
    d = default_browser()
    if d in inst:
        return d, inst[d]
    for key in ORDER:
        if key in inst and BROWSERS[key]["kind"] == "chromium":
            return key, inst[key]
    key = next(iter(inst))
    return key, inst[key]


def can_fill(key: str | None) -> bool:
    """Chromium browsers get the Helper from SharkyClips; Firefox only once the store add-on spoke to
    this SharkyClips from there (it was installed into the SharkyClips Firefox profile and paired)."""
    kind = BROWSERS.get(key or "", {}).get("kind")
    return bool(key) and (kind == "chromium" or (kind == "firefox" and seen("firefox") > 0))


def pause_s() -> int:
    try:
        n = int(config.get("assist_pause_s") or PAUSE_DEFAULT)
    except (TypeError, ValueError):
        n = PAUSE_DEFAULT
    return max(PAUSE_MIN, min(PAUSE_MAX, n))


def browsers_view() -> dict:
    inst = installed()
    p = pick()
    return {"installed": [{"key": k, "name": BROWSERS[k]["name"], "fills": can_fill(k),
                           "autoload": bool(BROWSERS[k]["autoload"])} for k in ORDER if k in inst],
            "default": default_browser(), "chosen": chosen(), "using": p[0] if p else None,
            "using_name": BROWSERS[p[0]]["name"] if p else None, "fills": can_fill(p[0]) if p else False}


# ===================================================================== the extension


def _template() -> Path:
    return Path(__file__).with_name("assist_ext")


def _ext_version(version: str) -> str:
    return ".".join(str(int(x)) for x in re.findall(r"\d+", version)[:4]) or "1.0.0"


def store_manifest(version: str, target: str) -> dict:
    """The manifest of a store package (installer/build_extension.py): target "edge" | "firefox".
    Same scripts as the copy SharkyClips writes itself, plus localized name/description, icons and
    the pairing popup; no test origins, no config.js (a store copy pairs with a code)."""
    m = {"manifest_version": 3, "name": "__MSG_name__", "short_name": "SharkyClips",
         "version": _ext_version(version), "description": "__MSG_description__", "default_locale": "en",
         "homepage_url": "https://utkualsir.github.io/sharkyclips-site/",
         "icons": {str(n): f"icons/icon-{n}.png" for n in EXT_ICON_SIZES},
         "action": {"default_title": "__MSG_name__", "default_popup": "popup.html",
                    "default_icon": {str(n): f"icons/icon-{n}.png" for n in EXT_ICON_SIZES}},
         "permissions": ["storage"],
         "host_permissions": ["http://127.0.0.1/*", "http://localhost/*"],
         "content_scripts": [
             {"matches": ["https://www.tiktok.com/*"], "js": ["common.js", "tiktok.js"], "run_at": "document_idle"},
             {"matches": ["https://www.instagram.com/*"], "js": ["common.js", "instagram.js"], "run_at": "document_idle"},
         ]}
    if target == "firefox":
        m["background"] = {"scripts": ["bg.js"]}
        m["browser_specific_settings"] = {"gecko": {"id": GECKO_ID, "strict_min_version": "142.0",
                                                    "data_collection_permissions": {"required": ["none"]}}}
    else:
        m["background"] = {"service_worker": "bg.js"}
        m["minimum_chrome_version"] = "116"
    return m


def manifest(version: str) -> dict:
    tt = ["https://www.tiktok.com/*"]
    ig = ["https://www.instagram.com/*"]
    extra = os.environ.get("SHARKYCLIPS_ASSIST_TEST_MATCHES")  # tests: the fake pages' origin
    if extra:  # any port on that host (the fake TikTok Studio and Instagram run on two ports)
        from urllib.parse import urlparse

        u = urlparse(extra)
        base = f"{u.scheme}://{u.hostname}"
        tt.append(f"{base}/tiktokstudio/*")
        tt.append(f"{base}/login*")
        ig.append(f"{base}/fakeig/*")
    v = _ext_version(version)
    return {"manifest_version": 3, "name": EXT_NAME, "version": v,
            "default_locale": "en",  # required once _locales/ is there: without it Chromium refuses the extension
            "description": "Fills in your TikTok / Instagram upload for SharkyClips. You check it and click Post yourself.",
            "background": {"service_worker": "bg.js"},
            "icons": {str(n): f"icons/icon-{n}.png" for n in EXT_ICON_SIZES},
            "action": {"default_title": EXT_NAME, "default_popup": "popup.html"},
            "permissions": ["storage"],
            "host_permissions": ["http://127.0.0.1/*", "http://localhost/*"],
            "content_scripts": [
                {"matches": tt, "js": ["common.js", "tiktok.js"], "run_at": "document_idle"},
                {"matches": ig, "js": ["common.js", "instagram.js"], "run_at": "document_idle"},
            ]}


def write_extension(base_url: str | None = None) -> Path:
    """Writes the extension (only the files that changed: a running browser keeps working)."""
    from . import __version__

    dest = ext_dir()
    dest.mkdir(parents=True, exist_ok=True)
    files = {name: (_template() / name).read_text(encoding="utf-8") for name in EXT_FILES}
    files["manifest.json"] = json.dumps(manifest(__version__), indent=2)
    conf = {"token": token(), "base": base_url or load_state().get("base"), "ports": list(PORTS),
            "version": __version__}
    files["config.js"] = "self.SC = " + json.dumps(conf) + ";\n"
    for name, text in files.items():
        f = dest / name
        try:
            if f.is_file() and f.read_text(encoding="utf-8") == text:
                continue
        except OSError:
            pass
        f.write_text(text, encoding="utf-8")
    write_icons(dest / "icons")
    loc = _template() / "_locales"
    for d in loc.iterdir() if loc.is_dir() else ():
        f = dest / "_locales" / d.name / "messages.json"
        text = (d / "messages.json").read_text(encoding="utf-8")
        if not (f.is_file() and f.read_text(encoding="utf-8") == text):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
    return dest


def write_icons(folder: Path) -> None:
    """The extension's icons (the app's logo, assets/icon/sharkyclips.png scaled), once."""
    src = config.REPO_ROOT / "assets" / "icon" / "sharkyclips.png"
    folder.mkdir(parents=True, exist_ok=True)
    if all((folder / f"icon-{n}.png").is_file() for n in EXT_ICON_SIZES):
        return
    try:
        from PIL import Image

        with Image.open(src) as im:
            im = im.convert("RGBA")
            for n in EXT_ICON_SIZES:
                im.resize((n, n), Image.Resampling.LANCZOS).save(folder / f"icon-{n}.png")
    except (OSError, ImportError):
        pass  # icons are optional: the browser shows a letter instead


# ===================================================================== pairing (store copies)

_pair: dict = {}


def pair_code(now: float | None = None) -> dict:
    """A fresh 6-digit code for a store-installed Helper (shown in Settings; replaces the old one)."""
    import time

    now = time.time() if now is None else now
    with _lock:
        code = f"{secrets.randbelow(10 ** 6):06d}"
        _pair.clear()
        _pair.update(code=code, until=now + PAIR_TTL, tries=0)
        return {"code": code, "expires_in": PAIR_TTL}


def pair(code: str | None, now: float | None = None) -> str | None:
    """The Helper's key for a right, fresh code (once); None otherwise. 5 wrong tries end the code."""
    import hmac
    import time

    now = time.time() if now is None else now
    want = str(code or "").strip().replace(" ", "")
    with _lock:
        if not _pair or now > _pair["until"] or _pair["tries"] >= PAIR_TRIES:
            _pair.clear()
            return None
        if not (re.fullmatch(r"\d{6}", want) and hmac.compare_digest(want.encode(), _pair["code"].encode())):
            _pair["tries"] += 1
            return None
        _pair.clear()
    return token()


def note_base(url: str) -> None:
    """The server's own address (the extension tries it first, then 8000-8010)."""
    if url and load_state().get("base") != url:
        save_state(base=url)


# ===================================================================== opening pages


def command(key: str, exe: str, url: str) -> list[str]:
    raw = os.environ.get("SHARKYCLIPS_ASSIST_CMD")  # tests: the browser command (JSON list), {url} / {profile} / {ext}
    prof = profile_dir(key)
    if raw:
        return [str(x).replace("{url}", url).replace("{profile}", str(prof)).replace("{ext}", str(ext_dir()))
                for x in json.loads(raw)]
    if BROWSERS[key]["kind"] == "firefox":
        return [exe, "-profile", str(prof), url]
    return [exe, f"--user-data-dir={prof}", f"--load-extension={ext_dir()}", "--no-first-run",
            "--no-default-browser-check", url]


def open_url(url: str, key: str | None = None) -> dict:
    """Opens `url` in the SharkyClips profile of the user's browser: a new window, or a new tab of
    the window already open there. Never anything attached to it."""
    p = pick() if key is None else (key, installed().get(key))
    if not p or not p[1]:
        raise SharkyClipsError("No supported browser was found.",
                               "Install Google Chrome, Microsoft Edge, Opera GX or Brave, then try again.")
    key, exe = p
    prof = profile_dir(key)
    prof.mkdir(parents=True, exist_ok=True)
    if BROWSERS[key]["kind"] == "chromium":
        write_extension()
    cmd = command(key, exe, url)
    try:
        if os.environ.get("SHARKYCLIPS_ASSIST_CMD"):
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             **procs.no_window())
        else:
            procs.launch_app(cmd)
    except OSError as exc:
        raise SharkyClipsError(f"{BROWSERS[key]['name']} couldn't be started.", str(exc)[:200]) from exc
    save_state(last_browser=key)
    return {"browser": key, "name": BROWSERS[key]["name"], "fills": can_fill(key)}


def open_folder(path: Path) -> None:
    from . import easy

    easy.open_folder(path)  # Explorer / Finder, the same hidden-window way as everywhere else


# ===================================================================== extension seen?


def seen(key: str | None = None) -> float:
    """When the extension last spoke to SharkyClips (from this browser, when given)."""
    d = load_state()
    if key:
        return float((d.get("seen") or {}).get(key) or 0)
    return max([float(v or 0) for v in (d.get("seen") or {}).values()] or [0.0])


def note_seen(key: str | None, at: float) -> None:
    d = load_state()
    s = dict(d.get("seen") or {})
    k = key or d.get("last_browser") or "unknown"
    if at - float(s.get(k) or 0) > 20:  # not a disk write on every poll
        s[k] = at
        save_state(seen=s)
