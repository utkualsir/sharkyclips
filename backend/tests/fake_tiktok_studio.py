"""A local fake TikTok Studio (1.2.42 tests): the same data-e2e structure as the real upload page
(Turkish UI texts), so tiktok_browser.py runs its real steps against it.

Modes (FakeStudio.mode): normal | captcha (a CAPTCHA after the file is chosen) | uploadfail |
uichanged (no caption editor) | captcha_content (CAPTCHA on the content list) | nologin.
What was "posted" lands in FakeStudio.posts (caption text, schedule, date, time, visibility,
switches) and shows on /tiktokstudio/content; FakeStudio.seed adds rows posted earlier.
"""

from __future__ import annotations

import html
import json
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPLOAD_PAGE = r"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>TikTok Studio</title>
<style>
 body{font-family:sans-serif;margin:20px} .hidden{display:none!important}
 [role=switch]{display:inline-block;width:36px;height:20px;background:#ccc;border-radius:10px;cursor:pointer}
 [role=switch][aria-checked=true]{background:#fe2c55}
 .public-DraftEditor-content{min-height:60px;border:1px solid #999;padding:6px;white-space:pre-wrap}
 #suggest{border:1px solid #333;padding:4px;width:200px} .tiktok-timepicker-option-item{display:block;padding:2px 6px;cursor:pointer}
 .col{display:inline-block;vertical-align:top;height:160px;overflow:auto;border:1px solid #ddd}
 .day{display:inline-block;width:28px;height:22px;text-align:center;cursor:pointer} .day.invalid{color:#bbb}
 .arrow{display:inline-block;padding:4px 10px;cursor:pointer} #captcha-verify-container{position:fixed;left:20%;top:20%;width:320px;height:220px;background:#fff;border:2px solid #000;z-index:9}
</style></head><body>
<div data-e2e="draft_banner">Düzenlemekte olduğunuz bir video kaydedilmedi. <button>Sil</button> <button>Devam</button></div>
<div data-e2e="select_video_container"><input type="file" accept="video/*" id="file" style="display:none">
  <button data-e2e="select_video_button" onclick="document.getElementById('file').click()">Video seç</button></div>
<div id="area" class="hidden">
 <div data-e2e="upload_status_container" id="status"></div>
 __CAPTION__
 <div data-e2e="video_visibility_container"><span>Bu videoyu kimler izleyebilir</span>
   <button role="combobox" id="vis">Arkadaşlar</button>
   <div role="listbox" id="visopts" class="hidden"><div role="option">Herkes</div><div role="option">Arkadaşlar</div><div role="option">Yalnızca ben</div></div></div>
 <div data-e2e="schedule_container">
   <label><input type="radio" name="postSchedule" value="post_now" checked> Şimdi</label>
   <label><input type="radio" name="postSchedule" value="schedule"> Planla</label>
   <div id="when" class="hidden">
     <input class="TUXTextInputCore-input" id="time" readonly>
     <input class="TUXTextInputCore-input" id="date" readonly>
     <div id="tp" class="hidden"><div class="col" id="hcol"></div><div class="col" id="mcol"></div></div>
     <div id="cal" class="calendar-wrapper hidden"><span class="arrow" id="prev">&lt;</span><span class="month-title" id="mt"></span><span class="arrow" id="next">&gt;</span><div class="days-wrapper" id="days"></div></div>
   </div>
 </div>
 <div data-e2e="advanced_settings_container"><button id="more">Daha fazla göster</button></div>
 <div id="moreArea" class="hidden">
   <div data-e2e="user_perm_container"><label><input type="checkbox" id="c_comment"> Yorum</label> <label><input type="checkbox" id="c_duet" checked> Düet</label></div>
   <div data-e2e="disclose_content_container">Ticari içerik <span role="switch" aria-checked="false" id="disc"></span></div>
   <div data-e2e="aigc_container">Yapay zeka ile oluşturuldu <span role="switch" aria-checked="false" id="aigc"></span></div>
 </div>
 <div data-e2e="copyright_container"></div>
 <button data-e2e="save_draft_button">Taslak</button> <button data-e2e="discard_post_button">At</button>
 <button data-e2e="post_video_button" id="post" disabled>Paylaş</button>
</div>
<script>
const MODE = "__MODE__";
const $ = (id) => document.getElementById(id);
const pad = (n) => String(n).padStart(2, '0');
let shown = new Date();
const today = new Date(); today.setHours(0,0,0,0);
const last = new Date(today.getTime() + 10*86400000);
function iso(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()); }
$('file').addEventListener('change', () => {
  const f = $('file').files[0]; if (!f) return;
  $('area').classList.remove('hidden');
  if (MODE === 'captcha') { const c = document.createElement('div'); c.id = 'captcha-verify-container'; c.textContent = 'Bulmacayı çöz'; document.body.appendChild(c); return; }
  let pct = 0;
  const tick = setInterval(() => {
    pct += 25;
    if (MODE === 'uploadfail' && pct >= 50) { clearInterval(tick); $('status').textContent = 'Yükleme başarısız. Tekrar deneyin.'; return; }
    if (pct < 100) { $('status').textContent = 'Yükleniyor ' + pct + '%'; return; }
    clearInterval(tick);
    $('status').textContent = 'Yüklendi (' + (f.size/1048576).toFixed(2) + ' MB)';
    const cap = document.querySelector('.public-DraftEditor-content');
    if (cap) cap.textContent = f.name.replace(/\.[^.]+$/, '');
    $('post').disabled = false;
  }, 120);
});
const cap = document.querySelector('.public-DraftEditor-content');
if (cap) {
  const sug = $('suggest');
  const tail = () => (cap.innerText || '').replace(/\n$/, '');
  cap.addEventListener('input', () => { sug.classList.toggle('hidden', !/#[^\s#]+$/.test(tail()) && !/@[^\s@]+$/.test(tail())); });
  cap.addEventListener('keydown', (e) => {
    if (sug.classList.contains('hidden')) return;
    if (e.key === 'Escape') { sug.classList.add('hidden'); }
    if (e.key === 'Enter') {  // the trap: Enter picks the first suggestion
      e.preventDefault(); window.__picked = (window.__picked || 0) + 1;
      document.execCommand('insertText', false, 'suggested ');
      sug.classList.add('hidden');
    }
  });
}
$('vis').addEventListener('click', () => $('visopts').classList.toggle('hidden'));
document.querySelectorAll('#visopts [role=option]').forEach((o) => o.addEventListener('click', () => { $('vis').textContent = o.textContent; $('visopts').classList.add('hidden'); }));
document.querySelectorAll('input[name=postSchedule]').forEach((r) => r.addEventListener('change', () => {
  const s = document.querySelector('input[name=postSchedule]:checked').value === 'schedule';
  $('when').classList.toggle('hidden', !s); $('post').textContent = s ? 'Planla' : 'Paylaş';
  if (s && !$('time').value) { const d = new Date(Date.now() + 20*60000); d.setMinutes(Math.ceil(d.getMinutes()/5)*5);
    $('time').value = pad(d.getHours()) + ':' + pad(d.getMinutes()); $('date').value = iso(d); shown = new Date(d); }
}));
for (let h = 0; h < 24; h++) { const s = document.createElement('span'); s.className = 'tiktok-timepicker-option-item'; s.textContent = pad(h);
  s.onclick = () => { $('time').value = pad(h) + ':' + $('time').value.split(':')[1]; }; $('hcol').appendChild(s); }
for (let m = 0; m < 60; m += 5) { const s = document.createElement('span'); s.className = 'tiktok-timepicker-option-item'; s.textContent = pad(m);
  s.onclick = () => { $('time').value = $('time').value.split(':')[0] + ':' + pad(m); }; $('mcol').appendChild(s); }
$('time').addEventListener('click', () => { $('tp').classList.remove('hidden'); $('cal').classList.add('hidden'); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { $('tp').classList.add('hidden'); $('cal').classList.add('hidden'); } });
function drawCal() {
  $('mt').textContent = shown.getFullYear() + '-' + pad(shown.getMonth()+1);
  const days = $('days'); days.innerHTML = '';
  const n = new Date(shown.getFullYear(), shown.getMonth()+1, 0).getDate();
  for (let d = 1; d <= n; d++) { const day = new Date(shown.getFullYear(), shown.getMonth(), d);
    const ok = day >= today && day <= last; const s = document.createElement('span');
    s.className = 'day ' + (ok ? 'valid' : 'invalid'); s.textContent = String(d);
    if (ok) s.onclick = () => { $('date').value = iso(day); $('cal').classList.add('hidden'); };
    days.appendChild(s); }
}
$('date').addEventListener('click', () => { const [y, m] = $('date').value.split('-').map(Number); shown = new Date(y, m-1, 1); drawCal(); $('cal').classList.remove('hidden'); $('tp').classList.add('hidden'); });
$('prev').onclick = () => { shown = new Date(shown.getFullYear(), shown.getMonth()-1, 1); drawCal(); };
$('next').onclick = () => { shown = new Date(shown.getFullYear(), shown.getMonth()+1, 1); drawCal(); };
$('more').addEventListener('click', () => $('moreArea').classList.toggle('hidden'));
document.querySelectorAll('[role=switch]').forEach((s) => s.addEventListener('click', () => s.setAttribute('aria-checked', s.getAttribute('aria-checked') === 'true' ? 'false' : 'true')));
$('post').addEventListener('click', async () => {
  const body = {caption: cap ? cap.innerText : '', schedule: document.querySelector('input[name=postSchedule]:checked').value,
    date: $('date').value, time: $('time').value, visibility: $('vis').textContent,
    aigc: $('aigc').getAttribute('aria-checked') === 'true', disclose: $('disc').getAttribute('aria-checked') === 'true',
    comment: $('c_comment').checked, duet: $('c_duet').checked, picked: window.__picked || 0};
  await fetch('/__post', {method: 'POST', body: JSON.stringify(body)});
  location.href = '/tiktokstudio/content';
});
</script></body></html>"""

CAPTION = """<div data-e2e="caption_container"><span>Açıklama</span>
 <div class="DraftEditor-root"><div class="public-DraftEditor-content" contenteditable="true" role="combobox" spellcheck="false"></div></div>
 <div id="suggest" class="hidden" data-e2e="hashtag-suggest">#suggested</div></div>"""


class FakeStudio:
    def __init__(self):
        self.mode = "normal"
        self.posts: list[dict] = []
        self.seed: list[dict] = []  # {"caption", "scheduled": "14 Kas, 18:00 (GMT+1) Budapest" | None, "id"}
        self.username = "fakeuser"
        self.server = None
        self.thread = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def rows(self) -> list[dict]:
        out = list(self.seed)
        for i, p in enumerate(self.posts):
            sched = None
            if p.get("schedule") == "schedule":
                d = datetime.strptime(p["date"] + " " + p["time"], "%Y-%m-%d %H:%M")
                sched = f"{d.day} Kas, {p['time']} (GMT+1) Budapest"
            out.append({"caption": p["caption"], "scheduled": sched, "id": f"73000000000000{i:05d}"})
        return list(reversed(out))

    def start(self) -> "FakeStudio":
        studio = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _logged(self) -> bool:
                return "sessionid=" in (self.headers.get("Cookie") or "") and studio.mode != "nologin"

            def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8", headers=None):
                data = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/__autologin":
                    return self._send(302, "", headers={"Location": "/tiktokstudio/content",
                                                        "Set-Cookie": "sessionid=fake123; Path=/; Max-Age=86400"})
                if path == "/login":
                    return self._send(200, '<!doctype html><html><body><div id="loginContainer" style="width:300px;height:200px">'
                                      '<button id="go" onclick="document.cookie=\'sessionid=fake123; path=/; max-age=86400\';'
                                      'location.href=\'/tiktokstudio/content\'">Giriş yap</button></div></body></html>')
                if path.startswith("/passport/web/account/info"):
                    return self._send(200, json.dumps({"data": {"username": studio.username} if self._logged() else {}}),
                                      "application/json")
                if path.startswith("/tiktokstudio"):
                    if not self._logged():
                        return self._send(302, "", headers={"Location": "/login"})
                    if path == "/tiktokstudio/upload":
                        page = UPLOAD_PAGE.replace("__MODE__", studio.mode).replace(
                            "__CAPTION__", "" if studio.mode == "uichanged" else CAPTION)
                        return self._send(200, page)
                    if path == "/tiktokstudio/content":
                        rows = []
                        for r in studio.rows():
                            first = html.escape(r["caption"].split("\n")[0])
                            meta = html.escape(r["scheduled"]) if r.get("scheduled") else "Herkes · 12 görüntülenme · 13 Kas, 21:00"
                            link = "" if r.get("scheduled") else f'<a href="https://www.tiktok.com/@{studio.username}/video/{r["id"]}">Aç</a>'
                            rows.append(f'<div class="row" data-e2e="content_row"><div class="info"><span class="cap">{first}</span>'
                                        f'<span class="meta">{meta}</span></div>{link}</div>')
                        extra = ('<div id="captcha-verify-container">Doğrula</div>'
                                 if studio.mode == "captcha_content" else "")
                        return self._send(200, "<!doctype html><html><body><h1>Gönderiler</h1>"
                                          + "".join(rows) + extra + "</body></html>")
                return self._send(404, "not found")

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8") if n else "{}"
                if self.path == "/__post":
                    studio.posts.append(json.loads(body))
                    return self._send(200, "{}", "application/json")
                return self._send(404, "not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()


def ahead(days: int = 2, hour: int = 18, minute: int = 0) -> datetime:
    d = (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return d.astimezone()
