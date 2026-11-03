"""Phone approval through your own Telegram bot (free, private, no server of ours).

Why Telegram: free, works on every phone, push notifications with photos and buttons, and the
bot API can be *polled* from this PC (getUpdates), so tapping a button works without any public
server or open port. The user creates a bot with @BotFather (1 minute), pastes its token, then
opens the bot and taps Start: that message carries a one-time pairing code, so only that chat
is accepted from then on. Everything else is ignored.

A ready clip is sent as: cover picture, title, viral label, buttons Upload / Plan / Skip and
Watch (sends the video itself when it is small enough for Telegram, 50 MB).

The token + chat id are stored encrypted (secretstore: DPAPI / Keychain): <settings>/telegram.enc.
SHARKYCLIPS_TG_ENDPOINT=http://127.0.0.1:<port> points at a fake API (tests; loopback only).
"""

from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from . import config, secretstore
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

API = "https://api.telegram.org"
VIDEO_LIMIT = 49 * 1024 * 1024

TEXT = {
    "en": {"upload": "⬆ Upload", "plan": "📅 Plan", "skip": "✖ Skip", "watch": "▶ Watch",
           "viral": "Viral", "hello": "SharkyClips is connected. Ready clips will show up here.",
           "uploading": "⬆ Uploading…", "planned": "📅 Planned: {when}", "skipped": "✖ Skipped",
           "done": "Already handled.", "too_big": "The video is too big for Telegram: watch it on your PC.",
           "test": "Test from SharkyClips 🦈 Everything works."},
    "tr": {"upload": "⬆ Yükle", "plan": "📅 Planla", "skip": "✖ Atla", "watch": "▶ İzle",
           "viral": "Viral", "hello": "SharkyClips bağlandı. Hazır klipler buraya gelecek.",
           "uploading": "⬆ Yükleniyor…", "planned": "📅 Planlandı: {when}", "skipped": "✖ Atlandı",
           "done": "Bu klip zaten işlendi.", "too_big": "Video Telegram için çok büyük: bilgisayarında izle.",
           "test": "SharkyClips'ten deneme 🦈 Her şey çalışıyor."},
    "de": {"upload": "⬆ Hochladen", "plan": "📅 Planen", "skip": "✖ Überspringen", "watch": "▶ Ansehen",
           "viral": "Viral", "hello": "SharkyClips ist verbunden. Fertige Clips erscheinen hier.",
           "uploading": "⬆ Wird hochgeladen…", "planned": "📅 Geplant: {when}", "skipped": "✖ Übersprungen",
           "done": "Schon erledigt.", "too_big": "Das Video ist zu groß für Telegram: sieh es am PC an.",
           "test": "Test von SharkyClips 🦈 Alles funktioniert."},
    "hu": {"upload": "⬆ Feltöltés", "plan": "📅 Ütemezés", "skip": "✖ Kihagy", "watch": "▶ Megnéz",
           "viral": "Virális", "hello": "A SharkyClips csatlakozott. A kész klipek itt jelennek meg.",
           "uploading": "⬆ Feltöltés…", "planned": "📅 Ütemezve: {when}", "skipped": "✖ Kihagyva",
           "done": "Már elintézve.", "too_big": "A videó túl nagy a Telegramhoz: nézd meg a gépen.",
           "test": "Teszt a SharkyClipstől 🦈 Minden működik."},
    "ru": {"upload": "⬆ Загрузить", "plan": "📅 В план", "skip": "✖ Пропустить", "watch": "▶ Смотреть",
           "viral": "Вирусность", "hello": "SharkyClips подключён. Готовые клипы будут приходить сюда.",
           "uploading": "⬆ Загружается…", "planned": "📅 В плане: {when}", "skipped": "✖ Пропущено",
           "done": "Уже сделано.", "too_big": "Видео слишком большое для Telegram: посмотрите на ПК.",
           "test": "Тест от SharkyClips 🦈 Всё работает."},
    "ar": {"upload": "⬆ رفع", "plan": "📅 جدولة", "skip": "✖ تخطي", "watch": "▶ مشاهدة",
           "viral": "الانتشار", "hello": "تم ربط SharkyClips. ستصلك المقاطع الجاهزة هنا.",
           "uploading": "⬆ جارٍ الرفع…", "planned": "📅 مجدول: {when}", "skipped": "✖ تم التخطي",
           "done": "تمت معالجته بالفعل.", "too_big": "الفيديو كبير جدًا على تيليجرام: شاهده على الكمبيوتر.",
           "test": "تجربة من SharkyClips 🦈 كل شيء يعمل."},
    "zh": {"upload": "⬆ 上传", "plan": "📅 排期", "skip": "✖ 跳过", "watch": "▶ 观看",
           "viral": "爆款度", "hello": "SharkyClips 已连接。剪辑好了会发到这里。",
           "uploading": "⬆ 正在上传…", "planned": "📅 已排期：{when}", "skipped": "✖ 已跳过",
           "done": "已经处理过了。", "too_big": "视频太大，无法通过 Telegram 发送：请在电脑上观看。",
           "test": "来自 SharkyClips 的测试 🦈 一切正常。"},
}


def t(key: str) -> str:
    lang = str(config.get("ui_language") or "en")
    return TEXT.get(lang, TEXT["en"]).get(key) or TEXT["en"][key]


def secret_path() -> Path:
    return config.config_dir() / "telegram.enc"


def cards_path() -> Path:
    return config.config_dir() / "phone_cards.json"


def _base() -> str:
    env = (os.environ.get("SHARKYCLIPS_TG_ENDPOINT") or "").rstrip("/")
    if env:
        from urllib.parse import urlparse

        if urlparse(env).hostname in ("127.0.0.1", "localhost", "::1"):
            return env
    return API


def _http():
    import requests

    return requests


_lock = threading.RLock()


def _load() -> dict:
    try:
        return secretstore.load(secret_path()) or {}
    except Exception:  # noqa: BLE001 - unreadable (another user / machine): start over
        return {}


def _save(data: dict) -> None:
    secretstore.save(secret_path(), data)


def call(method: str, token: str | None = None, http_timeout: float = 20, files: dict | None = None,
         **params) -> dict:
    """One Bot API call -> its result. params are the method's own (e.g. getUpdates "timeout")."""
    tok = token or _load().get("token")
    if not tok:
        raise SharkyClipsError("Telegram isn't set up.", "Settings > Phone: connect your bot.")
    try:
        if files:
            res = _http().post(f"{_base()}/bot{tok}/{method}", data=params, files=files, timeout=http_timeout)
        else:
            res = _http().post(f"{_base()}/bot{tok}/{method}", json=params, timeout=http_timeout)
    except Exception as exc:  # noqa: BLE001 - no internet
        raise SharkyClipsError("Couldn't reach Telegram.", "Check the internet connection and try again.") from exc
    try:
        data = res.json()
    except ValueError:
        data = {}
    if not data.get("ok"):
        desc = str(data.get("description") or res.status_code)
        if res.status_code in (401, 404):
            raise SharkyClipsError("Telegram doesn't know this bot token.",
                                   "Copy the token again from @BotFather (it looks like 123456:ABC...).")
        raise SharkyClipsError(f"Telegram said: {desc[:200]}")
    return data.get("result") or {}


# ===================================================================== setup


def status() -> dict:
    d = _load()
    return {"configured": bool(d.get("token")), "paired": bool(d.get("chat_id")), "bot": d.get("bot"),
            "chat": d.get("chat_name"), "link": d.get("link") if not d.get("chat_id") else None,
            "send": config.get("phone_send") is not False, "send_top": int(config.get("phone_send_top") or 3),
            "protection": secretstore.protection(secret_path()) if secret_path().is_file() else None}


def set_token(token: str) -> dict:
    token = token.strip()
    if ":" not in token or len(token) < 30 or " " in token:
        raise SharkyClipsError("That doesn't look like a bot token.",
                               "@BotFather sends it after /newbot: numbers, a colon, then letters (123456:ABC...).")
    me = call("getMe", token=token)
    code = secrets.token_hex(4)
    bot = me.get("username") or ""
    data = {"token": token, "bot": bot, "code": code, "link": f"https://t.me/{bot}?start={code}", "offset": 0}
    with _lock:
        _save(data)
    return status()


def pair_check() -> dict:
    """Look for the user's /start <code> message (sent by tapping Start in the bot)."""
    with _lock:
        d = _load()
        if not d.get("token") or d.get("chat_id"):
            return status()
        ups = call("getUpdates", http_timeout=15, offset=int(d.get("offset") or 0))
        for u in ups if isinstance(ups, list) else []:
            d["offset"] = int(u["update_id"]) + 1
            msg = u.get("message") or {}
            text = str(msg.get("text") or "")
            if text.strip() in (f"/start {d['code']}", d["code"]):
                chat = msg.get("chat") or {}
                d["chat_id"] = chat.get("id")
                d["chat_name"] = chat.get("first_name") or chat.get("username") or ""
        _save(d)
        if d.get("chat_id"):
            try:
                call("sendMessage", chat_id=d["chat_id"], text=t("hello"))
            except SharkyClipsError:
                pass
    return status()


def disconnect() -> None:
    with _lock:
        secret_path().unlink(missing_ok=True)
        cards_path().unlink(missing_ok=True)


def send_test() -> None:
    d = _load()
    if not d.get("chat_id"):
        raise SharkyClipsError("Pair your phone first.", "Open the bot on your phone and tap Start.")
    call("sendMessage", chat_id=d["chat_id"], text=t("test"))


# ===================================================================== clip cards


def _cards() -> dict:
    try:
        return read_json(cards_path()) if cards_path().is_file() else {}
    except (OSError, ValueError):
        return {}


def _save_cards(cards: dict) -> None:
    if len(cards) > 300:
        cards = dict(sorted(cards.items(), key=lambda kv: -float(kv[1].get("at") or 0))[:200])
    write_json_atomic(cards_path(), cards)


def card_for(project_id: str, clip_id: str) -> str | None:
    for tok, c in _cards().items():
        if c.get("project_id") == project_id and c.get("clip_id") == clip_id:
            return tok
    return None


def thumbnail(video: Path, at: float, dest: Path) -> Path:
    from .errors import require_tool
    from .procs import no_window

    ffmpeg = require_tool("ffmpeg")
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", f"{max(0.0, at):.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=540:-2", "-q:v", "4", str(dest)], capture_output=True, text=True, **no_window())
    if r.returncode != 0 or not dest.is_file():
        raise SharkyClipsError("Couldn't make the preview picture.", (r.stderr or "")[-200:] or None)
    return dest


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_clip(project_id: str, clip_id: str, video: Path, title: str, viral_label: str | None,
              viral_score: int | None, project_title: str, peak_at: float = 1.0) -> str | None:
    """Send one ready clip with its buttons. Returns the card token (None: not paired / sent before)."""
    d = _load()
    if not d.get("chat_id"):
        return None
    with _lock:
        if card_for(project_id, clip_id):
            return None  # never twice
        tok = secrets.token_hex(4)
        cards = _cards()
        cards[tok] = {"project_id": project_id, "clip_id": clip_id, "at": time.time(), "state": "sent"}
        _save_cards(cards)
    viral = ""
    if viral_score is not None:
        viral = f"\n🔥 {t('viral')}: {_esc(viral_label or '')} ({int(viral_score)}/100)"
    caption = f"<b>{_esc(title)[:200]}</b>{viral}\n<i>{_esc(project_title)[:80]}</i>"
    markup = {"inline_keyboard": [
        [{"text": t("upload"), "callback_data": f"u|{tok}"}, {"text": t("plan"), "callback_data": f"p|{tok}"},
         {"text": t("skip"), "callback_data": f"s|{tok}"}],
        [{"text": t("watch"), "callback_data": f"w|{tok}"}]]}
    import json

    with tempfile.TemporaryDirectory(prefix="sharkyclips-tg-") as tmp:
        img = thumbnail(video, peak_at, Path(tmp) / "cover.jpg")
        with open(img, "rb") as f:
            res = call("sendPhoto", http_timeout=60, files={"photo": ("cover.jpg", f, "image/jpeg")},
                       chat_id=str(d["chat_id"]), caption=caption, parse_mode="HTML",
                       reply_markup=json.dumps(markup))
    with _lock:
        cards = _cards()
        if tok in cards:
            cards[tok]["message_id"] = res.get("message_id")
            cards[tok]["caption"] = caption
            _save_cards(cards)
    return tok


# ===================================================================== the button poller


Action = Callable[[str, str, str], str]  # (action upload|plan|skip, project_id, clip_id) -> result text


class Poller:
    """Long-polls getUpdates while paired and runs the button actions."""

    def __init__(self, act: Action, video_for: Callable[[str, str], Path | None]):
        self.act = act
        self.video_for = video_for
        self.status = "off"
        self.error: str | None = None
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="sharkyclips-telegram", daemon=True)

    def start(self) -> "Poller":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        backoff = 3.0
        while not self._stop.is_set():
            d = _load()
            if not d.get("chat_id"):
                self.status = "not_paired"
                self._stop.wait(15)
                continue
            try:
                ups = self._get_updates(d)
                self.status, self.error = "on", None
                backoff = 3.0
                for u in ups:
                    self.handle(u, d)
            except SharkyClipsError as exc:
                self.status, self.error = "error", exc.message
                self._stop.wait(backoff)
                backoff = min(120.0, backoff * 2)

    def _get_updates(self, d: dict) -> list:
        ups = call("getUpdates", http_timeout=40, offset=int(d.get("offset") or 0), timeout=25,
                   allowed_updates=["callback_query", "message"])
        ups = ups if isinstance(ups, list) else []
        if ups:
            with _lock:
                cur = _load()
                cur["offset"] = max(int(cur.get("offset") or 0), max(int(u["update_id"]) for u in ups) + 1)
                _save(cur)
        return ups

    def handle(self, u: dict, d: dict) -> None:
        cq = u.get("callback_query")
        if not cq:
            return
        chat_id = ((cq.get("message") or {}).get("chat") or {}).get("id")
        if chat_id != d.get("chat_id") or (cq.get("from") or {}).get("id") != d.get("chat_id"):
            return  # only the paired chat may press the buttons
        data = str(cq.get("data") or "")
        kind, _, tok = data.partition("|")
        card = _cards().get(tok)
        answer = ""
        try:
            if card is None or kind not in ("u", "p", "s", "w"):
                answer = t("done")
            elif kind == "w":
                video = self.video_for(card["project_id"], card["clip_id"])
                if video is None or not video.is_file() or video.stat().st_size > VIDEO_LIMIT:
                    answer = t("too_big")
                else:
                    with open(video, "rb") as f:
                        call("sendVideo", http_timeout=300, files={"video": (video.name, f, "video/mp4")},
                             chat_id=str(d["chat_id"]), reply_to_message_id=str(card.get("message_id") or ""),
                             supports_streaming="true")
            elif card.get("state") != "sent":
                answer = t("done")
            else:
                action = {"u": "upload", "p": "plan", "s": "skip"}[kind]
                result = self.act(action, card["project_id"], card["clip_id"])
                with _lock:
                    cards = _cards()
                    if tok in cards:
                        cards[tok]["state"] = action
                        _save_cards(cards)
                answer = result
                if card.get("message_id"):
                    try:
                        call("editMessageCaption", chat_id=d["chat_id"], message_id=card["message_id"],
                             caption=(card.get("caption") or "") + f"\n\n<b>{_esc(result)}</b>", parse_mode="HTML")
                    except SharkyClipsError:
                        pass
        except SharkyClipsError as exc:
            answer = exc.message + (f" {exc.hint}" if exc.hint else "")
        try:
            call("answerCallbackQuery", callback_query_id=cq.get("id"), text=answer[:190], show_alert=bool(answer))
        except SharkyClipsError:
            pass
