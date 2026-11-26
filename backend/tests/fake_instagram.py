"""A local fake instagram.com "New post" flow (1.2.70 assisted upload tests), English UI, shaped
like the real web dialog: the Create link (svg aria-label "New post") -> Post menu -> a dialog
with the file box -> "Video posts are now shared as reels" (OK) -> crop (Select crop -> Original)
-> Next -> edit -> Next -> caption box (contenteditable, role=textbox) + Share. Share posts it
(FakeInstagram.posts) and shows "Your reel has been shared."; FakeInstagram.user_posts clicks Share
like a person once SharkyClips outlined it. logged_in False shows the login page first
(user_login: the "person" logs in after a moment).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Instagram</title>
<style>body{font-family:sans-serif} [role=dialog]{position:fixed;left:20%;top:10%;width:60%;min-height:300px;background:#fff;border:1px solid #333;padding:10px}
 .hidden{display:none!important} [role=button]{display:inline-block;padding:4px 8px;cursor:pointer;color:#0095f6}
 [contenteditable]{min-height:60px;border:1px solid #999;white-space:pre-wrap}</style></head><body>
<nav><a href="#" role="link" id="create"><svg aria-label="New post" width="24" height="24"><rect width="24" height="24"/></svg><span>Create</span></a></nav>
<div id="menu" class="hidden"><a href="#" role="link" id="m_post"><span>Post</span></a> <a href="#" role="link"><span>Live video</span></a></div>
<div role="dialog" id="dlg" class="hidden"><h1 id="head">Create new post</h1><div id="body"></div></div>
<script>
const $ = (id) => document.getElementById(id);
let crop = "1:1", file = null;
$('create').onclick = (e) => { e.preventDefault(); $('menu').classList.remove('hidden'); };
$('m_post').onclick = (e) => { e.preventDefault(); $('menu').classList.add('hidden'); step0(); };
function head(title, right) { $('head').innerHTML = title + (right ? ' <div role="button" id="hbtn">' + right + '</div>' : ''); }
function step0() {
  $('dlg').classList.remove('hidden'); head('Create new post');
  $('body').innerHTML = '<p>Drag photos and videos here</p><button type="button" id="pick">Select from computer</button>'
    + '<form enctype="multipart/form-data"><input type="file" accept="image/jpeg,image/png,video/mp4,video/quicktime" id="f" style="display:none"></form>';
  $('pick').onclick = () => $('f').click();
  $('f').addEventListener('change', () => { file = $('f').files[0]; if (file) reelsNote(); });
}
function reelsNote() {
  head('Video posts are now shared as reels');
  $('body').innerHTML = '<p>Your video will be shared as a reel.</p><button type="button" id="ok">OK</button>';
  $('ok').onclick = cropStep;
}
function cropStep() {
  head('Crop', 'Next');
  $('body').innerHTML = '<div>preview ' + crop + '</div><button type="button" id="cb"><svg aria-label="Select crop" width="16" height="16"><rect width="16" height="16"/></svg></button>'
    + '<div id="crops" class="hidden"><div role="button" id="orig"><span>Original</span></div><div role="button"><span>1:1</span></div><div role="button"><span>9:16</span></div></div>';
  $('cb').onclick = () => $('crops').classList.toggle('hidden');
  $('orig').onclick = () => { crop = 'original'; $('crops').classList.add('hidden'); };
  $('hbtn').onclick = editStep;
}
function editStep() { head('Edit', 'Next'); $('body').innerHTML = '<div>Cover photo / Trim</div>'; $('hbtn').onclick = capStep; }
function capStep() {
  head('Create new reel', 'Share');
  $('body').innerHTML = '<div contenteditable="true" role="textbox" aria-label="Write a caption..." id="cap"></div>';
  $('hbtn').onclick = async () => {
    await fetch('/fakeig/__post', {method: 'POST', body: JSON.stringify({caption: $('cap').innerText, crop, name: file && file.name, size: file && file.size})});
    head('Reel shared'); $('body').innerHTML = '<p>Your reel has been shared.</p>';
  };
}
__USER__
</script></body></html>"""

USER = """const iv = setInterval(() => { const b = document.getElementById('hbtn');
 if (document.getElementById('sharkyclips-assist') && b && b.style.outline) { clearInterval(iv); setTimeout(() => b.click(), 700); } }, 300);"""

LOGIN = """<!doctype html><html><body><form><input name="username"><input name="password" type="password">
<button type="button" id="go" onclick="document.cookie='ig_session=1; path=/'; location.href='/fakeig/'">Log in</button></form>
__AUTO__</body></html>"""


class FakeInstagram:
    def __init__(self):
        self.posts: list[dict] = []
        self.user_posts = False
        self.user_login = False
        self.logged_in = True
        self.server = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self) -> "FakeInstagram":
        ig = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

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
                logged = ig.logged_in or "ig_session=1" in (self.headers.get("Cookie") or "")
                if path.startswith("/fakeig/accounts/login"):
                    auto = ("<script>setTimeout(() => document.getElementById('go').click(), 2500)</script>"
                            if ig.user_login else "")
                    return self._send(200, LOGIN.replace("__AUTO__", auto))
                if path.startswith("/fakeig"):
                    if not logged:
                        return self._send(302, "", headers={"Location": "/fakeig/accounts/login/"})
                    return self._send(200, PAGE.replace("__USER__", USER if ig.user_posts else ""))
                return self._send(404, "not found")

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8") if n else "{}"
                if self.path == "/fakeig/__post":
                    ig.posts.append(json.loads(body))
                    return self._send(200, "{}", "application/json")
                return self._send(404, "not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
