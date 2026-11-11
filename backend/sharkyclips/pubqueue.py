"""Publish queue for an outside uploader (1.2.40): no platform APIs.

SharkyClips only gets everything ready; Claude in Chrome (or you) does the uploads in the browser:
  1. compress   every approved clip to 9:16 H.264 + AAC under 10 MB (two-pass, bitrate from the
                length, 9.5 MB target, audio 96k; still too big -> 10 % less, then 1080 -> 720)
  2. queue.json in <root>/publish_queue/<YYYY-MM-DD_batch>/ next to the files: title,
                description, tags, hashtags (always the brand tag), and per platform the planned
                time (Europe/Budapest), status, url, note; plus CHROME.md, the uploader's brief
  3. schedule   per platform: posts per day + times, daily caps (YouTube 8, Instagram 10,
                TikTok adjustable, default 10), never sooner than 1 hour from now, a full day
                moves on to the next one
  4. calendar   <root>/takvim.json (the master record) + takvim.md (readable); a file (sha256)
                or clip already "scheduled" on a platform is not queued there again
                (skipped_duplicate); the uploader's status JSON is imported back into it

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

TZ_NAME = "Europe/Budapest"
PLATFORMS = ("youtube", "tiktok", "instagram")
NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}
HARD_CAP = {"youtube": 8, "instagram": 10}  # TikTok: the "tiktok_cap" setting (default 10)
STATUSES = ("pending", "scheduled", "failed", "skipped_duplicate")
LIMIT_BYTES = 10_000_000  # "under 10 MB": the decimal MB, the stricter of the two
TARGET_BYTES = 9_500_000
AUDIO_BPS = 96_000
MIN_LEAD = timedelta(hours=1)
MAX_TRIES = 5

DEFAULTS = {
    "root": "",
    "brand_hashtag": "#utkualsirr",
    "tiktok_cap": 10,
    "instagram_account": "auto",  # auto: gaming projects -> instagram_gaming, others -> instagram_default
    "instagram_accounts": ["utkualsirr", "utkualsirr48"],
    "instagram_default": "utkualsirr",
    "instagram_gaming": "utkualsirr48",
    "platforms": {
        "youtube": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
        "tiktok": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
        "instagram": {"on": True, "per_day": 3, "times": ["12:00", "18:00", "21:00"]},
    },
}

_lock = threading.RLock()
ProgressFn = Callable[[str, float | None], None]


# ===================================================================== Europe/Budapest


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


def budapest() -> tzinfo:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(TZ_NAME)
    except Exception:  # noqa: BLE001 - no tz database on this system
        return _EuCentral()


def now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone(budapest())


def parse_time(value) -> datetime | None:
    """ISO with an offset, or a wall time "YYYY-MM-DD HH:MM" in Budapest."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s.replace(" ", "T"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=budapest())
    return dt.astimezone(budapest())


def iso(dt: datetime) -> str:
    return dt.astimezone(budapest()).replace(second=0, microsecond=0).isoformat()


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
    out["brand_hashtag"] = ("#" + tag.lstrip("#")) if tag.lstrip("#") else ""
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
        elif k in DEFAULTS and k != "platforms":
            cur[k] = v
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
    return str(s["instagram_gaming"] if (mode or "gaming") == "gaming" else s["instagram_default"])


def with_brand(hashtags: list[str], brand: str) -> list[str]:
    out: list[str] = []
    for h in [brand, *hashtags]:
        h = "#" + str(h or "").strip().lstrip("#").replace(" ", "")
        if len(h) > 1 and h.lower() not in [x.lower() for x in out]:
            out.append(h)
    return out


# ===================================================================== scheduler


def slots_for_day(day: date, conf: dict) -> list[datetime]:
    tz = budapest()
    times = conf["times"][: max(0, int(conf.get("per_day") or 0))]
    return [datetime.combine(day, dtime(*_hm(t))).replace(tzinfo=tz).astimezone(tz) for t in times]


def next_slot(platform: str, taken: list[datetime], s: dict, now: datetime | None = None,
              max_days: int = 366) -> datetime:
    """The first planned time >= now + 1 h that's free and whose day isn't full."""
    conf = s["platforms"][platform]
    if not conf["times"] or not conf["per_day"]:
        raise SharkyClipsError(f"No posting times set for {NAMES[platform]}.", "Add times in the publish queue settings.")
    now = (now or now_local()).astimezone(budapest())
    earliest = now + MIN_LEAD
    limit = min(cap(platform, s), conf["per_day"])
    used: dict[date, int] = {}
    minutes = set()
    for t in taken:
        lt = t.astimezone(budapest())
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
    now = (now or now_local()).astimezone(budapest())
    if when < now + MIN_LEAD:
        raise SharkyClipsError(f"{NAMES[platform]}: a planned time must be at least 1 hour from now.",
                               "Pick a later time, or leave it empty for the next free slot.")
    day = when.astimezone(budapest()).date()
    n = sum(1 for t in taken if t.astimezone(budapest()).date() == day)
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
    return {"version": 1, "timezone": TZ_NAME, "entries": []}


def save_calendar(data: dict) -> None:
    root().mkdir(parents=True, exist_ok=True)
    data["entries"].sort(key=lambda e: (e.get("scheduled_at") or "", e.get("platform") or ""))
    data["updated_at"] = iso(now_local())
    write_json_atomic(calendar_path(), data)
    calendar_md_path().write_text(calendar_md(data), encoding="utf-8")


MD = {
    "tr": {"title": "Yayın takvimi", "tz": "Saatler: Europe/Budapest", "date": "Tarih", "time": "Saat",
           "platform": "Platform", "head": "Başlık", "status": "Durum", "empty": "Henüz planlanan gönderi yok.",
           "st": {"pending": "bekliyor", "scheduled": "planlandı", "failed": "başarısız",
                  "skipped_duplicate": "zaten planlı (atlandı)"}},
    "en": {"title": "Publishing calendar", "tz": "Times: Europe/Budapest", "date": "Date", "time": "Time",
           "platform": "Platform", "head": "Title", "status": "Status", "empty": "Nothing planned yet.",
           "st": {"pending": "pending", "scheduled": "scheduled", "failed": "failed",
                  "skipped_duplicate": "already scheduled (skipped)"}},
}


def calendar_md(data: dict) -> str:
    L = MD["tr" if (config.get("ui_language") or "tr") == "tr" else "en"]
    lines = [f"# {L['title']}", "", f"_{L['tz']}_", ""]
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
        st = L["st"].get(e.get("status"), e.get("status") or "")
        if e.get("url"):
            st = f"[{st}]({e['url']})"
        lines.append(f"| {dt:%Y-%m-%d} | {dt:%H:%M} | {plat} | {title} | {st} |" if dt else
                     f"| ? | ? | {plat} | {title} | {st} |")
    return "\n".join(lines) + "\n"


def _taken(cal: dict, platform: str) -> list[datetime]:
    out = []
    for e in cal["entries"]:
        if e.get("platform") == platform and e.get("status") in ("pending", "scheduled"):
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
                dup = _find(cal, p, it.get("sha256"), it.get("source"), ("scheduled",))
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
    data = {"version": 1, "batch": folder.name, "created_at": iso(now_local()), "timezone": TZ_NAME,
            "folder": str(folder), "clips": clips}
    write_json_atomic(folder / "queue.json", data)
    (folder / "CHROME.md").write_text(chrome_brief(folder, data), encoding="utf-8")
    return folder / "queue.json"


def chrome_brief(folder: Path, data: dict) -> str:
    """The uploader's instructions (Claude in Chrome): what to post where and what to answer."""
    return f"""# SharkyClips publish queue: {data['batch']}

Folder: `{folder}`
Every clip is a 9:16 MP4 under 10 MB. Times are **Europe/Budapest**.

For each clip in `queue.json`, and each platform whose `status` is `pending`:
1. Open the platform's upload page in Chrome (YouTube Studio / TikTok Studio / Instagram, signed in
   as `platforms.instagram.account` for Instagram).
2. Upload the clip's `file`. Title = `title`, description = `description` followed by the
   `hashtags`; YouTube tags = `tags`.
3. Schedule it for `scheduled_at` (Europe/Budapest). If the platform can't schedule, post it at that
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
           "published": "scheduled", "planned": "scheduled", "error": "failed", "fail": "failed",
           "duplicate": "skipped_duplicate", "skipped": "skipped_duplicate"}
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
    touched_batches: dict[str, list[dict]] = {}
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
            if data and isinstance(data, dict) and data.get("batch"):
                cands = [e for e in cands if e.get("batch") == data["batch"]] or cands
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
            e["updated_at"] = iso(now_local())
            updated += 1
            if e.get("batch"):
                touched_batches.setdefault(e["batch"], []).append(e)
        save_calendar(cal)
        for batch, entries in touched_batches.items():
            q = queue_root() / batch / "queue.json"
            try:
                qd = json.loads(q.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for e in entries:
                for c in qd.get("clips") or []:
                    if c.get("id") == e["id"] and e["platform"] in (c.get("platforms") or {}):
                        c["platforms"][e["platform"]].update(
                            {k: e.get(k) for k in ("status", "url", "note", "scheduled_at")})
            write_json_atomic(q, qd)
    return {"updated": updated, "unmatched": unmatched, "rows": len(rows)}


def upcoming(limit: int = 200, include_past_days: int = 1) -> list[dict]:
    since = now_local() - timedelta(days=include_past_days)
    out = []
    for e in load_calendar()["entries"]:
        dt = parse_time(e.get("scheduled_at"))
        if dt is None or dt >= since:
            out.append(e)
    return out[:limit]


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

