"""YouTube sign-in, token refresh and resumable upload against a scripted fake HTTP layer."""

from __future__ import annotations

import urllib.parse

import pytest

from sharkyclips import youtube
from sharkyclips.errors import SharkyClipsError


class Res:
    def __init__(self, status: int, body=None, headers: dict | None = None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeHTTP:
    """Stands in for `requests`: answers come from a list, calls are recorded."""

    class RequestException(Exception):
        pass

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str, dict]] = []

    def _next(self, method, url, kw):
        self.calls.append((method, url, kw))
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a(method, url, kw) if callable(a) else a

    def get(self, url, **kw):
        return self._next("GET", url, kw)

    def post(self, url, **kw):
        return self._next("POST", url, kw)

    def put(self, url, **kw):
        return self._next("PUT", url, kw)


@pytest.fixture
def http(monkeypatch):
    def install(*answers):
        fake = FakeHTTP(answers)
        monkeypatch.setattr(youtube, "_http", lambda: fake)
        return fake

    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    for name in ("token.json", "token.enc", "client.json", "quota.json", "sessions.json", "locked.json", "unlocked.json"):
        (youtube.folder() / name).unlink(missing_ok=True)
    youtube.set_client({"installed": {"client_id": "1.apps.googleusercontent.com", "client_secret": "sec"}})
    yield install
    for name in ("token.json", "token.enc", "client.json", "quota.json", "sessions.json", "locked.json", "unlocked.json"):
        (youtube.folder() / name).unlink(missing_ok=True)


def _connect(http):
    url = youtube.auth_url("http://127.0.0.1:8123/")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    fake = http(Res(200, {"access_token": "A1", "refresh_token": "R1", "expires_in": 3600, "scope": "s"}),
                Res(200, {"items": [{"id": "UC1", "snippet": {"title": "My channel", "thumbnails": {}}}]}))
    youtube.finish_auth("the-code", q["state"])
    return q, fake


def test_sign_in_uses_pkce_and_all_scopes(http):
    q, fake = _connect(http)
    assert q["code_challenge_method"] == "S256" and q["access_type"] == "offline"
    assert set(q["scope"].split()) == set(youtube.SCOPES)
    token_call = fake.calls[0][2]["data"]
    assert token_call["code"] == "the-code" and len(token_call["code_verifier"]) >= 43
    assert youtube.connected() and youtube.status()["connected"]
    raw = (youtube.folder() / "token.enc").read_text(encoding="utf-8")
    assert "refresh_token" not in raw and "My channel" not in raw  # encrypted at rest
    assert not (youtube.folder() / "token.json").exists()
    assert youtube._token()["channel"]["title"] == "My channel"
    with pytest.raises(SharkyClipsError):  # a state can only be used once
        youtube.finish_auth("again", q["state"])


def test_refused_sign_in_explains(http):
    url = youtube.auth_url("http://127.0.0.1:8123/")
    state = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))["state"]
    http(Res(400, {"error": "invalid_grant", "error_description": "Bad code"}))
    with pytest.raises(SharkyClipsError, match="Bad code"):
        youtube.finish_auth("x", state)
    assert not youtube.connected()


def test_token_refresh_and_sign_out(http):
    _connect(http)
    youtube._expire_access()
    fake = http(Res(200, {"access_token": "A2", "expires_in": 3600}))
    assert youtube.access_token() == "A2"
    assert fake.calls[0][2]["data"]["grant_type"] == "refresh_token"
    assert youtube.access_token() == "A2" and len(fake.calls) == 1  # cached until it expires

    youtube._expire_access()
    http(Res(400, {"error": "invalid_grant"}))
    with pytest.raises(SharkyClipsError, match="signed SharkyClips out"):
        youtube.access_token()
    assert not youtube.connected()


def test_disconnect_revokes_and_forgets_even_offline(http):
    _connect(http)
    fake = http(FakeHTTP.RequestException("offline"))
    youtube.disconnect()
    assert fake.calls[0][1] == youtube.REVOKE_URL and not youtube.connected()


def test_api_errors_get_hints_and_quota_exceeded_empties_the_counter(http):
    _connect(http)
    http(Res(403, {"error": {"message": "Quota", "errors": [{"reason": "quotaExceeded"}]}}))
    with pytest.raises(SharkyClipsError) as e:
        youtube.channel()
    assert "midnight Pacific" in (e.value.hint or "")
    assert youtube.quota_view()["uploads_left"] == 0


def _video(tmp_path, size=youtube.CHUNK + 1000):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\0" * size)
    return p, size


def test_resumable_upload_in_chunks(http, tmp_path):
    _connect(http)
    path, size = _video(tmp_path)
    progress: list[float] = []
    fake = http(Res(200, {}, {"Location": "https://upload/session1"}),
                Res(308, None, {"Range": f"bytes=0-{youtube.CHUNK - 1}"}),
                Res(200, {"id": "VID1"}))
    out = youtube.upload(path, {"snippet": {"title": "t"}}, key="p:c01", on_progress=progress.append)
    assert out["id"] == "VID1" and progress[-1] == 1.0 and 0 < progress[0] < 1
    ranges = [c[2]["headers"]["Content-Range"] for c in fake.calls[1:]]
    assert ranges == [f"bytes 0-{youtube.CHUNK - 1}/{size}", f"bytes {youtube.CHUNK}-{size - 1}/{size}"]
    assert "p:c01" not in youtube._sessions()  # finished: the session is forgotten
    assert youtube.quota_used() >= youtube.COST["upload"]


def test_upload_continues_after_a_restart(http, tmp_path):
    _connect(http)
    path, size = _video(tmp_path)
    youtube._save_session("p:c02", "https://upload/old")
    fake = http(Res(308, None, {"Range": f"bytes=0-{youtube.CHUNK - 1}"}),  # "where are we?"
                Res(201, {"id": "VID2"}))
    assert youtube.upload(path, {}, key="p:c02")["id"] == "VID2"
    assert fake.calls[0][2]["headers"]["Content-Range"] == f"bytes */{size}"
    assert fake.calls[1][2]["headers"]["Content-Range"].startswith(f"bytes {youtube.CHUNK}-")


def test_upload_survives_network_errors_and_gives_up_on_rejections(http, tmp_path):
    _connect(http)
    path, size = _video(tmp_path, 5000)
    http(Res(200, {}, {"Location": "https://upload/s"}),
         FakeHTTP.RequestException("wifi dropped"),
         Res(308, None, {}),  # status check: nothing arrived
         Res(200, {"id": "VID3"}))
    assert youtube.upload(path, {}, key="p:c03")["id"] == "VID3"

    http(Res(200, {}, {"Location": "https://upload/s2"}),
         Res(403, {"error": {"message": "Forbidden", "errors": [{"reason": "uploadLimitExceeded"}]}}))
    with pytest.raises(SharkyClipsError) as e:
        youtube.upload(path, {}, key="p:c04")
    assert "upload limit" in (e.value.hint or "") and "p:c04" not in youtube._sessions()


def test_upload_refuses_without_quota(http, tmp_path):
    _connect(http)
    path, _ = _video(tmp_path, 100)
    youtube.spend(youtube.daily_quota())
    fake = http()
    with pytest.raises(SharkyClipsError):
        youtube.upload(path, {}, key="p:c05")
    assert fake.calls == []


def test_stats_and_retention_parse_google_answers(http):
    _connect(http)
    http(Res(200, {"items": [{"id": "V1", "statistics": {"viewCount": "120", "likeCount": "7"},
                              "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                              "snippet": {"publishedAt": "2026-10-01T10:00:00Z"}}]}))
    st = youtube.video_stats(["V1"])
    assert st["V1"] == {"views": 120, "likes": 7, "privacy": "public", "published_at": "2026-10-01T10:00:00Z",
                        "upload_status": "processed"}
    fake = http(Res(200, {"columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewDuration"},
                                            {"name": "averageViewPercentage"}],
                          "rows": [["V1", 120, 21.5, 73.2]]}))
    r = youtube.retention(["V1"], "2026-10-01", "2026-10-03")
    assert r["V1"]["avg_view_percentage"] == 73.2
    assert fake.calls[0][2]["params"]["ids"] == "channel==MINE"
    http(Res(403, {"error": {"message": "no"}}))
    with pytest.raises(SharkyClipsError, match="no"):
        youtube.retention(["V1"], "2026-10-01")
