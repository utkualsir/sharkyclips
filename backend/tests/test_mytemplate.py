"""1.2.63 My style template: titles (3 options, ALL CAPS with Turkish letters, 1-2 emojis at the
end, (BÖLÜM N) on story episodes, #Shorts on Shorts, <= 100), descriptions ("Selamlar! Bu
bölümde ..." + 3-5 / 1-2 sentences "... iyi seyirler!" + CTA + the social block word for word +
"Etiketler:"), 9-13 hashtags, episode numbers, facts only, storage and the API."""

from __future__ import annotations

import contextlib
import json
import re
import shutil

import pytest

from sharkyclips import analyze, config
from sharkyclips.edit import brand
from sharkyclips.project import Project, read_json, write_json_atomic
from sharkyclips.titles import banks
from sharkyclips.titles import mytemplate as M
from sharkyclips.titles import style as S

BLOCK = ("🎮 Canlı Yayınlar & Sosyal Medya:\n🟩 Kick: https://kick.com/example\n"
         "📸 Instagram: https://www.instagram.com/example")


@pytest.fixture(autouse=True)
def _template():
    M.save({"enabled": True, "lang": "tr", "channel_tag": "#TestKanal", "social_block": BLOCK,
            "title_words": ["SEKANS", "PATLATTIK", "EFSANE"], "story_games": [], "series": {}})
    yield
    shutil.rmtree(S.folder(), ignore_errors=True)
    for d in config.workspace_dir().glob("mt-*"):
        shutil.rmtree(d, ignore_errors=True)


def _tpl(lang="tr", **kw):
    t = M.resolved(lang)
    return {**t, **kw}


# ===================================================================== storage


def test_template_lives_in_the_settings_folder_and_the_repo_example_is_generic():
    assert M.path() == config.config_dir() / "style" / "template.json" and M.path().is_file()
    ex = json.loads(M.EXAMPLE_FILE.read_text(encoding="utf-8"))
    flat = json.dumps(ex, ensure_ascii=False).casefold()
    assert "http" not in flat and "utku" not in flat and ex["enabled"] is False and not ex["social_block"]
    shutil.rmtree(S.folder())
    assert M.load()["enabled"] is False and M.resolved("tr") is None and S.active("tr") is None


def test_every_output_language_has_the_translated_structure():
    from sharkyclips import languages

    for code in languages.codes():
        s = M.STRINGS[code]
        assert all(s[k] for k in ("intro", "outro", "cta", "label", "episode", "episode_tag", "combo"))
        assert "{n}" in s["episode"] and "{n}" in s["episode_tag"]
        p = S.active(code)
        assert p and p["template"]["s"]["intro"] == s["intro"]
        assert p["template"]["social_block"] == BLOCK  # the social block is never translated


# ===================================================================== titles


@pytest.mark.parametrize("core,fmt,want", [
    ("MASTER YI JUNGLE İLE DÖRTTE DÖRT! RAKİP TAKIMI DARMADAĞIN ETTİK! ⚔️🔥", "long",
     "MASTER YI JUNGLE İLE DÖRTTE DÖRT! RAKİP TAKIMI DARMADAĞIN ETTİK! ⚔️🔥"),
    ("SADECE DUMDUZ TIKLAYARAK 4'TE 4 ATTIM! (EFORSUZ MASTER YI) 😂🔥", "short",
     "SADECE DÜMDÜZ TIKLAYARAK 4'TE 4 ATTIM! (EFORSUZ MASTER YI) 😂🔥 #Shorts"),
    ("MUKEMMEL BIR SEKANS!", "long", "MÜKEMMEL BİR SEKANS! 🔥"),
])
def test_titles_follow_the_template(core, fmt, want):
    t = _tpl()
    out = M.finish_title(core, fmt, t, "tr", "exciting")
    assert out == want and not M.check_title(out, fmt, t, "tr")


def test_story_episode_and_english_names():
    t = _tpl(episode=9, series_key="spider_man_2")
    out = M.finish_title("KRAVEN SCORPION'I ÖLDÜRDÜ! İNANILMAZ VILLAIN ÖLÜMÜ! 😱 (BÖLÜM 3)", "long", t, "tr")
    assert out == "KRAVEN SCORPION'I ÖLDÜRDÜ! İNANILMAZ VILLAIN ÖLÜMÜ! 😱 (BÖLÜM 9)"  # the real number, no SCORPİON
    assert not M.check_title(out, "long", t, "tr")
    assert "BÖLÜM" not in M.finish_title("EFSANE AN! 🔥", "short", t, "tr")  # Shorts: only #BölümN


def test_title_checks_catch_every_rule():
    t = _tpl(episode=4, series_key="x")
    assert any("#Shorts" in e for e in M.check_title("EFSANE AN! 🔥", "short", t, "tr"))
    assert any("BÖLÜM 4" in e for e in M.check_title("EFSANE AN! 🔥", "long", t, "tr"))
    assert any("emojis" in e for e in M.check_title("EFSANE AN! (BÖLÜM 4)", "long", t, "tr"))
    assert any("Turkish letters" in e for e in M.check_title("MUKEMMEL AN! 🔥 (BÖLÜM 4)", "long", t, "tr"))
    assert any("TikTok" in e for e in M.check_title("TIKTOK EFSANESİ! 🔥 (BÖLÜM 4)", "long", t, "tr"))
    long = M.finish_title("ÇOK " * 40 + "UZUN!", "short", _tpl(), "tr")
    assert len(long) <= M.TITLE_LIMIT and long.endswith(" #Shorts")


# ===================================================================== descriptions


def test_description_layout_and_sentence_counts():
    t = _tpl()
    d = M.assemble(["Bu bölümde Master Yi ile jungle'a girdik.", "Duom Jax top lane'i aldı.",
                    "Son takım savaşında dörtte dört yaptım"], t, "tr")
    para, cta = d.split("\n\n")
    assert para.startswith("Selamlar! Bu bölümde Master Yi ile") and para.endswith(", iyi seyirler!")
    assert cta == M.STRINGS["tr"]["cta"]
    allowed = "Master Yi jungle Jax top lane dörtte dört"
    assert not M.check_description(d, "long", t, "tr", allowed)
    assert any("sentences" in e for e in M.check_description(d, "short", t, "tr", allowed))
    short = M.assemble(["Tek tıkla dört kişi gitti"], t, "tr")
    assert not M.check_description(short, "short", t, "tr", "dört")


def test_invented_names_and_tiktok_are_problems():
    t = _tpl()
    d = M.assemble(["Bu bölümde Kraven ile savaştık.", "Sonra Mysterio geldi.", "Peter kazandı"], t, "tr")
    errs = M.check_description(d, "long", t, "tr", "Kraven Peter savaş")
    assert any("Mysterio" in e for e in errs)
    d2 = M.assemble(["TikTok hesabıma da bakın.", "Çok iyi oynadık.", "Kazandık"], t, "tr")
    assert any("TikTok" in e for e in M.check_description(d2, "long", t, "tr", "tiktok"))


def test_full_description_has_the_social_block_word_for_word():
    t = _tpl(game=M.game_info("lol"))
    d = M.assemble(["Master Yi ile girdik.", "Çok iyi oldu.", "Kazandık"], t, "tr")
    tags = M.build_hashtags(t, fmt="short", facts={"terms": [{"term": "Master Yi", "kind": "champions"}]},
                            clip_text="jungle", moment="skill", lang="tr")
    full = brand.with_socials(S.compose(d, tags), "tr", limit=4900, short=True)
    assert BLOCK in full and "tiktok" not in full.casefold()
    assert full.index("unutmayın! 🚀") < full.index("🎮") < full.index("Etiketler:\n#LeagueOfLegends")


# ===================================================================== hashtags


def test_hashtags_follow_the_template_order_and_count():
    t = _tpl(game=M.game_info("lol"))
    facts = {"terms": [{"term": "Master Yi", "kind": "champions"}], "events": []}
    h = M.build_hashtags(t, fmt="short", facts=facts, clip_text="jungle'a girdim jungle", moment="skill", lang="tr")
    assert h[:6] == ["#LeagueOfLegends", "#MasterYi", "#Jungle", "#LolTürkiye", "#TestKanal", "#MasterYiSekansı"]
    assert h[-1] == "#Shorts" and M.HASHTAGS_MIN <= len(h) <= M.HASHTAGS_MAX and not M.check_hashtags(h, "short", t)
    sm = _tpl(game=M.game_info("spider_man_2"), episode=9, series_key="spider_man_2", platform="#PS5")
    h2 = M.build_hashtags(sm, fmt="long", facts={}, clip_text="", moment="exciting", lang="tr")
    assert "#SpiderMan2" in h2 and "#Bölüm9" in h2 and "#PS5" in h2 and "#SpiderMan2Sekansı" in h2
    assert "#Shorts" not in h2 and M.HASHTAGS_MIN <= len(h2) <= M.HASHTAGS_MAX


# ===================================================================== games + episodes


def _project(pid: str, title: str, text: str = "kanka girdik") -> Project:
    d = config.workspace_dir() / pid
    d.mkdir(parents=True, exist_ok=True)
    words = [{"word": w, "start": 10 + i * 0.4, "end": 10.3 + i * 0.4} for i, w in enumerate(text.split())]
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": [
        {"start": 10, "end": 10 + len(words) * 0.4, "text": text, "words": words}]})
    write_json_atomic(d / "meta.json", {"id": pid, "title": title, "mode": "gaming", "game": "auto",
                                        "transcript": {"words": len(words)}, "duration": 120})
    return Project(id=pid, dir=d)


@pytest.mark.parametrize("title,gid", [("Battlefield 6 conquest gecesi", "battlefield_6"),
                                       ("REMATCH turnuva", "rematch"),
                                       ("Marvel's Spider-Man 2 bölüm 9", "spider_man_2")])
def test_games_named_in_the_project_name(title, gid):
    assert M.detect_game(title) == gid
    g = banks.project_game(_project(f"mt-{gid}", title))
    assert g["known"] and g["id"] == gid


def test_episode_numbers_count_up_per_series_and_can_be_edited():
    a, b = _project("mt-ep1", "Spider-Man 2 hikaye"), _project("mt-ep2", "Spider-Man 2 devam")
    assert M.episode(a, "spider_man_2")["n"] == 1 and M.episode(a, "spider_man_2")["n"] == 1  # kept
    assert M.episode(b, "spider_man_2")["n"] == 2
    M.set_episode(b, 9, "spider_man_2")
    c = _project("mt-ep3", "Spider-Man 2 final")
    assert M.episode(c, "spider_man_2")["n"] == 10  # continues from the edited number
    assert M.episode(c, "lol") is None or M.episode(_project("mt-ep4", "lol"), "lol") is None  # not a story game


# ===================================================================== analysis end to end

TALK = "Master Yi ile jungle'a girdim. Dörtte dört yaptım! Jax top lane'de çok iyiydi. İnanılmaz oldu"


class FakeLLM:
    model = "fake:1"
    calls = retries = 0
    seconds = load_seconds = tokens_per_second = 0.0

    def __init__(self):
        self.prompts: list[str] = []

    def json(self, system, prompt, schema, check=None, soft=None, **kw):
        self.prompts.append(prompt)
        props = schema["properties"]
        if "game_or_topic" in props:
            return {"game_or_topic": "League of Legends", "what_happens": "Master Yi gets a quadra kill in the jungle.",
                    "self_contained": True, "moment_type": "skill", "funny": 4, "exciting": 9, "useful": 1,
                    "hook_score": 80, "retention_score": 75, "trend_fit_score": 70, "start_shift_s": 0,
                    "end_shift_s": 0, "hashtags": ["#outplay"], "hook_text": "Dörtte dört", "cover_scene": "A fight",
                    "cover_text": "DÖRTTE DÖRT"}
        if "kind" in json.dumps(props.get("titles", {})):
            return {"titles": [
                {"kind": "fact", "text": "Master Yi jungle ile dörtte dört! Rakip takımı darmadağın ettik! ⚔️🔥"},
                {"kind": "story", "text": "Sadece tıklayarak dörtte dört attım! (Eforsuz Master Yi) 😂🔥"},
                {"kind": "rage", "text": "Bu Master Yi yasaklanmalı! Jungle'ı patlattık! 🔥"},
                {"kind": "question", "text": "Master Yi bu kadar güçlü olmalı mı?! 😱"}]}
        if "keep" in json.dumps(props.get("titles", {})):
            listing = prompt.split("Titles:\n", 1)[1].split("\n\n", 1)[0]
            return {"titles": [{"i": int(i), "text": t, "keep": True}
                               for i, t in re.findall(r"^(\d+)\. (.+)$", listing, re.M)]}
        if "sentences" in props:
            if "Problems last time" not in prompt:  # first: an invented villain
                return {"sentences": ["Bu bölümde Master Yi ile Baron Nashor'u çaldık.", "Sonra Zed geldi."],
                        "mood_hashtags": ["#Outplay"], "search_tags": ["master yi jungle"]}
            return {"sentences": ["Master Yi ile jungle'a girdim ve maçı ele aldım."] if "Shorts" in prompt.split("\n")[0]
                    else ["Master Yi ile jungle'a girdim.", "Jax top lane'de çok iyiydi.", "Sonunda dörtte dört yaptım"],
                    "mood_hashtags": ["#Outplay"], "search_tags": ["master yi jungle", "lol türkçe"]}
        raise AssertionError(f"unexpected schema {list(props)}")


def _fake(monkeypatch, fake):
    from sharkyclips import llm

    @contextlib.contextmanager
    def lazy(model=None):
        yield fake

    @contextlib.contextmanager
    def session(model=None, auto=None):
        yield fake

    monkeypatch.setattr(llm, "lazy_session", lazy)
    monkeypatch.setattr(llm, "session", session)
    monkeypatch.setattr(llm, "choose_model", lambda ignore_fast=False: "fake:1")


def test_analysis_writes_shorts_in_the_template(monkeypatch):
    config.update(output_language="tr")  # the content language decides
    p = _project("mt-lol", "League of Legends dereceli", TALK)
    cand = {"id": "c01", "rank": 1, "start": 10.0, "end": 24.0, "duration": 14.0, "hype_score": 80, "hype_raw": 0.4,
            "signal_scores": {}, "text": TALK, "reasons": []}
    write_json_atomic(p.dir / "highlights.json", {"mode": "gaming", "duration": 120, "candidates": [cand]})
    fake = FakeLLM()
    _fake(monkeypatch, fake)
    analyze.analyze_project(p, out_lang="tr", translate=False)
    pub = read_json(p.dir / "highlights.json")["candidates"][0]["publish"]
    assert len(pub["titles"]) == M.TITLE_OPTIONS, pub["title_checks"]["rejected"]
    for t in pub["titles"]:
        assert t.endswith(" #Shorts") and t == t.upper().replace("#SHORTS", "#Shorts") or "YI" in t, t
        assert len(t) <= 100
    body, tags = brand.split_tail_hashtags(pub["description"])
    assert body.startswith("Selamlar! Bu bölümde Master Yi") and "Zed" not in body and "Baron" not in body
    assert "#TestKanal" in pub["hashtags"] and "#Shorts" in pub["hashtags"] and "#Jungle" in pub["hashtags"]
    assert any(h.endswith("Sekansı") for h in pub["hashtags"]) and M.HASHTAGS_MIN <= len(pub["hashtags"]) <= 13
    assert any("THE CREATOR'S TEMPLATE" in x for x in fake.prompts)
    # per-field regenerate: hashtags instantly, description with the AI
    pub2 = analyze.regenerate_hashtags(p, "c01")
    assert pub2["hashtags"] == pub["hashtags"]
    pub3 = analyze.regenerate_description(p, "c01")
    assert pub3["description"].startswith("Selamlar! Bu bölümde")


def test_api(monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    c = TestClient(app)
    r = c.get("/api/mystyle/template").json()
    assert r["template"]["enabled"] and r["limits"]["options"] == 3
    r = c.put("/api/mystyle/template", json={"social_block": "🟩 Kick: https://kick.com/new", "enabled": False}).json()
    assert r["template"]["social_block"] == "🟩 Kick: https://kick.com/new" and not r["template"]["enabled"]
    p = _project("mt-api", "Spider-Man 2 hikaye")
    c.put("/api/mystyle/template", json={"enabled": True})
    assert c.put(f"/api/projects/{p.id}/episode", json={"n": 7}).json()["episode"]["n"] == 7
    assert c.get(f"/api/projects/{p.id}/episode").json()["story"] is True
    assert c.post(f"/api/projects/{p.id}/candidates/x/regenerate/nope").status_code == 404


# ===================================================================== bugs found by the 5 real samples


def test_regression_own_game_is_never_another_game():
    """Battlefield 6 project: its own name was "another game" -> no #Battlefield6, fallback text."""
    from sharkyclips import analyze

    forbidden = analyze._forbidden("battlefield_6")
    assert forbidden("Battlefield 6 conquest") is None and forbidden("#Battlefield6") is None
    assert forbidden("Valorant oynadık") == "Valorant"
    t = _tpl(game=M.game_info("battlefield_6"))
    h = M.build_hashtags(t, fmt="long", facts={}, clip_text="conquest", moment="exciting", lang="tr",
                         forbidden=forbidden)
    assert h[0] == "#Battlefield6" and "#Battlefield6Sekansı" in h


def test_regression_official_full_name_counts_as_said():
    """"Baron" was said, the AI wrote "Baron Nashor": not an invented name."""
    allowed = M.widen_allowed("Baron'a gidiyoruz", ["Baron Nashor", "Elder Dragon"])
    t = _tpl()
    d = M.assemble(["Baron Nashor'u aldık.", "Çok iyi oynadık.", "Kazandık"], t, "tr")
    assert not any("names" in e for e in M.check_description(d, "long", t, "tr", allowed))
    assert any("Mysterio" in e for e in M.check_description(
        M.assemble(["Mysterio geldi.", "Çok iyi oynadık.", "Kazandık"], t, "tr"), "long", t, "tr", allowed))


def test_regression_outro_closes_the_last_sentence():
    """"...maçı bitirdim. iyi seyirler!" -> "...maçı bitirdim, iyi seyirler!"."""
    d = M.assemble(["Kaleyi ben tuttum.", "Üç gol attık.", "Maçı bitirdim. iyi seyirler!"], _tpl(), "tr")
    assert "bitirdim, iyi seyirler!" in d and ". iyi" not in d


def test_regression_names_keep_their_capitals():
    """Fallback "Selamlar! Bu bölümde league of Legends oynadık" -> "League of Legends"."""
    d = M.fallback_description(_tpl(), "long", "tr", "League of Legends", {})
    assert "Bu bölümde League of Legends oynadık" in d
    out = M.finish_title("MASTER Yİ İLE DÖRTTE DÖRT!", "short", _tpl(), "tr", protected={"master", "yi"})
    assert out.startswith("MASTER YI İLE")


def test_regression_no_swear_that_nobody_said():
    t = _tpl()
    title = M.finish_title("3 DÜŞMANI S*KTİRDİM! 🔥", "long", t, "tr")
    assert any("swear" in e for e in M.check_title(title, "long", t, "tr", clip_text="üç kişiyi indirdim"))
    assert not any("swear" in e for e in M.check_title(title, "long", t, "tr", clip_text="siktir ya üç kişi"))


def test_regression_sekans_tag_uses_the_main_character():
    t = _tpl(game=M.game_info("lol"), project_title="Master Yi jungle")
    facts = {"terms": [{"term": "Jax", "kind": "champions"}, {"term": "Master Yi", "kind": "champions"}]}
    h = M.build_hashtags(t, fmt="long", facts=facts, clip_text="Master Yi Master Yi Jax", moment="skill", lang="tr")
    assert "#MasterYiSekansı" in h and "#JaxSekansı" not in h


def test_regression_a_name_said_in_the_clip_is_not_lowercased():
    """2nd sample run: "Selamlar! Bu bölümde peter ve Miles ..."."""
    keep = M.proper_names("Spider-Man 2 hikayesine devam ediyoruz. Peter ve Miles birlikte şehirde sallanıyor.")
    assert "miles" in keep
    keep |= M.proper_names("Bugün Peter ve Miles geldi.")
    d = M.assemble(["Peter ve Miles şehirde sallandı.", "Kraven geldi.", "Bitti"], _tpl(), "tr", keep=keep)
    assert "Bu bölümde Peter ve Miles" in d
    t = _tpl(game=M.game_info("rematch"))
    assert "#Rehber" not in M.build_hashtags(t, fmt="long", facts={}, clip_text="", moment="useful", lang="tr")
