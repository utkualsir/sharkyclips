"""One-click "Connect with Google": a one-shot sign-in listener on a random loopback port.

start() opens a tiny HTTP server on 127.0.0.1:<random port>, builds the Google sign-in URL
(youtube.auth_url: PKCE, redirect back to that port) and opens it in the system browser.
Google sends the browser back to http://127.0.0.1:<port>/?code=..&state=..; the listener
finishes the sign-in, shows a SharkyClips-styled result page in the UI language and stops.
The UI polls get(flow_id) (once a second), so the channel shows up the moment Google is done.

States: waiting -> ok | no_channel | choose_channel | cancelled | error | expired.
Only one sign-in runs at a time; a new start() cancels the old one.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.parse
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, youtube
from .errors import SharkyClipsError

TIMEOUT = 10 * 60  # seconds a sign-in may take before the listener gives up

_lock = threading.RLock()
_flows: dict[str, dict] = {}  # flow id (= OAuth state) -> flow


def _lang() -> str:
    code = str(config.get("ui_language") or "en").split("-")[0].lower()
    return code if code in TEXT else "en"


def _view(flow: dict) -> dict:
    return {k: flow.get(k) for k in ("id", "status", "message", "hint", "reason", "port", "created")}


def get(flow_id: str) -> dict:
    with _lock:
        flow = _flows.get(flow_id)
    if flow is None:
        raise SharkyClipsError("This sign-in isn't running any more.", "Click Connect again.")
    return _view(flow)


def cancel(flow_id: str | None = None) -> None:
    """Stop a waiting sign-in (the user clicked Cancel, or a new one started)."""
    with _lock:
        ids = [flow_id] if flow_id else list(_flows)
        for fid in ids:
            flow = _flows.get(fid)
            if flow and flow["status"] == "waiting":
                flow["status"] = "cancelled"
                flow["reason"] = "app"
                _stop(flow)


def _stop(flow: dict) -> None:
    youtube.forget_pending(flow["id"])
    srv = flow.pop("server", None)
    if srv is not None:
        def close():
            srv.shutdown()
            srv.server_close()

        threading.Thread(target=close, daemon=True).start()


def _finish(flow: dict, status: str, message: str | None = None, hint: str | None = None,
            reason: str | None = None) -> None:
    with _lock:
        flow.update(status=status, message=message, hint=hint, reason=reason, finished=time.time())
        _stop(flow)


def start(open_browser: bool = True) -> dict:
    """Begin a sign-in. Returns {id, url, opened, port}."""
    cancel()
    with _lock:  # forget old, finished flows
        for k in [k for k, f in _flows.items() if f["status"] != "waiting" and time.time() - f["created"] > 3600]:
            _flows.pop(k, None)

    holder: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):  # noqa: N802 - http.server API
            flow = holder.get("flow")
            parts = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(parts.query))
            if parts.path != "/" or flow is None or q.get("state") != flow["id"]:
                self._send(404, _page("error", _lang(), detail="Not found."))
                return
            if flow["status"] != "waiting":  # reloaded the tab
                self._send(200, _page(flow["status"], _lang(), channel=flow.get("channel")))
                return
            _handle(flow, q)
            self._send(200, _page(flow["status"], _lang(), channel=flow.get("channel"),
                                  detail=flow.get("message")))

        def _send(self, code: int, html: str):
            data = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")  # the code is in our URL
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    try:
        auth = youtube.auth_url(f"http://127.0.0.1:{port}/")
    except Exception:
        server.server_close()
        raise
    state = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(auth).query))["state"]
    flow = {"id": state, "status": "waiting", "port": port, "created": time.time(), "server": server,
            "url": auth, "message": None, "hint": None, "reason": None}
    holder["flow"] = flow
    with _lock:
        _flows[state] = flow
    threading.Thread(target=server.serve_forever, daemon=True, name="yt-signin").start()

    def expire():
        with _lock:
            if flow["status"] == "waiting":
                _finish(flow, "expired", "The sign-in took too long.", "Click Connect again.", "timeout")

    timer = threading.Timer(TIMEOUT, expire)
    timer.daemon = True
    timer.start()

    opened = False
    if open_browser and not os.environ.get("SHARKYCLIPS_NO_BROWSER"):
        try:
            opened = bool(webbrowser.open(auth, new=2))
        except Exception:  # noqa: BLE001 - the UI shows the link instead
            opened = False
    return {"id": state, "url": auth, "opened": opened, "port": port}


def _handle(flow: dict, q: dict) -> None:
    """Google came back: finish the sign-in and decide what the user sees."""
    err = q.get("error")
    if err:
        if err == "access_denied":  # Cancel on Google's screen
            _finish(flow, "cancelled", reason="google")
        else:
            _finish(flow, "error", f"Google said: {err}", "Try again.", err)
        return
    try:
        st = youtube.finish_auth(q.get("code") or "", flow["id"])
    except SharkyClipsError as exc:
        reason = getattr(exc, "reason", None)
        if reason in ("accessNotConfigured", "SERVICE_DISABLED", "forbidden", "PERMISSION_DENIED"):
            _finish(flow, "api_disabled", exc.message, exc.hint, reason)
        else:
            _finish(flow, "error", exc.message, exc.hint, reason)
        return
    except Exception as exc:  # noqa: BLE001 - network trouble: say so on the page and in the app
        _finish(flow, "error", f"Could not reach Google ({type(exc).__name__}).", "Check the internet "
                "connection and try again.", "network")
        return
    flow["channel"] = st.get("channel")
    if st.get("no_channel"):
        _finish(flow, "no_channel", reason="no_channel")
    elif len(st.get("channels") or []) > 1:
        _finish(flow, "choose_channel", reason="several")
    else:
        _finish(flow, "ok")


# ------------------------------------------------------------------ the page in the browser tab

TEXT: dict[str, dict[str, str]] = {
    "en": {"ok": "Connected!", "ok_body": "SharkyClips can now publish to {name}. You can close this tab.",
           "ok_plain": "SharkyClips can now publish to your channel. You can close this tab.",
           "no_channel": "Signed in, but there's no YouTube channel yet",
           "no_channel_body": "Create a free channel on YouTube, then go back to SharkyClips and click Check again.",
           "create": "Create a channel", "choose_channel": "Connected!",
           "choose_channel_body": "Go back to SharkyClips and pick the channel to publish to.",
           "cancelled": "Connection cancelled", "cancelled_body": "Nothing was changed. You can close this tab "
           "and try again in SharkyClips whenever you like.",
           "error": "Couldn't connect", "error_body": "Go back to SharkyClips: it says what to do next.",
           "api_disabled": "One step is missing in your Google project",
           "expired": "This sign-in has expired", "close": "Close this tab",
           "closing": "This tab closes by itself in a moment."},
    "tr": {"ok": "Bağlandı!", "ok_body": "SharkyClips artık {name} kanalında yayınlayabilir. Bu sekmeyi kapatabilirsin.",
           "ok_plain": "SharkyClips artık kanalında yayınlayabilir. Bu sekmeyi kapatabilirsin.",
           "no_channel": "Giriş yapıldı ama henüz bir YouTube kanalın yok",
           "no_channel_body": "YouTube'da ücretsiz bir kanal aç, sonra SharkyClips'e dönüp Tekrar kontrol et'e tıkla.",
           "create": "Kanal oluştur", "choose_channel": "Bağlandı!",
           "choose_channel_body": "SharkyClips'e dön ve yayınlanacak kanalı seç.",
           "cancelled": "Bağlantı iptal edildi", "cancelled_body": "Hiçbir şey değişmedi. Bu sekmeyi kapatıp "
           "istediğin zaman SharkyClips'te tekrar deneyebilirsin.",
           "error": "Bağlanamadı", "error_body": "SharkyClips'e dön: ne yapman gerektiğini orada yazıyor.",
           "api_disabled": "Google projende bir adım eksik",
           "expired": "Bu girişin süresi doldu", "close": "Sekmeyi kapat",
           "closing": "Bu sekme birazdan kendiliğinden kapanır."},
    "de": {"ok": "Verbunden!", "ok_body": "SharkyClips kann jetzt auf {name} veröffentlichen. Du kannst diesen Tab schließen.",
           "ok_plain": "SharkyClips kann jetzt auf deinem Kanal veröffentlichen. Du kannst diesen Tab schließen.",
           "no_channel": "Angemeldet, aber es gibt noch keinen YouTube-Kanal",
           "no_channel_body": "Erstelle kostenlos einen Kanal auf YouTube, geh dann zurück zu SharkyClips und klick auf Erneut prüfen.",
           "create": "Kanal erstellen", "choose_channel": "Verbunden!",
           "choose_channel_body": "Geh zurück zu SharkyClips und wähle den Kanal aus.",
           "cancelled": "Verbindung abgebrochen", "cancelled_body": "Nichts wurde geändert. Schließ diesen Tab "
           "und versuch es jederzeit in SharkyClips erneut.",
           "error": "Verbindung fehlgeschlagen", "error_body": "Geh zurück zu SharkyClips: dort steht, was zu tun ist.",
           "api_disabled": "In deinem Google-Projekt fehlt ein Schritt",
           "expired": "Diese Anmeldung ist abgelaufen", "close": "Tab schließen",
           "closing": "Dieser Tab schließt sich gleich von selbst."},
    "hu": {"ok": "Csatlakozva!", "ok_body": "A SharkyClips mostantól közzétehet a(z) {name} csatornán. Bezárhatod ezt a lapot.",
           "ok_plain": "A SharkyClips mostantól közzétehet a csatornádon. Bezárhatod ezt a lapot.",
           "no_channel": "Bejelentkeztél, de még nincs YouTube-csatornád",
           "no_channel_body": "Hozz létre egy ingyenes csatornát a YouTube-on, majd a SharkyClipsben kattints az Újraellenőrzésre.",
           "create": "Csatorna létrehozása", "choose_channel": "Csatlakozva!",
           "choose_channel_body": "Térj vissza a SharkyClipsbe, és válaszd ki a csatornát.",
           "cancelled": "A csatlakozás megszakadt", "cancelled_body": "Semmi sem változott. Bezárhatod ezt a lapot, "
           "és bármikor újrapróbálhatod a SharkyClipsben.",
           "error": "Nem sikerült csatlakozni", "error_body": "Térj vissza a SharkyClipsbe: ott látod, mi a teendő.",
           "api_disabled": "Egy lépés hiányzik a Google-projektedből",
           "expired": "Ez a bejelentkezés lejárt", "close": "Lap bezárása",
           "closing": "Ez a lap mindjárt magától bezárul."},
    "ru": {"ok": "Подключено!", "ok_body": "Теперь SharkyClips может публиковать на канале {name}. Эту вкладку можно закрыть.",
           "ok_plain": "Теперь SharkyClips может публиковать на вашем канале. Эту вкладку можно закрыть.",
           "no_channel": "Вход выполнен, но канала YouTube пока нет",
           "no_channel_body": "Создайте бесплатный канал на YouTube, затем вернитесь в SharkyClips и нажмите «Проверить снова».",
           "create": "Создать канал", "choose_channel": "Подключено!",
           "choose_channel_body": "Вернитесь в SharkyClips и выберите канал для публикации.",
           "cancelled": "Подключение отменено", "cancelled_body": "Ничего не изменилось. Закройте вкладку и "
           "попробуйте снова в SharkyClips, когда захотите.",
           "error": "Не удалось подключиться", "error_body": "Вернитесь в SharkyClips: там написано, что делать дальше.",
           "api_disabled": "В вашем проекте Google не хватает одного шага",
           "expired": "Срок этого входа истёк", "close": "Закрыть вкладку",
           "closing": "Вкладка сейчас закроется сама."},
    "ar": {"ok": "تم الربط!", "ok_body": "يمكن لـ SharkyClips الآن النشر على {name}. يمكنك إغلاق هذا التبويب.",
           "ok_plain": "يمكن لـ SharkyClips الآن النشر على قناتك. يمكنك إغلاق هذا التبويب.",
           "no_channel": "تم تسجيل الدخول، لكن لا توجد قناة يوتيوب بعد",
           "no_channel_body": "أنشئ قناة مجانية على يوتيوب، ثم عد إلى SharkyClips واضغط «تحقق مجددًا».",
           "create": "إنشاء قناة", "choose_channel": "تم الربط!",
           "choose_channel_body": "عد إلى SharkyClips واختر القناة التي تريد النشر عليها.",
           "cancelled": "أُلغي الربط", "cancelled_body": "لم يتغير شيء. أغلق هذا التبويب وحاول مجددًا في "
           "SharkyClips متى شئت.",
           "error": "تعذّر الربط", "error_body": "عد إلى SharkyClips: ستجد هناك الخطوة التالية.",
           "api_disabled": "ينقص مشروعك على Google خطوة واحدة",
           "expired": "انتهت صلاحية تسجيل الدخول هذا", "close": "إغلاق التبويب",
           "closing": "سيُغلق هذا التبويب تلقائيًا بعد قليل."},
    "zh": {"ok": "已连接！", "ok_body": "SharkyClips 现在可以发布到 {name}。你可以关闭此标签页。",
           "ok_plain": "SharkyClips 现在可以发布到你的频道。你可以关闭此标签页。",
           "no_channel": "已登录，但还没有 YouTube 频道",
           "no_channel_body": "先在 YouTube 免费创建一个频道，然后回到 SharkyClips 点击“重新检查”。",
           "create": "创建频道", "choose_channel": "已连接！",
           "choose_channel_body": "回到 SharkyClips，选择要发布的频道。",
           "cancelled": "已取消连接", "cancelled_body": "没有任何更改。关闭此标签页，随时可在 SharkyClips 中重试。",
           "error": "无法连接", "error_body": "回到 SharkyClips：那里会告诉你下一步怎么做。",
           "api_disabled": "你的 Google 项目还缺一步",
           "expired": "此登录已过期", "close": "关闭标签页",
           "closing": "此标签页稍后会自动关闭。"},
}

_FIN = "M13 44C17.5 33 28 18 48.5 11.5C42 20 39.5 32 46.5 44ZM25.5 30L25.5 40.5L35 35.25Z"
_WAVE = ("M8 50Q11 48.4 14 50Q17 51.6 20 50Q23 48.4 26 50Q29 51.6 32 50Q35 48.4 38 50Q41 51.6 44 50Q47 48.4 "
         "50 50Q53 51.6 56 50")


def _page(status: str, lang: str, channel: dict | None = None, detail: str | None = None) -> str:
    tx = TEXT.get(lang, TEXT["en"])
    good = status in ("ok", "choose_channel")
    title = tx.get(status) or tx["error"]
    name = (channel or {}).get("title")
    if status == "ok":
        body = tx["ok_body"].format(name=f"<b>{escape(name)}</b>") if name else escape(tx["ok_plain"])
    elif status in ("choose_channel", "no_channel", "cancelled"):
        body = escape(tx[f"{status}_body"])
    else:
        body = escape(tx["error_body"])
    extra = ""
    if status == "no_channel":
        extra = f'<a class="btn" href="{youtube.CREATE_CHANNEL_URL}">{escape(tx["create"])}</a>'
    elif not good and detail:
        extra = f'<p class="detail">{escape(detail)}</p>'
    avatar = ""
    thumb = (channel or {}).get("thumbnail")
    if good and thumb and str(thumb).startswith("https://"):
        avatar = f'<img class="avatar" src="{escape(thumb)}" alt="" referrerpolicy="no-referrer">'
    icon = ('<svg class="badge ok" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" '
            'fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
            if good else
            '<svg class="badge bad" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7v6M12 16.5v.5" fill="none" '
            'stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>')
    close_js = ("setTimeout(function(){try{window.close()}catch(e){}},2500);" if good else "")
    rtl = ' dir="rtl"' if lang == "ar" else ""
    hint = f'<p class="muted" id="closing">{escape(tx["closing"])}</p>' if good else ""
    return f"""<!doctype html><html lang="{lang}"{rtl}><head><meta charset="utf-8">
<title>SharkyClips</title><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='6 8 52 48'%3E%3Cpath fill='%231F6FE5' fill-rule='evenodd' d='{_FIN}'/%3E%3C/svg%3E">
<style>
:root{{--bg:#f4f7fd;--card:#fff;--text:#0e1a33;--muted:#55617a;--border:#e4e8f0;--ok:#17694a;--bad:#a3341f;--accent:#1f6fe5}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a1020;--card:#111a2e;--text:#eef2f8;--muted:#aeb7ca;--border:#25324f;--ok:#4fd39a;--bad:#ff8a75;--accent:#5b9bff}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}}
main{{width:100%;max-width:440px;background:var(--card);border:1px solid var(--border);border-radius:20px;
padding:32px 24px;text-align:center;box-shadow:0 12px 40px rgba(14,26,51,.08)}}
.logo{{width:56px;height:52px;display:block;margin:0 auto 8px}}
.badge{{width:44px;height:44px;border-radius:50%;padding:8px;margin:8px auto 4px;display:block}}
.ok{{color:#fff;background:var(--ok)}}.bad{{color:#fff;background:var(--bad)}}
.avatar{{width:56px;height:56px;border-radius:50%;display:block;margin:12px auto 0;border:2px solid var(--border)}}
h1{{font-size:24px;font-weight:600;margin:12px 0 8px}}p{{color:var(--muted);line-height:1.55;margin:8px 0}}
p b{{color:var(--text)}}.detail{{font-size:13px;background:var(--bg);border-radius:10px;padding:8px 12px}}
.btn{{display:inline-block;margin-top:12px;padding:10px 18px;border-radius:999px;background:var(--accent);color:#fff;
text-decoration:none;font-weight:600}}.btn:focus-visible{{outline:3px solid var(--text);outline-offset:2px}}
.muted{{font-size:12.5px}}
@media (prefers-reduced-motion:no-preference){{main{{animation:pop .35s ease-out}}@keyframes pop{{from{{opacity:0;transform:translateY(8px)}}}}}}
</style></head><body><main role="main" aria-live="polite">
<svg class="logo" viewBox="6 8 52 48" aria-hidden="true"><path fill="#1F6FE5" fill-rule="evenodd" d="{_FIN}"/>
<path d="{_WAVE}" fill="none" stroke="#A9C6F3" stroke-width="3.4" stroke-linecap="round"/></svg>
{icon}{avatar}<h1>{escape(title)}</h1><p>{body}</p>{extra}{hint}
</main><script>{close_js}</script></body></html>"""
