"""1.2.53 pluggable game profiles (game/profiles/<id>/profile.json)."""

import json

from sharkyclips import game
from sharkyclips.game import events, gameprofiles, presets
from sharkyclips.titles import banks, templates

SPEC_GAMES = {"cs2", "valorant", "warzone", "fortnite", "apex", "pubg", "gta5", "gta6", "minecraft", "lol",
              "dota2", "overwatch", "marvel_rivals", "eafc", "arc_raiders"}


def test_every_builtin_profile_is_valid():
    found = {}
    for d in sorted(gameprofiles.BUILTIN_DIR.iterdir()):
        p = json.loads((d / "profile.json").read_text(encoding="utf-8"))
        assert gameprofiles.validate(p) == [], (d.name, gameprofiles.validate(p))
        assert p["id"] == d.name
        found[p["id"]] = p
    assert SPEC_GAMES <= set(found)
    # only games checked on real footage may say "verified"
    assert {k for k, p in found.items() if p["status"] == "verified"} <= {"lol", "delta_force"}
    assert found["gta6"]["status"] == "preview"


def test_profiles_have_english_and_turkish_texts_and_hashtags():
    for gid, p in gameprofiles.all_profiles().items():
        assert p["hashtags"].get("all"), gid
        for _region, rules in (p.get("ocr") or {}).items():
            for code, phrases in rules.items():
                assert phrases == [x.lower() for x in phrases], (gid, code)  # normalized form


def test_profiles_plug_into_detection_and_ocr():
    assert SPEC_GAMES <= set(game.CHOICES)
    assert presets.match_rules("valorant", "banner", "ACE") == ["val_ace"]
    assert presets.match_rules("valorant", "banner", "TEAM ACE") == ["val_team_ace"]
    assert presets.match_rules("pubg", "banner", "WINNER WINNER CHICKEN DINNER!") == ["pubg_win"]
    assert presets.match_rules("gta5", "center", "WASTED") == ["gta_wasted"]
    assert "fn_victory" in presets.match_rules("fortnite", "banner", "#1 VICTORY ROYALE")


def test_banner_events_dedupe_and_padding():
    obs = [{"t": 10, "kind": "text", "region": "banner", "text": "CLUTCH"},
           {"t": 11, "kind": "text", "region": "banner", "text": "CLUTCH"},
           {"t": 40, "kind": "text", "region": "center", "text": "VICTORY"}]
    evs = events.build_events("valorant", obs)
    assert [e["code"] for e in evs] == ["val_clutch", "val_victory"]
    assert evs[0]["pre"] == 10 and evs[0]["source"] == "banner"


def test_detect_from_title_and_transcript():
    assert game.detect("Ranked grind | VALORANT", None)[0] == "valorant"
    seg = {"segments": [{"text": "erangel airdrop kar98 mavi alan tava m416 chicken dinner"}]}
    assert game.detect("", seg)[0] == "pubg"


def test_hashtags_follow_the_content_language():
    tags = banks.build_hashtags(banks.get("fortnite"), {"events": [], "terms": []}, None, "es", channel=["#me"])
    assert tags[0] == "#me" and "#fortnite" in tags and "#fortniteespañol" in tags
    pt = banks.build_hashtags(banks.get("cs2"), {"events": [], "terms": []}, None, "pt")
    assert "#cs2brasil" in pt and not any(t.endswith("tr") for t in pt)


def test_template_titles_without_llm():
    cand = {"text": "no way we did it", "reasons": [{"code": "val_ace", "strength": 1.0, "t": 3}]}
    out = templates.titles(cand, "VALORANT", "en")
    assert out and out[0] == "ACE! VALORANT"
    assert templates.titles(cand, "VALORANT", "es")[0].startswith("¡ACE!")
    assert templates.titles({"text": "hello there", "reasons": []}, None, "ja") == ["hello there"]


def test_user_profile_folder_is_loaded(tmp_path, monkeypatch):
    d = gameprofiles.user_dir() / "rocket_league"
    d.mkdir(parents=True)
    (d / "profile.json").write_text(json.dumps({
        "id": "rocket_league", "name": "Rocket League", "aliases": ["rocket league"],
        "regions": {"banner": {"box": [460, 120, 1000, 220]}},
        "ocr": {"banner": {"rl_goal": ["goal"]}}, "events": {"rl_goal": {"strength": 0.7}},
        "hashtags": {"all": ["#rocketleague"]}}), encoding="utf-8")
    try:
        p = gameprofiles.get("rocket_league")
        assert p and p["_source"] == "user" and gameprofiles.is_beta("rocket_league")
    finally:  # later tests must not see this game
        import shutil

        shutil.rmtree(d, ignore_errors=True)
    bad = {"id": "x", "name": "X", "aliases": ["x"], "regions": {"r": {"box": [0, 0, 5000, 10]}}}
    assert gameprofiles.validate(bad)


def test_ocr_fragments_dont_invent_events():
    """Real footage (1.2.53): the fading 'WASTED' banner read as 'sted' must not become BUSTED."""
    obs = [{"t": 13, "kind": "text", "region": "center", "text": "wasted"},
           {"t": 15, "kind": "text", "region": "center", "text": "sted"},
           {"t": 40, "kind": "text", "region": "center", "text": "BUSTED"}]
    assert [e["code"] for e in events.build_events("gta5", obs)] == ["gta_wasted", "gta_busted"]


def test_overwatch_death_is_not_a_kill_and_checked_moments_are_listed():
    obs = [{"t": 11, "kind": "text", "region": "elims", "text": "ELIMINATED PEGROEG'S MECH"},
           {"t": 40, "kind": "text", "region": "elims", "text": "YOU WERE ELIMINATED BY EIDEX14"}]
    assert [e["code"] for e in events.build_events("overwatch", obs)] == ["ow_elim", "ow_death"]
    s = gameprofiles.summary("valorant")
    assert s["beta"] and "ACE" in s["checked"]


def test_marvel_rivals_real_banners():
    """Real footage (1.2.55): 'ACE!' and 'N PLAYER KO STREAK!' (not double / triple kill)."""
    assert presets.match_rules("marvel_rivals", "banner", "ACE!") == ["mr_ace"]
    assert presets.match_rules("marvel_rivals", "banner", "15 PLAYER KO STREAK!") == ["mr_ko_streak"]
