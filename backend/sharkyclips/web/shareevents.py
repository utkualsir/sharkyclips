"""1.2.68: one notice per clip per platform when sharing ends, never a silent failure.

  shared        "Shared to YouTube ✓" + the clip title, with the link (in-app toast + Windows notice)
  private       "Uploaded as private" + "make it public in YouTube Studio" (the Studio link)
  manual_ready  "Ready to upload by hand" (the file is saved, the texts are ready to copy)
  share_failed  "<Platform>: not shared" + what went wrong

Every notice goes through easy.push_notice (the tray turns it into a Windows notification, the UI
shows it as a toast) and every shared post into history.py. Called from the YouTube upload job,
platforms.record (TikTok / Instagram status changes) and the manual-upload "I posted it" button.
"""

from __future__ import annotations

from .. import config, easy as E, history

NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "reels": "Instagram"}

TEXT: dict[str, dict[str, str]] = {
    "en": {"shared": "Shared to {p} ✓", "private": "Uploaded as private on {p}",
           "private_body": "{t} - YouTube kept it private. Make it public in YouTube Studio.",
           "manual_ready": "Ready to upload by hand on {p}", "manual_body": "{t} - the video is saved and the texts are ready to copy.",
           "failed": "{p}: not shared", "failed_body": "{t} - {m}"},
    "tr": {"shared": "{p}'da paylaşıldı ✓", "private": "{p}'a gizli yüklendi",
           "private_body": "{t} - YouTube videoyu gizli tuttu. YouTube Studio'da herkese açık yap.",
           "manual_ready": "{p} için elle yüklemeye hazır", "manual_body": "{t} - video kaydedildi, metinler kopyalanmaya hazır.",
           "failed": "{p}: paylaşılamadı", "failed_body": "{t} - {m}"},
    "es": {"shared": "Compartido en {p} ✓", "private": "Subido como privado en {p}",
           "private_body": "{t} - YouTube lo dejó privado. Hazlo público en YouTube Studio.",
           "manual_ready": "Listo para subir a mano en {p}", "manual_body": "{t} - el video está guardado y los textos listos para copiar.",
           "failed": "{p}: no se compartió", "failed_body": "{t} - {m}"},
    "pt": {"shared": "Compartilhado no {p} ✓", "private": "Enviado como privado no {p}",
           "private_body": "{t} - o YouTube deixou privado. Deixe público no YouTube Studio.",
           "manual_ready": "Pronto para enviar à mão no {p}", "manual_body": "{t} - o vídeo está salvo e os textos prontos para copiar.",
           "failed": "{p}: não compartilhado", "failed_body": "{t} - {m}"},
    "de": {"shared": "Auf {p} geteilt ✓", "private": "Auf {p} als privat hochgeladen",
           "private_body": "{t} - YouTube hat es privat gelassen. Mach es in YouTube Studio öffentlich.",
           "manual_ready": "Bereit zum Hochladen von Hand auf {p}", "manual_body": "{t} - das Video ist gespeichert, die Texte sind bereit zum Kopieren.",
           "failed": "{p}: nicht geteilt", "failed_body": "{t} - {m}"},
    "fr": {"shared": "Partagé sur {p} ✓", "private": "Mis en ligne en privé sur {p}",
           "private_body": "{t} - YouTube l'a laissé privé. Rends-le public dans YouTube Studio.",
           "manual_ready": "Prêt à publier à la main sur {p}", "manual_body": "{t} - la vidéo est enregistrée et les textes sont prêts à copier.",
           "failed": "{p} : pas partagé", "failed_body": "{t} - {m}"},
    "hu": {"shared": "Megosztva: {p} ✓", "private": "Privátként feltöltve: {p}",
           "private_body": "{t} - a YouTube privát maradt. Tedd nyilvánossá a YouTube Studióban.",
           "manual_ready": "Kézi feltöltésre kész: {p}", "manual_body": "{t} - a videó elmentve, a szövegek másolásra készek.",
           "failed": "{p}: nincs megosztva", "failed_body": "{t} - {m}"},
    "ru": {"shared": "Опубликовано в {p} ✓", "private": "Загружено в {p} как приватное",
           "private_body": "{t} - YouTube оставил видео приватным. Сделайте его открытым в YouTube Studio.",
           "manual_ready": "Готово к ручной загрузке в {p}", "manual_body": "{t} - видео сохранено, тексты готовы к копированию.",
           "failed": "{p}: не опубликовано", "failed_body": "{t} - {m}"},
    "ar": {"shared": "تمت المشاركة على {p} ✓", "private": "تم الرفع بشكل خاص على {p}",
           "private_body": "{t} - أبقى YouTube الفيديو خاصًا. اجعله عامًا في YouTube Studio.",
           "manual_ready": "جاهز للرفع يدويًا على {p}", "manual_body": "{t} - تم حفظ الفيديو والنصوص جاهزة للنسخ.",
           "failed": "{p}: لم تتم المشاركة", "failed_body": "{t} - {m}"},
    "zh": {"shared": "已分享到 {p} ✓", "private": "已作为私享视频上传到 {p}",
           "private_body": "{t} - YouTube 将其设为私享。请在 YouTube Studio 中设为公开。",
           "manual_ready": "可以手动上传到 {p}", "manual_body": "{t} - 视频已保存，文字可以复制。",
           "failed": "{p}：未分享", "failed_body": "{t} - {m}"},
    "ja": {"shared": "{p} に共有しました ✓", "private": "{p} に非公開でアップロードされました",
           "private_body": "{t} - YouTube が非公開のままにしました。YouTube Studio で公開にしてください。",
           "manual_ready": "{p} に手動でアップロードできます", "manual_body": "{t} - 動画を保存し、テキストをコピーできます。",
           "failed": "{p}：共有できませんでした", "failed_body": "{t} - {m}"},
}


def _t(key: str, **kw) -> str:
    lang = str(config.get("ui_language") or "en")
    table = TEXT.get(lang, TEXT["en"])
    return (table.get(key) or TEXT["en"][key]).format(**kw)


def _title(project, cid: str) -> str:
    return (history._clip_title(project, cid) or cid)[:80]


def shared(project, cid: str, platform: str, url: str | None, *, video_id: str | None = None,
           private: bool = False, manual: bool = False, title: str | None = None) -> dict:
    history.note_post(project, cid, platform, url=url, video_id=video_id, manual=manual, private=private,
                      title=title)
    t = (title or _title(project, cid))[:80]
    p = NAMES.get(platform, platform)
    if private:
        studio = f"https://studio.youtube.com/video/{video_id}/edit" if video_id else url
        return E.push_notice("private", _t("private", p=p), _t("private_body", t=t), studio)
    return E.push_notice("shared", _t("shared", p=p), t, url)


def manual_ready(project, cid: str, platform: str) -> dict:
    p = NAMES.get(platform, platform)
    return E.push_notice("manual_ready", _t("manual_ready", p=p), _t("manual_body", t=_title(project, cid)), None)


def failed(project, cid: str, platform: str, message: str, hint: str | None = None) -> dict:
    p = NAMES.get(platform, platform)
    m = message + (f" {hint}" if hint else "")
    return E.push_notice("share_failed", _t("failed", p=p), _t("failed_body", t=_title(project, cid), m=m[:300]), None)


def on_record(project, cid: str, platform: str, before: dict, after: dict) -> None:
    """platforms.record hook: a TikTok / Instagram post changed state."""
    old, new = before.get("status"), after.get("status")
    if new == old:
        return
    try:
        if new == "published":
            shared(project, cid, platform, after.get("url"), manual=bool(after.get("manual")))
        elif new == "ready" and after.get("mode") == "semi":
            manual_ready(project, cid, platform)
        elif new == "failed" and not after.get("next_try_at"):
            err = after.get("error") or {}
            failed(project, cid, platform, str(err.get("message") or "Something went wrong."), err.get("hint"))
    except Exception:  # noqa: BLE001 - a notice never breaks the post itself
        pass
