"""TikTok and Instagram Reels (1.2.18), next to YouTube.

Two ways to post, and the app always says which one is active:
  semi  (default) the clip is exported with the platform's preset into Downloads/SharkyClips, the
        caption + hashtags go to the clipboard and the platform's upload page opens: you drop the
        file in and press Post. Works for everyone, no account linking.
  api   automatic, through the official APIs, after a guided setup with YOUR OWN developer app:
        TikTok Content Posting API (Login Kit + PKCE, loopback redirect), Instagram Graph API
        (Instagram Login token "IGAA..." of a Business / Creator account on graph.instagram.com, or
        since 1.2.37 a Facebook-side token "EAA..." - Business portfolio system user, "API setup with
        unified login" - on graph.facebook.com; resumable Reels upload either way).
        Both platforms review apps first: until TikTok approves yours, its posts are private
        ("Only me"); until Meta approves yours, only the app's own accounts can post.

Tokens are kept encrypted (secretstore) in <settings>/platforms/<name>/token.enc.
Tests point the API hosts at fake servers: SHARKYCLIPS_TIKTOK_ENDPOINT / SHARKYCLIPS_IG_ENDPOINT /
SHARKYCLIPS_FB_ENDPOINT (loopback only).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urlparse

from . import config, secretstore
from .errors import SharkyClipsError

PLATFORMS = ("youtube", "tiktok", "reels")
PRESET = {"tiktok": "tiktok", "reels": "instagram_reels", "youtube": "youtube_shorts"}
UPLOAD_PAGE = {"tiktok": "https://www.tiktok.com/tiktokstudio/upload",
               "reels": "https://www.instagram.com/"}
CAPTION_MAX = {"tiktok": 2200, "reels": 2200}
HASHTAG_MAX = {"tiktok": 10, "reels": 30}
TIKTOK_SCOPES = "user.info.basic,video.publish,video.list"  # video.list: views of your posts (1.2.36)
CHUNK = 10 * 1024 * 1024
ProgressFn = Callable[[float], None]


def _endpoint(env: str, default: str) -> str:
    url = os.environ.get(env)
    if url:
        host = urlparse(url).hostname or ""
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise SharkyClipsError(f"{env} may only point at this computer.")
        return url.rstrip("/")
    return default


def tiktok_api() -> str:
    return _endpoint("SHARKYCLIPS_TIKTOK_ENDPOINT", "https://open.tiktokapis.com")


def tiktok_auth_url() -> str:
    return _endpoint("SHARKYCLIPS_TIKTOK_ENDPOINT", "https://www.tiktok.com")


def ig_api() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://graph.instagram.com")


def ig_upload_api() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://rupload.facebook.com")


IG_VERSION = "v21.0"
FB_VERSION = "v24.0"


def fb_api() -> str:
    return _endpoint("SHARKYCLIPS_FB_ENDPOINT", "https://graph.facebook.com")


def _ig_graph(tok: dict) -> str:
    """The Graph API a saved Instagram token talks to: graph.facebook.com for a Facebook-side token
    (EAA...), graph.instagram.com for an Instagram Login token (IGAA...)."""
    if tok.get("graph") == "facebook":
        return f"{fb_api()}/{FB_VERSION}"
    return f"{ig_api()}/{IG_VERSION}"


def _ig_upload_url(tok: dict, container: str) -> str:
    version = FB_VERSION if tok.get("graph") == "facebook" else IG_VERSION
    return f"{ig_upload_api()}/ig-api-upload/{version}/{container}"


def _http():
    import requests

    return requests


def folder(name: str) -> Path:
    return config.config_dir() / "platforms" / name


def _token_path(name: str) -> Path:
    return folder(name) / "token.enc"


def load_token(name: str) -> dict | None:
    return secretstore.load(_token_path(name))


def save_token(name: str, data: dict) -> None:
    folder(name).mkdir(parents=True, exist_ok=True)
    secretstore.save(_token_path(name), data)


def forget(name: str, everything: bool = True) -> None:
    """Sign out. everything=False (Disconnect in Accounts) keeps your developer app's keys, so
    Reconnect is one click."""
    _token_path(name).unlink(missing_ok=True)
    for f in ("avatar.jpg", "problem.json", "quota.json"):
        (folder(name) / f).unlink(missing_ok=True)
    _creator_cache.clear()
    if everything:
        (folder(name) / "app.enc").unlink(missing_ok=True)


def load_app(name: str) -> dict | None:
    return secretstore.load(folder(name) / "app.enc")


def save_app(name: str, data: dict) -> None:
    folder(name).mkdir(parents=True, exist_ok=True)
    secretstore.save(folder(name) / "app.enc", data)


# ===================================================================== status / mode


def connected(name: str) -> bool:
    tok = load_token(name)
    return bool(tok and tok.get("access_token"))


def mode(name: str) -> str:
    """'api' only when connected AND the user turned automatic posting on; else 'semi'."""
    if name == "youtube":
        return "api"
    want = (config.get("platform_modes") or {}).get(name)
    return "api" if want == "api" and connected(name) else "semi"


def status(name: str) -> dict:
    tok = load_token(name) or {}
    app = load_app(name) or {}
    out = {"platform": name, "mode": mode(name), "connected": bool(tok.get("access_token")),
           "account": tok.get("account"), "audited": bool(app.get("audited")),
           "has_app": bool(app.get("client_key") or app.get("app_id") or name == "reels"),
           "upload_page": UPLOAD_PAGE.get(name), "preset": PRESET[name]}
    if name == "tiktok":
        out["privacy_note"] = "self_only" if not app.get("audited") else None
    if name == "reels":
        out["privacy_note"] = "app_review" if not app.get("audited") else None
        out["expires_at"] = tok.get("expires_at")
    return out


def set_mode(name: str, value: str) -> dict:
    if name not in ("tiktok", "reels") or value not in ("semi", "api"):
        raise SharkyClipsError("Unknown platform or mode.")
    if value == "api" and not connected(name):
        raise SharkyClipsError("Connect the account first.", "Follow the guided setup, or keep the semi-automatic mode.")
    modes = dict(config.get("platform_modes") or {})
    modes[name] = value
    config.update(platform_modes=modes)
    return status(name)


def set_audited(name: str, audited: bool) -> dict:
    app = load_app(name) or {}
    app["audited"] = bool(audited)
    save_app(name, app)
    return status(name)


# ===================================================================== captions


def caption(platform: str, title: str, description: str, hashtags: list[str], note: str | None = None,
            socials: str = "") -> str:
    """Title + the first line of the description (+ `note`, e.g. the AI-voice line) + hashtags
    + the channel's socials block, within the platform's limits. The note is never cut off; a
    tight caption drops socials lines from the bottom (a link is never cut), then shortens the body."""
    from .youtube import _has_swear, censor_text

    title, description = censor_text(title, None), censor_text(description, None)
    hashtags = [h for h in hashtags if not _has_swear(str(h), None)]
    tags = []
    for h in hashtags:
        h = "#" + str(h).lstrip("#").strip()
        if len(h) > 1 and h.lower() not in (t.lower() for t in tags):
            tags.append(h)
    tags = tags[: HASHTAG_MAX.get(platform, 10)]
    first = next((ln.strip() for ln in (description or "").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")), "")
    body = title.strip()
    if first and first.lower() != body.lower():
        body += "\n\n" + first
    extra = f"\n\n{note.strip()}" if note and note.strip() else ""
    tail = ("\n\n" + " ".join(tags)) if tags else ""
    limit = CAPTION_MAX.get(platform, 2200)
    block = ""
    if socials and socials.strip():
        from .edit import brand

        block = brand.fit_block(socials.strip(), limit - len((body + extra + tail).strip()) - 2)
    text = (body + extra + tail + (f"\n\n{block}" if block else "")).strip()
    if len(text) > limit:
        text = body[: max(0, limit - len(extra) - len(tail) - 1)].rstrip() + "…" + extra + tail
    return text


# ===================================================================== TikTok


_pending: dict[str, dict] = {}
_plock = threading.Lock()


def tiktok_redirect(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/platforms/tiktok/callback"


def tiktok_start(client_key: str, client_secret: str, port: int) -> str:
    """Save the user's app and return the TikTok sign-in URL (PKCE)."""
    client_key, client_secret = client_key.strip(), client_secret.strip()
    saved = load_app("tiktok") or {}
    if not client_key and not client_secret and saved.get("client_key"):  # Reconnect: the saved app
        client_key, client_secret = saved["client_key"], saved.get("client_secret") or ""
    if not client_key or not client_secret:
        raise SharkyClipsError("Enter the Client key and Client secret of your TikTok app.",
                               "developers.tiktok.com -> Manage apps -> your app -> Credentials.")
    app = load_app("tiktok") or {}
    save_app("tiktok", {**app, "client_key": client_key, "client_secret": client_secret})
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    with _plock:
        _pending.clear()
        _pending[state] = {"verifier": verifier, "redirect": tiktok_redirect(port), "at": time.time()}
    q = {"client_key": client_key, "scope": TIKTOK_SCOPES, "response_type": "code",
         "redirect_uri": tiktok_redirect(port), "state": state, "code_challenge": challenge,
         "code_challenge_method": "S256"}
    return f"{tiktok_auth_url()}/v2/auth/authorize/?{urlencode(q)}"


def tiktok_finish(code: str, state: str) -> dict:
    with _plock:
        p = _pending.pop(state, None)
    if p is None or time.time() - p["at"] > 900:
        raise SharkyClipsError("This TikTok sign-in expired.", "Start the connection again.")
    app = load_app("tiktok") or {}
    r = _http().post(f"{tiktok_api()}/v2/oauth/token/", timeout=30, data={
        "client_key": app.get("client_key"), "client_secret": app.get("client_secret"), "code": code,
        "grant_type": "authorization_code", "redirect_uri": p["redirect"], "code_verifier": p["verifier"]})
    tok = _tiktok_json(r, "sign-in")
    _save_tiktok_token(tok)
    try:
        info = tiktok_call("GET", "/v2/user/info/?fields=open_id,display_name,avatar_url")
        user = (info.get("data") or {}).get("user") or {}
        name = user.get("display_name")
        save_avatar("tiktok", user.get("avatar_url"))
    except SharkyClipsError:
        name = None
    t = load_token("tiktok") or {}
    t["account"] = name
    t["connected_at"] = time.time()
    save_token("tiktok", t)
    note_problem("tiktok", None)
    _creator_cache.clear()
    try:
        tiktok_creator_info(fresh=True)  # handle + avatar
    except SharkyClipsError:
        pass
    return status("tiktok")


def _save_tiktok_token(tok: dict) -> None:
    now = time.time()
    old = load_token("tiktok") or {}
    save_token("tiktok", {**old, "access_token": tok["access_token"],
                          "refresh_token": tok.get("refresh_token") or old.get("refresh_token"),
                          "expires_at": now + float(tok.get("expires_in") or 86400),
                          "refresh_expires_at": now + float(tok.get("refresh_expires_in") or 31536000),
                          "scope": tok.get("scope") or old.get("scope") or "", "open_id": tok.get("open_id")})


def _tiktok_json(r, what: str) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    err = d.get("error")
    if isinstance(err, dict):
        code, msg = err.get("code"), err.get("message")
    else:
        code, msg = err, d.get("error_description")
    if r.status_code >= 400 or (code and code != "ok"):
        raise api_error("tiktok", f"TikTok refused the {what}: {msg or code or r.status_code}.",
                        _tiktok_hint(str(code)), str(code or r.status_code), r.status_code)
    return d


def _tiktok_hint(code: str) -> str | None:
    return {
        "access_token_invalid": "Connect TikTok again in Settings.",
        "scope_not_authorized": "Your TikTok app needs the Content Posting API with video.publish: add it in the developer portal.",
        "unaudited_client_can_only_post_to_private_accounts": "Until TikTok reviews your app, set your TikTok account to private or use the semi-automatic mode.",
        "spam_risk_too_many_posts": "TikTok's daily posting limit is reached: try again tomorrow.",
        "rate_limit_exceeded": "Too many requests: wait a minute and try again.",
        "invalid_grant": "Connect TikTok again in Settings.",
        "reached_active_user_cap": "TikTok lets an app that isn't reviewed yet post for 5 accounts a day: try again tomorrow.",
        "privacy_level_option_mismatch": "Pick who can see the video again: TikTok changed the choices.",
        "access_token_expired": "Connect TikTok again in Settings.",
        "url_ownership_unverified": None,
    }.get(code)


def _tiktok_access() -> str:
    tok = load_token("tiktok")
    if not tok or not tok.get("access_token"):
        raise SharkyClipsError("TikTok isn't connected.", "Connect it in Settings, or use the semi-automatic mode.")
    if tok.get("expires_at", 0) - time.time() < 120:
        refresh_tiktok()
        tok = load_token("tiktok") or {}
    return tok["access_token"]


def refresh_tiktok() -> None:
    """New access token from the refresh token (TikTok: 24 h access, 365 days refresh)."""
    tok = load_token("tiktok") or {}
    app = load_app("tiktok") or {}
    try:
        r = _http().post(f"{tiktok_api()}/v2/oauth/token/", timeout=30, data={
            "client_key": app.get("client_key"), "client_secret": app.get("client_secret"),
            "grant_type": "refresh_token", "refresh_token": tok.get("refresh_token")})
        _save_tiktok_token(_tiktok_json(r, "refresh"))
        note_problem("tiktok", None)
    except SharkyClipsError as exc:
        if getattr(exc, "code", "") in ("invalid_grant", "access_token_invalid", "400", "401"):
            note_problem("tiktok", "signed_out", exc.message)
        raise


def tiktok_call(method: str, path: str, body: dict | None = None) -> dict:
    """One API call; an access token TikTok says is invalid / expired is refreshed once."""
    for attempt in (1, 2):
        r = _http().request(method, f"{tiktok_api()}{path}", timeout=60, json=body,
                            headers={"Authorization": f"Bearer {_tiktok_access()}",
                                     "Content-Type": "application/json; charset=UTF-8"})
        try:
            return _tiktok_json(r, "request")
        except SharkyClipsError as exc:
            if attempt == 1 and getattr(exc, "code", "") in ("access_token_invalid", "access_token_expired"):
                refresh_tiktok()
                continue
            raise
    raise SharkyClipsError("TikTok request failed.")


def tiktok_post(file: Path, text: str, on_progress: ProgressFn | None = None,
                poll: float = 3.0, cancel: threading.Event | None = None, ai_label: bool = False) -> dict:
    """Direct Post (FILE_UPLOAD) -> {"publish_id", "status", "privacy"}. Private until audited.
    ai_label: TikTok's "AI-generated content" label (post_info.is_aigc, 1.2.20)."""
    info = tiktok_call("POST", "/v2/post/publish/creator_info/query/")
    opts = (info.get("data") or {}).get("privacy_level_options") or ["SELF_ONLY"]
    audited = bool((load_app("tiktok") or {}).get("audited"))
    privacy = "PUBLIC_TO_EVERYONE" if audited and "PUBLIC_TO_EVERYONE" in opts else "SELF_ONLY"
    if privacy not in opts:
        privacy = opts[0]
    size = file.stat().st_size
    chunk = size if size <= 64 * 1024 * 1024 else CHUNK
    count = max(1, size // chunk)
    post_info = {"title": text[:2200], "privacy_level": privacy, "disable_comment": False,
                 "disable_duet": False, "disable_stitch": False}
    if ai_label:
        post_info["is_aigc"] = True
    init = tiktok_call("POST", "/v2/post/publish/video/init/", {
        "post_info": post_info,
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
    data = init.get("data") or {}
    url, pid = data.get("upload_url"), data.get("publish_id")
    if not url or not pid:
        raise SharkyClipsError("TikTok didn't give an upload address.", "Try again later.")
    with open(file, "rb") as f:
        for i in range(count):
            a = i * chunk
            b = size - 1 if i == count - 1 else a + chunk - 1
            f.seek(a)
            part = f.read(b - a + 1)
            r = _http().put(url, data=part, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                "Content-Range": f"bytes {a}-{b}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise SharkyClipsError(f"TikTok stopped the upload ({r.status_code}).", "Try again later.")
            if on_progress:
                on_progress(0.9 * (b + 1) / size)
    end = time.time() + 600
    while time.time() < end:
        if cancel is not None and cancel.is_set():
            break
        st = tiktok_call("POST", "/v2/post/publish/status/fetch/", {"publish_id": pid})
        s = (st.get("data") or {}).get("status")
        if s in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            if on_progress:
                on_progress(1.0)
            return {"publish_id": pid, "status": "published", "privacy": privacy.lower()}
        if s == "FAILED":
            reason = (st.get("data") or {}).get("fail_reason") or "unknown"
            raise SharkyClipsError(f"TikTok couldn't publish the video ({reason}).", _tiktok_hint(reason))
        time.sleep(poll)
    return {"publish_id": pid, "status": "processing", "privacy": privacy.lower()}


# ===================================================================== Instagram


_IG_TEXT = {
    "en": {"bad_token": ("Meta didn't accept this access token.",
                         "Copy it again in full (it starts with EAA or IGAA) and paste it as it is."),
           "no_account": ("This token doesn't reach any Instagram professional account.",
                          "Business settings → System users → assign the Instagram account (full control), then "
                          "generate the token again with instagram_basic and instagram_content_publish."),
           "wrong_account": ("This token belongs to another account: it can't post to {account}.",
                             "Generate the token for {account} (business portfolio → system user → assigned "
                             "assets), or leave the account field empty to connect the token's own account."),
           "no_publish": ("This token sees {account} but isn't allowed to post to it.",
                          "Generate the token again with instagram_content_publish (and instagram_manage_insights "
                          "for views).")},
    "tr": {"bad_token": ("Meta bu erişim token'ını kabul etmedi.",
                         "Token'ı baştan sona yeniden kopyala (EAA veya IGAA ile başlar) ve olduğu gibi yapıştır."),
           "no_account": ("Bu token hiçbir Instagram profesyonel hesabına erişemiyor.",
                          "İşletme ayarları → Sistem kullanıcıları → Instagram hesabını ata (tam kontrol), sonra "
                          "token'ı instagram_basic ve instagram_content_publish izinleriyle yeniden oluştur."),
           "wrong_account": ("Bu token başka bir hesaba ait: {account} hesabına paylaşım yapamaz.",
                             "Token'ı {account} için oluştur (işletme portföyü → sistem kullanıcısı → atanan "
                             "varlıklar) ya da hesap alanını boş bırak, token'ın kendi hesabı bağlansın."),
           "no_publish": ("Bu token {account} hesabını görüyor ama paylaşım iznine sahip değil.",
                          "Token'ı instagram_content_publish izniyle yeniden oluştur (görüntülenmeler için "
                          "instagram_manage_insights da ekle).")},
    "de": {"bad_token": ("Meta hat dieses Zugriffstoken nicht angenommen.",
                         "Kopiere es noch einmal vollständig (es beginnt mit EAA oder IGAA) und füge es unverändert ein."),
           "no_account": ("Dieses Token erreicht kein professionelles Instagram-Konto.",
                          "Unternehmenseinstellungen → Systemnutzer → Instagram-Konto zuweisen (volle Kontrolle), "
                          "dann das Token mit instagram_basic und instagram_content_publish neu erstellen."),
           "wrong_account": ("Dieses Token gehört zu einem anderen Konto: es kann nicht auf {account} posten.",
                             "Erstelle das Token für {account} oder lass das Kontofeld leer, um das Konto des "
                             "Tokens zu verbinden."),
           "no_publish": ("Dieses Token sieht {account}, darf dort aber nicht posten.",
                          "Erstelle das Token mit instagram_content_publish neu (und instagram_manage_insights "
                          "für Aufrufe).")},
    "hu": {"bad_token": ("A Meta nem fogadta el ezt a hozzáférési tokent.",
                         "Másold ki újra teljes egészében (EAA vagy IGAA az eleje), és illeszd be változatlanul."),
           "no_account": ("Ez a token egyetlen Instagram szakmai fiókot sem ér el.",
                          "Vállalati beállítások → Rendszerfelhasználók → rendeld hozzá az Instagram-fiókot (teljes "
                          "hozzáférés), majd hozd létre újra a tokent instagram_basic és instagram_content_publish "
                          "engedéllyel."),
           "wrong_account": ("Ez a token egy másik fiókhoz tartozik: nem tud posztolni ide: {account}.",
                             "Hozd létre a tokent ehhez: {account}, vagy hagyd üresen a fiók mezőt, hogy a token "
                             "saját fiókja kapcsolódjon."),
           "no_publish": ("Ez a token látja ezt: {account}, de nem posztolhat oda.",
                          "Hozd létre újra a tokent instagram_content_publish engedéllyel (a megtekintésekhez "
                          "instagram_manage_insights is kell).")},
    "ru": {"bad_token": ("Meta не приняла этот токен доступа.",
                         "Скопируйте его ещё раз целиком (он начинается с EAA или IGAA) и вставьте как есть."),
           "no_account": ("Этот токен не даёт доступа ни к одному профессиональному аккаунту Instagram.",
                          "Настройки компании → Системные пользователи → назначьте аккаунт Instagram (полный "
                          "доступ), затем создайте токен заново с instagram_basic и instagram_content_publish."),
           "wrong_account": ("Этот токен принадлежит другому аккаунту: он не может публиковать в {account}.",
                             "Создайте токен для {account} или оставьте поле аккаунта пустым, чтобы подключить "
                             "аккаунт самого токена."),
           "no_publish": ("Этот токен видит {account}, но не может публиковать.",
                          "Создайте токен заново с instagram_content_publish (и instagram_manage_insights для "
                          "просмотров).")},
    "ar": {"bad_token": ("لم تقبل Meta رمز الوصول هذا.",
                         "انسخه مرة أخرى كاملًا (يبدأ بـ EAA أو IGAA) والصقه كما هو."),
           "no_account": ("هذا الرمز لا يصل إلى أي حساب Instagram احترافي.",
                          "إعدادات الأعمال ← مستخدمو النظام ← عيّن حساب Instagram (تحكم كامل)، ثم أنشئ الرمز من "
                          "جديد مع instagram_basic و instagram_content_publish."),
           "wrong_account": ("هذا الرمز يخص حسابًا آخر: لا يمكنه النشر على {account}.",
                             "أنشئ الرمز لـ {account}، أو اترك حقل الحساب فارغًا لربط حساب الرمز نفسه."),
           "no_publish": ("هذا الرمز يرى {account} لكنه لا يملك إذن النشر.",
                          "أنشئ الرمز من جديد مع instagram_content_publish (و instagram_manage_insights للمشاهدات).")},
    "zh": {"bad_token": ("Meta 不接受这个访问令牌。",
                         "请重新完整复制（以 EAA 或 IGAA 开头）并原样粘贴。"),
           "no_account": ("这个令牌无法访问任何 Instagram 专业账号。",
                          "商务设置 → 系统用户 → 分配该 Instagram 账号（完全控制），然后用 instagram_basic 和 "
                          "instagram_content_publish 重新生成令牌。"),
           "wrong_account": ("这个令牌属于另一个账号：不能发布到 {account}。",
                             "为 {account} 生成令牌，或把账号栏留空以连接令牌自己的账号。"),
           "no_publish": ("这个令牌能看到 {account}，但没有发布权限。",
                          "用 instagram_content_publish 重新生成令牌（查看次数还需 instagram_manage_insights）。")},
}


def _ig_error(key: str, **kw) -> SharkyClipsError:
    """A connection error in the UI language (the user reads it while setting the account up)."""
    lang = str(config.get("ui_language") or "en")
    msg, hint = (_IG_TEXT.get(lang) or _IG_TEXT["en"])[key]
    return SharkyClipsError(msg.format(**kw), hint.format(**kw))


def clean_token(token: str) -> str:
    """A pasted token without spaces, line breaks, quotes, "Bearer " or the access_token= around it."""
    t = str(token or "")
    m = re.search(r"access_token=([^&\s]+)", t)
    if m:
        t = m.group(1)
    t = re.sub(r"\s+", "", t).strip("\"'`<>")
    for prefix in ("Bearer", "OAuth"):
        t = t.removeprefix(prefix)
    return t


def token_kind(token: str) -> str | None:
    """facebook (EAA..., graph.facebook.com) | instagram (IGAA... / IGQ..., graph.instagram.com) | None."""
    if token.startswith("EAA"):
        return "facebook"
    if token.startswith("IG"):
        return "instagram"
    return None


def _wanted(account: str | None) -> tuple[str | None, str | None]:
    """The optional account field: an Instagram user id (digits) or a @username / profile link."""
    a = (account or "").strip()
    if not a:
        return None, None
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", a)
    if m:
        a = m.group(1)
    a = a.lstrip("@").strip("/")
    return (a, None) if a.isdigit() else (None, a.lower())


def ig_connect(token: str, account: str | None = None) -> dict:
    """Check a pasted Instagram access token and keep it: an Instagram Login token (IGAA...) or a
    Facebook-side one (EAA..., e.g. a business portfolio's system user). `account` (optional): the
    Instagram account it must post to (user id or @username)."""
    token = clean_token(token)
    if len(token) < 20:
        raise SharkyClipsError("Paste the long access token of your Instagram app.",
                               "Meta for Developers -> your app -> Instagram -> API setup -> Generate token.")
    kind = token_kind(token)
    if kind == "facebook":
        return _fb_connect(token, account)
    if kind == "instagram":
        return _ig_save(token, 60 * 86400, account)
    try:  # unknown prefix: Instagram first, then the Facebook side
        return _ig_save(token, 60 * 86400, account)
    except PlatformError as exc:
        if exc.kind != "auth":
            raise
    return _fb_connect(token, account)


def _check_wanted(account: str | None, uid: str, username: str | None) -> None:
    want_id, want_name = _wanted(account)
    if (want_id and want_id != uid) or (want_name and want_name != (username or "").lower()):
        raise _ig_error("wrong_account", account="@" + want_name if want_name else want_id)


def _ig_save(token: str, expires_in: float, account: str | None = None) -> dict:
    r = _http().get(f"{ig_api()}/{IG_VERSION}/me", timeout=30,
                    params={"fields": "user_id,username,account_type,profile_picture_url", "access_token": token})
    d = _ig_json(r, "connection")
    kind = (d.get("account_type") or "").upper()
    if kind and kind not in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
        raise SharkyClipsError("Instagram only lets Business or Creator accounts post through its API.",
                               "Switch the account to Creator in the Instagram app (Settings → Account type).")
    uid = str(d.get("user_id") or d.get("id"))
    _check_wanted(account, uid, d.get("username"))
    save_token("reels", {"access_token": token, "graph": "instagram", "user_id": uid,
                         "account": d.get("username"), "saved_at": time.time(), "connected_at": time.time(),
                         "expires_at": time.time() + float(expires_in or 60 * 86400)})
    if load_app("reels") is None:
        save_app("reels", {"audited": False})
    note_problem("reels", None)
    save_avatar("reels", d.get("profile_picture_url"))
    return status("reels")


IG_FIELDS = "id,username,profile_picture_url"


def _fb_get(path: str, token: str, what: str, **params) -> dict:
    r = _http().get(f"{fb_api()}/{FB_VERSION}/{path.lstrip('/')}", timeout=30,
                    params={**params, "access_token": token})
    return _ig_json(r, what)


def _fb_ig_accounts(token: str) -> list[dict]:
    """The Instagram professional accounts a Facebook-side token reaches: through its Pages, and
    through the Pages of its business portfolios (a system user's assigned assets)."""
    found: dict[str, dict] = {}

    def add(pages):
        for pg in pages or []:
            ig = (pg or {}).get("instagram_business_account") or {}
            if ig.get("id"):
                found.setdefault(str(ig["id"]), ig)

    sub = f"instagram_business_account{{{IG_FIELDS}}}"
    try:
        add(_fb_get("me/accounts", token, "check", fields=f"name,{sub}", limit="100").get("data"))
    except SharkyClipsError:
        pass
    if not found:
        try:
            biz = _fb_get("me/businesses", token, "check",
                          fields=f"owned_pages{{{sub}}},client_pages{{{sub}}}", limit="25").get("data") or []
            for b in biz:
                for edge in ("owned_pages", "client_pages"):
                    add(((b or {}).get(edge) or {}).get("data"))
        except SharkyClipsError:
            pass
    return list(found.values())


def _fb_connect(token: str, account: str | None = None) -> dict:
    """A Facebook-side token (EAA...): find its Instagram account, check it may post there, keep it.
    System-user tokens never expire (nothing to refresh); a revoked one shows up as signed out."""
    try:
        _fb_get("me", token, "connection", fields="id,name")
    except PlatformError as exc:
        if exc.kind == "auth":
            raise _ig_error("bad_token") from exc
        raise
    info: dict = {}
    try:
        info = _fb_get("debug_token", token, "check", input_token=token).get("data") or {}
    except SharkyClipsError:
        pass
    want_id, want_name = _wanted(account)
    accounts = _fb_ig_accounts(token)
    old = load_token("reels") or {}
    target = None
    if want_id:
        target = want_id
    elif want_name:
        target = next((str(a["id"]) for a in accounts if (a.get("username") or "").lower() == want_name), None)
        if target is None:
            raise _ig_error("wrong_account" if accounts else "no_account", account="@" + want_name)
    elif accounts:
        ids = [str(a["id"]) for a in accounts]
        target = old.get("user_id") if old.get("user_id") in ids else ids[0]
    if not target:
        raise _ig_error("no_account")
    label = "@" + want_name if want_name else target
    try:
        ig = _fb_get(target, token, "connection", fields=IG_FIELDS)
    except PlatformError as exc:
        raise _ig_error("wrong_account", account=label) from exc
    label = "@" + ig["username"] if ig.get("username") else label
    try:  # posting rights: the publishing limit needs instagram_content_publish on this account
        _fb_get(f"{target}/content_publishing_limit", token, "check", fields="quota_usage")
    except PlatformError as exc:
        if exc.kind in ("auth", "fatal"):
            raise _ig_error("no_publish", account=label) from exc
    scopes = info.get("scopes") or []
    expires = float(info.get("expires_at") or 0)  # 0: never (system user)
    save_token("reels", {"access_token": token, "graph": "facebook", "user_id": str(ig.get("id") or target),
                         "account": ig.get("username"), "handle": ig.get("username"), "saved_at": time.time(),
                         "connected_at": time.time(), "expires_at": expires if expires > time.time() else 0,
                         "token_type": info.get("type"),
                         "scope": ",".join(scopes) if isinstance(scopes, list) else ""})
    if load_app("reels") is None:
        save_app("reels", {"audited": False})
    note_problem("reels", None)
    save_avatar("reels", ig.get("profile_picture_url"))
    return status("reels")


def _ig_json(r, what: str) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400 or "error" in d:
        e = d.get("error") or {}
        if not isinstance(e, dict):
            e = {"message": str(e)}
        code, sub = e.get("code"), e.get("error_subcode")
        hint = {190: "The sign-in expired or was revoked: connect Instagram again in Settings.",
                10: "Your Meta app lacks the instagram_business_content_publish permission.",
                200: "Your Meta app lacks the instagram_business_content_publish permission.",
                9007: "Instagram is still processing the video: try again in a minute.",
                4: "Instagram's hourly limit is reached: SharkyClips tries again by itself.",
                17: "Instagram's hourly limit is reached: SharkyClips tries again by itself.",
                32: "Instagram's hourly limit is reached: SharkyClips tries again by itself.",
                613: "Instagram's hourly limit is reached: SharkyClips tries again by itself.",
                }.get(code)
        if code == 9 and sub == 2207042:
            hint = "Instagram allows a limited number of API posts per 24 hours: it goes out when there's room again."
        tag = f"{code}:{sub}" if sub else str(code if code is not None else r.status_code)
        raise api_error("reels", f"Instagram refused the {what}: {e.get('message') or r.status_code}.", hint, tag,
                        r.status_code)
    return d


def _ig_token() -> dict:
    tok = load_token("reels")
    if not tok or not tok.get("access_token"):
        raise SharkyClipsError("Instagram isn't connected.", "Connect it in Settings → Accounts.")
    if float(tok.get("expires_at") or 0) and float(tok["expires_at"]) < time.time():
        note_problem("reels", "signed_out", "The Instagram sign-in expired.")
        raise api_error("reels", "The Instagram sign-in expired.", "Connect Instagram again in Settings → Accounts.",
                        "190", 401)
    if tok.get("graph") != "facebook" and time.time() - float(tok.get("saved_at") or 0) > IG_REFRESH_AFTER:
        # Instagram Login tokens last 60 days: refreshed weekly (Facebook-side system-user tokens don't expire)
        try:
            refresh_ig()
            tok = load_token("reels") or tok
        except SharkyClipsError:
            pass  # still valid for a while; the next post / health check tries again
    return tok


IG_REFRESH_AFTER = 7 * 86400


def refresh_ig() -> None:
    tok = load_token("reels") or {}
    if tok.get("graph") == "facebook":
        return  # nothing to refresh: a system-user token doesn't expire
    r = _http().get(f"{ig_api()}/refresh_access_token", timeout=30,
                    params={"grant_type": "ig_refresh_token", "access_token": tok.get("access_token")})
    try:
        d = _ig_json(r, "token refresh")
    except SharkyClipsError as exc:
        if str(getattr(exc, "code", "")).startswith("190"):
            note_problem("reels", "signed_out", exc.message)
        raise
    tok.update(access_token=d["access_token"], saved_at=time.time(),
               expires_at=time.time() + float(d.get("expires_in") or 60 * 86400))
    save_token("reels", tok)
    note_problem("reels", None)


def ig_post(file: Path, text: str, on_progress: ProgressFn | None = None, poll: float = 3.0,
            cancel: threading.Event | None = None, ai_label: bool = False) -> dict:
    """Reels upload: container (resumable) -> bytes to rupload -> wait FINISHED -> publish.
    ai_label: Instagram's AI self-disclosure (is_ai_generated, 1.2.20)."""
    cid = ig_container(text, ai_label)
    ig_send(file, cid)
    if on_progress:
        on_progress(0.8)
    end = time.time() + 900
    while True:
        if cancel is not None and cancel.is_set():
            raise SharkyClipsError("Cancelled.")
        st = ig_container_status(cid)
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise SharkyClipsError("Instagram couldn't process the video.",
                                   "Reels need MP4 H.264, 3-180 s; the Reels preset makes that. Try again.")
        if time.time() > end:
            raise SharkyClipsError("Instagram is taking too long with this video.", "Try again later.")
        time.sleep(poll)
    media = ig_publish(cid)
    url = ig_permalink(media)
    if on_progress:
        on_progress(1.0)
    return {"media_id": media, "status": "published", "url": url}


# ===================================================================== per-clip record


def record_path(project) -> Path:
    return project.dir / "platform_uploads.json"


_rlock = threading.RLock()


def records(project) -> dict:
    p = record_path(project)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def record(project, cid: str, platform: str, **data) -> dict:
    from .project import write_json_atomic

    with _rlock:
        all_ = records(project)
        cur = {**(all_.get(cid) or {}).get(platform, {}), **data, "at": time.time()}
        all_.setdefault(cid, {})[platform] = cur
        write_json_atomic(record_path(project), all_)
        return cur


# ===================================================================== 1.2.36: errors, health, avatars


class PlatformError(SharkyClipsError):
    """An API refusal with what the posting engine needs to react: `kind` is one of
    auth (connect again) | rate_limit (try again in a minute or two) | quota (daily cap: later) |
    transient (network / 5xx: try again) | fatal (this post can't work as it is)."""

    def __init__(self, message: str, hint: str | None, platform: str, code: str, kind: str,
                 retry_after: float | None = None):
        super().__init__(message, hint)
        self.platform, self.code, self.kind, self.retry_after = platform, code, kind, retry_after


_TT_KIND = {"rate_limit_exceeded": "rate_limit", "spam_risk_too_many_posts": "quota",
            "spam_risk_user_banned_from_posting": "fatal", "reached_active_user_cap": "quota",
            "access_token_invalid": "auth", "access_token_expired": "auth", "invalid_grant": "auth",
            "scope_not_authorized": "auth", "unaudited_client_can_only_post_to_private_accounts": "fatal",
            "privacy_level_option_mismatch": "fatal", "internal_error": "transient"}


def api_error(platform: str, message: str, hint: str | None, code: str, http: int = 400) -> PlatformError:
    if platform == "tiktok":
        kind = _TT_KIND.get(code) or ("rate_limit" if http == 429 else "transient" if http >= 500 else
                                      "auth" if http == 401 else "fatal")
    else:
        base = code.split(":")[0]
        kind = ("quota" if code == "9:2207042" else "rate_limit" if base in ("4", "17", "32", "613") or http == 429
                else "auth" if base in ("190", "10", "200") or http == 401 else
                "transient" if base in ("1", "2", "-1") or http >= 500 else "fatal")
    retry = {"rate_limit": 90.0, "quota": 6 * 3600.0, "transient": 60.0}.get(kind)
    return PlatformError(message, hint, platform, code, kind, retry)


def note_problem(name: str, kind: str | None, message: str | None = None) -> None:
    """Remember why an account needs you (signed_out / attention), or clear it (kind None)."""
    p = folder(name) / "problem.json"
    if kind is None:
        p.unlink(missing_ok=True)
        return
    folder(name).mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"kind": kind, "message": message, "at": time.time()}), encoding="utf-8")


def problem(name: str) -> dict | None:
    try:
        return json.loads((folder(name) / "problem.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def avatar_path(name: str) -> Path:
    return folder(name) / "avatar.jpg"


def save_avatar(name: str, url: str | None) -> None:
    """The profile picture is kept here (the UI never loads it from the platform)."""
    if not url:
        return
    try:
        r = _http().get(url, timeout=20)
        if r.status_code == 200 and r.content and len(r.content) < 3_000_000:
            folder(name).mkdir(parents=True, exist_ok=True)
            tmp = avatar_path(name).with_suffix(".tmp")
            tmp.write_bytes(r.content)
            os.replace(tmp, avatar_path(name))
    except Exception:  # noqa: BLE001 - a missing picture is fine
        pass


def health(name: str) -> dict:
    """Account card state: pill ok (green) | attention (amber) | signed_out (red), with the reason."""
    tok = load_token(name) or {}
    prob = problem(name)
    now = time.time()
    if not tok.get("access_token"):
        signed_out = (prob or {}).get("kind") == "signed_out"
        return {"pill": "signed_out", "reason": "signed_out" if signed_out else "not_connected",
                "message": (prob or {}).get("message")}
    if prob and prob.get("kind") == "signed_out":
        return {"pill": "signed_out", "reason": "signed_out", "message": prob.get("message")}
    if name == "tiktok":
        scope = str(tok.get("scope") or "")
        if scope and "video.publish" not in scope:
            return {"pill": "attention", "reason": "scope", "message": None}
        if float(tok.get("refresh_expires_at") or now + 1e9) - now < 7 * 86400:
            return {"pill": "attention", "reason": "expires", "message": None}
    if name == "reels":
        if float(tok.get("expires_at") or now + 1e9) - now < 5 * 86400:
            return {"pill": "attention", "reason": "expires", "message": None}
    if prob:
        return {"pill": "attention", "reason": prob.get("kind") or "attention", "message": prob.get("message")}
    return {"pill": "ok", "reason": None, "message": None}


def keep_fresh() -> list[str]:
    """Background (publish loop): refresh tokens before they run out. Returns what it did."""
    acts = []
    now = time.time()
    tok = load_token("tiktok") or {}
    if tok.get("access_token") and float(tok.get("expires_at") or 0) - now < 2 * 3600 and \
            (problem("tiktok") or {}).get("kind") != "signed_out":
        try:
            refresh_tiktok()
            acts.append("refresh:tiktok")
        except SharkyClipsError:
            acts.append("refresh_failed:tiktok")
    tok = load_token("reels") or {}
    if tok.get("access_token") and tok.get("graph") != "facebook" and \
            now - float(tok.get("saved_at") or 0) > IG_REFRESH_AFTER and \
            (problem("reels") or {}).get("kind") != "signed_out":
        try:
            refresh_ig()
            acts.append("refresh:reels")
        except SharkyClipsError:
            acts.append("refresh_failed:reels")
    return acts


def account(name: str) -> dict:
    """What an Accounts card shows (no secrets)."""
    tok = load_token(name) or {}
    app = load_app(name) or {}
    out = {"platform": name, "connected": bool(tok.get("access_token")),
           "handle": tok.get("handle") or tok.get("account"), "name": tok.get("account"),
           "avatar": avatar_path(name).is_file(), "health": health(name), "audited": bool(app.get("audited")),
           "has_app": bool(app.get("client_key") or app.get("app_id")),
           "app_id": app.get("client_key") or app.get("app_id"), "expires_at": tok.get("expires_at"),
           "connected_at": tok.get("connected_at") or tok.get("saved_at"), "encrypted": True}
    if name == "tiktok":
        out["scopes"] = [x for x in str(tok.get("scope") or "").split(",") if x]
        out["stats"] = "video.list" in out["scopes"]
    if name == "reels":
        out["stats"] = "insights" in str(tok.get("scope") or "insights")
        out["redirect"] = app.get("redirect")
    return out


# ===================================================================== 1.2.36: TikTok step by step

TIKTOK_DAILY_CAP = 15  # TikTok's own cap per creator account is "around 15 posts a day"
_creator_cache: dict = {}


def tiktok_creator_info(fresh: bool = False) -> dict:
    """creator_info/query (TikTok's UX rules: who posts, the privacy choices, which interactions
    the creator allows, the longest video). Cached a minute (TikTok allows 20 calls a minute)."""
    if not fresh and _creator_cache.get("at", 0) > time.time() - 60:
        return dict(_creator_cache["data"])
    d = tiktok_call("POST", "/v2/post/publish/creator_info/query/").get("data") or {}
    info = {"username": d.get("creator_username"), "nickname": d.get("creator_nickname"),
            "avatar_url": d.get("creator_avatar_url"),
            "privacy_options": list(d.get("privacy_level_options") or ["SELF_ONLY"]),
            "comment_disabled": bool(d.get("comment_disabled")), "duet_disabled": bool(d.get("duet_disabled")),
            "stitch_disabled": bool(d.get("stitch_disabled")),
            "max_seconds": int(d.get("max_video_post_duration_sec") or 600)}
    _creator_cache.update(at=time.time(), data=info)
    tok = load_token("tiktok") or {}
    if info["username"] and (tok.get("handle") != info["username"] or not avatar_path("tiktok").is_file()):
        tok["handle"] = info["username"]
        tok["account"] = info["nickname"] or tok.get("account")
        save_token("tiktok", tok)
        save_avatar("tiktok", info["avatar_url"])
    return dict(info)


def tiktok_post_info(text: str, settings: dict, audited: bool, info: dict, ai_label: bool = False,
                     cover_ms: int | None = None) -> dict:
    """post_info from the user's choices, checked against TikTok's rules (raises when one breaks)."""
    privacy = settings.get("privacy") if audited else "SELF_ONLY"
    if not privacy:
        raise SharkyClipsError("Choose who can see the TikTok video.")
    if privacy not in info["privacy_options"]:
        raise api_error("tiktok", "TikTok doesn't offer this privacy choice for your account.",
                        _tiktok_hint("privacy_level_option_mismatch"), "privacy_level_option_mismatch")
    disclose = bool(settings.get("disclose"))
    organic, branded = disclose and bool(settings.get("brand_organic")), disclose and bool(settings.get("brand_content"))
    if disclose and not (organic or branded):
        raise SharkyClipsError("Say whether the video promotes you or a brand, or switch the disclosure off.")
    if branded and privacy == "SELF_ONLY":
        raise SharkyClipsError("Branded content can't be private on TikTok.")
    out = {"title": text[:CAPTION_MAX["tiktok"]], "privacy_level": privacy,
           "disable_comment": info["comment_disabled"] or not settings.get("allow_comment"),
           "disable_duet": info["duet_disabled"] or not settings.get("allow_duet"),
           "disable_stitch": info["stitch_disabled"] or not settings.get("allow_stitch"),
           "brand_content_toggle": branded, "brand_organic_toggle": organic}
    if cover_ms is not None:
        out["video_cover_timestamp_ms"] = max(0, int(cover_ms))
    if ai_label:
        out["is_aigc"] = True
    return out


def tiktok_init(file: Path, post_info: dict) -> dict:
    size = file.stat().st_size
    chunk = size if size <= 64 * 1024 * 1024 else CHUNK
    count = max(1, size // chunk)
    init = tiktok_call("POST", "/v2/post/publish/video/init/", {
        "post_info": post_info,
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
    data = init.get("data") or {}
    if not data.get("upload_url") or not data.get("publish_id"):
        raise api_error("tiktok", "TikTok didn't give an upload address.", "SharkyClips tries again.", "no_url", 500)
    return {"publish_id": data["publish_id"], "upload_url": data["upload_url"], "chunk": chunk, "count": count,
            "size": size}


def tiktok_send(file: Path, up: dict, on_progress: ProgressFn | None = None,
                cancel: threading.Event | None = None) -> None:
    size, chunk, count = up["size"], up["chunk"], up["count"]
    with open(file, "rb") as f:
        for i in range(count):
            if cancel is not None and cancel.is_set():
                raise SharkyClipsError("Cancelled.")
            a = i * chunk
            b = size - 1 if i == count - 1 else a + chunk - 1
            f.seek(a)
            part = f.read(b - a + 1)
            r = _http().put(up["upload_url"], data=part, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                "Content-Range": f"bytes {a}-{b}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise api_error("tiktok", f"TikTok stopped the upload ({r.status_code}).", "SharkyClips tries again.",
                                str(r.status_code), 429 if r.status_code == 429 else max(500, r.status_code))
            if on_progress:
                on_progress((b + 1) / size)


def tiktok_status(publish_id: str) -> dict:
    """{"status": PROCESSING_UPLOAD | PROCESSING_DOWNLOAD | SEND_TO_USER_INBOX | PUBLISH_COMPLETE | FAILED,
    "fail_reason", "post_ids"}"""
    d = tiktok_call("POST", "/v2/post/publish/status/fetch/", {"publish_id": publish_id}).get("data") or {}
    return {"status": d.get("status"), "fail_reason": d.get("fail_reason"),
            "post_ids": [str(x) for x in (d.get("publicaly_available_post_id") or [])]}


def tiktok_video_stats(since: float) -> list[dict]:
    """Your recent public videos with views / likes (needs the video.list scope)."""
    tok = load_token("tiktok") or {}
    if "video.list" not in str(tok.get("scope") or ""):
        return []
    out, cursor = [], None
    for _page in range(5):
        body = {"max_count": 20, **({"cursor": cursor} if cursor else {})}
        d = tiktok_call("POST", "/v2/video/list/?fields=id,title,create_time,view_count,like_count,share_url",
                        body).get("data") or {}
        vids = d.get("videos") or []
        out += vids
        if not d.get("has_more") or not vids or min(int(v.get("create_time") or 0) for v in vids) < since:
            break
        cursor = d.get("cursor")
    return out


# ===================================================================== 1.2.36: Instagram Login (OAuth)

IG_SCOPES = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights"


def ig_auth_host() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://www.instagram.com")


def ig_token_host() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://api.instagram.com")


def ig_redirect(port: int) -> str:
    return f"https://localhost:{port}/api/platforms/reels/callback"


def ig_start(app_id: str, app_secret: str, port: int, redirect: str | None = None) -> str:
    """Save your Meta app (Instagram app ID + secret) and return the Instagram sign-in URL.
    Meta wants an https redirect address: the sign-in ends on https://localhost/..., which the
    browser can't open (SharkyClips runs plain http), so the user pastes that address back."""
    app_id, app_secret = app_id.strip(), app_secret.strip()
    saved = load_app("reels") or {}
    if not app_id and not app_secret and saved.get("app_id"):  # Reconnect: the saved app
        app_id, app_secret = saved["app_id"], saved.get("app_secret") or ""
    if not app_id or not app_secret:
        raise SharkyClipsError("Enter the Instagram app ID and app secret of your Meta app.",
                               "developers.facebook.com → your app → Instagram → API setup with Instagram login → "
                               "3. Set up Instagram business login → Business login settings.")
    app = load_app("reels") or {}
    redirect = (redirect or "").strip() or ig_redirect(port)
    save_app("reels", {**app, "app_id": app_id, "app_secret": app_secret, "redirect": redirect})
    state = secrets.token_urlsafe(16)
    with _plock:
        _pending["ig"] = {"state": state, "redirect": redirect, "at": time.time()}
    q = {"client_id": app_id, "redirect_uri": redirect, "response_type": "code", "scope": IG_SCOPES,
         "state": state, "enable_fb_login": "0", "force_reauth": "true"}
    return f"{ig_auth_host()}/oauth/authorize?{urlencode(q)}"


def ig_finish(code: str, state: str | None = None) -> dict:
    """code -> short-lived token -> 60-day token -> profile. `code` may be the whole address the
    browser ended on (the https://localhost page that doesn't load)."""
    from urllib.parse import parse_qs

    code = (code or "").strip()
    if "code=" in code:
        q = {k: v[0] for k, v in parse_qs(urlparse(code).query or code.split("?", 1)[-1]).items()}
        code, state = q.get("code", ""), q.get("state") or state
    code = code.split("#")[0].strip()
    with _plock:
        p = _pending.get("ig")
    if p is None or time.time() - p["at"] > 1800 or (state and state != p["state"]):
        raise SharkyClipsError("This Instagram sign-in expired.", "Start the connection again.")
    if not code:
        raise SharkyClipsError("Instagram didn't send a sign-in code.",
                               "Copy the whole address from the browser's address bar after you allowed access.")
    app = load_app("reels") or {}
    r = _http().post(f"{ig_token_host()}/oauth/access_token", timeout=30, data={
        "client_id": app.get("app_id"), "client_secret": app.get("app_secret"), "grant_type": "authorization_code",
        "redirect_uri": p["redirect"], "code": code})
    d = _ig_json(r, "sign-in")
    if isinstance(d.get("data"), list) and d["data"]:
        d = d["data"][0]
    short = d.get("access_token")
    if not short:
        raise SharkyClipsError("Instagram didn't send a token.", "Start the connection again.")
    r = _http().get(f"{ig_api()}/access_token", timeout=30, params={
        "grant_type": "ig_exchange_token", "client_secret": app.get("app_secret"), "access_token": short})
    long = _ig_json(r, "sign-in")
    with _plock:
        _pending.pop("ig", None)
    st = _ig_save(long["access_token"], float(long.get("expires_in") or 60 * 86400))
    perms = d.get("permissions")
    tok = load_token("reels") or {}
    tok["scope"] = ",".join(perms) if isinstance(perms, list) else str(perms or IG_SCOPES)
    save_token("reels", tok)
    return st


# ===================================================================== 1.2.36: Instagram step by step


def ig_container(text: str, ai_label: bool = False, thumb_ms: int | None = None) -> str:
    tok = _ig_token()
    data = {"media_type": "REELS", "upload_type": "resumable", "caption": text[:CAPTION_MAX["reels"]],
            "share_to_feed": "true", "access_token": tok["access_token"]}
    if thumb_ms is not None:
        data["thumb_offset"] = str(max(0, int(thumb_ms)))
    if ai_label:
        data["is_ai_generated"] = "true"
    r = _http().post(f"{_ig_graph(tok)}/{tok['user_id']}/media", timeout=60, data=data)
    cid = _ig_json(r, "upload").get("id")
    if not cid:
        raise api_error("reels", "Instagram didn't create the upload.", "SharkyClips tries again.", "no_id", 500)
    return str(cid)


def ig_send(file: Path, container: str) -> None:
    tok = _ig_token()
    size = file.stat().st_size
    with open(file, "rb") as f:
        r = _http().post(_ig_upload_url(tok, container), data=f, timeout=900, headers={
            "Authorization": f"OAuth {tok['access_token']}", "offset": "0", "file_size": str(size)})
    _ig_json(r, "upload")


def ig_container_status(container: str) -> str:
    """IN_PROGRESS | FINISHED | ERROR | EXPIRED | PUBLISHED"""
    tok = _ig_token()
    r = _http().get(f"{_ig_graph(tok)}/{container}", timeout=30,
                    params={"fields": "status_code,status", "access_token": tok["access_token"]})
    return str(_ig_json(r, "upload").get("status_code") or "IN_PROGRESS")


def ig_publish(container: str) -> str:
    tok = _ig_token()
    r = _http().post(f"{_ig_graph(tok)}/{tok['user_id']}/media_publish", timeout=60,
                     data={"creation_id": container, "access_token": tok["access_token"]})
    mid = _ig_json(r, "publish").get("id")
    if not mid:
        raise api_error("reels", "Instagram didn't confirm the post.", "SharkyClips checks again.", "no_id", 500)
    return str(mid)


def ig_recent(limit: int = 12) -> list[dict]:
    """Your newest posts (finds a post whose confirmation got lost, so nothing is posted twice)."""
    tok = _ig_token()
    r = _http().get(f"{_ig_graph(tok)}/{tok['user_id']}/media", timeout=30, params={
        "fields": "id,caption,timestamp,permalink,media_type", "limit": str(limit), "access_token": tok["access_token"]})
    return list(_ig_json(r, "check").get("data") or [])


def ig_permalink(media: str) -> str | None:
    tok = _ig_token()
    try:
        r = _http().get(f"{_ig_graph(tok)}/{media}", timeout=30,
                        params={"fields": "permalink", "access_token": tok["access_token"]})
        return _ig_json(r, "link").get("permalink")
    except SharkyClipsError:
        return None


def ig_quota() -> dict | None:
    """{"used", "total"} of Instagram's API posts in the last 24 h (cached 10 minutes)."""
    p = folder("reels") / "quota.json"
    try:
        q = json.loads(p.read_text(encoding="utf-8"))
        if q.get("at", 0) > time.time() - 600:
            return q
    except (OSError, ValueError):
        pass
    try:
        tok = _ig_token()
        r = _http().get(f"{_ig_graph(tok)}/{tok['user_id']}/content_publishing_limit", timeout=20,
                        params={"fields": "quota_usage,config", "access_token": tok["access_token"]})
        d = (_ig_json(r, "limit").get("data") or [{}])[0]
        q = {"used": int(d.get("quota_usage") or 0), "total": int((d.get("config") or {}).get("quota_total") or 50),
             "at": time.time()}
        p.write_text(json.dumps(q), encoding="utf-8")
        return q
    except Exception:  # noqa: BLE001 - only shown when it works
        return None


def ig_stats(media: str) -> dict:
    """Views / likes of a Reel (views need the insights permission; likes come with the basic one)."""
    tok = _ig_token()
    out: dict = {}
    r = _http().get(f"{_ig_graph(tok)}/{media}", timeout=30,
                    params={"fields": "like_count,comments_count,permalink", "access_token": tok["access_token"]})
    d = _ig_json(r, "stats")
    out["likes"], out["comments"], out["url"] = d.get("like_count"), d.get("comments_count"), d.get("permalink")
    try:
        r = _http().get(f"{_ig_graph(tok)}/{media}/insights", timeout=30,
                        params={"metric": "views", "access_token": tok["access_token"]})
        for m in _ig_json(r, "stats").get("data") or []:
            if m.get("name") == "views":
                vals = m.get("values") or []
                v = vals[0].get("value") if vals else (m.get("total_value") or {}).get("value")
                out["views"] = int(v or 0)
    except SharkyClipsError:
        pass
    return out


def ig_delete(media: str) -> bool:
    """Delete a post. Meta only allows this for some apps: False means delete it in the Instagram app."""
    tok = _ig_token()
    try:
        r = _http().delete(f"{_ig_graph(tok)}/{media}", timeout=30, params={"access_token": tok["access_token"]})
        _ig_json(r, "delete")
        return True
    except SharkyClipsError:
        return False
