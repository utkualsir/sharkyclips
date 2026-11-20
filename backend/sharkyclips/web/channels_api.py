"""Channel monitoring (1.2.57): the background service and the API (channels.py decides).

The loop (one per server; the server lock makes sure there is only one) wakes every LOOP_S:
  1. catch-up: it slept much longer than planned (PC off / asleep) -> every channel is due now
  2. polls the channels that are due (network outside the lock, merge under it)
  3. one download at a time: the oldest waiting VOD -> gates (queue paused, game running,
     metered connection, free disk space) -> an Easy import job (the normal pipeline)
  4. moves the downloaded VODs of finished streams to the trash after the channel's keep days

Job hooks: the import's end (verified in app.submit_import) and "clips ready" (web/easy.py ->
on_clips_ready) move a VOD through downloading -> clipping -> done.
SHARKYCLIPS_LIVE_LOOP=0 keeps the thread off (tests call tick() themselves).
"""

from __future__ import annotations

import os
import threading
import json
import time

from fastapi import APIRouter

from .. import channels as C
from .. import config
from ..errors import SharkyClipsError
from ..project import Project
from .jobs import ACTIVE, Job

router = APIRouter()
LOOP_S = 30.0


def _app():
    from . import app as appmod

    return appmod


def _lang() -> str:
    return str(config.get("ui_language") or "en")


# ===================================================================== texts (tray + Telegram)

TEXT = {
    "en": {"ready_own": ("Your stream is over", "Your stream is over, {n} clips are ready. ({title})"),
           "ready_other": ("{name}'s stream is over", "{name}'s stream is over, {n} clips are ready. ({title})"),
           "disk": ("Not enough free space", "“{title}” needs about {need} GB, {free} GB are free. It waits until there is room."),
           "skipped": ("Stream skipped", "“{title}” can't be downloaded without an account (subscriber-only or age-restricted)."),
           "error": ("Stream download failed", "“{title}” couldn't be downloaded after several tries.")},
    "tr": {"ready_own": ("Yayının bitti", "Yayının bitti, {n} klip hazır. ({title})"),
           "ready_other": ("{name} yayını bitti", "{name} yayını bitti, {n} klip hazır. ({title})"),
           "disk": ("Yeterli boş alan yok", "“{title}” için yaklaşık {need} GB gerekiyor, {free} GB boş. Yer açılınca devam eder."),
           "skipped": ("Yayın atlandı", "“{title}” hesap olmadan indirilemiyor (abonelere özel veya yaş sınırlı)."),
           "error": ("Yayın indirilemedi", "“{title}” birkaç denemeye rağmen indirilemedi.")},
    "de": {"ready_own": ("Dein Stream ist vorbei", "Dein Stream ist vorbei, {n} Clips sind fertig. ({title})"),
           "ready_other": ("Der Stream von {name} ist vorbei", "Der Stream von {name} ist vorbei, {n} Clips sind fertig. ({title})"),
           "disk": ("Nicht genug Speicherplatz", "„{title}“ braucht etwa {need} GB, {free} GB sind frei. Es wartet, bis Platz ist."),
           "skipped": ("Stream übersprungen", "„{title}“ lässt sich ohne Konto nicht laden (nur für Abonnenten oder altersbeschränkt)."),
           "error": ("Stream-Download fehlgeschlagen", "„{title}“ konnte nach mehreren Versuchen nicht geladen werden.")},
    "hu": {"ready_own": ("Véget ért az adásod", "Véget ért az adásod, {n} klip kész. ({title})"),
           "ready_other": ("{name} adása véget ért", "{name} adása véget ért, {n} klip kész. ({title})"),
           "disk": ("Nincs elég szabad hely", "A(z) „{title}” kb. {need} GB-ot igényel, {free} GB szabad. Megvárja, amíg lesz hely."),
           "skipped": ("Adás kihagyva", "A(z) „{title}” fiók nélkül nem tölthető le (csak feliratkozóknak vagy korhatáros)."),
           "error": ("Az adás letöltése nem sikerült", "A(z) „{title}” több próbálkozás után sem tölthető le.")},
    "ru": {"ready_own": ("Стрим закончился", "Стрим закончился, готово клипов: {n}. ({title})"),
           "ready_other": ("Стрим {name} закончился", "Стрим {name} закончился, готово клипов: {n}. ({title})"),
           "disk": ("Мало свободного места", "Для «{title}» нужно около {need} ГБ, свободно {free} ГБ. Загрузка подождёт."),
           "skipped": ("Стрим пропущен", "«{title}» нельзя скачать без аккаунта (только для подписчиков или с возрастным ограничением)."),
           "error": ("Не удалось скачать стрим", "«{title}» не скачался после нескольких попыток.")},
    "ar": {"ready_own": ("انتهى بثك", "انتهى بثك، {n} مقاطع جاهزة. ({title})"),
           "ready_other": ("انتهى بث {name}", "انتهى بث {name}، {n} مقاطع جاهزة. ({title})"),
           "disk": ("المساحة الحرة غير كافية", "يحتاج “{title}” إلى نحو {need} غيغابايت والمتاح {free}. سينتظر حتى تتوفر مساحة."),
           "skipped": ("تم تخطي البث", "لا يمكن تنزيل “{title}” بدون حساب (للمشتركين فقط أو مقيد بالعمر)."),
           "error": ("فشل تنزيل البث", "تعذر تنزيل “{title}” بعد عدة محاولات.")},
    "zh": {"ready_own": ("直播结束了", "直播结束了，{n} 个剪辑已就绪。（{title}）"),
           "ready_other": ("{name} 的直播结束了", "{name} 的直播结束了，{n} 个剪辑已就绪。（{title}）"),
           "disk": ("磁盘空间不足", "“{title}” 需要约 {need} GB，目前只有 {free} GB 可用。腾出空间后继续。"),
           "skipped": ("已跳过直播", "“{title}” 需要账号才能下载（仅限订阅者或有年龄限制）。"),
           "error": ("直播下载失败", "“{title}” 多次尝试后仍无法下载。")},
    "es": {"ready_own": ("Tu directo terminó", "Tu directo terminó, {n} clips están listos. ({title})"),
           "ready_other": ("Terminó el directo de {name}", "Terminó el directo de {name}, {n} clips están listos. ({title})"),
           "disk": ("No hay espacio suficiente", "“{title}” necesita unos {need} GB y hay {free} GB libres. Esperará a que haya espacio."),
           "skipped": ("Directo omitido", "“{title}” no se puede descargar sin cuenta (solo suscriptores o con restricción de edad)."),
           "error": ("Falló la descarga del directo", "“{title}” no se pudo descargar tras varios intentos.")},
    "pt": {"ready_own": ("Sua live acabou", "Sua live acabou, {n} clipes estão prontos. ({title})"),
           "ready_other": ("A live de {name} acabou", "A live de {name} acabou, {n} clipes estão prontos. ({title})"),
           "disk": ("Espaço livre insuficiente", "“{title}” precisa de cerca de {need} GB e há {free} GB livres. Vai esperar até ter espaço."),
           "skipped": ("Live ignorada", "“{title}” não pode ser baixada sem conta (só para inscritos ou com restrição de idade)."),
           "error": ("Falha ao baixar a live", "“{title}” não pôde ser baixada após várias tentativas.")},
    "fr": {"ready_own": ("Ton live est terminé", "Ton live est terminé, {n} clips sont prêts. ({title})"),
           "ready_other": ("Le live de {name} est terminé", "Le live de {name} est terminé, {n} clips sont prêts. ({title})"),
           "disk": ("Pas assez d'espace libre", "« {title} » demande environ {need} Go, {free} Go sont libres. Il attend qu'il y ait de la place."),
           "skipped": ("Live ignoré", "« {title} » ne peut pas être téléchargé sans compte (réservé aux abonnés ou limité par l'âge)."),
           "error": ("Échec du téléchargement du live", "« {title} » n'a pas pu être téléchargé après plusieurs essais.")},
    "ja": {"ready_own": ("配信が終わりました", "配信が終わりました。クリップが {n} 本できています。（{title}）"),
           "ready_other": ("{name} の配信が終わりました", "{name} の配信が終わりました。クリップが {n} 本できています。（{title}）"),
           "disk": ("空き容量が足りません", "「{title}」には約 {need} GB 必要ですが、空きは {free} GB です。空きができるまで待ちます。"),
           "skipped": ("配信をスキップしました", "「{title}」はアカウントなしではダウンロードできません（サブスク限定または年齢制限）。"),
           "error": ("配信のダウンロードに失敗しました", "「{title}」は何度試してもダウンロードできませんでした。")},
}


def text(key: str, **kw) -> tuple[str, str]:
    t = (TEXT.get(_lang()) or TEXT["en"]).get(key) or TEXT["en"][key]
    return t[0].format(**kw), t[1].format(**kw)


def notify(kind: str, key: str, url: str | None = None, telegram: bool = True, **kw) -> None:
    from .. import easy as E

    title, body = text(key, **kw)
    E.push_notice(kind, title, body, url)
    if telegram:
        try:
            from .. import phone

            phone.send_text(body)
        except Exception:  # noqa: BLE001 - the phone is a bonus
            pass


# ===================================================================== the service


class Monitor:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._poke = threading.Event()
        self.last_tick: float | None = None
        self.last_error: str | None = None
        self.waiting: dict | None = None  # why the next download waits: {"key", "reason", ...}
        self._resumed = False
        self._busy = threading.Lock()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="sharkyclips-channels", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._poke.set()

    def poke(self) -> None:
        self._poke.set()

    def _loop(self) -> None:
        self._stop.wait(5)  # let the server finish starting
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - never let the monitor die
                self.last_error = str(exc)[:200]
            self._poke.wait(LOOP_S)
            self._poke.clear()

    # ---- one round
    def tick(self, now: float | None = None) -> dict:
        if not self._busy.acquire(blocking=False):
            return {"skipped": True}
        try:
            return self._tick(now)
        finally:
            self._busy.release()

    def _tick(self, now: float | None) -> dict:
        now = time.time() if now is None else now
        out: dict = {"polled": [], "started": None, "trashed": []}
        with C._lock:
            data = C.load()
            if not data["channels"]:
                self.last_tick = now
                return out
            before = json.dumps(data, sort_keys=True, default=str)
            if self.last_tick is not None and now - self.last_tick > LOOP_S + C.WAKE_GAP_S:
                C.wake_all(data, now)  # catch-up: the PC was off or asleep
                C.log(data, "catch_up", note=f"{int(now - self.last_tick)} s", now=now)
            if not self._resumed:
                self._resume(data, now)
                self._resumed = True
            due = [dict(c) for c in C.due(data, now)]
            if json.dumps(data, sort_keys=True, default=str) != before:
                C.save(data)
        self.last_tick = now
        for snap in due:
            out["polled"].append(self.poll_one(snap["id"], now))
        out["started"] = self.process(now)
        out["trashed"] = self.cleanup_sources(now)
        return out

    def poll_one(self, cid: str, now: float | None = None) -> dict:
        """Network outside the lock, merge under it (an API change in between is kept)."""
        now = time.time() if now is None else now
        with C._lock:
            data = C.load()
            ch = data["channels"].get(cid)
            if ch is None:
                return {"id": cid, "gone": True}
            snap = {"channels": {cid: dict(ch)}, "vods": {k: dict(v) for k, v in data["vods"].items()
                                                          if v.get("channel") == cid}, "log": []}
        res = C.poll(snap, snap["channels"][cid], now)  # network happens here
        with C._lock:
            data = C.load()
            if cid not in data["channels"]:
                return {"id": cid, "gone": True}
            cur = data["channels"][cid]
            for k in ("live", "live_since", "ended_at", "last_check", "next_check", "fails", "last_error",
                      "last_ok", "first_listing"):
                if k in snap["channels"][cid]:
                    cur[k] = snap["channels"][cid][k]
                else:
                    cur.pop(k, None)
            for k, v in snap["vods"].items():
                old = data["vods"].get(k)
                # a VOD the import moved on in the meantime keeps its newer state
                if old is not None and old.get("status") in ("downloading", "clipping", "done") \
                        and v.get("status") != old.get("status"):
                    continue
                data["vods"][k] = v
            for k in list(data["vods"]):
                if data["vods"][k].get("channel") == cid and k not in snap["vods"] and data["vods"][k].get("placeholder"):
                    data["vods"].pop(k, None)  # a stand-in the poll dropped
            data["log"].extend(snap["log"])
            C.save(data)
        if res["new"]:
            self.poke()
        return {"id": cid, **res}

    # ---- after a restart
    def _resume(self, data: dict, now: float) -> None:
        """A download cut short by a restart goes back to the queue (yt-dlp continues the part
        files: the project id comes from the VOD id). A VOD whose clips were being made gets
        its pipeline going again."""
        active = _running()
        for key, v in data["vods"].items():
            if v.get("status") == "downloading" and key not in active:
                v.update(status="queued", note="resumed")
            elif v.get("status") == "clipping" and v.get("project_id"):
                try:
                    self._continue_pipeline(v["project_id"], key, data, now)
                except Exception:  # noqa: BLE001
                    pass

    def _continue_pipeline(self, pid: str, key: str, data: dict, now: float) -> None:
        from .. import easy as E
        from ..project import get_project
        from . import easy as ezw, state
        from .jobs import automatic

        A = _app()
        try:
            project = get_project(pid)
        except SharkyClipsError:
            data["vods"][key].update(status="error", note="project_gone", done_at=now)
            return
        if A.jobs.active_for(pid) is not None or ezw.pipeline_busy(pid):
            return
        hl = state.load_highlights(project) or {}
        ed = E.load(project)
        if hl.get("created_at") and ed.get("notified_for") == hl.get("created_at"):
            clips = state.load_clips(project)
            data["vods"][key].update(status="done", clips=len(clips), done_at=now)
            return
        with automatic():
            if not project.transcript_path.is_file():
                A.submit_transcribe(pid, "auto")
            elif not (project.dir / "highlights.json").is_file():
                A.submit_highlights(pid)
            else:
                ezw.ensure_renders(project)

    # ---- downloads
    def process(self, now: float | None = None) -> str | None:
        now = time.time() if now is None else now
        with C._lock:
            data = C.load()
            active =[k for k, v in data["vods"].items() if v.get("status") == "downloading"]
            if active:
                running = _running()
                if any(k in running for k in active):
                    self.waiting = None
                    return None  # one download at a time
                for k in active:  # its job is gone without a result (crash): queue it again
                    data["vods"][k].update(status="queued", note="resumed")
            pick = C.next_waiting(data, now)
            if pick is None:
                self.waiting = None
                if active:
                    C.save(data)
                return None
            key, rec = pick
            ch = data["channels"][rec["channel"]]
            reason = self._gate(rec, now)
            if reason is not None:
                self._wait(data, key, rec, reason, now)
                C.save(data)
                return None
            self.waiting = None
            try:
                job = self._submit(key, rec, ch)
            except SharkyClipsError as exc:
                C.on_import_failed(data, key, exc.message, now)
                C.save(data)
                return None
            rec.update(status="downloading", job_id=job.id, attempts=int(rec.get("attempts") or 0) + 1,
                       started_dl=now, note=None)
            rec.pop("warned", None)
            C.log(data, "download", rec["channel"], key, note=rec.get("title") or "", now=now)
            C.save(data)
            return key

    def _gate(self, rec: dict, now: float) -> dict | None:
        A = _app()
        s = C.settings()
        if A.jobs.paused:
            return {"reason": "queue_paused"}
        if s["pause_games"]:
            game = C.game_running()
            if game:
                return {"reason": "game", "detail": game}
        if s["pause_metered"] and C.metered():
            return {"reason": "metered"}
        ok, free, need = C.disk_ok(rec.get("duration"))
        if not ok:
            return {"reason": "disk", "free": free, "need": need}
        return None

    def _wait(self, data: dict, key: str, rec: dict, why: dict, now: float) -> None:
        status = {"disk": "waiting_disk", "metered": "waiting_metered", "game": "waiting_game"}.get(why["reason"])
        if status and rec.get("status") != "retry":
            rec["status"] = status
        self.waiting = {"key": key, **why, "at": now}
        if why["reason"] == "disk" and not rec.get("warned"):
            rec["warned"] = now
            C.log(data, "low_disk", rec.get("channel"), key, now=now)
            notify("channel_disk", "disk", "/#/settings", title=(rec.get("title") or key)[:60],
                   need=f"{why['need'] / 1024 ** 3:.0f}", free=f"{why['free'] / 1024 ** 3:.0f}")

    def _submit(self, key: str, rec: dict, ch: dict) -> Job:
        A = _app()
        mode = ch.get("mode") or "auto"
        real = str(config.get("default_mode") or "gaming") if mode == "auto" else mode
        title = (rec.get("title") or rec["vod_id"])[:120]
        extra = {"easy": True, "mode_auto": mode == "auto", "channel_vod": key, "channel_id": ch["id"],
                 "full_upload": False, "nice_title": title}
        if rec.get("duration"):
            extra["expect_duration"] = float(rec["duration"])
        return A.submit_import(rec["url"], real, "auto", title, extra=extra)

    # ---- the source video after the clips
    def cleanup_sources(self, now: float | None = None) -> list[str]:
        from .. import trash

        now = time.time() if now is None else now
        A = _app()
        out = []
        with C._lock:
            data = C.load()
            for key, v in data["vods"].items():
                ch = data["channels"].get(v.get("channel") or "")
                if not C.source_due(v, ch, now):
                    continue
                pid = v["project_id"]
                if A.jobs.active_for(pid) is not None:
                    continue  # renders / uploads still need it
                try:
                    res = trash.trash_source(pid, keep=2)
                except SharkyClipsError:
                    v["source_trashed"] = now  # the project is gone (deleted by the user)
                    continue
                except OSError:
                    continue  # in use (a player): next round
                v["source_trashed"] = now
                C.log(data, "source_trashed", v.get("channel"), key,
                      note=str((res or {}).get("bytes") or 0), now=now)
                out.append(key)
            if out:
                C.save(data)
        return out

    def view(self) -> dict:
        return {"running": self._thread is not None, "last_tick": self.last_tick, "error": self.last_error,
                "waiting": self.waiting, "ipv4_only": C.ipv4_only()}


def _running() -> set:
    """Channel VODs whose import job is queued or running."""
    return {j.params.get("channel_vod") for j in _app().jobs.jobs()
            if j.kind == "import" and j.status in ACTIVE and j.params.get("channel_vod")}


_monitor = Monitor()


def monitor() -> Monitor:
    return _monitor


def install(jobs) -> None:
    if on_job_finished not in jobs.on_finished:
        jobs.on_finished.append(on_job_finished)
    if os.environ.get("SHARKYCLIPS_LIVE_LOOP") == "0":
        return
    _monitor.start()


# ===================================================================== job hooks


def on_job_finished(job: Job) -> None:
    key = job.params.get("channel_vod")
    if job.kind != "import" or not key:
        return
    now = time.time()
    with C._lock:
        data = C.load()
        rec = data["vods"].get(key)
        if rec is None:
            return
        if job.status == "done" and job.project_id:
            rec.update(status="clipping", project_id=job.project_id, note=None, dl_done=now)
            rec.pop("job_id", None)
            C.log(data, "downloaded", rec.get("channel"), key, now=now)
            ch = data["channels"].get(rec.get("channel") or "") or {}
            C.save(data)
            _tag_project(job.project_id, key, rec, ch)
        elif job.status == "cancelled":
            rec.update(status="skipped", note="cancelled", done_at=now)  # Cancel is final
            rec.pop("job_id", None)
            C.save(data)
        else:
            msg = ((job.error or {}).get("message") or "") + " " + ((job.error or {}).get("hint") or "")
            st = C.on_import_failed(data, key, msg, now)
            C.save(data)
            if st == "skipped":
                notify("channel_skipped", "skipped", "/#/settings", telegram=False, title=(rec.get("title") or key)[:60])
            elif st == "error":
                notify("channel_error", "error", "/#/settings", telegram=False, title=(rec.get("title") or key)[:60])
    _monitor.poke()


def _tag_project(pid: str, key: str, rec: dict, ch: dict) -> None:
    """The project remembers its channel + stream (the Library shows it) and the channel's game."""
    from ..project import get_project

    try:
        project = get_project(pid)
    except SharkyClipsError:
        return
    meta = project.load_meta()
    meta["channel"] = {"key": key, "id": ch.get("id") or rec.get("channel"), "platform": rec.get("platform"),
                       "name": ch.get("name"), "own": bool(ch.get("own")), "stream_title": rec.get("title"),
                       "started_at": rec.get("started_at"), "url": rec.get("url")}
    game = ch.get("game") or "auto"
    if game != "auto" and meta.get("game") in (None, "auto"):
        meta["game"] = game
    project.save_meta(meta)


def channel_of(project: Project) -> dict | None:
    try:
        return project.load_meta().get("channel") or None
    except Exception:  # noqa: BLE001
        return None


def on_clips_ready(project: Project, top: list[dict]) -> bool:
    """web/easy.py: the grid of an Easy project is rendered. True = a channel VOD (its own
    notice and its channel's auto-publish rule; the generic notice and the auto-clip
    publish setting don't apply)."""
    info = channel_of(project)
    if not info or not info.get("key"):
        return False
    from . import state

    clips = state.load_clips(project)
    ready = [c for c in top if c["id"] in clips]
    now = time.time()
    with C._lock:
        data = C.load()
        rec = data["vods"].get(info["key"])
        ch = data["channels"].get(info.get("id") or "") or {}
        if rec is not None:
            first = rec.get("status") != "done"
            rec.update(status="done", clips=len(ready), done_at=rec.get("done_at") if not first else now,
                       project_id=project.id)
            if first:
                C.log(data, "done", rec.get("channel"), info["key"], note=str(len(ready)), now=now)
            C.save(data)
        else:
            first = True
    if not first:
        return True
    title = (info.get("stream_title") or project.load_meta().get("title") or project.id)[:60]
    name = ch.get("name") or info.get("name") or ""
    own = bool(ch.get("own", info.get("own")))
    notify("channel_ready", "ready_own" if own else "ready_other", f"/#/p/{project.id}", n=len(ready), title=title,
           name=name)
    if ch.get("auto_publish") and ready:
        from .. import autopilot

        top_n = max(1, int(config.get("watch_publish_top") or 3))
        autopilot.on_clips_ready(project, ready[:top_n],
                                 lambda cid, when: _ez().upload(project, cid, when), "auto")
    return True


def _ez():
    from . import easy as ezmod

    return ezmod


# ===================================================================== API


def _view() -> dict:
    from ..game import CHOICES, presets

    data = C.load()
    chans = sorted(data["channels"].values(), key=lambda c: (not c.get("own"), float(c.get("added_at") or 0)))
    rows = []
    for k, v in data["vods"].items():
        if v.get("status") == "baseline" or v.get("placeholder") and v.get("status") not in C.WATCHING:
            continue
        rows.append(C.vod_view(k, v, data["channels"].get(v.get("channel") or "")))
    rows.sort(key=lambda r: -float(r.get("started_at") or r.get("queued_at") or 0))
    return {"channels": [C.channel_view(c, data) for c in chans], "vods": rows[:40],
            "settings": C.settings(), "service": _monitor.view(), "games": list(CHOICES),
            "game_names": {g: presets.GAMES[g] for g in CHOICES if presets.GAMES.get(g)},
            "log": list(reversed(data["log"][-20:]))}


@router.get("/api/channels")
def api_channels() -> dict:
    return _view()


@router.post("/api/channels/lookup")
def api_lookup(body: dict) -> dict:
    info = C.lookup(str(body.get("text") or ""), body.get("platform"))
    with C._lock:
        known = info["id"] in C.load()["channels"]
    return {**info, "known": known}


@router.post("/api/channels")
def api_add(body: dict) -> dict:
    info = C.lookup(str(body.get("text") or ""), body.get("platform"))
    now = time.time()
    own = body.get("own")
    with C._lock:
        data = C.load()
        if info["id"] in data["channels"]:
            raise SharkyClipsError("This channel is connected already.", "Change its settings below.")
        if len(data["channels"]) >= 20:
            raise SharkyClipsError("20 channels at most.", "Remove one you don't need.")
        opts = {k: body.get(k) for k in ("mode", "game", "keep_days", "yt_kinds")}
        ch = C.new_channel(info, own=True if own is None else bool(own), now=now, **opts)
        if body.get("auto_publish") is not None:
            ch["auto_publish"] = bool(body["auto_publish"])  # others' channels: OFF unless set here
        data["channels"][ch["id"]] = ch
        C.log(data, "added", ch["id"], note="own" if ch["own"] else "other", now=now)
        C.save(data)
    threading.Thread(target=_first_poll, args=(ch["id"],), name="sharkyclips-channel-add", daemon=True).start()
    return _view()


def _first_poll(cid: str) -> None:
    try:
        _monitor.poll_one(cid)
    except Exception:  # noqa: BLE001
        pass


@router.put("/api/channels/settings")
def api_settings_put(body: dict) -> dict:
    changes: dict = {}
    if "pause_metered" in body:
        changes["channel_pause_metered"] = bool(body["pause_metered"])
    if "pause_games" in body:
        changes["channel_pause_games"] = bool(body["pause_games"])
    if "min_free_gb" in body:
        changes["channel_min_free_gb"] = max(1.0, min(500.0, float(body["min_free_gb"])))
    if "min_minutes" in body:
        changes["channel_min_minutes"] = max(0.0, min(240.0, float(body["min_minutes"])))
    if changes:
        config.update(**changes)
    _monitor.poke()
    return _view()


@router.put("/api/channels/{cid:path}/options")
def api_update(cid: str, body: dict) -> dict:
    with C._lock:
        data = C.load()
        ch = data["channels"].get(cid)
        if ch is None:
            raise SharkyClipsError("This channel isn't connected.")
        C.apply_options(ch, {k: body.get(k) for k in ("mode", "game", "auto_publish", "keep_days", "yt_kinds",
                                                     "own", "enabled")})
        C.save(data)
    return _view()


@router.delete("/api/channels/{cid:path}/remove")
def api_remove(cid: str) -> dict:
    """The channel goes; its VOD records stay (adding it again never downloads one twice)."""
    with C._lock:
        data = C.load()
        if data["channels"].pop(cid, None) is None:
            raise SharkyClipsError("This channel isn't connected.")
        for v in data["vods"].values():
            if v.get("channel") == cid and v.get("status") in C.WAITING + C.WATCHING:
                v.update(status="skipped", note="channel_removed")
        C.log(data, "removed", cid)
        C.save(data)
    return _view()


@router.post("/api/channels/{cid:path}/check")
def api_check(cid: str) -> dict:
    res = _monitor.poll_one(cid)
    if res.get("gone"):
        raise SharkyClipsError("This channel isn't connected.")
    _monitor.poke()
    return {**_view(), "result": res}


@router.post("/api/channels/{cid:path}/import")
def api_import_recent(cid: str, body: dict) -> dict:
    with C._lock:
        data = C.load()
        if cid not in data["channels"]:
            raise SharkyClipsError("This channel isn't connected.")
        got = C.import_recent(data, cid, int(body.get("count") or 1), time.time())
        C.save(data)
    if not got:
        raise SharkyClipsError("There is no earlier stream to import.",
                               "Only streams the platform still keeps (with a public VOD) can be imported.")
    _monitor.poke()
    return {**_view(), "queued": got}


@router.post("/api/channels/vods/{key:path}/retry")
def api_vod_retry(key: str) -> dict:
    with C._lock:
        data = C.load()
        v = data["vods"].get(key)
        if v is None:
            raise SharkyClipsError("This stream isn't known.")
        if v.get("status") not in ("error", "gone", "skipped", "retry", "waiting_disk", "waiting_metered",
                                   "waiting_game"):
            raise SharkyClipsError("This stream is already being handled.")
        if not v.get("url"):
            raise SharkyClipsError("This stream has no VOD to download.")
        v.update(status="queued", attempts=0, next_try=None, note="retry", queued_at=time.time())
        v.pop("warned", None)
        C.save(data)
    _monitor.poke()
    return _view()


@router.post("/api/channels/vods/{key:path}/skip")
def api_vod_skip(key: str) -> dict:
    with C._lock:
        data = C.load()
        v = data["vods"].get(key)
        if v is None:
            raise SharkyClipsError("This stream isn't known.")
        if v.get("status") not in C.WAITING + C.WATCHING:
            raise SharkyClipsError("Only waiting streams can be skipped.")
        v.update(status="skipped", note="by_you", done_at=time.time())
        C.save(data)
    return _view()


def project_channel(project: Project) -> dict | None:
    """The Library's "from <channel> - <stream>" line."""
    info = channel_of(project)
    if not info:
        return None
    return {k: info.get(k) for k in ("platform", "name", "own", "stream_title", "started_at", "url")}
