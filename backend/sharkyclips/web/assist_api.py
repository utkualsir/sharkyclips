"""Assisted upload (1.2.70): the posts SharkyClips fills in for you in your own browser.

One task per clip per platform. The post job (multipost, mode "assist") makes the file (the same
Downloads copy + caption .txt as "by hand", so falling back is instant), opens the upload page in
the SharkyClips profile of your browser (assist.py) and then follows the task, which the companion
extension moves along with its reports:

  opening -> claimed -> uploading -> filling -> ready ("Everything is ready. Check and click Post.")
          -> post_clicked (your own click, seen in the page) -> posted (link) -> "Shared to TikTok ✓"
  login / captcha    you log in / finish the check in the browser; SharkyClips waits
  setup              the extension never answered: the one-time guide (Chrome: Load unpacked)
  confirm            the tab was closed / nothing after your click: "Did you post it? Yes / No"
  failed / fallback  the page looked different (or you chose so): the by-hand steps (copy
                     buttons + upload page + folder), with the reason, never silently

The jobs of one platform run one after another (the "tiktok" / "reels" slot of the network
lane), so a batch prepares clip after clip: the next one opens only after the previous one is
posted (or answered), with a pause of assist.pause_s() between two posts. YouTube is never held up.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse

from .. import assist, config, platforms as PF
from ..errors import SharkyClipsError
from ..project import write_json_atomic

router = APIRouter()

PLATS = ("tiktok", "reels")
NAMES = {"tiktok": "TikTok", "reels": "Instagram"}
ACTIVE = ("new", "pause", "opening", "claimed", "uploading", "filling", "login", "captcha", "ready",
          "post_clicked", "tab_closed")
FINAL = ("posted", "failed", "fallback", "confirm", "cancelled", "not_posted")
EXT_WAIT_S = 25.0  # the page must answer this soon after it opened, else the one-time setup guide
SETUP_WAIT_S = 15 * 60.0  # ... which waits this long for you
NO_PAGE_S = 120.0  # the extension works, but the page never asked for its post
STALL_S = 180.0  # filling in with no word from the page
USER_WAIT_S = 30 * 60.0  # a login / CAPTCHA you finish in the browser
READY_WAIT_S = 2 * 3600.0  # waiting for your click on Post
CLICK_WAIT_S = 120.0  # after your click the page must show that the post went out
KEEP_FINAL_S = 600.0  # finished tasks stay in the app's panel this long

TASKS: dict[str, dict] = {}
_lock = threading.RLock()
_loaded = {"done": False}

# The banner in the tab (the extension shows these; English when a language is missing).
STRINGS: dict[str, dict[str, str]] = {
    "en": {"filling": "SharkyClips is filling in your post…", "filling_sub": "Please wait a moment, don't click anything yet.",
           "uploading": "Uploading the video… {pct}%", "ready": "Everything is ready. Check and click Post.",
           "ready_ig": "Everything is ready. Check and click Share.", "ready_sub": "SharkyClips never posts for you: you decide.",
           "login": "Log in to {p} here once.", "login_sub": "SharkyClips never sees your password. It goes on by itself after that.",
           "captcha": "Please complete this in the browser.", "captcha_sub": "SharkyClips waits and goes on when it's done.",
           "posting": "Posting…", "posted": "Shared to {p} ✓", "posted_sub": "You can close this tab.",
           "failed": "SharkyClips couldn't fill in this page.", "failed_sub": "Post it by hand: the steps are in SharkyClips.",
           "note_visibility": "Set \"Who can watch\" to Everyone.", "note_ai": "Switch on \"AI-generated content\" (Show more).",
           "note_now": "Choose \"Now\" under When to post.", "note_crop": "Check the crop before you share.", "hide": "Hide"},
    "tr": {"filling": "SharkyClips gönderini dolduruyor…", "filling_sub": "Biraz bekle, henüz bir şeye tıklama.",
           "uploading": "Video yükleniyor… %{pct}", "ready": "Her şey hazır. Kontrol et ve Paylaş'a tıkla.",
           "ready_ig": "Her şey hazır. Kontrol et ve Paylaş'a tıkla.", "ready_sub": "SharkyClips senin yerine asla paylaşmaz: karar senin.",
           "login": "Burada {p}'a bir kez giriş yap.", "login_sub": "SharkyClips şifreni asla görmez. Sonra kendiliğinden devam eder.",
           "captcha": "Lütfen bunu tarayıcıda tamamla.", "captcha_sub": "SharkyClips bekliyor, bitince devam eder.",
           "posting": "Paylaşılıyor…", "posted": "{p}'da paylaşıldı ✓", "posted_sub": "Bu sekmeyi kapatabilirsin.",
           "failed": "SharkyClips bu sayfayı dolduramadı.", "failed_sub": "Elle paylaş: adımlar SharkyClips'te.",
           "note_visibility": "\"Kimler izleyebilir\"i Herkes yap.", "note_ai": "\"Yapay zekâ ile oluşturulan içerik\"i aç (Daha fazla göster).",
           "note_now": "Ne zaman paylaşılsın altında \"Şimdi\"yi seç.", "note_crop": "Paylaşmadan önce kırpmayı kontrol et.", "hide": "Gizle"},
    "es": {"filling": "SharkyClips está rellenando tu publicación…", "filling_sub": "Espera un momento, no hagas clic todavía.",
           "uploading": "Subiendo el video… {pct}%", "ready": "Todo está listo. Revisa y haz clic en Publicar.",
           "ready_ig": "Todo está listo. Revisa y haz clic en Compartir.", "ready_sub": "SharkyClips nunca publica por ti: tú decides.",
           "login": "Inicia sesión en {p} aquí una vez.", "login_sub": "SharkyClips nunca ve tu contraseña. Después sigue solo.",
           "captcha": "Completa esto en el navegador.", "captcha_sub": "SharkyClips espera y sigue cuando termines.",
           "posting": "Publicando…", "posted": "Compartido en {p} ✓", "posted_sub": "Puedes cerrar esta pestaña.",
           "failed": "SharkyClips no pudo rellenar esta página.", "failed_sub": "Publícalo a mano: los pasos están en SharkyClips.",
           "note_visibility": "Pon \"Quién puede verlo\" en Todos.", "note_ai": "Activa \"Contenido generado por IA\" (Mostrar más).",
           "note_now": "Elige \"Ahora\" en Cuándo publicar.", "note_crop": "Revisa el recorte antes de compartir.", "hide": "Ocultar"},
    "pt": {"filling": "O SharkyClips está preenchendo sua publicação…", "filling_sub": "Espere um pouco, não clique em nada ainda.",
           "uploading": "Enviando o vídeo… {pct}%", "ready": "Tudo pronto. Confira e clique em Publicar.",
           "ready_ig": "Tudo pronto. Confira e clique em Compartilhar.", "ready_sub": "O SharkyClips nunca publica por você: você decide.",
           "login": "Entre no {p} aqui uma vez.", "login_sub": "O SharkyClips nunca vê sua senha. Depois continua sozinho.",
           "captcha": "Conclua isto no navegador.", "captcha_sub": "O SharkyClips espera e continua quando terminar.",
           "posting": "Publicando…", "posted": "Compartilhado no {p} ✓", "posted_sub": "Você pode fechar esta aba.",
           "failed": "O SharkyClips não conseguiu preencher esta página.", "failed_sub": "Publique à mão: os passos estão no SharkyClips.",
           "note_visibility": "Deixe \"Quem pode ver\" em Todos.", "note_ai": "Ative \"Conteúdo gerado por IA\" (Mostrar mais).",
           "note_now": "Escolha \"Agora\" em Quando publicar.", "note_crop": "Confira o corte antes de compartilhar.", "hide": "Ocultar"},
    "de": {"filling": "SharkyClips füllt deinen Beitrag aus…", "filling_sub": "Kurz warten, noch nichts anklicken.",
           "uploading": "Video wird hochgeladen… {pct} %", "ready": "Alles ist bereit. Prüfen und auf Posten klicken.",
           "ready_ig": "Alles ist bereit. Prüfen und auf Teilen klicken.", "ready_sub": "SharkyClips postet nie für dich: du entscheidest.",
           "login": "Melde dich hier einmal bei {p} an.", "login_sub": "SharkyClips sieht dein Passwort nie. Danach geht es von selbst weiter.",
           "captcha": "Bitte schließe das im Browser ab.", "captcha_sub": "SharkyClips wartet und macht danach weiter.",
           "posting": "Wird gepostet…", "posted": "Auf {p} geteilt ✓", "posted_sub": "Du kannst diesen Tab schließen.",
           "failed": "SharkyClips konnte diese Seite nicht ausfüllen.", "failed_sub": "Poste es von Hand: die Schritte stehen in SharkyClips.",
           "note_visibility": "Stell \"Wer kann das sehen\" auf Alle.", "note_ai": "Schalte \"KI-generierte Inhalte\" ein (Mehr anzeigen).",
           "note_now": "Wähle \"Jetzt\" bei Wann posten.", "note_crop": "Prüfe den Zuschnitt vor dem Teilen.", "hide": "Ausblenden"},
    "fr": {"filling": "SharkyClips remplit ta publication…", "filling_sub": "Patiente un instant, ne clique sur rien pour l'instant.",
           "uploading": "Envoi de la vidéo… {pct} %", "ready": "Tout est prêt. Vérifie et clique sur Publier.",
           "ready_ig": "Tout est prêt. Vérifie et clique sur Partager.", "ready_sub": "SharkyClips ne publie jamais à ta place : c'est toi qui décides.",
           "login": "Connecte-toi à {p} ici une fois.", "login_sub": "SharkyClips ne voit jamais ton mot de passe. Ensuite, il continue tout seul.",
           "captcha": "Termine ceci dans le navigateur.", "captcha_sub": "SharkyClips attend et continue quand c'est fait.",
           "posting": "Publication…", "posted": "Partagé sur {p} ✓", "posted_sub": "Tu peux fermer cet onglet.",
           "failed": "SharkyClips n'a pas pu remplir cette page.", "failed_sub": "Publie-la à la main : les étapes sont dans SharkyClips.",
           "note_visibility": "Mets \"Qui peut voir\" sur Tout le monde.", "note_ai": "Active \"Contenu généré par l'IA\" (Afficher plus).",
           "note_now": "Choisis \"Maintenant\" sous Quand publier.", "note_crop": "Vérifie le cadrage avant de partager.", "hide": "Masquer"},
    "hu": {"filling": "A SharkyClips kitölti a bejegyzésedet…", "filling_sub": "Várj egy kicsit, még ne kattints semmire.",
           "uploading": "A videó feltöltése… {pct}%", "ready": "Minden kész. Ellenőrizd, és kattints a Közzététel gombra.",
           "ready_ig": "Minden kész. Ellenőrizd, és kattints a Megosztás gombra.", "ready_sub": "A SharkyClips sosem posztol helyetted: te döntesz.",
           "login": "Jelentkezz be itt egyszer a(z) {p} fiókodba.", "login_sub": "A SharkyClips sosem látja a jelszavad. Utána magától folytatja.",
           "captcha": "Kérlek, fejezd be ezt a böngészőben.", "captcha_sub": "A SharkyClips vár, és utána folytatja.",
           "posting": "Közzététel…", "posted": "Megosztva: {p} ✓", "posted_sub": "Bezárhatod ezt a lapot.",
           "failed": "A SharkyClips nem tudta kitölteni ezt az oldalt.", "failed_sub": "Posztold kézzel: a lépések a SharkyClipsben vannak.",
           "note_visibility": "Állítsd a \"Ki nézheti meg\" részt Mindenki értékre.", "note_ai": "Kapcsold be az \"MI által generált tartalom\" kapcsolót (Több).",
           "note_now": "Válaszd a \"Most\" lehetőséget.", "note_crop": "Megosztás előtt ellenőrizd a vágást.", "hide": "Elrejtés"},
    "ru": {"filling": "SharkyClips заполняет вашу публикацию…", "filling_sub": "Подождите немного, пока ничего не нажимайте.",
           "uploading": "Видео загружается… {pct}%", "ready": "Всё готово. Проверьте и нажмите «Опубликовать».",
           "ready_ig": "Всё готово. Проверьте и нажмите «Поделиться».", "ready_sub": "SharkyClips никогда не публикует за вас: решаете вы.",
           "login": "Войдите в {p} здесь один раз.", "login_sub": "SharkyClips никогда не видит ваш пароль. Дальше всё пойдёт само.",
           "captcha": "Пожалуйста, завершите это в браузере.", "captcha_sub": "SharkyClips подождёт и продолжит.",
           "posting": "Публикация…", "posted": "Опубликовано в {p} ✓", "posted_sub": "Эту вкладку можно закрыть.",
           "failed": "SharkyClips не смог заполнить эту страницу.", "failed_sub": "Опубликуйте вручную: шаги есть в SharkyClips.",
           "note_visibility": "Выберите «Все» в «Кто может смотреть».", "note_ai": "Включите «Контент, созданный ИИ» («Показать больше»).",
           "note_now": "Выберите «Сейчас» в «Когда опубликовать».", "note_crop": "Проверьте кадрирование перед публикацией.", "hide": "Скрыть"},
    "ar": {"filling": "يملأ SharkyClips منشورك…", "filling_sub": "انتظر قليلًا ولا تنقر على أي شيء بعد.",
           "uploading": "جارٍ رفع الفيديو… {pct}%", "ready": "كل شيء جاهز. راجِع ثم انقر نشر.",
           "ready_ig": "كل شيء جاهز. راجِع ثم انقر مشاركة.", "ready_sub": "لا ينشر SharkyClips نيابةً عنك أبدًا: القرار لك.",
           "login": "سجّل الدخول إلى {p} هنا مرة واحدة.", "login_sub": "لا يرى SharkyClips كلمة مرورك أبدًا. بعدها يكمل وحده.",
           "captcha": "يُرجى إكمال هذا في المتصفح.", "captcha_sub": "ينتظر SharkyClips ثم يكمل بعد الانتهاء.",
           "posting": "جارٍ النشر…", "posted": "تمت المشاركة على {p} ✓", "posted_sub": "يمكنك إغلاق علامة التبويب هذه.",
           "failed": "تعذّر على SharkyClips ملء هذه الصفحة.", "failed_sub": "انشره يدويًا: الخطوات في SharkyClips.",
           "note_visibility": "اجعل \"من يمكنه المشاهدة\" الجميع.", "note_ai": "فعّل \"محتوى منشأ بالذكاء الاصطناعي\" (عرض المزيد).",
           "note_now": "اختر \"الآن\" في وقت النشر.", "note_crop": "تحقق من القص قبل المشاركة.", "hide": "إخفاء"},
    "zh": {"filling": "SharkyClips 正在填写你的帖子…", "filling_sub": "请稍候，先不要点击任何内容。",
           "uploading": "正在上传视频… {pct}%", "ready": "一切就绪。请检查后点击“发布”。",
           "ready_ig": "一切就绪。请检查后点击“分享”。", "ready_sub": "SharkyClips 绝不会替你发布：由你决定。",
           "login": "请在这里登录一次 {p}。", "login_sub": "SharkyClips 永远看不到你的密码。之后会自动继续。",
           "captcha": "请在浏览器中完成此操作。", "captcha_sub": "SharkyClips 会等待，完成后继续。",
           "posting": "正在发布…", "posted": "已分享到 {p} ✓", "posted_sub": "你可以关闭此标签页。",
           "failed": "SharkyClips 无法填写此页面。", "failed_sub": "请手动发布：步骤在 SharkyClips 中。",
           "note_visibility": "把“谁可以观看”设为“所有人”。", "note_ai": "打开“AI 生成的内容”（显示更多）。",
           "note_now": "在发布时间中选择“现在”。", "note_crop": "分享前请检查裁剪。", "hide": "隐藏"},
    "ja": {"filling": "SharkyClips が投稿を入力しています…", "filling_sub": "少し待って、まだ何もクリックしないでください。",
           "uploading": "動画をアップロード中… {pct}%", "ready": "準備ができました。確認して「投稿」をクリックしてください。",
           "ready_ig": "準備ができました。確認して「シェア」をクリックしてください。", "ready_sub": "SharkyClips が代わりに投稿することはありません。決めるのはあなたです。",
           "login": "ここで一度 {p} にログインしてください。", "login_sub": "SharkyClips がパスワードを見ることはありません。その後は自動で続きます。",
           "captcha": "ブラウザーでこれを完了してください。", "captcha_sub": "SharkyClips は待って、終わったら続けます。",
           "posting": "投稿中…", "posted": "{p} にシェアしました ✓", "posted_sub": "このタブは閉じてかまいません。",
           "failed": "SharkyClips はこのページを入力できませんでした。", "failed_sub": "手動で投稿してください。手順は SharkyClips にあります。",
           "note_visibility": "「視聴できるユーザー」を「全員」にしてください。", "note_ai": "「AI 生成コンテンツ」をオンにしてください（もっと見る）。",
           "note_now": "投稿日時で「今すぐ」を選んでください。", "note_crop": "シェアする前に切り取りを確認してください。", "hide": "非表示"},
}


def strings() -> dict[str, str]:
    lang = str(config.get("ui_language") or "en")
    return {**STRINGS["en"], **STRINGS.get(lang, {})}


def upload_url(platform: str) -> str:
    from .. import tiktok_browser as TB
    import os

    if platform == "tiktok":
        return TB.upload_url()
    base = (os.environ.get("SHARKYCLIPS_IG_WEB") or "https://www.instagram.com").rstrip("/")
    return base + ("/fakeig/" if os.environ.get("SHARKYCLIPS_IG_WEB") else "/")


def _claimable(platform: str, url: str) -> bool:
    """Only the upload page (or the login it sent you to) may take a waiting post: a TikTok /
    Instagram tab you browse yourself in that profile never does."""
    try:
        path = urlparse(url).path or "/"
    except ValueError:
        return False
    if platform == "tiktok":
        return path.startswith("/tiktokstudio/upload") or path.startswith("/login")
    return path in ("/", "") or path.startswith("/fakeig") or path.startswith("/accounts/login")


# ===================================================================== tasks


def _path() -> Path:
    return assist.root() / "assist_tasks.json"


def _load() -> None:
    with _lock:
        if _loaded["done"]:
            return
        _loaded["done"] = True
        try:
            data = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for t in (data.get("tasks") or []) if isinstance(data, dict) else []:
            if isinstance(t, dict) and t.get("id"):
                if t.get("state") in ACTIVE:
                    t["tab"] = None  # the browser may have been closed meanwhile: the job reopens it
                TASKS[t["id"]] = t


def _persist() -> None:
    now = time.time()
    keep = [t for t in TASKS.values() if t["state"] in ACTIVE or now - float(t.get("updated_at") or 0) < 86400]
    try:
        assist.root().mkdir(parents=True, exist_ok=True)
        write_json_atomic(_path(), {"tasks": keep})
    except OSError:
        pass


def reset_for_tests() -> None:
    with _lock:
        TASKS.clear()
        _loaded["done"] = True


def get(tid: str | None) -> dict | None:
    _load()
    return TASKS.get(tid or "")


def snapshot(t: dict) -> dict:
    """What the clip's record and the app's panel show of a task."""
    return {k: t.get(k) for k in ("id", "state", "step", "progress", "notes", "reason", "detail", "url", "setup",
                                  "browser", "browser_name", "until", "ready_at", "created_at", "updated_at",
                                  "message", "hint", "login_for")}


def _write(t: dict, record: bool = True) -> None:
    t["updated_at"] = time.time()
    _persist()
    if record:
        try:
            project = _app().get_project(t["project_id"])
            PF.record(project, t["clip_id"], t["platform"], assist=snapshot(t))
        except Exception:  # noqa: BLE001 - a deleted project
            pass


def _set(t: dict, **changes) -> dict:
    with _lock:
        before = t.get("state")
        t.update(changes)
        _write(t, record=changes.get("state", before) != before or any(
            k in changes for k in ("setup", "notes", "url", "until", "message")))
        return t


def _app():
    from . import multipost as M

    return M._app()


def _new(project, cid: str, platform: str, file: Path, rec: dict) -> dict:
    from . import multipost as M
    from .. import tiktok_browser as TB

    caption = str(rec.get("caption") or "")
    if platform == "tiktok":  # hashtags last, the same text the 1.2.42 automation typed
        body, tags = TB.split_caption(caption)
        text = body + ("\n\n" if body and tags else "") + " ".join(tags)
    else:
        text = caption
    t = {"id": uuid.uuid4().hex[:16], "project_id": project.id, "clip_id": cid, "platform": platform,
         "title": M._clip_title(project, cid, rec), "text": text.strip(), "ai_label": bool(rec.get("ai_label")),
         "file": str(file), "file_name": Path(file).name, "state": "new", "step": None, "progress": None,
         "tab": None, "notes": [], "created_at": time.time(), "last_seen": time.time()}
    with _lock:
        _load()
        for old in TASKS.values():  # one task per clip per platform
            if old["project_id"] == project.id and old["clip_id"] == cid and old["platform"] == platform \
                    and old["state"] in ACTIVE:
                old["state"] = "cancelled"
        TASKS[t["id"]] = t
        _write(t)
    return t


def find(project_id: str, cid: str, platform: str) -> dict | None:
    _load()
    hits = [t for t in TASKS.values() if t["project_id"] == project_id and t["clip_id"] == cid
            and t["platform"] == platform]
    return max(hits, key=lambda x: x.get("created_at") or 0) if hits else None


# ===================================================================== the post job


def _last_done(platform: str) -> float:
    return float((assist.load_state().get("last_done") or {}).get(platform) or 0)


def _note_done(platform: str) -> None:
    d = dict(assist.load_state().get("last_done") or {})
    d[platform] = time.time()
    assist.save_state(last_done=d)


def run(project, cid: str, platform: str, file: Path, folder: Path, rec: dict, job) -> dict:
    """The body of an assisted post job (multipost.run_post): open, follow, finish."""
    from . import multipost as M

    prev = get((rec.get("assist") or {}).get("id"))
    t = prev if prev is not None and prev["state"] in ACTIVE and prev.get("file") == str(file) \
        else _new(project, cid, platform, file, rec)
    # a short pause between two posts of a batch (the jobs of one platform run one after another)
    until = _last_done(platform) + assist.pause_s()
    while time.time() < until:
        if t["state"] != "pause":
            _set(t, state="pause", until=until)
        M._wait(job, min(1.0, max(0.05, until - time.time())))
        _check_choice(t)
    pk = assist.pick()
    if pk is None:
        return fallback(project, cid, platform, t, "no_browser", "No browser for the assisted upload was found.",
                        "Install Google Chrome, Microsoft Edge, Opera GX or Brave. Until then: post it by hand.")
    key = pk[0]
    name = assist.BROWSERS[key]["name"]
    if not assist.can_fill(key):  # Firefox: it opens there, and you post by hand
        try:
            assist.open_url(upload_url(platform), key)
        except SharkyClipsError:
            pass
        return fallback(project, cid, platform, t, "firefox",
                        f"{name} can't be filled in by SharkyClips: the upload page is open, post it by hand.",
                        "Chrome, Edge, Opera GX and Brave can be filled in (Settings > Publishing > Browser).")
    if t["state"] in ("new", "pause", "opening") or not t.get("tab"):
        try:
            assist.open_url(upload_url(platform), key)
        except SharkyClipsError as exc:
            return fallback(project, cid, platform, t, "no_browser", exc.message, exc.hint)
        _set(t, state="opening", opened_at=time.time(), tab=None, browser=key, browser_name=name, until=None,
             setup=False)
    while True:
        M._wait(job, 1.0)
        out = _step(project, cid, platform, t)
        if out is not None:
            return out


def _check_choice(t: dict) -> None:
    from .jobs import JobCancelled

    if t["state"] == "cancelled":
        raise JobCancelled()


def _step(project, cid: str, platform: str, t: dict) -> dict | None:
    """One look at the task (every second): None = keep waiting, else the job's result."""
    _check_choice(t)
    st, now = t["state"], time.time()
    since = float(t.get("since") or t.get("opened_at") or now)
    if st == "posted":
        return posted(project, cid, platform, t)
    if st == "failed":
        why = {"ui_changed": "The page looked different than expected, so SharkyClips stopped filling it in.",
               "upload_failed": f"{NAMES[platform]} couldn't take the video.",
               "file": "The video couldn't be handed to the page."}.get(t.get("reason") or "", "Filling in the page stopped.")
        return fallback(project, cid, platform, t, t.get("reason") or "failed", why,
                        "Post it by hand: copy the texts, the upload page and the file are ready.")
    if st == "fallback":
        return fallback(project, cid, platform, t, "by_choice", "You chose to post this one by hand.", None)
    if st in ("confirm", "not_posted"):
        return {"status": "ready" if st == "confirm" else "idle", "mode": "assist"}
    if st == "tab_closed":
        if t.get("closed_from") in ("ready", "post_clicked"):
            return ask(project, cid, platform, t, "closed")
        return fallback(project, cid, platform, t, "closed", "The upload tab was closed before it was ready.",
                        "Press Retry to open it again, or post it by hand.")
    if st == "opening":
        age = now - float(t.get("opened_at") or now)
        if age > EXT_WAIT_S and not t.get("setup") and assist.seen(t.get("browser")) <= 0:
            _set(t, setup=True)  # the extension never spoke from this browser: the one-time guide
        limit = SETUP_WAIT_S if t.get("setup") else NO_PAGE_S
        if age > limit:
            return fallback(project, cid, platform, t, "no_page", "The upload page didn't answer SharkyClips.",
                            "Check that the SharkyClips Helper extension is on (the guide in SharkyClips). If the browser "
                            "closed unexpectedly, close it fully once. Then press Retry, or post it by hand now.")
        return None
    if st in ("claimed", "uploading", "filling") and now - float(t.get("last_seen") or now) > STALL_S:
        return fallback(project, cid, platform, t, "stalled", "The upload page stopped answering.",
                        "Press Retry to try again, or post it by hand.")
    if st in ("login", "captcha") and now - since > USER_WAIT_S:
        return fallback(project, cid, platform, t, st, "SharkyClips waited, but the page still needs you.",
                        "Finish it in the browser and press Retry, or post it by hand.")
    if st == "ready" and now - float(t.get("ready_at") or now) > READY_WAIT_S:
        return ask(project, cid, platform, t, "timeout")
    if st == "post_clicked" and now - float(t.get("clicked_at") or now) > CLICK_WAIT_S:
        return ask(project, cid, platform, t, "unsure")
    return None


def posted(project, cid: str, platform: str, t: dict) -> dict:
    from . import multipost as M

    url = t.get("url")
    PF.record(project, cid, platform, status="published", posted_at=M._iso(M._now()), url=url, manual=False,
              via="assist", error=None, fallback=None, assist=snapshot(t))
    _note_done(platform)
    M._calendar(project, cid, platform, "published", url)
    return {"status": "published", "url": url, "mode": "assist"}


def ask(project, cid: str, platform: str, t: dict, why: str) -> dict:
    """Not sure whether it went out: one click in the app ("Did you post it? Yes / No")."""
    _set(t, state="confirm", reason=why)
    PF.record(project, cid, platform, status="ready", assist=snapshot(t), error=None)
    _note_done(platform)
    _notice(t, "assist_confirm")
    return {"status": "ready", "mode": "assist", "confirm": True}


def fallback(project, cid: str, platform: str, t: dict, reason: str, message: str, hint: str | None) -> dict:
    """The by-hand steps for this clip (file + texts are ready in Downloads), with the reason."""
    if t["state"] not in ("fallback", "failed"):
        _set(t, state="fallback")
    _set(t, reason=reason, message=message, hint=hint)
    PF.record(project, cid, platform, mode="semi", assist_fallback=True, status="ready", ready_at=time.time(),
              fallback={"reason": reason, "message": message, "hint": hint, "shot": None, "at": time.time()},
              assist=snapshot(t), error=None)
    return {"status": "ready", "mode": "semi", "fallback": reason}


# ===================================================================== the extension's door


def _ext(request: Request) -> None:
    if not assist.token_ok(request.headers.get("x-sharkyclips-assist")):
        raise HTTPException(status_code=403, detail="Wrong SharkyClips Helper key.")


def _browser_of(ua: str | None) -> str | None:
    ua = ua or ""
    if "Edg/" in ua:
        return "edge"
    if "OPR/" in ua:
        last = assist.load_state().get("last_browser")
        return last if last in ("opera", "operagx") else "opera"
    if "Chrome/" in ua:
        last = assist.load_state().get("last_browser")
        return last if last in ("chrome", "brave") else "chrome"
    return None


def public(t: dict) -> dict:
    """What the extension gets: the post to fill in and the banner texts (no paths)."""
    return {"id": t["id"], "platform": t["platform"], "state": t["state"], "title": t.get("title"),
            "text": t.get("text"), "ai_label": bool(t.get("ai_label")), "upload_url": upload_url(t["platform"]),
            "strings": strings()}


@router.get("/api/assist/ext/hello")
def api_ext_hello(request: Request) -> dict:
    _ext(request)
    from .. import __version__

    assist.note_seen(_browser_of(request.headers.get("user-agent")), time.time())
    return {"app": "sharkyclips", "version": __version__, "ok": True}


@router.post("/api/assist/ext/task")
def api_ext_task(request: Request, body: dict | None = Body(default=None)) -> dict:
    """The page asks for its post: this tab's own one, or the oldest one waiting for a page."""
    _ext(request)
    b = body or {}
    platform, tab, url = str(b.get("platform") or ""), b.get("tab"), str(b.get("url") or "")
    assist.note_seen(_browser_of(b.get("ua")), time.time())
    if platform not in PLATS:
        return {"task": None}
    with _lock:
        _load()
        mine = [t for t in TASKS.values() if t["platform"] == platform and tab is not None and t.get("tab") == tab
                and t["state"] in ACTIVE]
        if mine:
            t = mine[0]
            t["last_seen"] = time.time()
            return {"task": public(t)}
        if not _claimable(platform, url):
            return {"task": None}
        waiting = sorted((t for t in TASKS.values() if t["platform"] == platform and t["state"] == "opening"
                          and not t.get("tab")), key=lambda x: x.get("opened_at") or 0)
        if not waiting:
            return {"task": None}
        t = waiting[0]
        t["tab"], t["last_seen"] = tab, time.time()
        _set(t, setup=False)
        return {"task": public(t)}


@router.get("/api/assist/ext/file/{tid}")
def api_ext_file(tid: str, request: Request):
    _ext(request)
    t = get(tid)
    if t is None or t["state"] not in ACTIVE or not Path(t["file"]).is_file():
        raise HTTPException(status_code=404, detail="No such post.")
    return FileResponse(t["file"], media_type="video/mp4", headers={"X-File-Name": quote(t["file_name"])})


STEP_STATE = {"uploading": "uploading", "filling": "filling", "edit": "filling", "caption": "filling"}


@router.post("/api/assist/ext/report")
def api_ext_report(request: Request, body: dict | None = Body(default=None)) -> dict:
    _ext(request)
    b = body or {}
    ev = str(b.get("event") or "")
    now = time.time()
    assist.note_seen(_browser_of(b.get("ua")), now)
    if ev == "hello":
        return {"ok": True}
    with _lock:
        _load()
        t = TASKS.get(str(b.get("id") or ""))
        if t is None and ev == "tab_closed" and b.get("tab") is not None:
            t = next((x for x in TASKS.values() if x.get("tab") == b.get("tab") and x["state"] in ACTIVE), None)
        if t is None:
            return {"gone": True}
        if t.get("tab") is not None and b.get("tab") is not None and t["tab"] != b["tab"]:
            return {"gone": True}  # another tab took this post meanwhile
        if t["state"] not in ACTIVE:
            return {"task": {"state": t["state"]}, "gone": t["state"] in ("cancelled", "not_posted", "fallback")}
        t["last_seen"] = now
        st = t["state"]
        if ev == "claimed":
            _set(t, state="claimed", claimed_at=now, step=None)
        elif ev == "step":
            _set(t, state=STEP_STATE.get(str(b.get("step")), "filling"), step=str(b.get("step") or "")[:20],
                 progress=None)
        elif ev == "progress":
            p = b.get("progress")
            t["progress"] = max(0.0, min(1.0, float(p))) if isinstance(p, int | float) else None
        elif ev in ("login", "captcha"):
            if st not in ("login", "captcha"):
                t["resume_to"] = st
            _set(t, state=ev, since=now, reason=str(b.get("reason") or ev)[:20], login_for=NAMES[t["platform"]])
            _notice(t, "assist_action")
        elif ev == "resume":
            back = t.get("resume_to") if t.get("resume_to") in ("claimed", "uploading", "filling", "ready", "post_clicked") \
                else "filling"
            _set(t, state=back, since=None)
        elif ev == "ready":
            notes = [str(x)[:160] for x in (b.get("notes") or [])][:5]
            _set(t, state="ready", ready_at=now, notes=notes, step=None, progress=None)
            _notice(t, "assist_ready")
        elif ev == "post_clicked":
            _set(t, state="post_clicked", clicked_at=now)
        elif ev == "posted":
            u = str(b.get("url") or "").strip()
            ok = re.match(r"^https://(www\.)?(tiktok\.com|instagram\.com)/", u)
            _set(t, state="posted", posted_at=now, url=u if ok else None)
        elif ev == "failed":
            _set(t, state="failed", reason=str(b.get("reason") or "failed")[:30], step=str(b.get("step") or "")[:30],
                 detail=str(b.get("detail") or "")[:200])
        elif ev == "tab_closed":
            _set(t, state="tab_closed", closed_from=st, tab=None)
        out: dict = {"task": {"state": t["state"]}}
        if float(t.get("focus_at") or 0) > float(t.get("focus_sent") or 0):
            t["focus_sent"] = now
            out["focus"] = True
        return out


def _notice(t: dict, kind: str) -> None:
    try:
        from . import shareevents

        project = _app().get_project(t["project_id"])
        shareevents.assist(project, t["clip_id"], t["platform"], kind)
    except Exception:  # noqa: BLE001 - a notice never breaks the post
        pass


# ===================================================================== the app's side


def view() -> dict:
    _load()
    now = time.time()
    rows = []
    for t in sorted(TASKS.values(), key=lambda x: x.get("created_at") or 0):
        if t["state"] in ("cancelled", "not_posted"):
            continue
        if t["state"] not in ACTIVE and t["state"] != "confirm" and now - float(t.get("updated_at") or 0) > KEEP_FINAL_S:
            continue
        rows.append({**snapshot(t), "project_id": t["project_id"], "clip_id": t["clip_id"], "platform": t["platform"],
                     "title": t.get("title")})
    p = assist.pick()
    key = p[0] if p else None
    return {"browsers": assist.browsers_view(), "pause_s": assist.pause_s(), "tasks": rows,
            "ext": {"dir": str(assist.ext_dir()), "seen_at": assist.seen(key) if key else 0,
                    "page": assist.BROWSERS[key]["ext_page"] if key else None,
                    "autoload": bool(assist.BROWSERS[key]["autoload"]) if key else False},
            "modes": {"tiktok": PF.mode("tiktok"), "reels": PF.mode("reels")}}


@router.get("/api/assist")
def api_view(request: Request) -> dict:
    if (request.url.hostname or "") in ("127.0.0.1", "localhost"):  # the extension runs on this PC
        assist.note_base(str(request.base_url).rstrip("/"))
    return view()


@router.put("/api/assist/settings")
def api_settings(body: dict) -> dict:
    changes = {}
    if "browser" in body:
        b = str(body.get("browser") or "auto")
        if b != "auto" and b not in assist.BROWSERS:
            raise SharkyClipsError("Unknown browser.")
        changes["assist_browser"] = b
    if "pause_s" in body:
        try:
            changes["assist_pause_s"] = max(assist.PAUSE_MIN, min(assist.PAUSE_MAX, int(body["pause_s"])))
        except (TypeError, ValueError):
            raise SharkyClipsError("Pick a number of seconds.") from None
    if changes:
        config.update(**changes)
    return view()


@router.post("/api/assist/open")
def api_open(body: dict | None = Body(default=None)) -> dict:
    """Opens the upload page in the SharkyClips profile (to log in once, or to look)."""
    platform = str((body or {}).get("platform") or "tiktok")
    if platform not in PLATS:
        raise SharkyClipsError("Unknown platform.")
    return assist.open_url(upload_url(platform))


@router.post("/api/assist/setup")
def api_setup(body: dict | None = Body(default=None)) -> dict:
    """The one-time extension guide: open the browser's extensions page, or the extension folder."""
    what = str((body or {}).get("action") or "extensions")
    folder = assist.write_extension()
    if what == "folder":
        assist.open_folder(folder)
        return {"ok": True, "dir": str(folder)}
    p = assist.pick()
    if not p or not assist.BROWSERS[p[0]]["ext_page"]:
        raise SharkyClipsError("This browser can't take the SharkyClips Helper.",
                               "Use Google Chrome, Microsoft Edge, Opera GX or Brave for the assisted upload.")
    out = assist.open_url(assist.BROWSERS[p[0]]["ext_page"], p[0])
    return {**out, "dir": str(folder)}


@router.post("/api/assist/task/{tid}/{action}")
def api_task(tid: str, action: str, body: dict | None = Body(default=None)) -> dict:
    """show (bring the tab to the front / open it again) | posted (Yes, I posted it) | not_posted
    (No) | skip (this clip not now) | manual (post this one by hand instead)."""
    from . import multipost as M

    t = get(tid)
    if t is None:
        raise SharkyClipsError("This post isn't waiting any more.")
    A = _app()
    project = A.get_project(t["project_id"])
    cid, platform = t["clip_id"], t["platform"]
    if action == "show":
        if t.get("tab") and t["state"] in ("claimed", "uploading", "filling", "login", "captcha", "ready", "post_clicked"):
            _set(t, focus_at=time.time())
        elif t["state"] in ACTIVE:
            assist.open_url(upload_url(platform), t.get("browser"))
            _set(t, state="opening", opened_at=time.time(), tab=None)
        else:
            assist.open_url(upload_url(platform), t.get("browser"))
    elif action == "posted":
        u = str((body or {}).get("url") or "").strip()
        _set(t, state="posted", url=u if u.startswith("https://") else t.get("url"))
        if M.active_job(project.id, cid, platform) is None:
            PF.record(project, cid, platform, status="published", posted_at=M._iso(M._now()), manual=True,
                      url=t.get("url"), via="assist", assist=snapshot(t), error=None)
            M._calendar(project, cid, platform, "published", t.get("url"))
    elif action == "not_posted":
        _set(t, state="not_posted")
        if M.active_job(project.id, cid, platform) is None:
            PF.record(project, cid, platform, status="idle", assist=snapshot(t), error=None)
    elif action == "skip":
        _set(t, state="cancelled")
        j = M.active_job(project.id, cid, platform)
        if j is not None:
            A.jobs.cancel(j.id)
        PF.record(project, cid, platform, status="cancelled", assist=snapshot(t))
    elif action == "manual":
        if M.active_job(project.id, cid, platform) is not None and t["state"] in ACTIVE:
            _set(t, state="fallback")  # the job falls back within a second
        else:
            fallback(project, cid, platform, t, "by_choice", "You chose to post this one by hand.", None)
    else:
        raise SharkyClipsError("Unknown action.")
    return view()
