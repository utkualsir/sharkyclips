"""TikTok Studio in a browser (1.2.42): automatic TikTok posts without the TikTok API.

SharkyClips drives TikTok Studio (https://www.tiktok.com/tiktokstudio/upload) in its own browser
profile, the way you would post by hand:

  profile   <settings>/browser/tiktok-profile: a separate Chrome / Edge / Chromium profile just for
            SharkyClips (never your own browser profile). You log in yourself once ("Log in to
            TikTok"); SharkyClips keeps only that browser profile (its cookies), never your password.
  login     (1.2.43) your INSTALLED Google Chrome, started as a plain program on that profile with
            the TikTok login page: no remote debugging, no automation attached, so TikTok sees an
            ordinary Chrome (the 1.2.42 Playwright window got "too many attempts" every time, QR
            included). Once you close that window, SharkyClips opens the profile with the
            automation (off the screen) and checks that TikTok knows you.
  window    always a real (headed) window, moved off the screen while it posts; one browser at a
            time on the profile (a lock), so two TikTok posts never run at once
  pacing    a pause of 1-3 s between steps, typing with real key presses
  limit     at most N automatic posts a day (setting "tiktok_auto_daily", default 3); the daily
            count is kept by multipost, which moves a full day's post to the next day
  stop      a CAPTCHA, a verification, a login wall or a screen it doesn't know: it stops at once
            (never tries to solve anything), takes a screenshot, tells you (tray + Telegram) and
            the clip falls back to the semi-automatic flow (file + caption ready, you post it)

Selectors are TikTok's data-e2e attributes (not texts), so the English and the Turkish UI (and the
others) work the same. Tests run the same steps against a local fake TikTok Studio page
(backend/tests/fake_tiktok_studio.py) with the same data-e2e structure.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import psutil

from . import config, procs
from .errors import SharkyClipsError
from .project import write_json_atomic

MIN_AHEAD = timedelta(minutes=20)  # TikTok plans posts >= 15 min ahead: keep a margin
MAX_AHEAD = timedelta(days=9, hours=20)  # ... and up to ~10 days ahead
DEFAULT_DAILY = 3
BLOCK_COOLDOWN_S = 6 * 3600  # after a CAPTCHA / verification: no automatic posts for a while
UPLOAD_TIMEOUT_S = 15 * 60
LOGIN_TIMEOUT_S = 30 * 60  # waiting for you to close the login window
LOGIN_OPEN_S = 25  # the Chrome window must show up within this
PROFILE_V = 2  # 2 = the profile was first logged in by a plain Chrome (1.2.43), never under automation
LOCK_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile")
CHANNELS = ("chrome", "msedge", "chromium")
NO_AUTOMATION_FLAG = ["--enable-automation"]  # Playwright's default "controlled by automated software" flag
WINDOW = (1280, 900)

SEL = {
    "file": '[data-e2e="select_video_container"] input[type="file"]',
    "file_any": 'input[type="file"][accept*="video"]',
    "select_button": '[data-e2e="select_video_button"]',
    "status": '[data-e2e="upload_status_container"]',
    "caption": '[data-e2e="caption_container"] .public-DraftEditor-content',
    "caption_any": '[data-e2e="caption_container"] [contenteditable="true"]',
    "schedule": '[data-e2e="schedule_container"]',
    "radio_now": 'input[name="postSchedule"][value="post_now"]',
    "radio_schedule": 'input[name="postSchedule"][value="schedule"]',
    "text_input": ".TUXTextInputCore-input",
    "time_item": ".tiktok-timepicker-option-item",
    "visibility": '[data-e2e="video_visibility_container"]',
    "more": '[data-e2e="advanced_settings_container"]',
    "perm": '[data-e2e="user_perm_container"]',
    "disclose": '[data-e2e="disclose_content_container"]',
    "aigc": '[data-e2e="aigc_container"]',
    "post": '[data-e2e="post_video_button"]',
}

UPLOADED = re.compile(r"(yüklendi|uploaded|hochgeladen|feltöltve|feltöltöttük|загружено|已上传|上传成功|تم التحميل|تم الرفع)", re.I)
UPLOAD_FAILED = re.compile(r"(fail|başarısız|hata|error|fehlgeschlagen|sikertelen|ошибк|не удалось|失败|فشل)", re.I)
EVERYONE = re.compile(r"^\s*(herkes|everyone|public|alle|mindenki|все|所有人|公开|الجميع)\s*$", re.I)
SCHEDULED_ROW = re.compile(r"(\(GMT|planlan|zamanlan|scheduled|geplant|ütemez|запланир|已排期|定时|مجدول)", re.I)
COMMENT_WORDS = re.compile(r"(yorum|comment|kommentar|hozzászól|коммент|评论|تعليق)", re.I)

_lock = threading.RLock()  # one browser on the profile at a time: posts, checks, the login window
_login = {"thread": None, "cancel": threading.Event(), "state": "idle", "error": None, "started_at": None,
          "reset": None}
_on_login: list[Callable[[dict], None]] = []


class Blocked(SharkyClipsError):
    """The automation stopped on purpose. reason: captcha | verify | login | unknown | ui_changed |
    upload_failed | no_browser. submitted: the post button was already pressed (never post again:
    look the post up instead)."""

    def __init__(self, reason: str, message: str, hint: str | None = None, shot: str | None = None,
                 submitted: bool = False, step: str | None = None):
        super().__init__(message, hint)
        self.reason, self.shot, self.submitted, self.step = reason, shot, submitted, step
        self.kind, self.code, self.platform = "blocked", reason, "tiktok"


class ScheduleUnavailable(SharkyClipsError):
    """TikTok's own planner couldn't be set (outside its window, or its picker changed): the caller
    keeps the plan itself and posts at the planned time instead."""


# ===================================================================== places + settings


def base_url() -> str:
    return (os.environ.get("SHARKYCLIPS_TT_STUDIO") or "https://www.tiktok.com").rstrip("/")


def upload_url() -> str:
    return base_url() + "/tiktokstudio/upload"


def content_url() -> str:
    return base_url() + "/tiktokstudio/content"


def login_url() -> str:
    return base_url() + "/login"


def root() -> Path:
    return config.config_dir() / "browser"


def profile_dir() -> Path:
    return root() / "tiktok-profile"


def _state_path() -> Path:
    return root() / "tiktok.json"


def _load() -> dict:
    try:
        d = json.loads(_state_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(**changes) -> dict:
    with _lock:
        d = {**_load(), **changes}
        root().mkdir(parents=True, exist_ok=True)
        write_json_atomic(_state_path(), d)
        return d


def daily_cap() -> int:
    try:
        n = int(config.get("tiktok_auto_daily") or DEFAULT_DAILY)
    except (TypeError, ValueError):
        n = DEFAULT_DAILY
    return max(1, min(15, n))


def set_daily_cap(n: int) -> int:
    config.update(tiktok_auto_daily=max(1, min(15, int(n))))
    return daily_cap()


def available() -> tuple[bool, str | None]:
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:  # noqa: BLE001
        return False, "playwright_missing"
    return True, None


def blocked() -> dict | None:
    b = _load().get("blocked")
    if isinstance(b, dict) and time.time() - float(b.get("at") or 0) < BLOCK_COOLDOWN_S:
        return b
    return None


def logged_in() -> bool:
    d = _load()
    return bool(d.get("logged_in")) and profile_dir().is_dir()


def ready() -> bool:
    """Automatic posting can run now: Playwright is there, logged in, not stopped by a CAPTCHA."""
    return available()[0] and logged_in() and blocked() is None


def status() -> dict:
    d = _load()
    ok, why = available()
    b = blocked()
    if not d.get("login_at"):
        pill = "not_connected"
    elif not d.get("logged_in"):
        pill = "signed_out"
    elif b or not ok:
        pill = "attention"
    else:
        pill = "ok"
    return {"available": ok, "missing": why, "logged_in": bool(d.get("logged_in")), "username": d.get("username"),
            "login_at": d.get("login_at"), "checked_at": d.get("checked_at"), "pill": pill, "blocked": b,
            "login": {"state": _login["state"], "error": _login["error"], "started_at": _login["started_at"],
                      "reset": _login["reset"]},
            "daily_cap": daily_cap(), "channel": d.get("channel"), "busy": _is_busy(),
            "profile": profile_dir().is_dir(), "last_error": d.get("last_error")}


def _is_busy() -> bool:
    got = _lock.acquire(blocking=False)
    if got:
        _lock.release()
    return not got


def clear_block() -> dict:
    _save(blocked=None)
    return status()


def note_block(reason: str, message: str, shot: str | None = None) -> None:
    if reason in ("captcha", "verify", "login", "unknown"):
        _save(blocked={"reason": reason, "message": message, "shot": shot, "at": time.time()},
              **({"logged_in": False} if reason == "login" else {}))


def logout() -> dict:
    """Forget the TikTok login: the browser profile is removed (cookies and all)."""
    with _lock:
        _close_profile_browser()
        shutil.rmtree(profile_dir(), ignore_errors=True)
        _save(logged_in=False, username=None, login_at=None, checked_at=time.time(), blocked=None, channel=None)
    return status()


def on_login(fn: Callable[[dict], None]) -> None:
    if fn not in _on_login:
        _on_login.append(fn)


# ===================================================================== pacing


def _range(env: str, default: tuple[float, float]) -> tuple[float, float]:
    raw = os.environ.get(env)
    if raw:
        try:
            a, b = (float(x) for x in raw.split(","))
            return min(a, b), max(a, b)
        except ValueError:
            pass
    return default


def pause(scale: float = 1.0) -> None:
    """A human-like pause between steps: 1-3 s (SHARKYCLIPS_TT_PACE="lo,hi" for tests)."""
    lo, hi = _range("SHARKYCLIPS_TT_PACE", (1.0, 3.0))
    time.sleep(random.uniform(lo, hi) * scale)


def _key_delay() -> float:
    lo, hi = _range("SHARKYCLIPS_TT_TYPE_MS", (35.0, 90.0))
    return random.uniform(lo, hi)


def _scale_timeout(seconds: float) -> float:
    try:
        return seconds * float(os.environ.get("SHARKYCLIPS_TT_TIMEOUT_SCALE") or 1)
    except ValueError:
        return seconds


# ===================================================================== the profile folder


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path.strip().strip('"')))


def _profile_pids() -> list[int]:
    """Browser processes that have the SharkyClips TikTok profile open now (the login window, a
    post): their command line holds --user-data-dir=<profile>."""
    want = _norm(str(profile_dir()))
    out = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            args = proc.info.get("cmdline") or []
        except (psutil.Error, OSError):
            continue
        for a in args:
            if isinstance(a, str) and a.startswith("--user-data-dir=") and _norm(a.split("=", 1)[1]) == want:
                out.append(proc.pid)
                break
    return out


def _close_profile_browser() -> int:
    """Close a browser still running on the profile (Cancel / Log out). Returns how many processes."""
    pids = _profile_pids()
    procs_ = []
    for pid in pids:
        try:
            procs_.append(psutil.Process(pid))
        except psutil.Error:
            pass
    for pr in procs_:
        try:
            pr.terminate()
        except psutil.Error:
            pass
    psutil.wait_procs(procs_, timeout=5)
    return len(procs_)


def _json_ok(path: Path) -> bool:
    """A browser state file is fine when it is missing (not written yet) or valid JSON."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        json.loads(raw)
        return True
    except ValueError:
        return False


def _clear_locks(prof: Path) -> list[str]:
    """Lock files a crashed / killed browser left behind (only called when no browser has the
    profile open: then they are stale and make the next start fail or hand off)."""
    removed = []
    for name in LOCK_FILES:
        f = prof / name
        if f.exists() or f.is_symlink():
            try:
                f.unlink()
                removed.append(name)
            except OSError:
                pass
    return removed


def _writable(prof: Path) -> None:
    probe = prof / ".sharkyclips-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise Blocked("no_browser", "SharkyClips can't write to its TikTok browser folder.",
                      f"{prof}: {exc}") from exc


def prepare_profile(for_login: bool = False) -> dict:
    """Make the profile folder ready for a browser: there and writable, no stale lock files. For
    the login also a fresh start when the folder is corrupted (unreadable Local State /
    Preferences) or was made by the 1.2.42 automated login window and never logged in (TikTok had
    flagged that "device"). Does nothing while a browser has the profile open."""
    prof = profile_dir()
    report: dict = {"reset": None, "removed_locks": [], "in_use": False}
    if _profile_pids():
        report["in_use"] = True
        return report
    d = _load()
    if for_login and prof.exists():
        reason = None
        if not (_json_ok(prof / "Local State") and _json_ok(prof / "Default" / "Preferences")):
            reason = "corrupted"
        elif int(d.get("profile_v") or 1) < PROFILE_V and not d.get("logged_in"):
            reason = "automation"
        if reason:
            shutil.rmtree(prof, ignore_errors=True)
            if prof.exists():
                raise Blocked("no_browser", "SharkyClips couldn't clear its old TikTok browser folder.",
                              f"Close every Chrome window, then try again ({prof}).")
            _save(channel=None, logged_in=False)
            report["reset"] = reason
    prof.mkdir(parents=True, exist_ok=True)
    report["removed_locks"] = _clear_locks(prof)
    _writable(prof)
    return report


def _installed() -> list[tuple[str, str]]:
    """(channel, executable) of the installed Google Chrome, then Microsoft Edge."""
    found: list[tuple[str, str]] = []
    names = {"chrome": ("Google", "Chrome", "chrome.exe"), "msedge": ("Microsoft", "Edge", "msedge.exe")}
    for ch, (vendor, app, exe) in names.items():
        cands: list[str] = []
        if sys.platform == "win32":
            try:
                import winreg

                for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                            cands.append(str(winreg.QueryValue(k, None)))
                    except OSError:
                        pass
            except ImportError:
                pass
            for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
                base = os.environ.get(env)
                if base:
                    cands.append(str(Path(base) / vendor / app / "Application" / exe))
        elif sys.platform == "darwin":
            bundle = "Google Chrome" if ch == "chrome" else "Microsoft Edge"
            for base in ("/Applications", str(Path.home() / "Applications")):
                cands.append(f"{base}/{bundle}.app/Contents/MacOS/{bundle}")
        else:
            for name in (("google-chrome-stable", "google-chrome") if ch == "chrome"
                         else ("microsoft-edge-stable", "microsoft-edge")):
                w = shutil.which(name)
                if w:
                    cands.append(w)
        for c in cands:
            c = c.strip().strip('"')
            if c and Path(c).is_file():
                found.append((ch, c))
                break
    return found


def find_browser() -> tuple[str | None, list[str]] | None:
    """(channel, command) for the plain login window: the installed Google Chrome (Edge when there
    is no Chrome). SHARKYCLIPS_TT_LOGIN_CMD (a JSON list, tests only) replaces it."""
    raw = os.environ.get("SHARKYCLIPS_TT_LOGIN_CMD")
    if raw:
        return None, [str(x) for x in json.loads(raw)]
    want = str(config.get("tiktok_browser") or "auto")
    got = _installed()
    got.sort(key=lambda x: 0 if x[0] == want else 1)
    return (got[0][0], [got[0][1]]) if got else None


# ===================================================================== the browser


def _headless() -> bool:
    return os.environ.get("SHARKYCLIPS_TT_HEADLESS") == "1"  # tests / CI only: posting is always headed


class _Session:
    """One persistent-profile browser (context manager). visible: on screen (the login window);
    else moved off the screen while it works."""

    def __init__(self, visible: bool = False):
        self.visible = visible
        self.pw = None
        self.ctx = None
        self.page = None
        self.channel = None

    def __enter__(self) -> "_Session":
        ok, _ = available()
        if not ok:
            raise Blocked("no_browser", "Automatic TikTok posting needs Playwright.",
                          "Run `python cli.py doctor` (or pip install playwright), then try again.")
        from playwright.sync_api import sync_playwright

        prep = prepare_profile()
        if prep["in_use"]:
            raise Blocked("in_use", "The TikTok login window is still open.",
                          "Close the Chrome window with TikTok, then try again.")
        self.pw = sync_playwright().start()
        w, h = WINDOW
        args = [f"--window-size={w},{h}", "--no-first-run", "--no-default-browser-check"]
        if not self.visible:
            args.append("--window-position=-32000,-32000")  # off the screen (still a real window)
        pinned = _load().get("channel")
        order = [pinned] if pinned else []
        want = os.environ.get("SHARKYCLIPS_TT_CHANNEL") or str(config.get("tiktok_browser") or "auto")
        order += [want] if want in CHANNELS else []
        order += [c for c in CHANNELS if c not in order]
        errors = []
        for ch in order:
            try:
                kw = {"channel": ch} if ch != "chromium" else {}
                self.ctx = self.pw.chromium.launch_persistent_context(
                    str(profile_dir()), headless=_headless(), args=args, no_viewport=True,
                    accept_downloads=False, ignore_default_args=NO_AUTOMATION_FLAG, **kw)
                self.channel = ch
                break
            except Exception as exc:  # noqa: BLE001 - that browser isn't installed: the next one
                errors.append(f"{ch}: {str(exc).splitlines()[0][:120]}")
                if pinned and ch == pinned:
                    continue
        if self.ctx is None:
            self.pw.stop()
            raise Blocked("no_browser", "No browser for TikTok Studio was found.",
                          "Install Google Chrome or Microsoft Edge (or run `playwright install chromium`). "
                          + " / ".join(errors)[:300])
        if not pinned:
            _save(channel=self.channel)  # cookies of one browser can't be read by another
        self.ctx.set_default_timeout(_scale_timeout(30_000))
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self.ctx is not None:
                self.ctx.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.pw is not None:
                self.pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def session_cookie(self) -> bool:
        try:
            for c in self.ctx.cookies(base_url()):
                if c.get("name") in ("sessionid", "sessionid_ss") and c.get("value"):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False


GUARD_JS = r"""() => {
  const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const any = (sel) => Array.from(document.querySelectorAll(sel)).some(vis);
  if (any('#captcha-verify-container, #captcha_container, [id*="captcha" i], [class*="captcha" i], iframe[src*="captcha"], [class*="secsdk" i]')) return 'captcha';
  if (any('[data-e2e="login-modal"], #loginContainer, [data-e2e="login-form"], [class*="login-modal" i]')) return 'login';
  if (any('[class*="verify-bar" i], [class*="verification-code" i], [data-e2e*="verify" i]')) return 'verify';
  return '';
}"""

USERNAME_JS = r"""async () => {
  try { const r = await fetch('/passport/web/account/info/?aid=1459', {credentials: 'include'});
        const j = await r.json(); const d = (j && j.data) || {}; if (d.username) return String(d.username); } catch (e) {}
  const a = document.querySelector('a[data-e2e="nav-profile"], a[href^="/@"]');
  if (a) { const m = (a.getAttribute('href') || '').match(/\/@([^/?#]+)/); if (m) return m[1]; }
  return null;
}"""

UPLOAD_JS = r"""(sel) => {
  const c = document.querySelector(sel.status); const b = document.querySelector(sel.post);
  const dis = b ? (b.disabled || b.getAttribute('aria-disabled') === 'true' || b.getAttribute('data-disabled') === 'true') : true;
  return {text: c ? (c.innerText || '') : '', has: !!c, disabled: dis, button: !!b,
          editor: !!document.querySelector(sel.caption) || !!document.querySelector(sel.caption_any)};
}"""

ROWS_JS = r"""(titles) => {
  const norm = (s) => (s || '').normalize('NFKC').replace(/[\u200b\ufeff]/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim().toLowerCase();
  const leaves = Array.from(document.querySelectorAll('body *')).filter((el) => el.childElementCount === 0 && (el.textContent || '').trim().length >= 6);
  const timeRe = /\d{1,2}:\d{2}/;
  const out = [];
  for (const title of titles) {
    const w = norm(title).slice(0, 32);
    let hit = null;
    if (w.length >= 6) {
      for (const el of leaves) {
        const t = norm(el.textContent);
        if (t.length < 6) continue;
        if (t.startsWith(w) || (t.length >= 16 && w.startsWith(t.slice(0, Math.min(t.length, 32))))) { hit = el; break; }
      }
    }
    if (!hit) { out.push({title, found: false}); continue; }
    let row = hit, href = null;
    for (let k = 0; k < 10 && row.parentElement; k++) {
      row = row.parentElement;
      const a = row.querySelector('a[href*="/video/"]');
      if (a) { href = a.href; break; }
      if (timeRe.test(row.innerText || '') && (row.innerText || '').length > norm(title).length + 4) break;
      if ((row.innerText || '').length > 3000) break;
    }
    if (!href) {  // the link may sit next to the text block: look a few levels up (same row only)
      let up = row;
      for (let k = 0; k < 3 && up.parentElement; k++) {
        up = up.parentElement;
        if ((up.innerText || '').length > (row.innerText || '').length + 80) break;
        const a = up.querySelector('a[href*="/video/"]');
        if (a) { href = a.href; row = up; break; }
      }
    }
    out.push({title, found: true, text: (row.innerText || '').slice(0, 600), href});
  }
  return out;
}"""

TAG_TIME_JS = r"""(sel) => {
  const items = Array.from(document.querySelectorAll(sel));
  const cols = [];
  for (const it of items) { let i = cols.indexOf(it.parentElement); if (i < 0) { cols.push(it.parentElement); i = cols.length - 1; }
    it.setAttribute('data-sc-col', String(i)); it.setAttribute('data-sc-val', (it.textContent || '').trim()); }
  return cols.length;
}"""


def _guard(page) -> str:
    """'' when the page is fine, else captcha | login | verify."""
    try:
        if "/login" in (page.url or ""):
            return "login"
        return page.evaluate(GUARD_JS) or ""
    except Exception:  # noqa: BLE001 - the page is navigating
        return ""


def _shot(page, shots_dir: Path | None, tag: str, reason: str) -> str | None:
    if page is None or shots_dir is None:
        return None
    try:
        shots_dir.mkdir(parents=True, exist_ok=True)
        dest = shots_dir / f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}-{reason}.png"
        page.screenshot(path=str(dest), full_page=False)
        return str(dest)
    except Exception:  # noqa: BLE001
        return None


_WORDS = {
    "captcha": "TikTok asked for a CAPTCHA.",
    "verify": "TikTok asked for a verification.",
    "login": "TikTok logged SharkyClips out.",
    "unknown": "TikTok Studio showed a screen SharkyClips doesn't know.",
    "ui_changed": "TikTok Studio looks different than expected.",
    "upload_failed": "TikTok Studio couldn't upload the video.",
    "error": "The TikTok Studio window ran into a problem.",
}


def _stop(page, shots_dir, tag: str, reason: str, step: str, submitted: bool = False, detail: str = "") -> Blocked:
    shot = _shot(page, shots_dir, tag, reason)
    msg = _WORDS.get(reason, "TikTok Studio stopped the post.") + (f" ({step})" if step else "")
    hint = {"captcha": "SharkyClips never solves CAPTCHAs: the clip is ready for you to post by hand.",
            "verify": "Open TikTok in the SharkyClips window (Settings > Accounts > TikTok) and finish the check.",
            "login": "Settings > Accounts > TikTok > Log in to TikTok.",
            }.get(reason, "The clip is ready for you to post by hand. Detail: " + detail[:160] if detail else
                  "The clip is ready for you to post by hand.")
    return Blocked(reason, msg, hint, shot, submitted, step)


def _check(page, shots_dir, tag: str, step: str, submitted: bool = False) -> None:
    g = _guard(page)
    if g:
        raise _stop(page, shots_dir, tag, g, step, submitted)


def _wait_for(page, selector: str, seconds: float, shots_dir, tag: str, step: str, state: str = "visible"):
    """The element, or a stop: CAPTCHA / login (checked while waiting) or ui_changed (not found)."""
    end = time.time() + _scale_timeout(seconds)
    loc = page.locator(selector).first
    while time.time() < end:
        _check(page, shots_dir, tag, step)
        try:
            loc.wait_for(state=state, timeout=1000)
            return loc
        except Exception:  # noqa: BLE001 - not there yet
            pass
    _check(page, shots_dir, tag, step)
    raise _stop(page, shots_dir, tag, "ui_changed", step, detail=f"missing {selector}")


# ===================================================================== login + check


def _read_username(page) -> str | None:
    try:
        u = page.evaluate(USERNAME_JS)
        return str(u).lstrip("@") if u else None
    except Exception:  # noqa: BLE001
        return None


def login_start() -> dict:
    """Opens your installed Google Chrome (a plain window, nothing attached) on TikTok's login page
    in the SharkyClips profile; you log in yourself (password manager, QR code, ...). When you close
    that window, SharkyClips checks the login."""
    ok, why = available()
    if not ok:
        raise SharkyClipsError("Automatic TikTok posting needs Playwright.",
                               "Run `python cli.py doctor` (or pip install playwright), then try again.")
    t = _login.get("thread")
    if t is not None and t.is_alive():
        return status()
    _login["cancel"] = threading.Event()
    _login.update(state="opening", error=None, started_at=time.time(), reset=None)
    th = threading.Thread(target=_login_run, name="tiktok-login", daemon=True)
    _login["thread"] = th
    th.start()
    return status()


def login_cancel() -> dict:
    _login["cancel"].set()
    return status()


def _probe() -> tuple[str, str | None]:
    """Opens TikTok Studio with the automation (off the screen) on the profile.
    ('ok' | 'login' | captcha / verify, username)."""
    with _Session() as s:
        page = s.page
        page.goto(content_url(), wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=_scale_timeout(15_000))
        except Exception:  # noqa: BLE001
            pass
        g = _guard(page)
        if g == "login" or not s.session_cookie():
            return "login", None
        if g:
            return g, None
        return "ok", _read_username(page)


def _wait_closed(cancel: threading.Event) -> str:
    """Waits until the login window shows up and then until every window on the profile is closed.
    'closed' | 'cancelled' | 'timeout' | 'never_opened'."""
    t0 = time.time()
    seen = False
    while True:
        if cancel.is_set():
            return "cancelled"
        if _profile_pids():
            seen = True
        elif seen:
            return "closed"
        elif time.time() - t0 > _scale_timeout(LOGIN_OPEN_S):
            return "never_opened"
        if time.time() - t0 > LOGIN_TIMEOUT_S:
            return "timeout"
        cancel.wait(1.0)


def _login_run() -> None:
    cancel = _login["cancel"]
    try:
        with _lock:
            prep = prepare_profile(for_login=True)
            _login["reset"] = prep["reset"]
            if not prep["in_use"]:  # a login window from before (e.g. before a restart) is still open: wait for it
                found = find_browser()
                if found is None:
                    raise Blocked("no_browser", "Google Chrome was not found.",
                                  "Install Google Chrome (or Microsoft Edge), then try again.")
                channel, cmd = found
                procs.launch_app([*cmd, f"--user-data-dir={profile_dir()}", "--no-first-run",
                                  "--no-default-browser-check", "--new-window", login_url()])
                _save(profile_v=PROFILE_V, **({"channel": channel} if channel else {}))
            _login["state"] = "waiting"  # "I'll continue once you close the login window"
            how = _wait_closed(cancel)
            if how == "cancelled":
                _close_profile_browser()
                _login["state"] = "cancelled"
                return
            if how == "timeout":
                _login["state"] = "cancelled"
                return
            if how == "never_opened":
                raise Blocked("no_browser", "The Chrome window for the TikTok login didn't open.",
                              "Try again; if it keeps happening, start Google Chrome once by hand.")
            _login["state"] = "checking"
            time.sleep(1.0)  # the browser finishes writing its cookies as it quits
            prepare_profile()  # stale locks if it was closed the hard way
            result, user = _probe()
            if result == "ok":
                d = _save(logged_in=True, username=user or _load().get("username"), login_at=time.time(),
                          checked_at=time.time(), blocked=None, last_error=None, profile_v=PROFILE_V)
                _login["state"] = "done"
                for fn in list(_on_login):
                    try:
                        fn(d)
                    except Exception:  # noqa: BLE001
                        pass
            elif result == "login":
                _save(logged_in=False, checked_at=time.time())
                _login["state"] = "not_logged_in"
            else:
                note_block(result, _WORDS[result])
                _login.update(state="error", error=_WORDS[result])
    except Blocked as exc:
        _login.update(state="error", error=exc.message + (f" {exc.hint}" if exc.hint else ""))
    except Exception as exc:  # noqa: BLE001
        _login.update(state="error", error=f"{type(exc).__name__}: {str(exc)[:200]}")


def check() -> dict:
    """Is the saved login still good? (opens TikTok Studio off the screen, reads the username)"""
    with _lock:
        result, user = _probe()
        if result == "login":
            _save(logged_in=False, checked_at=time.time())
        elif result != "ok":
            note_block(result, _WORDS[result])
        else:
            d = _load()
            _save(logged_in=True, username=user or d.get("username"), checked_at=time.time(), blocked=None,
                  **({} if d.get("login_at") else {"login_at": time.time()}))
    return status()


# ===================================================================== caption


def split_caption(text: str) -> tuple[str, list[str]]:
    """(body, hashtags): lines made only of hashtags become the tag list (typed last); everything
    else (title, description, the AI-voice line, the socials block) stays in the body, in order."""
    body, tags = [], []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        words = line.split()
        if words and all(w.startswith("#") and len(w) > 1 for w in words):
            for w in words:
                if w.lower() not in (t.lower() for t in tags):
                    tags.append(w)
        else:
            body.append(line.rstrip())
    out = "\n".join(body).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out, tags


def _norm_text(s: str) -> str:
    s = (s or "").replace("\u200b", "").replace("\ufeff", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def expected_text(body: str, tags: list[str]) -> str:
    return _norm_text(body + ("\n\n" if body and tags else "") + " ".join(tags))


def _editor_text(ed) -> str:
    try:
        return ed.inner_text()
    except Exception:  # noqa: BLE001
        return ""


def _type_caption(page, ed, body: str, tags: list[str]) -> None:
    mod = "Meta" if sys.platform == "darwin" else "Control"
    ed.click()
    pause(0.3)
    page.keyboard.press(f"{mod}+A")
    page.keyboard.press("Delete")
    pause(0.3)
    lines = body.split("\n") if body else []
    for i, line in enumerate(lines):
        if line:
            page.keyboard.type(line, delay=_key_delay())
        if "#" in line or "@" in line:  # a suggestion list may be open: Enter would pick from it
            page.keyboard.press("Escape")
            page.keyboard.press(f"{mod}+End")
        if i < len(lines) - 1:
            page.keyboard.press("Enter")
    if tags:
        if lines:
            page.keyboard.press("Enter")
            page.keyboard.press("Enter")
        for tag in tags:
            page.keyboard.type(tag, delay=_key_delay())
            page.keyboard.type(" ", delay=_key_delay())
            time.sleep(random.uniform(0.15, 0.5))
        page.keyboard.press("Escape")  # close the hashtag suggestions (never Enter after a hashtag)


def _set_caption(page, shots_dir, tag: str, body: str, tags: list[str]) -> str:
    ed = _wait_for(page, f'{SEL["caption"]}, {SEL["caption_any"]}', 60, shots_dir, tag, "caption")
    want = expected_text(body, tags)
    got = ""
    for _ in range(2):
        _type_caption(page, ed, body, tags)
        pause(0.5)
        got = _norm_text(_editor_text(ed))
        if got == want or got.rstrip() == want.rstrip():
            return got
    raise _stop(page, shots_dir, tag, "ui_changed", "caption",
                detail=f"caption reads {len(got)} chars, expected {len(want)}")


# ===================================================================== settings on the page


def _checked(loc) -> bool | None:
    try:
        return bool(loc.evaluate("""(el) => {
            const t = el.matches('input,[role=switch],[role=checkbox],[aria-checked]') ? el :
                      el.querySelector('input[type=checkbox],[role=switch],[role=checkbox],[aria-checked]');
            if (!t) return null;
            if (t.matches('input')) return t.checked;
            return t.getAttribute('aria-checked') === 'true';
        }"""))
    except Exception:  # noqa: BLE001
        return None


def _toggle_to(page, container_sel: str, want: bool, pick: Callable | None = None) -> bool | None:
    """Sets the switch / checkbox in a container (or the one `pick` chooses) and reads it back."""
    box = page.locator(container_sel).first
    if not box.count():
        return None
    target = pick(box) if pick else box.locator('input[type=checkbox],[role=switch],[role=checkbox]').first
    if target is None or not target.count():
        return None
    for _ in range(2):
        cur = _checked(target)
        if cur is None:
            return None
        if cur == want:
            return cur
        try:
            target.click(timeout=5000)
        except Exception:  # noqa: BLE001 - a hidden input: click what the user sees
            try:
                target.evaluate("(el) => (el.closest('label') || el.parentElement || el).click()")
            except Exception:  # noqa: BLE001
                return None
        pause(0.3)
    return _checked(target)


def _expand_more(page) -> bool:
    if page.locator(SEL["aigc"]).first.is_visible():
        return True
    more = page.locator(SEL["more"]).first
    if not more.count():
        return False
    btn = more.locator("button, [role=button]").first
    try:
        (btn if btn.count() else more).click(timeout=5000)
    except Exception:  # noqa: BLE001
        return False
    try:
        page.locator(SEL["aigc"]).first.wait_for(state="visible", timeout=_scale_timeout(8000))
        return True
    except Exception:  # noqa: BLE001
        return False


def _comment_box(box):
    boxes = box.locator('input[type=checkbox],[role=checkbox],[role=switch]')
    n = boxes.count()
    for i in range(n):
        b = boxes.nth(i)
        try:
            label = b.evaluate("(el) => (el.closest('label') || el.parentElement || el).innerText || ''")
        except Exception:  # noqa: BLE001
            label = ""
        if COMMENT_WORDS.search(label or ""):
            return b
    return boxes.first if n else None


def _set_visibility(page, shots_dir, tag: str) -> str:
    box = _wait_for(page, SEL["visibility"], 20, shots_dir, tag, "visibility")
    opener = box.locator('[role=combobox], button, [class*="select" i]').first

    def current() -> str:
        try:
            if opener.count():
                return _norm_text(opener.inner_text())
        except Exception:  # noqa: BLE001
            pass
        return _norm_text(box.inner_text())

    def everyone(text: str) -> bool:
        return bool(EVERYONE.match(text)) or any(EVERYONE.match(x) for x in re.split(r"[\n·|]", text))

    if everyone(current()):
        return current()
    (opener if opener.count() else box).click()
    pause(0.4)
    opts = page.locator('[role=option], [role=listbox] li, [class*="option" i]')
    pick = None
    for i in range(min(opts.count(), 30)):
        o = opts.nth(i)
        try:
            if o.is_visible() and EVERYONE.match(_norm_text(o.inner_text())):
                pick = o
                break
        except Exception:  # noqa: BLE001
            continue
    if pick is None:
        raise _stop(page, shots_dir, tag, "ui_changed", "visibility", detail="no 'Everyone' option")
    pick.click()
    pause(0.4)
    if not everyone(current()):
        raise _stop(page, shots_dir, tag, "ui_changed", "visibility", detail=f"reads {current()[:40]}")
    return current()


def _radio(page, value: str) -> bool:
    r = page.locator(f'{SEL["schedule"]} input[name="postSchedule"][value="{value}"]').first
    if not r.count():
        r = page.locator(f'input[name="postSchedule"][value="{value}"]').first
    if not r.count():
        return False
    if r.is_checked():
        return True
    for how in ("check", "label", "js"):
        try:
            if how == "check":
                r.check(timeout=3000)
            elif how == "label":
                r.evaluate("(el) => (el.closest('label') || el.parentElement).click()")
            else:
                r.evaluate("(el) => el.click()")
        except Exception:  # noqa: BLE001
            continue
        pause(0.3)
        if r.is_checked():
            return True
    return False


def _inputs(page) -> tuple:
    """(time input, date input) after "Schedule" was picked."""
    time_in = date_in = None
    loc = page.locator(f'{SEL["schedule"]} {SEL["text_input"]}')
    if not loc.count():
        loc = page.locator(SEL["text_input"])
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            v = el.input_value()
        except Exception:  # noqa: BLE001
            continue
        if re.fullmatch(r"\s*\d{1,2}:\d{2}\s*", v or ""):
            time_in = el
        elif re.search(r"\d{4}-\d{2}-\d{2}", v or ""):
            date_in = el
    return time_in, date_in


def _set_time(page, inp, hh: int, mm: int) -> bool:
    want = f"{hh:02d}:{mm:02d}"
    for _ in range(2):
        try:
            inp.click()
            pause(0.3)
            if not page.evaluate(TAG_TIME_JS, SEL["time_item"]):
                break
            page.locator(f'{SEL["time_item"]}[data-sc-col="0"][data-sc-val="{hh:02d}"]').first.click()
            pause(0.3)
            mins = page.locator(f'{SEL["time_item"]}[data-sc-col="1"][data-sc-val="{mm:02d}"]').first
            if not mins.is_visible():
                inp.click()
                pause(0.3)
                page.evaluate(TAG_TIME_JS, SEL["time_item"])
            mins.click()
            pause(0.3)
        except Exception:  # noqa: BLE001
            pass
        try:
            if inp.input_value().strip() == want:
                page.keyboard.press("Escape")
                return True
        except Exception:  # noqa: BLE001
            pass
    try:  # the picker changed: try typing into the box
        inp.fill(want)
        pause(0.2)
        return inp.input_value().strip() == want
    except Exception:  # noqa: BLE001
        return False


def _set_date(page, inp, target) -> bool:
    want = target.strftime("%Y-%m-%d")
    try:
        cur = inp.input_value()
    except Exception:  # noqa: BLE001
        return False
    if want in cur:
        return True
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", cur)
    if not m:
        return False
    months = (target.year - int(m.group(1))) * 12 + target.month - int(m.group(2))
    try:
        inp.click()
        pause(0.4)
        cal = page.locator('[class*="calendar" i]').first
        cal.wait_for(state="visible", timeout=_scale_timeout(5000))
        for _ in range(max(0, months)):
            arrows = cal.locator('[class*="arrow" i]')
            arrows.nth(arrows.count() - 1).click()
            pause(0.3)
        days = cal.locator('[class*="day" i]')
        pick = None
        for i in range(days.count()):
            d = days.nth(i)
            cls = (d.get_attribute("class") or "").lower()
            if d.inner_text().strip() == str(target.day) and "valid" in cls and "invalid" not in cls \
                    and "disabled" not in cls:
                pick = d
                break
        if pick is None:
            page.keyboard.press("Escape")
            return False
        pick.click()
        pause(0.4)
    except Exception:  # noqa: BLE001
        pass
    try:
        if want in inp.input_value():
            return True
        inp.fill(want)  # last try: type it (works when the box isn't read-only)
        pause(0.2)
        return want in inp.input_value()
    except Exception:  # noqa: BLE001
        return False


def round_slot(when: datetime) -> datetime:
    """TikTok's minutes come in 5-minute steps: round up to the next one."""
    local = when.astimezone()  # the browser shows this computer's local time
    extra = (-local.minute) % 5
    out = (local + timedelta(minutes=extra)).replace(second=0, microsecond=0)
    return out


def in_window(when: datetime | None, now: datetime | None = None) -> bool:
    if when is None:
        return False
    now = now or datetime.now(timezone.utc)
    return MIN_AHEAD <= when - now <= MAX_AHEAD


def _set_schedule(page, shots_dir, tag: str, when: datetime) -> datetime:
    _wait_for(page, SEL["schedule"], 20, shots_dir, tag, "schedule")
    if not _radio(page, "schedule"):
        raise ScheduleUnavailable("TikTok's planner didn't open.")
    end = time.time() + _scale_timeout(10)
    time_in = date_in = None
    while time.time() < end:
        time_in, date_in = _inputs(page)
        if time_in is not None and date_in is not None:
            break
        page.wait_for_timeout(300)
    if time_in is None or date_in is None:
        raise ScheduleUnavailable("TikTok's date / time boxes didn't appear.")
    local = round_slot(when)
    if not _set_date(page, date_in, local):
        raise ScheduleUnavailable("TikTok doesn't take this date (outside its planning window?).")
    pause(0.4)
    if not _set_time(page, time_in, local.hour, local.minute):
        raise ScheduleUnavailable("TikTok's time picker didn't take the time.")
    pause(0.4)
    if local.strftime("%Y-%m-%d") not in date_in.input_value():  # the time change can move the day
        raise ScheduleUnavailable("TikTok's date box changed after setting the time.")
    _check(page, shots_dir, tag, "schedule")
    return local


# ===================================================================== posting


def _wait_upload(page, shots_dir, tag: str, on_step) -> str:
    end = time.time() + _scale_timeout(UPLOAD_TIMEOUT_S)
    last = ""
    while time.time() < end:
        _check(page, shots_dir, tag, "upload")
        st = page.evaluate(UPLOAD_JS, SEL)
        text = _norm_text(st.get("text") or "")
        last = text or last
        if text and UPLOAD_FAILED.search(text) and not UPLOADED.search(text):
            raise _stop(page, shots_dir, tag, "upload_failed", "upload", detail=text[:120])
        if st.get("has") and UPLOADED.search(text) and "%" not in text:
            return text
        pct = re.search(r"(\d{1,3})\s*%", text)
        if pct and on_step:
            on_step("uploading", min(0.6, 0.1 + 0.5 * int(pct.group(1)) / 100))
        page.wait_for_timeout(1000)
    raise _stop(page, shots_dir, tag, "upload_failed", "upload", detail=f"timeout ({last[:80]})")


def _find_rows(page, titles: list[str], rounds: int = 4) -> list[dict]:
    """Our posts in TikTok Studio's content list (scrolls a bit for older ones)."""
    found: dict[str, dict] = {}
    for _ in range(rounds):
        try:
            rows = page.evaluate(ROWS_JS, [t for t in titles if t not in found])
        except Exception:  # noqa: BLE001
            rows = []
        for r in rows:
            if r.get("found"):
                r["scheduled"] = bool(SCHEDULED_ROW.search(r.get("text") or ""))
                found[r["title"]] = r
        if len(found) == len(titles):
            break
        try:
            page.mouse.wheel(0, 2500)
            page.evaluate("() => document.querySelectorAll('*').forEach((el) => { if (el.scrollHeight > el.clientHeight + 50 && getComputedStyle(el).overflowY.match(/auto|scroll/)) el.scrollTop += 2500; })")
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(1200)
    return [found.get(t) or {"title": t, "found": False} for t in titles]


def post(file: Path, caption: str, when: datetime | None = None, ai_label: bool = False,
         title: str | None = None, shots_dir: Path | None = None, tag: str = "post",
         on_step: Callable[[str, float], None] | None = None,
         on_submit: Callable[[], None] | None = None) -> dict:
    """Posts one video through TikTok Studio. when: TikTok's own planner (in_window(when) must be
    true), None = post now. -> {"status": "scheduled" | "published", "url", "row", "scheduled_for",
    "username"}. Raises Blocked (stopped: fall back to by hand) or ScheduleUnavailable (planner
    not usable: nothing was posted, the caller posts at the planned time instead)."""
    body, tags = split_caption(caption)
    title = title or (body.split("\n")[0] if body else Path(file).stem)
    step = on_step or (lambda _s, _f: None)
    with _lock:
        with _Session() as s:
            page = s.page
            step("opening", 0.02)
            page.goto(upload_url(), wait_until="domcontentloaded")
            pause()
            _check(page, shots_dir, tag, "open")
            if not s.session_cookie():
                _save(logged_in=False, checked_at=time.time())
                raise _stop(page, shots_dir, tag, "login", "open")
            inp = page.locator(SEL["file"]).first
            try:
                inp.wait_for(state="attached", timeout=_scale_timeout(30_000))
            except Exception:  # noqa: BLE001
                _check(page, shots_dir, tag, "open")
                inp = page.locator(SEL["file_any"]).first
                try:
                    inp.wait_for(state="attached", timeout=_scale_timeout(5000))
                except Exception:  # noqa: BLE001
                    raise _stop(page, shots_dir, tag, "ui_changed", "open", detail="no file input") from None
            step("uploading", 0.08)
            inp.set_input_files(str(file))  # never the native file picker
            pause()
            _wait_upload(page, shots_dir, tag, step)
            step("caption", 0.65)
            pause()
            typed = _set_caption(page, shots_dir, tag, body, tags)
            pause()
            step("settings", 0.75)
            _set_visibility(page, shots_dir, tag)
            pause()
            expanded = _expand_more(page)
            if ai_label and not expanded:
                raise _stop(page, shots_dir, tag, "ui_changed", "ai_label", detail="more settings didn't open")
            if expanded:
                ai = _toggle_to(page, SEL["aigc"], bool(ai_label))
                if (ai is None and ai_label) or (ai is not None and ai != bool(ai_label)):
                    raise _stop(page, shots_dir, tag, "ui_changed", "ai_label", detail="AI switch didn't move")
                pause(0.5)
                _toggle_to(page, SEL["disclose"], False)  # branded content off
                pause(0.5)
                _toggle_to(page, SEL["perm"], True, _comment_box)  # comments on
                pause(0.5)
            scheduled_for = None
            if when is not None:
                step("schedule", 0.82)
                scheduled_for = _set_schedule(page, shots_dir, tag, when)
                pause()
            else:
                _radio(page, "post_now")
            if _norm_text(_editor_text(page.locator(f'{SEL["caption"]}, {SEL["caption_any"]}').first)) != typed:
                raise _stop(page, shots_dir, tag, "ui_changed", "caption", detail="caption changed before posting")
            _check(page, shots_dir, tag, "post")
            btn = page.locator(SEL["post"]).first
            if not btn.count() or not btn.is_enabled():
                raise _stop(page, shots_dir, tag, "ui_changed", "post", detail="post button missing / disabled")
            step("posting", 0.9)
            if on_submit:
                on_submit()  # written down first: a crash after this point never posts twice
            btn.click()
            end = time.time() + _scale_timeout(120)
            while time.time() < end and "/tiktokstudio/content" not in (page.url or ""):
                g = _guard(page)
                if g:
                    raise _stop(page, shots_dir, tag, g, "after post", submitted=True)
                page.wait_for_timeout(1000)
            if "/tiktokstudio/content" not in (page.url or ""):
                raise _stop(page, shots_dir, tag, "unknown", "after post", submitted=True,
                            detail=f"stayed on {page.url[:80]}")
            step("checking", 0.96)
            try:
                page.wait_for_load_state("networkidle", timeout=_scale_timeout(15_000))
            except Exception:  # noqa: BLE001
                pass
            row = None
            for _ in range(3):
                row = _find_rows(page, [title], rounds=2)[0]
                if row.get("found"):
                    break
                page.wait_for_timeout(3000)
                page.reload(wait_until="domcontentloaded")
            user = _read_username(page) or _load().get("username")
            if user and user != _load().get("username"):
                _save(username=user)
    row = row or {"found": False}
    status_ = "scheduled" if when is not None else "published"
    url = row.get("href") if row.get("found") and row.get("href") and not row.get("scheduled") else None
    return {"status": status_, "url": url, "row": (row.get("text") or "")[:300] if row.get("found") else None,
            "confirmed": bool(row.get("found")), "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            "username": user}


def find_posts(titles: list[str]) -> list[dict]:
    """Reads TikTok Studio's content list: per title {found, scheduled, href, text}."""
    with _lock:
        with _Session() as s:
            page = s.page
            page.goto(content_url(), wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=_scale_timeout(15_000))
            except Exception:  # noqa: BLE001
                pass
            g = _guard(page)
            if g or not s.session_cookie():
                reason = g or "login"
                if reason == "login":
                    _save(logged_in=False, checked_at=time.time())
                else:
                    note_block(reason, _WORDS[reason])
                raise Blocked(reason, _WORDS[reason], None)
            page.wait_for_timeout(1500)
            return _find_rows(page, titles, rounds=6)


# ===================================================================== tell the user


NOTE = {
    "en": ("TikTok post stopped", "{why} \"{title}\" is ready for you to post by hand."),
    "tr": ("TikTok paylaşımı durdu", "{why} \"{title}\" elle paylaşmanız için hazır."),
    "de": ("TikTok-Post angehalten", "{why} \"{title}\" liegt bereit zum Posten von Hand."),
    "hu": ("A TikTok-posztolás leállt", "{why} A(z) „{title}” kézi posztolásra kész."),
    "ru": ("Публикация в TikTok остановлена", "{why} «{title}» готово к ручной публикации."),
    "ar": ("توقف النشر على TikTok", "{why} “{title}” جاهز لتنشره بنفسك."),
    "zh": ("TikTok 发布已停止", "{why}“{title}”已准备好，请手动发布。"),
}
WHY = {
    "tr": {"captcha": "TikTok CAPTCHA istedi.", "verify": "TikTok doğrulama istedi.",
           "login": "TikTok oturumu kapandı.", "unknown": "TikTok Studio bilinmeyen bir ekran gösterdi.",
           "ui_changed": "TikTok Studio beklenenden farklı görünüyor.", "upload_failed": "Video yüklenemedi.",
           "no_browser": "Tarayıcı bulunamadı."},
}


def notify(reason: str, title: str, url: str | None = None) -> None:
    """Tray notice (the tray icon shows the server's notices) + Telegram, if a phone is paired."""
    lang = str(config.get("ui_language") or "en")
    head, body = NOTE.get(lang, NOTE["en"])
    why = (WHY.get(lang) or {}).get(reason) or _WORDS.get(reason, "")
    text = body.format(why=why, title=(title or "")[:70])
    try:
        from . import easy

        easy.push_notice("tiktok_stopped", head, text, url)
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import phone

        phone.send_text(f"{head}\n{text}")
    except Exception:  # noqa: BLE001
        pass
