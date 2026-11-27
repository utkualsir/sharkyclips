"""1.2.75 Uploads stats + honest YouTube quota + the (off) shared-pool counter + its Worker."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sharkyclips import config, history, poolcounter, uploadstats, youtube

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
SHARED_ID = "123-shared.apps.googleusercontent.com"
OWN_ID = "456-own.apps.googleusercontent.com"


def _client():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    return TestClient(app)


@pytest.fixture
def posts():
    """A clean upload history; restores what was there."""
    old = history.load()
    data = {**old, "posts": []}
    history._save(data)

    def add(at: datetime, platform: str, *, manual: bool = False, private: bool = False, n: int = 0) -> None:
        d = history.load()
        d["posts"].append({"key": f"p:{platform}:{n}:{at.isoformat()}", "at": at.isoformat(timespec="seconds"),
                           "project_id": "p", "project_title": "Stream", "clip_id": f"c{n:02d}",
                           "title": f"Clip {n}", "game": "Delta Force", "platform": platform,
                           "url": f"https://example.com/{platform}/{n}", "manual": manual, "private": private})
        history._save(d)

    yield add
    history._save(old)


@pytest.fixture
def quota_files(monkeypatch, tmp_path):
    """No own client, no shared client, no quota file, no pool counter; restored afterwards."""
    for name in ("quota.json", "client.json"):
        (youtube.folder() / name).unlink(missing_ok=True)
    monkeypatch.setenv("SHARKYCLIPS_SHARED_CLIENT", str(tmp_path / "none.json"))
    config.update(youtube_pool_counter=None, youtube_pool_url=None, owner_view=None, youtube_daily_uploads=None)
    poolcounter.clear_cache()
    yield tmp_path
    for name in ("quota.json", "client.json"):
        (youtube.folder() / name).unlink(missing_ok=True)
    config.update(youtube_pool_counter=None, youtube_pool_url=None, owner_view=None)
    poolcounter.clear_cache()


def _shared(monkeypatch, tmp_path) -> None:
    f = tmp_path / "google_client.json"
    f.write_text(json.dumps({"client_id": SHARED_ID, "client_secret": "GOCSPX-x", "project_id": "sharky-shared"}),
                 encoding="utf-8")
    monkeypatch.setenv("SHARKYCLIPS_SHARED_CLIENT", str(f))


def _own() -> None:
    youtube.set_client({"installed": {"client_id": OWN_ID, "client_secret": "GOCSPX-own", "project_id": "my-own"}})


# ===================================================================== stats


def test_stats_today_week_total_per_platform(posts):
    tz = timezone(timedelta(hours=1))  # Hungary in winter
    now = datetime(2026, 11, 27, 15, 0, tzinfo=tz)  # a Friday
    posts(now - timedelta(hours=1), "youtube", n=1)
    posts(now - timedelta(hours=2), "tiktok", n=2)
    posts(now - timedelta(hours=3), "reels", manual=True, n=3)  # by hand on Instagram: counts as "manual"
    posts(now - timedelta(days=2), "youtube", private=True, n=4)  # Wednesday: this week
    posts(now - timedelta(days=6), "reels", n=5)  # last Saturday: not this week
    posts(datetime(2026, 11, 26, 23, 30, tzinfo=UTC), "youtube", n=6)  # 00:30 Friday in Hungary: today
    s = uploadstats.stats(now, tz)
    assert s["groups"] == ["youtube", "reels", "tiktok", "manual"]
    assert s["today"]["total"] == 4 and s["today"]["by"] == {"youtube": 2, "reels": 0, "tiktok": 1, "manual": 1}
    assert s["week"]["from"] == "2026-11-23" and s["week"]["total"] == 5
    assert s["total"]["total"] == 6 and sum(s["total"]["by"].values()) == 6
    assert len(s["days"]) == uploadstats.DAYS and s["days"][-1]["date"] == "2026-11-27"
    assert s["days"][-1]["total"] == 4 and s["days"][-3]["by"]["youtube"] == 1
    item = next(i for i in s["today"]["items"] if i["group"] == "manual")
    assert item["platform"] == "reels" and item["status"] == "by_hand" and item["url"].startswith("https://")
    assert item["title"] == "Clip 3" and item["project_title"] == "Stream" and item["at"].endswith("+01:00")
    wed = next(i for i in s["week"]["items"] if i["title"] == "Clip 4")
    assert wed["status"] == "private"
    assert [i["at"] for i in s["today"]["items"]] == sorted((i["at"] for i in s["today"]["items"]), reverse=True)


def test_stats_api_and_empty_history(posts):
    r = _client().get("/api/uploads/stats")
    assert r.status_code == 200
    s = r.json()
    assert s["total"]["total"] == 0 and s["today"]["items"] == [] and len(s["days"]) == 14


# ===================================================================== quota: shared vs own


def test_shared_client_is_a_shared_pool_not_a_count(monkeypatch, quota_files):
    _shared(monkeypatch, quota_files)
    youtube.spend_upload()
    youtube.spend_upload()
    q = youtube.quota_view()
    assert q["mode"] == "shared" and q["exact"] is False and q["pool"] is None
    assert q["mine_today"] == 2 and q["exhausted"] is False
    view = _client().get("/api/youtube/quota").json()
    assert view["mode"] == "shared" and view["owner"] == {"enabled": False, "console_url": None}
    assert view["own_console_url"] is None and view["pool_counter"]["enabled"] is False
    # resets at midnight Pacific: 08:00 UTC in winter = 09:00 in Hungary
    assert youtube.next_reset(datetime(2026, 11, 27, 12, 0, tzinfo=UTC)) == datetime(2026, 11, 28, 8, 0, tzinfo=UTC)
    assert youtube.next_reset(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)) == datetime(2026, 7, 2, 7, 0, tzinfo=UTC)


def test_shared_quota_exceeded_message_and_my_count_stays_true(monkeypatch, quota_files):
    _shared(monkeypatch, quota_files)
    youtube.spend_upload()

    class Res:
        status_code = 403

        def json(self):
            return {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}

    err = youtube._api_error(Res(), "upload")
    assert err.message == "Today's shared upload limit is used up."
    assert "It resets at" in err.hint and "by hand" in err.hint and "own Google client" in err.hint
    q = youtube.quota_view()
    assert q["exhausted"] is True and q["uploads_left"] == 0 and q["mine_today"] == 1  # not "100 by me"
    with pytest.raises(Exception) as e:
        youtube.check_upload_quota()
    assert "shared upload limit" in str(e.value.message)


def test_own_client_exact_counter(monkeypatch, quota_files):
    _own()
    for _ in range(3):
        youtube.spend_upload()
    q = youtube.quota_view()
    assert q["mode"] == "own" and q["exact"] is True and q["cost_per_upload"] == 1
    assert (q["uploads_left"], q["uploads_limit"]) == (97, 100)
    view = _client().get("/api/youtube/quota").json()
    assert view["own_console_url"].endswith("?project=my-own")
    msg, hint = youtube.quota_exceeded_text()
    assert "100 a day" in msg and "midnight Pacific" in hint


def test_owner_view_link_only_when_on_and_no_credentials(monkeypatch, quota_files):
    _shared(monkeypatch, quota_files)
    c = _client()
    view = c.put("/api/youtube/quota/settings", json={"owner_view": True}).json()
    assert view["owner"]["enabled"] is True
    assert view["owner"]["console_url"] == ("https://console.cloud.google.com/apis/api/youtube.googleapis.com/"
                                            "quotas?project=sharky-shared")
    assert "secret" not in json.dumps(view).lower() and "GOCSPX" not in json.dumps(view)
    assert c.put("/api/youtube/quota/settings", json={"owner_view": False}).json()["owner"]["console_url"] is None


# ===================================================================== the shared-pool counter


def test_pool_counter_is_off_by_default_and_never_fetches(monkeypatch, quota_files):
    _shared(monkeypatch, quota_files)
    assert poolcounter.DEFAULT_ON is False and poolcounter.enabled() is False
    monkeypatch.setattr(poolcounter, "_fetch", lambda url: pytest.fail("fetched while off"))
    config.update(youtube_pool_url="https://pool.example.workers.dev/")
    assert poolcounter.read() is None and youtube.quota_view()["pool"] is None


def test_pool_counter_on_shows_the_real_pool(monkeypatch, quota_files):
    _shared(monkeypatch, quota_files)
    now = datetime.now(UTC)
    seen = []

    def fake(url):
        seen.append(url)
        return {"used": 50, "limit": 100, "resets_at": youtube.next_reset(now).isoformat()}

    monkeypatch.setattr(poolcounter, "_fetch", fake)
    c = _client()
    r = c.put("/api/youtube/quota/settings", json={"pool_counter": True, "pool_url": "https://pool.example.workers.dev/"})
    assert r.status_code == 200 and r.json()["pool_counter"]["enabled"] is True
    q = youtube.quota_view()
    assert q["pool"]["left"] == 50 and q["pool"]["limit"] == 100 and q["exact"] is True and q["uploads_left"] == 50
    youtube.quota_view()
    assert seen == ["https://pool.example.workers.dev/"]  # cached: one request, no parameters
    from sharkyclips.web import share as S

    assert S.limit_view()["left"] == 50 and S.limit_view()["mode"] == "shared"


@pytest.mark.parametrize("bad", ["http://pool.example.com/", "https://u:p@pool.example.com/",
                                 "https://pool.example.com/?user=1", "javascript:alert(1)"])
def test_pool_counter_url_must_be_plain_https(quota_files, bad):
    r = _client().put("/api/youtube/quota/settings", json={"pool_url": bad})
    assert r.status_code >= 400 and config.get("youtube_pool_url") in (None, "")


@pytest.mark.parametrize("data", [None, [], {"used": "5", "limit": 100, "resets_at": "2026-11-28T08:00:00Z"},
                                  {"used": True, "limit": 100, "resets_at": "2026-11-28T08:00:00Z"},
                                  {"used": 5, "limit": 0, "resets_at": "2026-11-28T08:00:00Z"},
                                  {"used": -1, "limit": 100, "resets_at": "2026-11-28T08:00:00Z"},
                                  {"used": 5, "limit": 100, "resets_at": "tomorrow"},
                                  {"used": 5, "limit": 100, "resets_at": "2026-11-28T08:00:00"},
                                  {"used": 5, "limit": 100, "resets_at": "2030-01-01T00:00:00Z"}])
def test_pool_answer_is_checked(data):
    assert poolcounter.parse(data, datetime(2026, 11, 27, 12, 0, tzinfo=UTC)) is None


def test_pool_answer_ok_and_capped():
    p = poolcounter.parse({"used": 120, "limit": 100, "resets_at": "2026-11-28T08:00:00Z"},
                          datetime(2026, 11, 27, 12, 0, tzinfo=UTC))
    assert p == {"used": 100, "limit": 100, "left": 0, "resets_at": "2026-11-28T08:00:00+00:00"}


def test_pool_fetch_sends_no_user_data(monkeypatch):
    calls = []

    class Res:
        status_code = 200
        content = b"{}"

        def json(self):
            return {}

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **kw: calls.append((url, kw)) or Res())
    poolcounter._fetch("https://pool.example.workers.dev/")
    url, kw = calls[0]
    assert url == "https://pool.example.workers.dev/" and "params" not in kw and "cookies" not in kw
    assert kw["headers"] == {"User-Agent": "SharkyClips", "Accept": "application/json"}
    assert kw["allow_redirects"] is False


# ===================================================================== the Worker (node)


WORKER_TEST = r"""
import { generateKeyPairSync } from "node:crypto";
const W = await import(process.argv[2]);
const out = {};
// Pacific day: winter (PST), summer (PDT), and the two DST change days
for (const [k, iso] of Object.entries({ winter: "2026-11-27T12:00:00Z", summer: "2026-07-01T12:00:00Z",
                                         fallback: "2026-11-01T12:00:00Z", spring: "2026-03-08T12:00:00Z" })) {
  const d = W.pacificDay(new Date(iso));
  out[k] = [d.start.toISOString(), d.next.toISOString()];
}
const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048, privateKeyEncoding: { type: "pkcs8", format: "pem" },
                                                    publicKeyEncoding: { type: "spki", format: "pem" } });
const env = { SA_KEY: JSON.stringify({ client_email: "pool@x.iam.gserviceaccount.com", private_key: privateKey }),
              PROJECT_ID: "sharky-shared", QUOTA_METRIC: "youtube.googleapis.com/uploads" };
const urls = [];
const fakeFetch = async (url, init = {}) => {
  urls.push({ url: String(url), auth: init.headers?.Authorization ?? null, body: String(init.body ?? "") });
  if (String(url).startsWith("https://oauth2.googleapis.com/token"))
    return new Response(JSON.stringify({ access_token: "ya29.test" }), { status: 200 });
  if (String(url).includes("quota%2Frate%2Fnet_usage"))
    return new Response(JSON.stringify({ timeSeries: [{ points: [{ value: { int64Value: "50" } }] }] }), { status: 200 });
  return new Response(JSON.stringify({ timeSeries: [{ points: [{ value: { int64Value: "100" } }] }] }), { status: 200 });
};
const store = new Map();
const cache = { match: async (r) => store.get(r.url)?.clone(), put: async (r, res) => store.set(r.url, res) };
const ctx = { waitUntil: (p) => p };
const now = new Date("2026-11-27T12:00:00Z");
const r1 = await W.handle(new Request("https://pool.example/?who=me"), env, ctx, { fetch: fakeFetch, cache, now });
out.status = r1.status;
out.body = await r1.json();
out.cacheControl = r1.headers.get("cache-control");
const n = urls.length;
await W.handle(new Request("https://pool.example/"), env, ctx, { fetch: fakeFetch, cache, now });
out.cachedCalls = urls.length - n;
out.post = (await W.handle(new Request("https://pool.example/", { method: "POST" }), env, ctx, { fetch: fakeFetch, cache, now })).status;
out.unconfigured = (await W.handle(new Request("https://pool.example/"), {}, ctx, { fetch: fakeFetch, now })).status;
out.urls = urls.map((u) => u.url);
out.tokenBody = urls[0].body;
out.auth = urls[1].auth;
console.log(JSON.stringify(out));
"""


def test_worker_reads_monitoring_and_returns_only_three_numbers(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = tmp_path / "worker-test.mjs"
    script.write_text(WORKER_TEST, encoding="utf-8")
    worker = (ROOT / "workers" / "shared-pool" / "worker.js").resolve().as_uri()
    res = subprocess.run([node, str(script), worker], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["winter"] == ["2026-11-27T08:00:00.000Z", "2026-11-28T08:00:00.000Z"]
    assert out["summer"] == ["2026-07-01T07:00:00.000Z", "2026-07-02T07:00:00.000Z"]
    assert out["fallback"] == ["2026-11-01T07:00:00.000Z", "2026-11-02T08:00:00.000Z"]  # 25-hour day
    assert out["spring"] == ["2026-03-08T08:00:00.000Z", "2026-03-09T07:00:00.000Z"]  # 23-hour day
    assert out["status"] == 200 and out["body"] == {"used": 50, "limit": 100, "resets_at": "2026-11-28T08:00:00Z"}
    assert "max-age=300" in out["cacheControl"] and out["cachedCalls"] == 0
    assert out["post"] == 405 and out["unconfigured"] == 503
    assert "jwt-bearer" in out["tokenBody"] and out["auth"] == "Bearer ya29.test"
    mon = [u for u in out["urls"] if "monitoring.googleapis.com" in u]
    assert len(mon) == 2 and all("/projects/sharky-shared/timeSeries?" in u for u in mon)
    assert all("youtube.googleapis.com%2Fuploads" in u for u in mon)
    assert not any("who=me" in u for u in out["urls"])  # the caller's request never reaches Google


def test_worker_has_no_secret_in_the_repo():
    folder = ROOT / "workers" / "shared-pool"
    text = "".join(p.read_text(encoding="utf-8") for p in folder.iterdir() if p.is_file())
    assert "BEGIN PRIVATE KEY" not in text and "private_key_id" not in text
    assert "workers/shared-pool/wrangler.toml" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_quota_settings_only_from_this_computer(monkeypatch, quota_files):
    import importlib

    appmod = importlib.import_module("sharkyclips.web.app")

    monkeypatch.setattr(appmod, "_is_local", lambda request: False)
    r = _client().put("/api/youtube/quota/settings", json={"pool_url": "https://pool.example.workers.dev/"})
    assert r.status_code == 403 and config.get("youtube_pool_url") in (None, "")
    assert _client().get("/api/youtube/quota").status_code == 200  # reading stays open
