"""1.2.59 waiting mini game ("Shark Snack").

1. The engine (frontend/src/minigame/engine.ts, run with Node): performance budget, round length
   30-90 s, rules (eat smaller, bigger hurts, combos, power-ups), deterministic.
2. Never hurts processing: no network calls in the game code, no image / sound files, a small
   lazily loaded bundle chunk, keys stay in the game (keyguard installed before React).
3. The server keeps the numbers: best, today's best, skins earned by playing, prefs, on/off.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
GAME = SRC / "minigame"


def _node_ts() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-e", "console.log(process.features && process.features.typescript || '')"],
                         capture_output=True, text=True)
    return node if out.stdout.strip() not in ("", "false", "undefined") else None


def _run(tmp_path, body: str) -> dict:
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    script = tmp_path / "run.mjs"
    script.write_text(f"const E = await import({json.dumps((GAME / 'engine.ts').as_uri())});\n{body}", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


# ------------------------------------------------------------------ 1. the engine

def test_engine_performance_budget(tmp_path):
    """60 simulated rounds at 60 steps a second, a bot playing: the simulation must be far below
    the frame budget (16.7 ms), so the game leaves the CPU to the render / Whisper jobs."""
    r = _run(tmp_path, """
const rounds = [];
let steps = 0;
const times = [];
const t0 = performance.now();
for (let seed = 1; seed <= 60; seed++) {
  const g = E.createGame(seed);
  E.startRound(g);
  let n = 0, peakFish = 0, peakParts = 0;
  while (g.phase === "playing" && n < 60 * 100) {
    const a = performance.now();
    E.step(g, 1 / 60, E.botInput(g));
    const d = performance.now() - a;
    if (n > 60) times.push(d);  // after warm-up (JIT)
    g.events.length = 0;
    n++;
    peakFish = Math.max(peakFish, g.fish.length);
    peakParts = Math.max(peakParts, g.particles.length);
  }
  steps += n;
  rounds.push({ s: g.elapsed, score: Math.round(g.score), fish: g.fishEaten, combo: g.bestCombo, lives: g.lives,
                peakFish, peakParts, hazards: g.hazards.length });
}
times.sort((a, b) => a - b);
const p99 = times[Math.floor(times.length * 0.99)];
console.log(JSON.stringify({ avg: (performance.now() - t0) / steps, p99, rounds }));
""")
    assert r["avg"] < 0.05, r["avg"]  # ms per step (measured ~0.003 ms)
    assert r["p99"] < 0.5, r["p99"]  # a busy PC / GC pause may stall one step: the 99th percentile counts
    for rd in r["rounds"]:
        assert 10 <= rd["s"] <= 90.01, rd  # short rounds, never past 90 s
        assert rd["peakFish"] <= 22 and rd["peakParts"] <= 160 and rd["hazards"] <= 7, rd  # hard caps
    lengths = sorted(rd["s"] for rd in r["rounds"])
    assert 30 <= lengths[len(lengths) // 2] <= 90  # a typical round is 30-90 s
    assert max(rd["score"] for rd in r["rounds"]) > 0 and min(rd["fish"] for rd in r["rounds"]) >= 1


def test_engine_rules(tmp_path):
    r = _run(tmp_path, """
const out = {};
// deterministic: same seed, same input -> same game
const run = (seed) => { const g = E.createGame(seed); E.startRound(g); for (let i = 0; i < 1200; i++) E.step(g, 1/60, E.botInput(g)); return [g.score, g.fishEaten, g.shark.x]; };
out.same = JSON.stringify(run(5)) === JSON.stringify(run(5));
out.differs = JSON.stringify(run(5)) !== JSON.stringify(run(6));
// eating a smaller fish: points, growth, combo
let g = E.createGame(1); E.startRound(g); g.fish = []; g.hazards = []; g.powers = []; g.spawnFish = g.spawnHazard = g.spawnPower = 99;
g.fish.push({ kind: "small", x: g.shark.x + 10, y: g.shark.y, vx: 0, vy: 0, r: 5, phase: 0, hue: 0 });
const size0 = g.shark.size;
E.step(g, 1/60);
out.ate = g.fishEaten === 1 && g.score === 10 && g.shark.size > size0 && g.combo === 1 && g.events.some((e) => e.type === "eat");
// a bigger predator hurts (a life, the combo), then a short safe time
g.events.length = 0;
g.fish.push({ kind: "predator", x: g.shark.x + 5, y: g.shark.y, vx: 0, vy: 0, r: 25, phase: 0, hue: 0 });
E.step(g, 1/60);
out.hurt = g.lives === 2 && g.combo === 0 && g.shark.inv > 0 && g.events.some((e) => e.type === "hit");
E.step(g, 1/60);
out.safe = g.lives === 2;
// shield takes one hit
g = E.createGame(2); E.startRound(g); g.fish = []; g.spawnFish = g.spawnHazard = g.spawnPower = 99; g.shield = true;
g.hazards.push({ kind: "urchin", x: g.shark.x, y: g.shark.y, vx: 0, vy: 0, r: 9, phase: 0 });
E.step(g, 1/60);
out.shield = g.lives === 3 && !g.shield;
// combo multiplier: x2 after 4 quick fish, x2 more in frenzy
g = E.createGame(3); E.startRound(g); g.combo = 4; out.mult = E.multiplier(g); g.frenzy = 3; out.multFrenzy = E.multiplier(g);
// time power-up adds 5 s but never past 90 s in total
g = E.createGame(4); E.startRound(g); g.elapsed = 80; g.timeLeft = 8; g.fish = []; g.hazards = []; g.spawnFish = g.spawnHazard = g.spawnPower = 99;
g.powers.push({ kind: "time", x: g.shark.x, y: g.shark.y, vy: 0, life: 5, phase: 0 });
E.step(g, 1/60);
out.timeCap = g.elapsed + g.timeLeft <= 90.0001 && g.timeLeft > 8;
// the round ends: at zero time, an "over" event, and nothing moves on after it
g = E.createGame(5); E.startRound(g); g.timeLeft = 0.01;
E.step(g, 1/60);
out.over = g.phase === "over" && g.events.some((e) => e.type === "over");
const sx = g.shark.x; E.step(g, 1/60, { tx: 0, ty: 0, dx: 1, dy: 0, dash: true }); out.frozen = g.shark.x === sx;
// keyboard steering and dash
g = E.createGame(6); E.startRound(g); g.fish = []; g.hazards = []; g.spawnFish = g.spawnHazard = g.spawnPower = 99;
const x0 = g.shark.x; for (let i = 0; i < 30; i++) E.step(g, 1/60, { tx: null, ty: null, dx: 1, dy: 0, dash: i === 0 });
out.moved = g.shark.x > x0 + 40 && g.shark.dashCd > 0;
console.log(JSON.stringify(out));
""")
    assert r == {"same": True, "differs": True, "ate": True, "hurt": True, "safe": True, "shield": True, "mult": 2,
                 "multFrenzy": 4, "timeCap": True, "over": True, "frozen": True, "moved": True}


# ------------------------------------------------------------------ 2. never hurts processing

def test_no_network_no_asset_files_and_small_code():
    files = list(GAME.glob("*"))
    assert files and all(f.suffix in (".ts", ".tsx", ".css") for f in files)  # art and sounds are made in code
    code = "\n".join(f.read_text(encoding="utf-8") for f in files) + (SRC / "components" / "GameDock.tsx").read_text(encoding="utf-8")
    for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "http://", "https://", "import(\"http",
                "<img", "new Image(", "Audio(", ".mp3", ".wav", ".ogg", ".png", "localStorage"):
        assert bad not in code, bad
    # its only server calls are the local stats API (miniGameApi in api.ts)
    assert "miniGameApi" in (GAME / "Panel.tsx").read_text(encoding="utf-8")
    size = sum(f.stat().st_size for f in files)
    assert size < 90_000, size  # source; the built chunk is checked below


def test_built_chunk_is_lazy_and_small():
    dist = ROOT / "frontend" / "dist" / "assets"
    if not dist.is_dir():
        pytest.skip("no built UI")
    chunks = [f for f in dist.glob("Panel-*.js")]
    assert chunks, "the game is a separate chunk (loaded only when opened)"
    js = max(chunks, key=lambda f: f.stat().st_mtime)
    assert js.stat().st_size < 45_000, js.stat().st_size  # ~ a few KB gzipped: tiny installer growth
    main = [f for f in dist.glob("index-*.js")]
    assert main and not any("spawnHazard" in f.read_text(encoding="utf-8") for f in main)  # not in the start bundle


def test_keys_stay_in_the_game():
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    assert main.index("installKeyGuard()") < main.index("createRoot(")
    guard = (SRC / "keyguard.ts").read_text(encoding="utf-8")
    assert "stopImmediatePropagation" in guard and 'addEventListener(type, guard, true)' in guard
    panel = (GAME / "Panel.tsx").read_text(encoding="utf-8")
    assert "GAME_ROOT_ATTR" in panel and "setGameKeyHandler" in panel
    # the game never listens to window keys itself (only what the guard hands it)
    assert not re.search(r"window\.addEventListener\(\s*\"key", panel)


def test_pauses_when_hidden():
    panel = (GAME / "Panel.tsx").read_text(encoding="utf-8")
    for hook in ("visibilitychange", '"blur"', "if (!open) pause()", "requestAnimationFrame", "MIN_FRAME_MS"):
        assert hook in panel, hook
    # the loop runs only while a round is being played in an open, focused, visible panel
    assert 'const playing = open && screen === "play" && focused && !ready;' in panel


# ------------------------------------------------------------------ 3. the numbers


@pytest.fixture(autouse=True)
def _fresh_numbers():
    from sharkyclips import config

    config.update(minigame={}, minigame_enabled=True)
    yield
    config.update(minigame={}, minigame_enabled=True)

def test_rounds_best_daily_and_skins():
    from sharkyclips import minigame as M

    v = M.view("2026-11-21")
    assert v["best"] == 0 and v["muted"] is True and v["skin"] == "classic" and not v["howto_seen"] and v["enabled"]
    assert [s["id"] for s in v["skins"] if s["unlocked"]] == ["classic"]
    r = M.record_round({"score": 1200, "fish": 40, "combo": 9, "date": "2026-11-21"})
    assert r["best"] == 1200 and r["today_best"] == 1200 and r["round"]["new_best"] and r["round"]["new_today"]
    r = M.record_round({"score": 900, "fish": 30, "combo": 4, "date": "2026-11-21"})
    assert r["best"] == 1200 and not r["round"]["new_best"] and not r["round"]["new_today"]
    r = M.record_round({"score": 500, "fish": 10, "combo": 2, "date": "2026-11-22"})  # a new day starts at 0
    assert r["today_best"] == 500 and r["round"]["new_today"] and r["best"] == 1200
    assert "reef" in r["round"]["new_skins"]  # 3 rounds played
    assert M.save_prefs({"skin": "gold"})["skin"] == "classic"  # only an unlocked skin can be worn
    assert M.view("2026-11-21")["today_best"] == 0  # only the latest day is kept: no history, no streaks
    r = M.record_round({"score": 99_999_999, "fish": -5, "combo": "x", "date": "not a date"})
    assert r["best"] == M.MAX_SCORE and r["fish"] == 80 and r["today_best"] == 0
    v = M.save_prefs({"skin": "reef", "muted": False, "howto_seen": True})
    assert v["skin"] == "reef" and v["muted"] is False and v["howto_seen"]
    assert {s["id"]: s["unlocked"] for s in v["skins"]}["gold"] is True  # the capped score still counts once


def test_skins_are_earned_never_bought_or_timed():
    from sharkyclips import minigame as M

    assert {rule for _id, rule, _n in M.SKINS} <= {"free", "rounds", "best", "fish", "combo"}
    src = Path(M.__file__).read_text(encoding="utf-8").lower()
    for bad in ("price", "purchase", "coin", "streak", "expire"):
        assert bad not in src.replace("nothing is bought", "").replace("no streaks", "").replace("nothing expires", ""), bad


def test_api_and_setting():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from sharkyclips.web import security
    from sharkyclips.web.app import app

    c = TestClient(app, headers={security.TOKEN_HEADER: security.token()})
    assert c.get("/api/minigame?today=2026-11-21").json()["best"] == 0
    r = c.post("/api/minigame/round", json={"score": 321, "fish": 12, "combo": 5, "date": "2026-11-21"}).json()
    assert r["best"] == 321 and r["round"]["new_best"]
    assert c.put("/api/minigame", json={"muted": False, "today": "2026-11-21"}).json()["muted"] is False
    assert c.get("/api/easy/settings").json()["minigame"] is True
    assert c.put("/api/easy/settings", json={"minigame": False}).json()["minigame"] is False
    assert c.get("/api/minigame").json()["enabled"] is False
