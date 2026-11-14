"""Publish queue for an outside uploader (1.2.40): no platform APIs.

SharkyClips only gets everything ready; Claude in Chrome (or you) does the uploads in the browser:
  1. compress   every approved clip to 9:16 H.264 + AAC under 10 MB (two-pass, bitrate from the
                length, 9.5 MB target, audio 96k; still too big -> 10 % less, then 1080 -> 720)
  2. queue.json in <root>/publish_queue/<YYYY-MM-DD_batch>/ next to the files: title,
                description, tags, hashtags (always the brand tag, if one is set), and per platform
                the planned time (the "timezone" setting; empty = this computer's), status, url,
                note; plus CHROME.md, the uploader's brief
  3. schedule   per platform: posts per day + times, daily caps (YouTube 8, Instagram 10,
                TikTok adjustable, default 10), never sooner than 1 hour from now, a full day
                moves on to the next one
  4. calendar   <root>/takvim.json (the master record) + takvim.md (readable); a file (sha256)
                or clip already "scheduled" on a platform is not queued there again
                (skipped_duplicate); the uploader's status JSON is imported back into it
  5. overdue    a "pending" post whose time has passed without a report shows as overdue: mark
                it by hand, check it with Claude in Chrome (VERIFY brief) or plan it again

1.2.41: the Instagram accounts, the brand hashtag and the time zone are settings (generic
defaults: no account, no brand tag, this computer's time zone), not code.

<root> is ~/SharkyClips (setting "root", env SHARKYCLIPS_QUEUE_HOME for tests and portable use).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Callable

from . import config
from .errors import SharkyClipsError, require_tool
from .project import write_json_atomic

TZ_NAME = "Europe/Budapest"  # the 1.2.40 zone; the zone in use is zone_name() (setting "timezone")
PLATFORMS = ("youtube", "tiktok", "instagram")
NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}
HARD_CAP = {"youtube": 8, "instagram": 10}  # TikTok: the "tiktok_cap" setting (default 10)
STATUSES = ("pending", "scheduled", "published", "failed", "skipped_duplicate")
LIVE = ("scheduled", "published")  # out there, or planned on the platform itself
LIMIT_BYTES = 10_000_000  # "under 10 MB": the decimal MB, the stricter of the two
TARGET_BYTES = 9_500_000
AUDIO_BPS = 96_000
MIN_LEAD = timedelta(hours=1)
MAX_TRIES = 5

DEFAULTS = {
    "root": "",
    "brand_hashtag": "",  # e.g. "#mychannel": first on every post
    "timezone": "",  # IANA name (e.g. "Europe/Berlin"); empty: this computer's time zone
    "tiktok_cap": 10,
    "instagram_account": "auto",  # auto: gaming projects -> instagram_gaming, others -> instagram_default
    "instagram_accounts": [],  # the @names (without @) this user posts to
    "instagram_default": "",
    "instagram_gaming": "",
    "platforms": {
        "youtube": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
        "tiktok": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
        "instagram": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
    },
}

_lock = threading.RLock()
ProgressFn = Callable[[str, float | None], None]


# ===================================================================== time zone


class _EuCentral(tzinfo):
    """CET/CEST by the EU rule (last Sunday of March / October, 01:00 UTC), for systems without
    a time zone database (Windows without the tzdata package)."""

    @staticmethod
    def _last_sunday(year: int, month: int) -> date:
        d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)

    def _dst_local(self, year: int) -> tuple[datetime, datetime]:
        """Summer time on the local clock: from 02:00 (-> 03:00) on the last Sunday of March to
        03:00 (-> 02:00) on the last Sunday of October."""
        return (datetime.combine(self._last_sunday(year, 3), dtime(2, 0)),
                datetime.combine(self._last_sunday(year, 10), dtime(3, 0)))

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=1)
        start, end = self._dst_local(dt.year)
        naive = dt.replace(tzinfo=None)
        if start <= naive < end - timedelta(hours=1):
            return timedelta(hours=2)
        if end - timedelta(hours=1) <= naive < end:  # the hour that happens twice
            return timedelta(hours=1) if dt.fold else timedelta(hours=2)
        return timedelta(hours=1)

    def dst(self, dt):
        return self.utcoffset(dt) - timedelta(hours=1)

    def tzname(self, dt):
        return "CEST" if self.dst(dt) else "CET"

    def fromutc(self, dt):
        naive = dt.replace(tzinfo=None)  # UTC
        start, end = self._dst_local(naive.year)
        start_utc, end_utc = start - timedelta(hours=1), end - timedelta(hours=2)  # both 01:00 UTC
        if start_utc <= naive < end_utc:
            return (naive + timedelta(hours=2)).replace(tzinfo=self)
        local = naive + timedelta(hours=1)
        fold = 1 if end_utc <= naive < end_utc + timedelta(hours=1) else 0
        return local.replace(tzinfo=self, fold=fold)


class _SystemLocal(tzinfo):
    """This computer's own time zone, summer time included (the OS knows the rules even where
    Python has no tz database): the offset of each moment comes from time.localtime."""

    @staticmethod
    def _std() -> timedelta:
        import time as _t

        return timedelta(seconds=-_t.timezone)

    def utcoffset(self, dt):
        import time as _t

        if dt is None:
            return self._std()
        try:
            ts = _t.mktime((*dt.replace(tzinfo=None).timetuple()[:8], -1))
            return timedelta(seconds=_t.localtime(ts).tm_gmtoff)
        except (OverflowError, ValueError, OSError):
            return self._std()

    def dst(self, dt):
        return self.utcoffset(dt) - self._std()

    def tzname(self, dt):
        import time as _t

        return _t.tzname[1 if self.dst(dt) else 0]

    def fromutc(self, dt):
        import time as _t

        naive = dt.replace(tzinfo=None)
        try:
            off = timedelta(seconds=_t.localtime((naive - datetime(1970, 1, 1)).total_seconds()).tm_gmtoff)
        except (OverflowError, ValueError, OSError):
            off = self._std()
        return (naive + off).replace(tzinfo=self)

    def __eq__(self, other):
        return isinstance(other, _SystemLocal)

    def __hash__(self):
        return hash("_SystemLocal")

    def __repr__(self) -> str:
        return "_SystemLocal()"


_CET_FAMILY = {"Europe/Budapest", "Europe/Berlin", "Europe/Vienna", "Europe/Paris", "Europe/Rome",
               "Europe/Madrid", "Europe/Amsterdam", "Europe/Brussels", "Europe/Prague", "Europe/Warsaw",
               "Europe/Stockholm", "Europe/Oslo", "Europe/Copenhagen", "Europe/Zurich", "CET"}


def _system_zone_name() -> str:
    """The IANA name of this computer's zone where the OS says it plainly (the TZ variable,
    /etc/localtime on Linux / macOS), else "" (Windows: "this computer's zone")."""
    env = os.environ.get("TZ", "").strip().lstrip(":")
    if "/" in env:
        return env
    try:
        link = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in link:
            return link.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return ""


def zone_name(s: dict | None = None) -> str:
    """The zone the queue plans in: the "timezone" setting, else this computer's (its IANA name
    where known, else "local")."""
    src = s if s is not None else (config.get("pubqueue") or {})
    name = str((src or {}).get("timezone") or "").strip()
    return name or _system_zone_name() or "local"


def valid_zone(name: str) -> bool:
    if not name or name == "local":
        return True
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name)
        return True
    except Exception:  # noqa: BLE001 - an unknown name, or no tz database
        return name in _CET_FAMILY


def zone(s: dict | None = None) -> tzinfo:
    name = zone_name(s)
    if name != "local":
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name)
        except Exception:  # noqa: BLE001 - no tz database here (or a bad name)
            if name in _CET_FAMILY:
                return _EuCentral()
    return _SystemLocal()


def budapest() -> tzinfo:
    """Europe/Budapest itself (the 1.2.40 zone: tests and the CET fallback check)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(TZ_NAME)
    except Exception:  # noqa: BLE001 - no tz database on this system
        return _EuCentral()


def now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone(zone())


def parse_time(value) -> datetime | None:
    """ISO with an offset, or a wall time "YYYY-MM-DD HH:MM" in the queue's time zone."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s.replace(" ", "T"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone())
    return dt.astimezone(zone())


def iso(dt: datetime) -> str:
    return dt.astimezone(zone()).replace(second=0, microsecond=0).isoformat()


# ===================================================================== settings + paths


def settings() -> dict:
    saved = config.get("pubqueue") or {}
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in saved.items():
        if k == "platforms" and isinstance(v, dict):
            for p in PLATFORMS:
                if isinstance(v.get(p), dict):
                    out["platforms"][p].update(v[p])
        elif k in out:
            out[k] = v
    out["tiktok_cap"] = max(1, min(int(out.get("tiktok_cap") or 10), 50))
    for p in PLATFORMS:
        s = out["platforms"][p]
        s["times"] = clean_times(s.get("times") or [])
        s["per_day"] = max(0, min(int(s.get("per_day") or 0), cap(p, out)))
        s["on"] = bool(s.get("on", True))
    tag = str(out.get("brand_hashtag") or "").strip()
    out["brand_hashtag"] = ("#" + tag.lstrip("#").replace(" ", "")) if tag.lstrip("#") else ""
    out["instagram_accounts"] = clean_accounts(out.get("instagram_accounts"))
    for k in ("instagram_default", "instagram_gaming"):
        out[k] = (clean_accounts([out.get(k)]) or [""])[0]
    if out.get("instagram_account") not in ("auto", *out["instagram_accounts"]):
        out["instagram_account"] = "auto"
    out["timezone"] = str(out.get("timezone") or "").strip()
    out["timezone_in_use"] = zone_name(out)
    return out


def clean_accounts(items) -> list[str]:
    """"@me, other" / ["@me", "other"] -> ["me", "other"] (Instagram names: letters, digits, . and _)."""
    raw = items if isinstance(items, list) else str(items or "").replace(";", ",").replace(" ", ",").split(",")
    out: list[str] = []
    for a in raw:
        a = str(a or "").strip().lstrip("@").strip()
        a = re.sub(r"[^A-Za-z0-9._]", "", a)[:30]
        if a and a.lower() not in [x.lower() for x in out]:
            out.append(a)
    return out


def save_settings(changes: dict) -> dict:
    cur = settings()
    for k, v in (changes or {}).items():
        if k == "platforms" and isinstance(v, dict):
            for p in PLATFORMS:
                if isinstance(v.get(p), dict):
                    if "times" in v[p]:
                        times = clean_times(v[p]["times"])
                        bad = [t for t in (v[p]["times"] if isinstance(v[p]["times"], list) else
                                           str(v[p]["times"]).split(",")) if str(t).strip() and not _hm(str(t))]
                        if bad:
                            raise SharkyClipsError(f"\"{str(bad[0]).strip()}\" isn't a time.", "Write times like 12:00, 18:00, 21:00.")
                        v[p]["times"] = times
                    cur["platforms"][p].update({kk: vv for kk, vv in v[p].items() if kk in ("on", "per_day", "times")})
        elif k == "timezone":
            name = str(v or "").strip()
            if name and not valid_zone(name):
                raise SharkyClipsError(f"\"{name}\" isn't a time zone.", "Use a name like Europe/Berlin, or leave it empty for this computer's.")
            cur[k] = name
        elif k == "instagram_accounts":
            cur[k] = clean_accounts(v)
            for kk in ("instagram_default", "instagram_gaming"):  # a removed account can't stay picked
                if cur.get(kk) and cur[kk] not in cur[k]:
                    cur[kk] = cur[k][0] if cur[k] else ""
        elif k in DEFAULTS and k != "platforms":
            cur[k] = v
    cur.pop("timezone_in_use", None)
    config.update(pubqueue=cur)
    return settings()


def _hm(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", text)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return (h, mi) if 0 <= h < 24 and 0 <= mi < 60 else None


def clean_times(times) -> list[str]:
    items = times if isinstance(times, list) else str(times or "").split(",")
    out = sorted({f"{hm[0]:02d}:{hm[1]:02d}" for t in items if (hm := _hm(str(t)))})
    return out


def cap(platform: str, s: dict | None = None) -> int:
    """The most posts a day: YouTube 8, Instagram 10, TikTok the setting (default 10)."""
    if platform == "tiktok":
        s = s if s is not None else settings()
        return max(1, min(int(s.get("tiktok_cap") or 10), 50))
    return HARD_CAP[platform]


def root() -> Path:
    env = os.environ.get("SHARKYCLIPS_QUEUE_HOME")
    custom = env or (config.get("pubqueue") or {}).get("root")
    return Path(custom).expanduser() if custom else Path.home() / "SharkyClips"


def queue_root() -> Path:
    return root() / "publish_queue"


def calendar_path() -> Path:
    return root() / "takvim.json"


def calendar_md_path() -> Path:
    return root() / "takvim.md"


def instagram_account(mode: str | None, s: dict | None = None) -> str:
    s = s or settings()
    pick = s.get("instagram_account") or "auto"
    if pick != "auto":
        return str(pick)
    accounts = s.get("instagram_accounts") or []
    want = s.get("instagram_gaming") if (mode or "gaming") == "gaming" else s.get("instagram_default")
    # "" = no account set: the uploader posts to whichever Instagram account is signed in
    return str(want or s.get("instagram_default") or (accounts[0] if accounts else ""))


def with_brand(hashtags: list[str], brand: str) -> list[str]:
    out: list[str] = []
    for h in [brand, *hashtags]:
        h = "#" + str(h or "").strip().lstrip("#").replace(" ", "")
        if len(h) > 1 and h.lower() not in [x.lower() for x in out]:
            out.append(h)
    return out


# ===================================================================== scheduler


def slots_for_day(day: date, conf: dict) -> list[datetime]:
    tz = zone()
    times = conf["times"][: max(0, int(conf.get("per_day") or 0))]
    return [datetime.combine(day, dtime(*_hm(t))).replace(tzinfo=tz).astimezone(tz) for t in times]


def next_slot(platform: str, taken: list[datetime], s: dict, now: datetime | None = None,
              max_days: int = 366) -> datetime:
    """The first planned time >= now + 1 h that's free and whose day isn't full."""
    conf = s["platforms"][platform]
    if not conf["times"] or not conf["per_day"]:
        raise SharkyClipsError(f"No posting times set for {NAMES[platform]}.", "Add times in the publish queue settings.")
    now = (now or now_local()).astimezone(zone())
    earliest = now + MIN_LEAD
    limit = min(cap(platform, s), conf["per_day"])
    used: dict[date, int] = {}
    minutes = set()
    for t in taken:
        lt = t.astimezone(zone())
        used[lt.date()] = used.get(lt.date(), 0) + 1
        minutes.add(lt.replace(second=0, microsecond=0))
    day = now.date()
    for _ in range(max_days):
        if used.get(day, 0) < limit:
            for slot in slots_for_day(day, conf):
                if slot >= earliest and slot not in minutes:
                    return slot
        day += timedelta(days=1)
    raise SharkyClipsError(f"No free {NAMES[platform]} time in the next year.")


def check_manual(platform: str, when: datetime, taken: list[datetime], s: dict, now: datetime | None = None) -> None:
    now = (now or now_local()).astimezone(zone())
    if when < now + MIN_LEAD:
        raise SharkyClipsError(f"{NAMES[platform]}: a planned time must be at least 1 hour from now.",
                               "Pick a later time, or leave it empty for the next free slot.")
    day = when.astimezone(zone()).date()
    n = sum(1 for t in taken if t.astimezone(zone()).date() == day)
    if n >= cap(platform, s):
        raise SharkyClipsError(f"{NAMES[platform]} already has {n} posts on {day.isoformat()} (the most a day).",
                               "Pick another day.")


# ===================================================================== compression


def video_kbps(duration: float, target: int = TARGET_BYTES, audio: int = AUDIO_BPS) -> int:
    """Two-pass target for the video stream: the whole file ~= target (3 % for the container)."""
    d = max(float(duration or 0), 0.5)
    kbps = (target * 8 * 0.97 / d - audio) / 1000
    return int(max(120, min(kbps, 8000)))


def _probe(path: Path) -> dict:
    from .audio import probe

    return probe(path)


def compress(src: Path, dest: Path, on_progress: ProgressFn | None = None) -> dict:
    """9:16 H.264 + AAC 96k under LIMIT_BYTES. -> {file, size_mb, bytes, duration_s, width, height, kbps, tries}"""
    from .render import run_ffmpeg

    ffmpeg = require_tool("ffmpeg")
    info = _probe(src)
    duration = float(info.get("duration") or 0)
    if duration <= 0:
        raise SharkyClipsError(f"Couldn't read the length of {src.name}.")
    fps = float(info.get("fps") or 30) or 30
    has_audio = bool(info.get("audio_codec"))
    kbps = video_kbps(duration)
    height = 1920 if kbps >= 900 else 1280
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-pq-"))
    tmp = dest.with_name(dest.stem + ".partial.mp4")
    tries = 0
    big_fails = 0
    try:
        while True:
            tries += 1
            width = height * 9 // 16
            vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                  f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
                  + (",fps=30" if fps > 31 else "") + ",format=yuv420p")
            common = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-i", str(src), "-vf", vf,
                      "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-b:v", f"{kbps}k",
                      "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 2}k",
                      "-passlogfile", str(work / "pass")]
            step = 0.5 / MAX_TRIES

            def prog(lo: float):
                return (lambda secs: on_progress("compressing", min(0.99, lo + step * secs / duration))) if on_progress else None

            base = (tries - 1) / MAX_TRIES
            code, err = run_ffmpeg([*common, "-pass", "1", "-an", "-f", "null", "-progress", "pipe:1", os.devnull],
                                   duration, prog(base), cwd=work)
            if code != 0:
                raise SharkyClipsError(f"Compressing {src.name} failed (pass 1).", err.strip()[-300:] or None)
            audio = ["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000"] \
                if has_audio else ["-map", "0:v:0", "-an"]
            code, err = run_ffmpeg([*common, "-pass", "2", *audio, "-movflags", "+faststart",
                                    "-progress", "pipe:1", str(tmp)], duration, prog(base + step), cwd=work)
            if code != 0:
                raise SharkyClipsError(f"Compressing {src.name} failed.", err.strip()[-300:] or None)
            size = tmp.stat().st_size
            if size < LIMIT_BYTES:
                break
            if tries >= MAX_TRIES:
                raise SharkyClipsError(f"{src.name} stays above 10 MB ({size / 1e6:.1f} MB) even at {kbps} kbps.",
                                       "Shorten the clip, then try again.")
            big_fails += 1
            kbps = max(100, int(kbps * 0.9))
            if big_fails >= 2 and height > 1280:
                height = 1280
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)
    out = _probe(dest)
    size = dest.stat().st_size
    return {"file": str(dest), "bytes": size, "size_mb": round(size / 1e6, 2),
            "duration_s": round(float(out.get("duration") or duration), 2),
            "width": out.get("width"), "height": out.get("height"), "kbps": kbps, "tries": tries,
            "video_codec": out.get("video_codec"), "audio_codec": out.get("audio_codec")}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===================================================================== calendar (takvim)


def load_calendar() -> dict:
    p = calendar_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "timezone": zone_name(), "entries": []}


def save_calendar(data: dict) -> None:
    root().mkdir(parents=True, exist_ok=True)
    data["entries"].sort(key=lambda e: (e.get("scheduled_at") or "", e.get("platform") or ""))
    data["updated_at"] = iso(now_local())
    data["timezone"] = zone_name()
    write_json_atomic(calendar_path(), data)
    calendar_md_path().write_text(calendar_md(data), encoding="utf-8")


MD = {
    "tr": {"title": "Yayın takvimi", "tz": "Saatler: {tz}", "date": "Tarih", "time": "Saat",
           "platform": "Platform", "head": "Başlık", "status": "Durum", "empty": "Henüz planlanan gönderi yok.",
           "local": "bu bilgisayarın saati",
           "st": {"pending": "bekliyor", "scheduled": "planlandı", "published": "yayında", "failed": "başarısız",
                  "skipped_duplicate": "zaten planlı (atlandı)", "overdue": "zamanı geçti, rapor yok"}},
    "en": {"title": "Publishing calendar", "tz": "Times: {tz}", "date": "Date", "time": "Time",
           "platform": "Platform", "head": "Title", "status": "Status", "empty": "Nothing planned yet.",
           "local": "this computer's time",
           "st": {"pending": "pending", "scheduled": "scheduled", "published": "published", "failed": "failed",
                  "skipped_duplicate": "already scheduled (skipped)", "overdue": "time passed, no report"}},
}


def calendar_md(data: dict) -> str:
    L = MD["tr" if (config.get("ui_language") or "tr") == "tr" else "en"]
    name = zone_name()
    lines = [f"# {L['title']}", "", "_" + L["tz"].format(tz=L["local"] if name == "local" else name) + "_", ""]
    now = now_local()
    rows = [e for e in data.get("entries") or [] if e.get("scheduled_at")]
    if not rows:
        return "\n".join([*lines, L["empty"], ""])
    lines += [f"| {L['date']} | {L['time']} | {L['platform']} | {L['head']} | {L['status']} |",
              "|---|---|---|---|---|"]
    for e in rows:
        dt = parse_time(e["scheduled_at"])
        plat = NAMES.get(e.get("platform"), e.get("platform") or "?")
        if e.get("platform") == "instagram" and e.get("account"):
            plat += f" (@{e['account']})"
        title = str(e.get("title") or "").replace("|", "/").replace("\n", " ")
        st = L["st"].get("overdue" if is_overdue(e, now) else e.get("status"), e.get("status") or "")
        if e.get("url"):
            st = f"[{st}]({e['url']})"
        lines.append(f"| {dt:%Y-%m-%d} | {dt:%H:%M} | {plat} | {title} | {st} |" if dt else
                     f"| ? | ? | {plat} | {title} | {st} |")
    return "\n".join(lines) + "\n"


def _taken(cal: dict, platform: str) -> list[datetime]:
    out = []
    for e in cal["entries"]:
        if e.get("platform") == platform and e.get("status") in ("pending", *LIVE):
            dt = parse_time(e.get("scheduled_at"))
            if dt is not None:
                out.append(dt)
    return out


def _find(cal: dict, platform: str, sha: str | None, source: str | None, statuses: tuple[str, ...]) -> dict | None:
    for e in cal["entries"]:
        if e.get("platform") == platform and e.get("status") in statuses and (
                (sha and e.get("sha256") == sha) or (source and e.get("source") == source)):
            return e
    return None


# ===================================================================== a batch


def new_batch_dir(today: date | None = None) -> Path:
    today = today or now_local().date()
    base = queue_root()
    base.mkdir(parents=True, exist_ok=True)
    name = f"{today.isoformat()}_batch"
    n = 1
    while (base / name).exists():
        n += 1
        name = f"{today.isoformat()}_batch{n}"
    (base / name).mkdir()
    return base / name


def plan_batch(items: list[dict], s: dict, now: datetime | None = None, write: bool = True,
               batch: str | None = None) -> list[dict]:
    """items: [{id, file, sha256, size_mb, duration_s, title, description, tags, hashtags, source,
    mode, platforms: [..], times: {platform: iso}}] -> queue clips (the calendar gets every new
    entry). write=False: a dry run for the preview (nothing is saved)."""
    with _lock:
        cal = load_calendar()
        clips = []
        stamp = iso(now or now_local())
        for it in items:
            plats = {}
            for p in PLATFORMS:
                if p not in (it.get("platforms") or [p for p in PLATFORMS if s["platforms"][p]["on"]]):
                    continue
                entry = {"scheduled_at": None, "status": "pending", "url": None, "note": None}
                if p == "instagram":
                    entry = {"account": it.get("instagram_account") or instagram_account(it.get("mode"), s), **entry}
                dup = _find(cal, p, it.get("sha256"), it.get("source"), LIVE)
                if dup is not None:
                    entry.update(status="skipped_duplicate", scheduled_at=dup.get("scheduled_at"), url=dup.get("url"),
                                 note=f"already scheduled ({dup.get('batch') or '?'})")
                    plats[p] = entry
                    continue
                old = _find(cal, p, it.get("sha256"), it.get("source"), ("pending",))
                if old is not None:  # queued before but not posted yet: this batch replaces it
                    cal["entries"].remove(old)
                taken = _taken(cal, p)
                want = parse_time((it.get("times") or {}).get(p))
                if want is not None:
                    check_manual(p, want, taken, s, now)
                    when = want
                elif old is not None and (t := parse_time(old.get("scheduled_at"))) is not None and \
                        t >= (now or now_local()) + MIN_LEAD:
                    when = t
                else:
                    when = next_slot(p, taken, s, now)
                entry["scheduled_at"] = iso(when)
                plats[p] = entry
                cal["entries"].append({
                    "id": it["id"], "sha256": it.get("sha256"), "source": it.get("source"), "platform": p,
                    "account": entry.get("account"), "scheduled_at": entry["scheduled_at"],
                    "title": it.get("title"), "status": "pending", "url": None, "note": None,
                    "batch": batch, "file": it.get("file"), "created_at": stamp, "updated_at": stamp})
            clips.append({k: it.get(k) for k in ("id", "file", "sha256", "size_mb", "duration_s", "title",
                                                   "description", "tags", "hashtags")} | {"platforms": plats})
        if write:
            save_calendar(cal)
        return clips


def write_queue(folder: Path, clips: list[dict], s: dict) -> Path:
    data = {"version": 1, "batch": folder.name, "created_at": iso(now_local()), "timezone": zone_name(),
            "folder": str(folder), "clips": clips}
    write_json_atomic(folder / "queue.json", data)
    (folder / "CHROME.md").write_text(chrome_brief(folder, data), encoding="utf-8")
    return folder / "queue.json"


def chrome_brief(folder: Path, data: dict) -> str:
    """The uploader's instructions (Claude in Chrome): what to post where and what to answer."""
    tz = _tz_words()
    return f"""# SharkyClips publish queue: {data['batch']}

Folder: `{folder}`
Every clip is a 9:16 MP4 under 10 MB. Times carry their UTC offset ({tz}).

For each clip in `queue.json`, and each platform whose `status` is `pending`:
1. Open the platform's upload page in Chrome (YouTube Studio / TikTok Studio / Instagram, signed in
   as `platforms.instagram.account` for Instagram when it is set).
2. Upload the clip's `file`. Title = `title`, description = `description` followed by the
   `hashtags`; YouTube tags = `tags`.
3. Schedule it for `scheduled_at` ({tz}). If the platform can't schedule, post it at that
   time, or report `failed` with a `note`.
4. Skip platforms whose status is `skipped_duplicate`.

When done, answer with this JSON only (one line per clip and platform), then paste it into
SharkyClips → Publish queue → "Import status":

```json
{{"batch": "{data['batch']}", "results": [
  {{"id": "<clip id>", "platform": "youtube|tiktok|instagram", "status": "scheduled|failed",
    "url": "<link or null>", "scheduled_at": "<ISO time if it changed, else null>", "note": "<optional>"}}
]}}
```
"""


# ===================================================================== status import


SYNONYM = {"ok": "scheduled", "done": "scheduled", "success": "scheduled", "uploaded": "scheduled",
           "planned": "scheduled", "live": "published", "posted": "published", "public": "published",
           "error": "failed", "fail": "failed", "duplicate": "skipped_duplicate", "skipped": "skipped_duplicate",
           "not_found": "pending", "not found": "pending", "missing": "pending", "waiting": "pending"}
PLATFORM_ALIAS = {"yt": "youtube", "youtube": "youtube", "shorts": "youtube", "tiktok": "tiktok", "tt": "tiktok",
                  "instagram": "instagram", "ig": "instagram", "reels": "instagram", "insta": "instagram"}


def _rows(data) -> list[dict]:
    """Accepts {"results": [...]}, a list of rows, or a queue.json-shaped {"clips": [{id, platforms: {...}}]}."""
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        data = data["results"]
    elif isinstance(data, dict) and isinstance(data.get("clips"), list):
        out = []
        for c in data["clips"]:
            for p, v in ((c or {}).get("platforms") or {}).items():
                if isinstance(v, dict):
                    out.append({"id": c.get("id"), "sha256": c.get("sha256"), "platform": p, **v})
        return out
    elif isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise SharkyClipsError("That isn't a status list.", "Paste the JSON Claude in Chrome answered with.")
    return [r for r in data if isinstance(r, dict)]


def parse_status_text(text: str):
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except ValueError:
        i, j = min([x for x in (t.find("{"), t.find("[")) if x >= 0] or [-1]), max(t.rfind("}"), t.rfind("]"))
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                pass
    raise SharkyClipsError("Couldn't read that JSON.", "Paste exactly what Claude in Chrome answered (the JSON part).")


def import_status(payload) -> dict:
    """Updates takvim.json (+ md) and the batch's queue.json. -> {updated, unmatched, rows}"""
    data = parse_status_text(payload) if isinstance(payload, str) else payload
    rows = _rows(data)
    if not rows:
        raise SharkyClipsError("No status lines found.")
    updated, unmatched = 0, []
    touched: list[dict] = []
    with _lock:
        cal = load_calendar()
        for r in rows:
            plat = PLATFORM_ALIAS.get(str(r.get("platform") or "").strip().lower())
            st = str(r.get("status") or "").strip().lower()
            st = SYNONYM.get(st, st)
            if plat is None or st not in STATUSES:
                unmatched.append({"row": r, "why": "platform or status"})
                continue
            rid, sha = r.get("id"), r.get("sha256")
            file_name = Path(str(r.get("file") or "")).stem or None
            cands = [e for e in cal["entries"] if e.get("platform") == plat and (
                (rid and e.get("id") == rid) or (sha and e.get("sha256") == sha) or
                (file_name and Path(str(e.get("file") or "")).stem == file_name))]
            want_batch = r.get("batch") or (data.get("batch") if isinstance(data, dict) else None)
            if want_batch:
                cands = [e for e in cands if e.get("batch") == want_batch] or cands
            if not cands:
                unmatched.append({"row": r, "why": "no such clip"})
                continue
            e = max(cands, key=lambda x: x.get("created_at") or "")
            e["status"] = st
            if r.get("url"):
                e["url"] = str(r["url"])
            if r.get("note") is not None:
                e["note"] = str(r["note"])[:500] or None
            when = parse_time(r.get("scheduled_at"))
            if when is not None:
                e["scheduled_at"] = iso(when)
            e["updated_at"] = e["reported_at"] = iso(now_local())
            updated += 1
            touched.append(e)
        save_calendar(cal)
        _sync_queue_files(touched)
    return {"updated": updated, "unmatched": unmatched, "rows": len(rows),
            "entries": [{k: e.get(k) for k in ("id", "platform", "batch", "status")} for e in touched]}


def _tz_words() -> str:
    name = zone_name()
    return "this computer's local time" if name == "local" else name


def is_overdue(e: dict, now: datetime | None = None) -> bool:
    """Still "pending" although its time has passed: nobody reported it (posted or not)."""
    if e.get("status") != "pending":
        return False
    dt = parse_time(e.get("scheduled_at"))
    return dt is not None and dt < (now or now_local())


def view(e: dict, now: datetime | None = None) -> dict:
    return {**e, "overdue": is_overdue(e, now)}


def upcoming(limit: int = 200, include_past_days: int = 1) -> list[dict]:
    """The calendar from yesterday on, plus every overdue post (however old: they need a decision)."""
    now = now_local()
    since = now - timedelta(days=include_past_days)
    out = []
    for e in load_calendar()["entries"]:
        dt = parse_time(e.get("scheduled_at"))
        if dt is None or dt >= since or is_overdue(e, now):
            out.append(view(e, now))
    return out[:limit]


def overdue(now: datetime | None = None) -> list[dict]:
    now = now or now_local()
    return [view(e, now) for e in load_calendar()["entries"] if is_overdue(e, now)]


def _sync_queue_files(entries: list[dict]) -> None:
    """Copies status / url / note / time of these calendar entries into their batch's queue.json."""
    by_batch: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("batch"):
            by_batch.setdefault(e["batch"], []).append(e)
    for batch, es in by_batch.items():
        q = queue_root() / batch / "queue.json"
        try:
            qd = json.loads(q.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for e in es:
            for c in qd.get("clips") or []:
                if c.get("id") == e["id"] and e["platform"] in (c.get("platforms") or {}):
                    c["platforms"][e["platform"]].update({k: e.get(k) for k in ("status", "url", "note", "scheduled_at")})
        write_json_atomic(q, qd)


def _entry(cal: dict, eid: str, platform: str, batch: str | None = None) -> dict:
    hits = [e for e in cal["entries"] if e.get("id") == eid and e.get("platform") == platform
            and (batch is None or e.get("batch") == batch)]
    if not hits:
        raise SharkyClipsError("That post isn't in the calendar any more.")
    return max(hits, key=lambda x: x.get("created_at") or "")


def mark(eid: str, platform: str, status: str, url: str | None = None, note: str | None = None,
         batch: str | None = None) -> dict:
    """By hand: what really happened to one post (you looked in TikTok Studio / Instagram)."""
    if status not in ("pending", "scheduled", "published", "failed"):
        raise SharkyClipsError("Unknown status.")
    with _lock:
        cal = load_calendar()
        e = _entry(cal, eid, platform, batch)
        e["status"] = status
        if url is not None:
            u = str(url).strip()
            e["url"] = u if u.startswith("https://") else None
        if note is not None:
            e["note"] = str(note)[:500] or None
        e["updated_at"] = iso(now_local())
        e["marked_by_hand"] = True
        save_calendar(cal)
        _sync_queue_files([e])
        return view(e)


def set_result(eid: str, platform: str, status: str, url: str | None = None, note: str | None = None,
               batch: str | None = None, by: str = "sharkyclips") -> dict:
    """What SharkyClips itself found out (1.2.42: posted automatically, or checked on the platform)."""
    if status not in ("pending", "scheduled", "published", "failed"):
        raise SharkyClipsError("Unknown status.")
    with _lock:
        cal = load_calendar()
        e = _entry(cal, eid, platform, batch)
        e["status"] = status
        if url is not None:
            u = str(url).strip()
            e["url"] = u if u.startswith("https://") else e.get("url")
        if note is not None:
            e["note"] = str(note)[:500] or None
        e["updated_at"] = e["reported_at"] = iso(now_local())
        e["checked_by"] = by
        save_calendar(cal)
        _sync_queue_files([e])
        return view(e)


def replan(keys: list[dict] | None = None, now: datetime | None = None) -> list[dict]:
    """Overdue posts (or the given [{id, platform, batch?}]) get the next free time again."""
    s = settings()
    now = now or now_local()
    with _lock:
        cal = load_calendar()
        if keys:
            todo = [_entry(cal, str(k.get("id")), str(k.get("platform")), k.get("batch")) for k in keys]
            todo = [e for e in todo if e.get("status") in ("pending", "failed")]
        else:
            todo = [e for e in cal["entries"] if is_overdue(e, now)]
        todo.sort(key=lambda e: e.get("scheduled_at") or "")
        for e in todo:
            e["scheduled_at"] = None  # its own old time isn't "taken"
        for e in todo:
            e["scheduled_at"] = iso(next_slot(e["platform"], _taken(cal, e["platform"]), s, now))
            e["status"] = "pending"
            e["note"] = None
            e["updated_at"] = iso(now)
        if todo:
            save_calendar(cal)
            _sync_queue_files(todo)
        return [view(e, now) for e in todo]


VERIFY = """# SharkyClips: check these posts

These posts were planned, but SharkyClips never got a report. Please look them up, without
changing anything:

- TikTok: TikTok Studio -> Posts (also the "Scheduled" tab)
- Instagram: Meta Business Suite -> Content / Planner (the account in brackets), or the profile
- YouTube: YouTube Studio -> Content

{lines}

Answer with this JSON only, one line per post above, then paste it into SharkyClips ->
Publish queue -> "Import status":

```json
{{"results": [
  {{"id": "<id>", "platform": "youtube|tiktok|instagram", "batch": "<batch or null>",
    "status": "published|scheduled|pending|failed", "url": "<link or null>",
    "scheduled_at": "<the time it is planned for, if it is scheduled, else null>",
    "note": "<what you saw, e.g. not found>"}}
]}}
```

`published` = it is live, `scheduled` = it is planned on the platform, `pending` = it isn't
there (never uploaded).
"""


def verify_brief(now: datetime | None = None) -> dict:
    """For Claude in Chrome: look up what really happened to the overdue posts (TikTok Studio,
    Instagram / Meta Business Suite, YouTube Studio) and answer in the import format."""
    rows = overdue(now)
    if not rows:
        raise SharkyClipsError("Nothing to check: no post is overdue.")
    lines = []
    for e in rows:
        acc = f" (@{e['account']})" if e.get("platform") == "instagram" and e.get("account") else ""
        title = str(e.get("title") or "").strip()
        lines.append(f"- `{e['id']}` (batch `{e.get('batch')}`) on **{NAMES.get(e['platform'], e['platform'])}**{acc}, "
                     f"planned for {e['scheduled_at']}: \"{title}\"")
    return {"text": VERIFY.format(lines="\n".join(lines)), "count": len(rows), "rows": rows}


def batches(limit: int = 20) -> list[dict]:
    base = queue_root()
    if not base.is_dir():
        return []
    out = []
    for d in sorted((x for x in base.iterdir() if (x / "queue.json").is_file()),
                    key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            q = json.loads((d / "queue.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"batch": d.name, "folder": str(d), "created_at": q.get("created_at"),
                    "clips": len(q.get("clips") or []),
                    "size_mb": round(sum(float(c.get("size_mb") or 0) for c in q.get("clips") or []), 2)})
    return out


def safe_id(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text or "")).strip("-.")
    return s[:80] or "clip"

