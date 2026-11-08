"""1.2.28 My style: the creator's own metadata style (profile in ~/.sharkyclips/style), the rule
checks, the gamer glossary, the description layout and the analysis / long-video paths."""

from __future__ import annotations

import contextlib
import json
import re
import shutil

import pytest

from sharkyclips import analyze, config, longmeta, publishing
from sharkyclips.edit import brand
from sharkyclips.project import Project, read_json, write_json_atomic
from sharkyclips.titles import style as S

SOCIALS = ["🟩 Kick: https://kick.com/example", "📸 Instagram: https://www.instagram.com/example"]
EXAMPLES = [
    {"format": "short", "game": "delta_force", "title": "\"BEN HALLEDERİM!\" DEDİKTEN 2 SANİYE SONRA... 💀😂 (DELTA FORCE)",
     "description": "Delta Force'ta \"bu adam beni nereden vurdu?\" çaresizliği... 💀\n\nMerdivenden inerken tek yedim! 😂\n\n"
                    "Sizce bu vuruş şans mı? Yorumlara yazın! 👇\n\nHashtag'ler\n#DeltaForce #DeltaForceTR"},
    {"format": "short", "game": "lol", "title": "\"BU NE ŞANS?!\" 😂💀 (LOL TR)"},
    {"format": "long", "game": "delta_force", "title": "TOPLAM 55 KILL & 44 REVIVE! LOBİYİ TEK BAŞIMIZA TEMİZLEDİK! 🚨💀 (DELTA FORCE)",
     "description": "Delta Force'ta inanılmaz bir maçla karşınızdayım!\n\nBu maçta duom Uluru aldı. İyi seyirler!\n\n"
                    "Videoyu beğenmeyi, kanala abone olmayı ve en sevdiğiniz operatörü yorumlarda belirtmeyi unutmayın! 🚀"},
]


@pytest.fixture(autouse=True)
def _profile():
    old = config.get("channel_text")
    brand.save_channel_text({"hashtags": ["#example"], "names": ["example"],
                             "socials": {"enabled": True, "lines": SOCIALS, "headings": {}}})
    S.save({"enabled": True, "lang": "tr", "name": "Test Name", "channel_tag": "#TestChannel", "examples": EXAMPLES})
    yield
    config.update(channel_text=old)
    shutil.rmtree(S.folder(), ignore_errors=True)
    for d in config.workspace_dir().glob("ms-*"):
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== storage


def test_profile_lives_in_the_settings_folder_and_the_repo_has_only_a_generic_sample():
    assert S.profile_path().parent == config.config_dir() / "style" and S.profile_path().is_file()
    sample = json.loads(S.SAMPLE_FILE.read_text(encoding="utf-8"))
    flat = json.dumps(sample, ensure_ascii=False).casefold()
    assert "utku" not in flat and "kick.com" not in flat and sample["examples"]
    shutil.rmtree(S.folder())
    assert S.active("tr") is None  # no profile: the normal title style
    S.load_sample()
    assert S.active("tr") and S.active("en") is None  # only for the profile's language


def test_liked_titles_join_the_profile_and_leave_again():
    t = "\"BU NE ŞANS?!\" 😱🔥"
    S.on_vote(t, "tr", 1, "lol")
    ex = [e for e in S.load()["examples"] if e["source"] == "liked"]
    assert ex and ex[0]["title"] == t and ex[0]["game"] == "lol" and ex[0]["format"] == "short"
    S.on_vote(t, "tr", 0, "lol")
    assert not [e for e in S.load()["examples"] if e["source"] == "liked"]
    S.on_vote(t, "en", 1, "lol")  # another language: not this profile
    assert not [e for e in S.load()["examples"] if e["source"] == "liked"]


def test_examples_match_game_and_format():
    p = S.load()
    ex = S.examples_for(p, "delta_force", "short")
    assert ex[0]["game"] == "delta_force" and ex[0]["format"] == "short"
    lol = S.examples_for(p, "lol", "short")
    assert lol[0]["game"] == "lol"
    block = S.examples_block(p, "lol", "short", {"delta_force": "Delta Force", "lol": "League of Legends"}, [])
    assert "League of Legends" in block.split("Same format")[0] and "Delta Force" not in block  # other games: no names


# ===================================================================== title rules


@pytest.mark.parametrize("raw,want", [
    ('"nasıl öldüm lan?" (delta force\'da akıl sağlığını kaybetme anı) 💀😂',
     '"NASIL ÖLDÜM LAN?!" 💀😂 (DELTA FORCE\'TA AKIL SAĞLIĞINI KAYBETME ANI)'),
    ("İki katil aldım, takımı revize ettim 🔥", "DOUBLE KILL ALDIM, TAKIMI REVIVE ATTIM! 🔥😂"),
    ("Viktor ile 1v9 maç taşıdım. ⚡🤬 💥", "VİKTOR İLE 1v9 MAÇ TAŞIDIM! ⚡🤬"),
    ("Kardeşimi kurtarırdin ama siktir oldu #kanal", "KARDEŞİMİ KURTARIRDIN AMA S*KTİR OLDU! 😂💀"),
    ("SIFIRDAN YÜKSELİŞ: REVİVE ŞOVU! 😭💔", "SIFIRDAN YÜKSELİŞ: REVIVE ŞOVU! 😭💔"),  # the model's Turkish İ
    ("iki double killle şikayet ettim", "İKİ DOUBLE KILL'LE ŞİKAYET ETTİM! 😂💀"),
])
def test_fix_title_writes_the_creator_format(raw, want):
    out = S.fix_title(raw, "tr", "funny")
    assert out == want
    assert S.fix_title(out, "tr", "funny") == out  # stable: fixing again changes nothing
    assert not S.check_title(out, lang="tr", fmt="long", clip_text="nasıl öldüm lan", forbidden=None)


def test_check_title_catches_every_rule():
    ok = '"NASIL ÖLDÜM LAN?!" 💀😂 (DELTA FORCE)'
    clip = "abi ya nasıl öldüm lan ben bu merdivende"
    assert S.check_title(ok, lang="tr", fmt="short", clip_text=clip) == []
    bad = S.check_title('"BUNU HİÇ SÖYLEMEDİM!" 💀😂', lang="tr", fmt="short", clip_text=clip)
    assert any("really said" in e for e in bad)
    assert any("CAPITALS" in e for e in S.check_title("Küçük harfli başlık! 💀😂", lang="tr", fmt="short", clip_text=clip))
    assert any("2 fitting emojis" in e for e in S.check_title("TEK EMOJİ! 💀", lang="tr", fmt="short", clip_text=clip))
    assert any("censor" in e for e in S.check_title("SİKTİR GİT! 💀😂", lang="tr", fmt="short", clip_text=clip))
    long_hook = "BU MAÇTA HER ŞEY ÇOK GÜZEL GİDİYORDU AMA SONRA BİR ŞEY OLDU VE! 💀😂"
    assert any("first 40" in e for e in S.check_title(long_hook, lang="tr", fmt="short", clip_text=clip))
    assert not any("first 40" in e for e in S.check_title(long_hook, lang="tr", fmt="long", clip_text=clip))
    assert any("100" in e for e in S.check_title("A" * 101 + "! 💀😂", lang="tr", fmt="long", clip_text=clip))
    f = analyze._forbidden("lol")
    assert any("Valorant" in e for e in S.check_title("VALORANT GİBİ OYNADIM! 💀😂", lang="tr", fmt="long",
                                                       clip_text=clip, forbidden=f))
    copy = S.check_title(EXAMPLES[0]["title"], lang="tr", fmt="short", clip_text=clip,
                         example_titles=[e["title"] for e in EXAMPLES], too_similar=analyze.too_similar)
    assert any("copies an example" in e for e in copy)


def test_quotes_must_come_from_the_transcript():
    clip = "Kardeşimi kurtaracağım dedim, koştum, sonra öldüm. Ya bu nasıl s*ktir"
    assert S.quote_in_transcript("KARDEŞİMİ KURTARACAĞIM", clip)
    assert S.quote_in_transcript("BU NASIL S*KTİR", clip)  # censored words still match
    assert not S.quote_in_transcript("BEN EN İYİSİYİM", clip)
    assert S.quote_of('"KARDEŞİMİ KURTARACAĞIM" DEDİKTEN 1 SANİYE SONRA... 💀😂') == "KARDEŞİMİ KURTARACAĞIM"
    assert S.hook_end('"KARDEŞİMİ KURTARACAĞIM" DEDİKTEN 1 SANİYE SONRA... 💀😂') <= 25


def test_swears_are_censored_never_written_out():
    out, n = S.censor("siktir lan bok gibi oldu amk, sıkıştım", "tr")
    assert out == "s*ktir lan b*k gibi oldu a*k, sıkıştım" and n == 3  # "lan" is the creator's style
    assert not analyze.has_profanity(out)


# ===================================================================== gamer Turkish


def test_gaming_terms_are_never_translated_and_turkish_is_proofread():
    assert S.proofread_tr("iki katil aldım, revize ettim")[0] == "double kill aldım, revive attım"
    assert S.proofread_tr("3 katil geldi")[0] == "3 kill geldi"
    assert S.proofread_tr("kardeşimi kurtarırdin")[0] == "kardeşimi kurtarırdın"
    assert S.fix_tr_harmony("geldın aldin")[0] == "geldin aldın"
    assert S.fix_tr_suffixes("Delta Force'da Yasuo'de")[0] == "Delta Force'ta Yasuo'da"
    assert S.fix_tr_suffixes("DELTA FORCE'DA")[0] == "DELTA FORCE'TA"
    assert S.fix_tr_harmony("geldin")[0] == "geldin"  # right words stay


def test_corrections_the_creator_makes_are_learned_and_applied():
    found = S.learn_from_edit("ULTİMATE YETENEĞİ İLE İKİ KİŞİ GİTTİ! 💀😂", "ULTİ İLE İKİ KİŞİ GİTTİ! 💀😂", "tr")
    assert found and S.glossary()["corrections"]
    assert S.learn_from_edit("çok güzel bir maç oldu", "aşırı güzel bir maç oldu", "tr") == []  # a style choice
    assert S.learn_from_edit("tamamen başka bir metin", "hiç alakası yok bunun", "tr") == []
    S.learn_from_edit("kafa kesti attım", "headshot attım", "tr")
    assert S.apply_corrections("KAFA KESTİ ATTIM")[0] == "HEADSHOT ATTIM"
    assert "headshot" in S.keep_terms()


# ===================================================================== hashtags, tags, layout


FACTS = {"events": [], "terms": [{"term": "Stinger", "kind": "operators"}, {"term": "Uluru", "kind": "operators"}]}


def test_hashtags_follow_the_creator_order_and_count():
    p = S.load()
    h = S.build_hashtags(p, fmt="short", gid="delta_force", game_name="Delta Force", facts=FACTS, moment="fail",
                         clip_text="of be tilt oldum", llm=["#MedicFail", "#Valorant", "#KomikAnlar"], lang="tr",
                         forbidden=analyze._forbidden("delta_force"))
    assert 10 <= len(h) <= 12, h
    assert h[:2] == ["#DeltaForce", "#DeltaForceTR"] and "#Stinger" in h and "#Uluru" in h
    assert "#GamingShorts" in h and "#ShortsTR" in h and h[-2:] == ["#TestChannel", "#GamingTR"]
    assert "#Valorant" not in h and "#Tilt" in h
    lg = S.build_hashtags(p, fmt="long", gid="lol", game_name="League of Legends", facts={"events": [], "terms": []},
                          moment="exciting", clip_text="", llm=[], lang="tr")
    assert lg[:2] == ["#LeagueOfLegends", "#LoLTR"] and "#LoLGameplay" in lg and "#GamingShorts" not in lg


def test_tags_are_natural_search_phrases_with_the_creator_name():
    p = S.load()
    t = S.build_tags(p, fmt="short", gid="delta_force", game_name="Delta Force", facts=FACTS, moment="funny",
                     llm=["delta force medic fail", "FPS komik anlar", "valorant clutch"],
                     forbidden=analyze._forbidden("delta_force"), bank_tags=["delta force türkçe", "delta force highlights", "delta force clips", "fps oyunları",
                                "delta force shorts", "delta force operatörler"])
    assert 10 <= len(t) <= 15, t
    assert "Test Name Shorts" in t and "Delta Force Türkçe" in t and not any("valorant" in x.lower() for x in t)
    lt = S.build_tags(p, fmt="long", gid="delta_force", game_name="Delta Force", facts=FACTS, moment="exciting",
                      llm=[], bank_tags=[])
    assert "Test Name Delta Force" in lt


def test_layout_shorts_without_socials_long_with_socials_before_hashtags():
    body = "Merdivenden inerken tek yedim! 😂\n\nSizce şans mı? Yorumlara yazın! 👇\n\n#DeltaForce #DeltaForceTR"
    short = brand.with_socials(body, "tr", limit=4800, short=True)
    assert "kick.com" not in short and short.endswith("Hashtag'ler:\n#DeltaForce #DeltaForceTR")
    long = brand.with_socials(body, "tr", limit=4800)
    assert long.index("kick.com") < long.index("Hashtag'ler:") and long.endswith("#DeltaForce #DeltaForceTR")
    assert brand.with_socials(long, "tr", limit=4800) == long  # once
    full = publishing.compose_description("Bir metin.", ["DeltaForce", "TestChannel"], lang="tr")
    assert full.index("kick.com") < full.index("Hashtag'ler:\n#DeltaForce #TestChannel")
    s = S.load()
    S.save({**s, "shorts_socials": True})
    assert "kick.com" in brand.with_socials(body, "tr", short=True)
    S.save({**s, "enabled": False})  # off: the normal layout (socials at the very end)
    assert brand.with_socials(body, "tr").endswith(SOCIALS[-1])


def test_assembled_descriptions_pass_their_checks():
    p = S.load()
    short = S.assemble_short({"lines": ["Delta Force'ta o an... 💀", "Merdivenden indim, tek yedim! 😂"],
                              "question": "Sizce bu şans mıydı?"}, p, "tr")
    assert short.endswith("Yorumlara yazın! 👇") and not S.check_short_description(short, lang="tr")
    long = S.assemble_long({"opener": "Delta Force'ta efsane bir maçla karşınızdayım!",
                            "story": "Bu maçta duom Uluru aldı, ben Stinger ile 44 revive attım ve lobiyi temizledik.",
                            "comment": "en sevdiğiniz operatör ikilisini yorumlarda belirtmeyi"}, p, "tr")
    assert "İyi seyirler!" in long and long.endswith("unutmayın! 🚀")
    assert not S.check_long_description(long, p, lang="tr")
    assert S.check_long_description("Bir maç.\n\nHikaye.", p, lang="tr")


# ===================================================================== analysis end to end


def _project(pid: str, text: str) -> Project:
    d = config.workspace_dir() / pid
    d.mkdir(parents=True, exist_ok=True)
    words = [{"word": w, "start": 10 + i * 0.4, "end": 10.3 + i * 0.4} for i, w in enumerate(text.split())]
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": [
        {"start": 10, "end": 10 + len(words) * 0.4, "text": text, "words": words}]})
    write_json_atomic(d / "meta.json", {"id": pid, "title": "Delta Force gece yayını", "mode": "gaming", "game": "auto",
                                        "transcript": {"words": len(words)}, "duration": 120})
    return Project(id=pid, dir=d)


DF_TALK = ("Kanka ben Stinger ile girdim. Kardeşimi kurtaracağım! Koştum ve öldüm. Nasıl öldüm lan? "
           "Uluru arkadan geldi, revive attım, zero dam haritasında tilt oldum")


class FakeLLM:
    """A model that first breaks the rules (copies an example, invents a quote, names Valorant),
    then writes good drafts once it gets the problems back."""

    model = "fake:1"
    calls = retries = 0
    seconds = load_seconds = tokens_per_second = 0.0

    def __init__(self):
        self.prompts: list[str] = []
        self.rounds = 0

    def json(self, system, prompt, schema, check=None, soft=None, **kw):
        self.prompts.append(prompt)
        props = schema["properties"]
        if "game_or_topic" in props:
            return {"game_or_topic": "Valorant", "what_happens": "The streamer runs to revive a teammate and dies.",
                    "self_contained": True, "moment_type": "fail", "funny": 8, "exciting": 6, "useful": 1,
                    "hook_score": 80, "retention_score": 75, "trend_fit_score": 70, "start_shift_s": 0, "end_shift_s": 0,
                    "hashtags": ["#fail"], "hook_text": "Kurtaracağım derken", "cover_scene": "A soldier running", "cover_text": "RİSK"}
        if "kind" in json.dumps(props.get("titles", {})):
            self.rounds += 1
            if self.rounds == 1 and "Problems with your earlier" not in prompt:
                return {"titles": [{"kind": "quote", "text": EXAMPLES[0]["title"]},
                                   {"kind": "quote", "text": '"Ben en iyisiyim" dedim ve öldüm 💀😂'},
                                   {"kind": "fact", "text": "Valorant gibi revive attım!"}]}
            return {"titles": [
                {"kind": "quote", "text": '"Kardeşimi kurtaracağım!" dedikten 2 saniye sonra... 💀😂'},
                {"kind": "quote", "text": '"Nasıl öldüm lan?" Stinger ile revive faciası 😂💀 (Delta Force)'},
                {"kind": "situation", "text": "Revize etmeye koştum, yere ben yattım! 💀😂"},
                {"kind": "fact", "text": "Stinger ile iki katil, sonra direkt öldüm! 🔥💀"},
                {"kind": "question", "text": "Medic oynayan herkes böyle mi ölüyor? 😂💀"},
                {"kind": "situation", "text": "Uluru arkadan geldi, tilt oldum! 😤💀 (Delta Force oynanış)"},
                {"kind": "story", "text": "Kurtarmaya gittim, kurtarılan ben oldum! 😂🙃"}]}
        if "keep" in json.dumps(props.get("titles", {})):
            listing = prompt.split("Titles:\n", 1)[1].split("\n\n", 1)[0]
            return {"titles": [{"i": int(i), "text": t, "keep": True} for i, t in re.findall(r"^(\d+)\. (.+)$", listing, re.M)]}
        if "lines" in props:
            return {"lines": ["Delta Force'ta \"kardeşimi kurtarırım\" özgüveni... 💀",
                              "Stinger ile koştum, revize edecektim, anında yere yattım! 😂"],
                    "question": "Siz de arkadaşınızı kurtarmaya giderken böyle oluyor musunuz?",
                    "mood_hashtags": ["#MedicFail", "#KomikAnlar", "#Valorant"],
                    "search_tags": ["delta force medic fail", "delta force komik anlar", "valorant clutch"]}
        if "opener" in props:
            return {"opener": "Delta Force'ta lobiyi tek başımıza temizlediğimiz bir maçla karşınızdayım!",
                    "story": "Bu maçta duom Uluru ile koridorları kapattı, ben de Stinger ile düşen kimseyi geride "
                             "bırakmadım. Revive üstüne revive attık ve maçı rahat kazandık.",
                    "comment": "en sevdiğiniz operatör ikilisini yorumlarda belirtmeyi",
                    "mood_hashtags": ["#TakımOyunu"], "search_tags": ["delta force duo maçları", "delta force stinger"]}
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


def test_analysis_writes_shorts_metadata_in_the_creator_style(monkeypatch):
    p = _project("ms-df", DF_TALK)
    cand = {"id": "c01", "rank": 1, "start": 10.0, "end": 24.0, "duration": 14.0, "hype_score": 80, "hype_raw": 0.4,
            "signal_scores": {}, "text": DF_TALK, "reasons": []}
    write_json_atomic(p.dir / "highlights.json", {"mode": "gaming", "duration": 120, "candidates": [cand]})
    fake = FakeLLM()
    _fake(monkeypatch, fake)
    analyze.analyze_project(p, out_lang="tr", translate=False)
    pub = read_json(p.dir / "highlights.json")["candidates"][0]["publish"]
    text = analyze._clip_text_around(p.load_transcript(), cand)
    assert len(pub["titles"]) >= 4, pub["title_checks"]["rejected"]
    for t in pub["titles"]:
        assert not S.check_title(t, lang="tr", fmt="short", clip_text=text, forbidden=analyze._forbidden("delta_force")), t
        assert "VALORANT" not in t and t != EXAMPLES[0]["title"]
    assert S.quote_of(pub["titles"][0])  # Shorts: quote titles lead
    assert any("DOUBLE KILL" in t for t in pub["titles"]) and any("REVIVE" in t for t in pub["titles"])
    rej = pub["title_checks"]["rejected"]
    assert any("copies an example" in r["reason"] for r in rej) and any("really said" in r["reason"] for r in rej)
    body, tags = brand.split_tail_hashtags(pub["description"])
    assert body.endswith("👇") and "revive" in body and "revize" not in body
    assert 10 <= len(pub["hashtags"]) <= 12 and pub["hashtags"][0] == "#DeltaForce" and "#Valorant" not in pub["hashtags"]
    assert 10 <= len(pub["tags"]) <= 15 and "Test Name Shorts" in pub["tags"]
    assert any("THIS creator's own titles" in x for x in fake.prompts)
    # the Library keeps the creator's hashtag order and the upload has no socials (Short)
    from sharkyclips.web import publishing as webpub

    c = read_json(p.dir / "highlights.json")["candidates"][0]
    meta = webpub.prefill(p, c)
    assert meta["hashtags"][0] == "DeltaForce"
    full = publishing.compose_description(meta["description"], meta["hashtags"], lang="tr", short=True)
    assert "kick.com" not in full and "Hashtag'ler:\n#DeltaForce" in full


def test_long_video_metadata(monkeypatch):
    p = _project("ms-long", DF_TALK)
    cand = {"id": "c01", "rank": 1, "start": 10.0, "end": 24.0, "duration": 14.0, "hype_score": 80, "hype_raw": 0.4,
            "signal_scores": {}, "text": DF_TALK, "reasons": [],
            "publish": {"available": True, "titles": ["ESKİ BAŞLIK! 💀😂"], "language": "tr"},
            "llm": {"what_happens": "Revives with Stinger", "moment_type": "exciting"}}
    write_json_atomic(p.dir / "highlights.json", {"mode": "gaming", "duration": 120, "candidates": [cand],
                                                  "analysis": {"language": "tr"}})
    _fake(monkeypatch, FakeLLM())
    out = longmeta.write(p)
    assert out["titles"] and all(not S.check_title(t, lang="tr", fmt="long", clip_text=DF_TALK) for t in out["titles"])
    paras = out["description"].split("\n\n")
    assert paras[0].endswith("karşınızdayım!") and "İyi seyirler!" in paras[1] and "abone" in paras[2]
    assert "#DeltaForceGameplay" in out["hashtags"] and "Test Name Delta Force" in out["tags"]
    assert read_json(p.dir / "highlights.json")["long_metadata"]["titles"] == out["titles"]
    full = brand.with_socials(out["description"], "tr", limit=4800)
    assert full.index("kick.com") < full.index("Hashtag'ler:")
