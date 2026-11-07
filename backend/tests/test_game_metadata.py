"""1.2.25 game-aware metadata: one game per project, per-game banks, no other game's names in
titles / hashtags / tags / descriptions, channel hashtags first, socials block at the end."""

from __future__ import annotations

import contextlib
import json
import re
import shutil

import pytest

from sharkyclips import analyze, config, platforms, publishing, youtube
from sharkyclips import titles as T
from sharkyclips.edit import brand
from sharkyclips.project import Project, read_json, write_json_atomic
from sharkyclips.titles import banks

OTHER = ["#Warzone", "#CallofDutyWarzone", "#CoD", "#CoDMobile", "#Valorant", "#ValorantTricks", "#TFT",
         "#Dota2Comparison", "#Fortnite", "#PUBG", "#ApexLegends", "#Overwatch2", "#EldenRing", "#TeamFortress2",
         "#DeltaForce", "#CS2", "#Minecraft"]
SOCIALS = ["🟩 Kick: https://kick.com/utkualsirr", "📸 Instagram: https://www.instagram.com/utkualsirr",
           "🔷 Facebook: https://www.facebook.com/utkualsirr"]


@pytest.fixture(autouse=True)
def _channel():
    old = config.get("channel_text")
    brand.save_channel_text({"hashtags": ["#utkualsirr"], "names": ["utku alsir"],
                             "socials": {"enabled": True, "lines": SOCIALS, "headings": {}}})
    yield
    config.update(channel_text=old)
    banks.user_file().unlink(missing_ok=True)
    for d in config.workspace_dir().glob("gm-*"):
        shutil.rmtree(d, ignore_errors=True)


def _no_other_game(texts, gid):
    bad = [(t, banks.other_game(t, gid)) for t in texts if banks.other_game(t, gid)]
    assert not bad, bad


# ===================================================================== blocklist


@pytest.mark.parametrize("tag", OTHER[:-3])
def test_other_games_are_blocked_on_a_lol_clip(tag):
    assert banks.other_game(tag, "lol")


def test_own_game_words_are_allowed_and_short_names_need_a_word_boundary():
    for ok in ["#LeagueofLegends", "#lol", "#lolclips", "#yasuo", "Kule altında cs farmı", "smite attım", "Baron'u çaldım",
               "codex", "apexi"]:
        assert banks.other_game(ok, "lol") is None, ok
    assert banks.other_game("Warzone'da 1v4", "lol") == "Warzone"
    assert banks.other_game("#lolclips", "delta_force") == "lol"  # LoL on a Delta Force clip
    assert banks.other_game("Black Hawk Down baskını", "delta_force") is None  # a Delta Force mode
    assert banks.other_game("Warfare modunda", "delta_force") is None
    assert banks.other_game("Modern Warfare gibi", "delta_force") == "Modern Warfare"
    # unknown game: every game name is blocked
    for t in ["#LeagueofLegends", "#deltaforce", "#valorant", "#cs2"]:
        assert banks.other_game(t, "generic"), t


def test_scrub_removes_other_games_from_model_text():
    assert banks.scrub("The streamer dies in Valorant after a fight.", "lol") == "The streamer dies the game after a fight."
    assert "Warzone" not in banks.scrub("A Warzone moment", "lol")


# ===================================================================== facts + hashtags + tags


def _lol_clip(text="Bire dört kaldım kanka, Yasuo ile pentakill geliyor, lane bitti", reasons=None):
    words = [{"word": w, "start": 10 + i * 0.5, "end": 10.4 + i * 0.5} for i, w in enumerate(text.split())]
    tr = {"language": "tr", "segments": [{"start": 10, "end": 30, "text": text, "words": words}]}
    c = {"id": "c01", "rank": 1, "start": 10.0, "end": 30.0, "duration": 20.0,
         "reasons": reasons if reasons is not None else [{"t": 15, "code": "lol_pentakill", "value": "Yasuo"}]}
    return c, tr


def test_clip_facts_from_game_events_and_transcript():
    c, tr = _lol_clip()
    f = banks.clip_facts(banks.get("lol"), c, tr)
    keys = [e["key"] for e in f["events"]]
    assert "lol_pentakill" in keys and "1v4" in keys
    assert [t["term"] for t in f["terms"]][:1] == ["Yasuo"]
    assert "event: Pentakill" in banks.facts_text(f) and "champion: Yasuo" in banks.facts_text(f)


def test_lol_clip_never_gets_another_games_hashtags_or_tags():
    """The 1.2.24 bug: a League of Legends clip got #Warzone / #CallofDuty."""
    c, tr = _lol_clip()
    bank = banks.get("lol")
    f = banks.clip_facts(bank, c, tr)
    hashtags, tags = analyze.clip_tags("gaming", {"id": "lol", "name": "League of Legends", "known": True}, f, "skill",
                                       "tr", OTHER + ["#viral", "#fyp", "#Deepfuck", "#KocaoYar", "#outplay"],
                                       "League of Legends", [])
    _no_other_game(hashtags + tags, "lol")
    assert hashtags[:3] == ["#utkualsirr", "#shorts", "#leagueoflegends"]  # YouTube shows the first 3
    assert 5 <= len(hashtags) <= 8
    assert "#pentakill" in hashtags and "#yasuo" in hashtags
    assert not {"#viral", "#fyp", "#deepfuck", "#kocaoyar"} & {h.lower() for h in hashtags}
    assert 10 <= len(tags) <= 20 and sum(len(t) for t in tags) + len(tags) <= 500
    assert not any("#" in t for t in tags)
    assert "yasuo" in tags and "utku alsir" in tags and "lol pentakill" in tags
    assert any("türkçe" in t for t in tags) and any(re.search(r"montage|gameplay|funny", t) for t in tags)


def test_delta_force_clip_tags():
    text = "Zero Dam haritasında son saniye tahliye oldu, M4A1 ile üç kişi indirdim"
    words = [{"word": w, "start": 10 + i * 0.5, "end": 10.4 + i * 0.5} for i, w in enumerate(text.split())]
    tr = {"language": "tr", "segments": [{"start": 10, "end": 30, "text": text, "words": words}]}
    c = {"id": "c01", "rank": 1, "start": 10.0, "end": 30.0, "reasons": [{"t": 20, "code": "df_extracted"}]}
    bank = banks.get("delta_force")
    f = banks.clip_facts(bank, c, tr)
    assert {"Zero Dam", "M4A1"} <= {t["term"] for t in f["terms"]}
    h = banks.build_hashtags(bank, f, "exciting", "tr", channel=["#utkualsirr"], llm=["#Warzone", "#Tarkov", "#loot"])
    t = banks.build_tags(bank, f, "exciting", "tr", channel=["utku alsir", "utkualsirr"])
    _no_other_game(h + t, "delta_force")
    assert h[:3] == ["#utkualsirr", "#shorts", "#deltaforce"] and "#extraction" in h
    assert "delta force türkçe" in t and "delta force tahliye" in t


def test_unknown_game_gets_only_generic_and_channel_tags():
    c, tr = _lol_clip("Kanka bu ne ya, chat çıldırdı, son saniyede clutch attım", reasons=[])
    bank = banks.get("generic")
    f = banks.clip_facts(bank, c, tr)
    h, t = analyze.clip_tags("gaming", {"id": "generic", "name": "", "known": False}, f, "funny", "tr",
                             ["#LeagueofLegends", "#Valorant", "#UnknownGame", "#gaming"], "Gaming", [])
    _no_other_game(h + t, "generic")
    assert h[0] == "#utkualsirr" and h[1] == "#shorts" and "#gaming" in h
    assert "#clutch" in h and not any("unknown" in x.lower() for x in h)
    assert 10 <= len(t) <= 20


def test_channel_hashtag_is_never_trimmed():
    brand.save_channel_text({"hashtags": ["#utkualsirr", "#sharkysquad", "#utkuyayin"]})
    c, tr = _lol_clip()
    bank = banks.get("lol")
    f = banks.clip_facts(bank, c, tr)
    h = banks.build_hashtags(bank, f, "skill", "tr", channel=brand.channel_hashtags(), limit=4)
    assert h[:3] == ["#utkualsirr", "#sharkysquad", "#utkuyayin"] and "#shorts" in h and "#leagueoflegends" in h
    # the channel tag also stays first when the clip's own hashtags already contain it
    h2 = banks.build_hashtags(bank, f, "skill", "tr", channel=["#utkualsirr"], llm=["#UtkuAlsirr", "#utkualsirr"])
    assert h2[0] == "#utkualsirr" and [x.lower() for x in h2].count("#utkualsirr") == 1


# ===================================================================== socials + descriptions


def test_socials_block_exact_format_and_translated_heading():
    assert brand.socials_block("tr") == "\n".join(["🎮 Canlı Yayınlar & Sosyal Medya:", *SOCIALS])
    assert brand.socials_block("en").split("\n")[0] == "🎮 Live Streams & Social Media:"
    assert brand.socials_block("de").split("\n")[1:] == SOCIALS
    brand.save_channel_text({"socials": {"enabled": False}})
    assert brand.socials_block("tr") == ""


def test_description_order_text_hashtags_socials_and_note_before_socials():
    d = publishing.compose_description("Bu maçta 1v4 attım. Sen olsan ne yapardın?", ["utkualsirr", "shorts", "lol"],
                                       lang="tr")
    parts = d.split("\n\n")
    assert parts[0].startswith("Bu maçta") and parts[1] == "#utkualsirr #shorts #lol"
    assert parts[2] == brand.socials_block("tr")
    assert publishing.compose_description(d, [], lang="tr").count("kick.com") == 1  # never twice
    noted = youtube.with_note(d, "AI voice line.")
    assert noted.index("AI voice line.") < noted.index("🎮 Canlı") and noted.endswith(SOCIALS[-1])


def test_tight_caption_drops_socials_lines_never_cuts_a_link():
    block = brand.socials_block("tr")
    room = len(block) - len(SOCIALS[-1]) - 1  # one line too short
    fit = brand.fit_block(block, room)
    assert fit.split("\n") == ["🎮 Canlı Yayınlar & Sosyal Medya:", *SOCIALS[:2]]
    assert brand.fit_block(block, 20) == ""  # a heading alone is dropped too
    cap = platforms.caption("tiktok", "x" * (2200 - 140), "", ["gg"], socials=block)
    assert len(cap) <= 2200
    for url in re.findall(r"https?://\S+", cap):
        assert url in "\n".join(SOCIALS)  # whole links only
    full = platforms.caption("reels", "Huge play", "What a moment.", ["gg"], socials=block)
    assert full.endswith(SOCIALS[-1])


def test_finish_description_drops_sentences_naming_other_games():
    out = analyze.finish_description("Bu Warzone gibiydi. Yasuo ile dörtlü aldım. Sen olsan ne yapardın?", "tr", None,
                                     ["#utkualsirr", "#shorts"], game_id="lol")
    assert "Warzone" not in out and out.startswith("Yasuo ile")


# ===================================================================== title style


def test_style_title_caps_emoji_and_bang():
    kw = ["PENTAKILL", "CLUTCH", "1v4", "SOLO KILL"]
    assert T.style_title("Bu PENTAKILL'i KİMSE BEKLEMİYORDU 💀🔥", "tr", kw) == "Bu PENTAKILL'i KİMSE beklemiyordu 💀"
    assert T.style_title("Son saniyede 1v4 CLUTCH 😱 chat çıldırdı", "tr", kw) == "Son saniyede 1v4 CLUTCH chat çıldırdı 😱"
    assert T.style_title("Bu pentakill nasıl oldu?", "tr", kw) == "Bu PENTAKILL nasıl oldu?"
    assert T.style_title("OLAMAZ! bu nasıl! oldu!", "tr", kw).count("!") == 1
    assert T.caps_words("Son saniyede 1v4 CLUTCH") == ["1v4", "CLUTCH"]


def test_punchy_pick_covers_the_formulas():
    pool = [{"style": f, "text": t} for f, t in [
        ("shock", "Kule altında 1v3 OUTPLAY, rakip şokta 😱"), ("question", "Bu Baron'u nasıl ÇALDIM?"),
        ("nobody_expected", "Bu PENTAKILL'i kimse beklemiyordu 💀"), ("number", "5 saniyede 4 KILL, chat çıldırdı"),
        ("story", "Lane'de öldüm, sonra gelen COMEBACK 👀"), ("punchy", "Saf OUTPLAY 🔥"),
        ("shock", "Takım bıraktı, ben SOLO KILL attım")]]
    out = T.pick(pool, punchy=True, lang="tr")
    assert len(out) == 6 and {t["style"] for t in out} == set(T.FORMULAS)
    assert sum(bool(T._end_emoji(t["text"])) for t in out) <= 3
    assert not T.punchy_problems(out, "tr") or all("emoji" not in p for p in T.punchy_problems(out, "tr"))


def test_game_specific_examples_never_leak_to_other_games():
    lol = [e["text"] for e in T.examples("tr", "gaming", game="lol")]
    df = [e["text"] for e in T.examples("tr", "gaming", game="delta_force")]
    assert any("PENTAKILL" in x for x in lol) and not any("PENTAKILL" in x for x in df)
    for lang in ("tr", "en", "de", "hu", "ru", "ar", "zh"):
        ex = T.examples(lang, "gaming")
        assert len(ex) >= 10 and {e["style"] for e in ex} <= set(T.FORMULAS)
        _no_other_game([e["text"] for e in ex], "generic")  # the neutral examples name no game


# ===================================================================== game of a project


def _project(pid: str, title: str, text: str, mode: str = "gaming") -> Project:
    d = config.workspace_dir() / pid
    d.mkdir(parents=True, exist_ok=True)
    words = [{"word": w, "start": 10 + i * 0.4, "end": 10.3 + i * 0.4} for i, w in enumerate(text.split())]
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": [
        {"start": 10, "end": 10 + len(words) * 0.4, "text": text, "words": words}]})
    write_json_atomic(d / "meta.json", {"id": pid, "title": title, "mode": mode, "game": "auto",
                                        "transcript": {"words": len(words)}, "duration": 120})
    return Project(id=pid, dir=d)


LOL_TALK = ("Kanka lane bitti minyon farm yaptım, kule altına daldım, Yasuo ile bire dört kaldım ve pentakill aldım. "
            "Baron geliyor ejder de bizde, jungle gank attı, chat çıldırdı ne oyun ama")


def test_project_game_detected_once_and_overridable():
    p = _project("gm-detect", "2026-11-06 19-25-41", LOL_TALK)
    g = banks.project_game(p)
    assert g["id"] == "lol" and g["known"] and g["source"] == "detected"
    meta = p.load_meta()
    meta["metadata_game"] = "valorant"
    p.save_meta(meta)
    assert banks.project_game(p)["id"] == "valorant"
    meta["metadata_game"] = "generic"
    p.save_meta(meta)
    g = banks.project_game(p)
    assert g["id"] == "generic" and not g["known"] and g["name"] == ""
    q = _project("gm-cs", "CS2 premier maçı", "bomba kuruldu")
    assert banks.project_game(q)["id"] == "cs2"  # title alias


def test_user_bank_override_merges_and_is_validated():
    assert banks.validate({"hashtags": ["#ok", "not ok"]})
    banks.save_user("lol", {**banks.get("lol"), "hashtags": ["#leagueoflegends", "#lolturkiye2"]})
    assert banks.get("lol")["hashtags"] == ["#leagueoflegends", "#lolturkiye2"]
    assert banks.get("lol")["terms"]["champions"]  # untouched keys come from the built-in bank
    stored = json.loads(banks.user_file().read_text(encoding="utf-8"))
    assert set(stored["lol"]) == {"hashtags"}  # only the change is stored
    banks.save_user("lol", None)
    assert banks.get("lol")["hashtags"][0] == "#leagueoflegends" and not banks.is_custom("lol")


@contextlib.contextmanager
def _client():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    yield TestClient(app)


def test_studio_and_brand_channel_api():
    with _client() as c:
        games = c.get("/api/studio/games").json()["games"]
        assert [g["id"] for g in games][:5] == list(banks.BUILTIN)
        lol = next(g for g in games if g["id"] == "lol")
        bank = {**lol["bank"], "keywords": ["PENTAKILL", "ACE"]}
        r = c.put("/api/studio/games/lol", json={"bank": bank})
        assert r.status_code == 200 and r.json()["custom"] is True
        assert c.put("/api/studio/games/lol", json={"bank": {"hashtags": "x"}}).status_code == 400
        assert c.delete("/api/studio/games/lol").status_code == 200 and not banks.is_custom("lol")
        ch = c.put("/api/brand/channel", json={"hashtags": ["utkualsirr", "#utkualsirr", "#x y"]}).json()
        assert ch["hashtags"] == ["#utkualsirr", "#xy"] and ch["preview"].startswith("🎮")


# ===================================================================== analysis end to end


class FakeLLM:
    """Plays a model that guesses the wrong game (the 1.2.24 bug) and pushes its hashtags."""

    model = "fake:1"
    calls = retries = 0
    seconds = load_seconds = tokens_per_second = 0.0

    def __init__(self):
        self.prompts: list[str] = []

    def json(self, system, prompt, schema, check=None, soft=None, **kw):
        self.prompts.append(prompt)
        props = schema["properties"]
        if "game_or_topic" in props:
            d = {"game_or_topic": "Call of Duty: Warzone", "what_happens": "In Warzone the streamer wins a 1v4 with Yasuo.",
                 "self_contained": True, "moment_type": "skill", "funny": 6, "exciting": 9, "useful": 2,
                 "hook_score": 80, "retention_score": 75, "trend_fit_score": 70, "start_shift_s": 0, "end_shift_s": 0,
                 "hashtags": ["#Warzone", "#CallofDuty", "#CoD", "#Valorant", "#outplay"],
                 "hook_text": "Bire dört CLUTCH", "cover_scene": "A champion standing alone", "cover_text": "1v4 CLUTCH"}
        elif "keep" in json.dumps(props.get("titles", {})):
            listing = prompt.split("Titles:\n", 1)[1].split("\n\n", 1)[0]
            lines = re.findall(r"^(\d+)\. (.+)$", listing, re.M)
            d = {"titles": [{"i": int(i), "text": t, "keep": True} for i, t in lines],
                 "hook_text": "Bire dört CLUTCH", "cover_text": "1v4 CLUTCH"}
        elif "titles" in props:
            d = {"titles": [{"style": s, "text": t} for s, t in [
                ("shock", "Kule altında 1v4 CLUTCH, rakipler şokta 😱"),
                ("question", "Bu PENTAKILL nasıl geldi, siz gördünüz mü?"),
                ("nobody_expected", "Warzone gibi bir dalış, kimse beklemiyordu 💀"),
                ("number", "Tek canla 4 KILL, takım arkadaşlarım dondu"),
                ("story", "Lane kaybettim, sonra gelen PENTAKILL 👀"),
                ("punchy", "Saf Yasuo OUTPLAY 🔥"),
                ("shock", "Valorant değil bu, LoL'de ACE attım"),
                ("question", "Sizce bu oyunun en iyi anı mıydı?"),
                ("story", "Herkes kaçtı, ben kaldım ve PENTAKILL aldım")]]}
        else:
            d = {"description": "Warzone'daki gibi değil, bu tamamen LoL. Yasuo ile kule altında dördünü de indirdim. "
                                "Sen olsan ne yapardın?"}
        if check and "description" in d and check(d):  # the real client retries; here: answer again, fixed
            d = {"description": "Yasuo ile kule altında dördünü de indirdim, chat çıldırdı. Sen olsan ne yapardın?"}
        return d


def test_lol_project_analysis_names_only_lol(monkeypatch):
    from sharkyclips import llm

    p = _project("gm-lol", "2026-11-06 19-25-41", LOL_TALK)
    cand = {"id": "c01", "rank": 1, "start": 10.0, "end": 30.0, "duration": 20.0, "hype_score": 80, "hype_raw": 0.4,
            "signal_scores": {}, "text": LOL_TALK, "reasons": [{"t": 15, "code": "lol_pentakill", "value": "Yasuo"}]}
    write_json_atomic(p.dir / "highlights.json", {"mode": "gaming", "duration": 120, "candidates": [cand]})
    fake = FakeLLM()

    @contextlib.contextmanager
    def lazy(model=None):
        yield fake

    monkeypatch.setattr(llm, "lazy_session", lazy)
    res = analyze.analyze_project(p, out_lang="tr", translate=False)
    assert res["game"]["id"] == "lol" and not res["failed"]
    c = read_json(p.dir / "highlights.json")["candidates"][0]
    pub = c["publish"]
    assert c["llm"]["game_or_topic"] == "League of Legends"  # not the model's "Warzone" guess
    assert "Warzone" not in c["llm"]["what_happens"]
    _no_other_game(pub["titles"] + pub["hashtags"] + pub["tags"] + [pub["description"], pub["cover_text"]], "lol")
    assert pub["hashtags"][:3] == ["#utkualsirr", "#shorts", "#leagueoflegends"]
    assert len(pub["titles"]) >= 5 and sum(bool(T.caps_words(t)) for t in pub["titles"]) >= len(pub["titles"]) - 1
    assert not any("Warzone" in t or "Valorant" in t for t in pub["titles"])
    assert pub["description"].split("\n\n")[0].rstrip().endswith("?")
    assert any("Game: League of Legends" in x for x in fake.prompts)
    # metadata only: cuts, score and the burned-in hook text stay
    c["start"], c["end"] = 11.0, 29.0
    pub["hook_text"] = "ESKI HOOK"
    hl = read_json(p.dir / "highlights.json")
    hl["candidates"][0] = c
    write_json_atomic(p.dir / "highlights.json", hl)
    score = pub["viral_score"]
    analyze.analyze_project(p, meta_only=True)
    c2 = read_json(p.dir / "highlights.json")["candidates"][0]
    assert (c2["start"], c2["end"]) == (11.0, 29.0) and c2["publish"]["hook_text"] == "ESKI HOOK"
    assert c2["publish"]["viral_score"] == score and c2["publish"]["tags"]
    # the Library's publish setup + the YouTube description
    from sharkyclips.web import publishing as webpub

    meta = webpub.prefill(p, c2)
    assert meta["hashtags"][0] == "utkualsirr" and meta["tags"] == c2["publish"]["tags"]
    full = publishing.compose_description(meta["description"], meta["hashtags"], lang="tr")
    assert full.endswith(SOCIALS[-1]) and "#utkualsirr #shorts #leagueoflegends" in full


# ===================================================================== 1.2.26 follow-ups (seen on real projects)


def test_glued_swears_and_clip_times_never_reach_titles():
    assert analyze.has_profanity("Deepfuck diye bi oyuncu var mı?")  # a player name with a swear inside
    assert not analyze.has_profanity("Kule altında sıkıştım, kombo geldi")
    for t in ["Son 5.7 saniyede gelen OUTPLAY", "+7 saniyede gelen ses", "at +14s it happened"]:
        assert analyze.has_timestamp(t), t
    for t in ["3 saniyede 3 KILL", "Son 10 saniye", "1v4 CLUTCH"]:
        assert not analyze.has_timestamp(t), t
    f = analyze._forbidden("lol")
    assert f("Warzone gibi") == "Warzone" and f("Son 5.7 saniyede") == "a clip time" and f("Bu PENTAKILL") is None


def test_metadata_only_tops_up_too_few_titles_with_clean_old_ones():
    new = [{"style": "punchy", "text": "Bu PENTAKILL kimse beklemiyordu 💀"}]
    old = ["Deepfuck ile yayına girdik", "Warzone'da 1v4", "Kule altında üç kişiyi indirdim", "Takım beni yine sattı"]
    out = analyze._top_up(new, old, "tr", analyze._forbidden("lol"))
    assert [t["text"] for t in out] == [new[0]["text"], "Kule altında üç kişiyi indirdim", "Takım beni yine sattı"]
