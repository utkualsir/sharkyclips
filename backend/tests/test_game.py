"""Game awareness: text rules, event building, clip boundaries (no video or OCR needed)."""

from __future__ import annotations

from clipforge.game import detect
from clipforge.game.events import df_events, lol_events, lol_kda_series
from clipforge.game.presets import match_rules, multi_count, normalize, save_override, scaled_boxes
from clipforge.game.sounds import event_code
from clipforge.highlights.candidates import fit_spans
from clipforge.highlights.modes import get_mode


def test_normalize_turkish():
    assert normalize("Hedefi Etkisiz Hale Getir +50 DP") == "hedefi etkisiz hale getir +50 dp"
    assert normalize("ÖLDÜRME") == "oldurme"
    assert normalize("İntikam") == "intikam"


def test_df_rules_with_ocr_noise():
    m = lambda s: match_rules("delta_force", "lines", s)  # noqa: E731
    assert m("Öldürme +100 DP") == ["df_kill"]
    assert m("oldarme +100 P") == ["df_kill"]  # OCR noise
    assert m("Kurtarma +100 DP") == ["df_revive"]
    assert m("Value Kurtarma +3 DP") == []  # not a revive
    assert m("Hedefi Ele Geçir +10 DP") == []  # objective capture, not a kill
    assert m("Ekip Bastırma Yardımı +15 DP") == []
    assert "df_multi_line" in m("Çifte Öldürme")
    assert multi_count("Çifte Öldürme") == 2 and multi_count("Triple kill") == 3


def test_lol_rules():
    assert match_rules("lol", "center", "BOZGUN") == ["lol_defeat"]
    assert match_rules("lol", "center", "VICTORY") == ["lol_victory"]
    assert match_rules("lol", "announce", "PENTAKILL") == ["lol_pentakill"]
    assert match_rules("lol", "announce", "Takımından biri katledildi!") == []


def _kda(t, k, d, a):
    return {"t": t, "kind": "kda", "k": k, "d": d, "a": a}


def _team(t, ally, enemy):
    return {"t": t, "kind": "team", "ally": ally, "enemy": enemy}


def test_lol_kda_misreads_are_dropped():
    # 11/0/0 is a misread: the next reading (1/0/0) can't follow it, so it's not confirmed
    obs = [_kda(0, 0, 0, 0), _kda(100, 1, 0, 0), _kda(101, 11, 0, 0), _kda(121, 1, 0, 0), _kda(130, 2, 0, 0)]
    assert [o["k"] for o in lol_kda_series(obs)] == [0, 1, 2]


def test_lol_multikill_from_kda_and_first_blood():
    obs = [_kda(0, 0, 0, 0), _team(0, 0, 0), _kda(50, 1, 0, 0), _team(50, 1, 0), _kda(70, 1, 0, 0),
           _kda(200, 2, 0, 0), _kda(206, 3, 0, 0), _kda(214, 4, 0, 0), _kda(222, 5, 0, 0), _kda(240, 5, 0, 0),
           {"t": 300, "kind": "text", "region": "announce", "text": "PENTAKILL"}]  # another player's
    ev = lol_events(obs)
    codes = [e["code"] for e in ev]
    assert "lol_first_blood" in codes
    quadra = [e for e in ev if e["code"] == "lol_quadrakill"]
    assert len(quadra) == 1 and quadra[0]["start"] == 200 and quadra[0]["end"] == 222
    assert codes.count("lol_kill") == 1 and "lol_pentakill" not in codes


def test_lol_baron_spawn_is_not_an_event():
    assert match_rules("lol", "announce", "Baron Nashor ortaya çıktı!") == []
    assert match_rules("lol", "announce", "Takımınız Baron Nashor'u katletti!") == ["lol_baron"]


def test_df_kills_from_skull_icon():
    skull = lambda t: {"t": t, "kind": "icon", "icon": "skull", "score": 0.95}  # noqa: E731
    obs = [skull(10), skull(15), {"t": 15.5, "kind": "lines", "texts": ["Öldürme +100 DP", "Öldürme +100 DP"]},
           skull(60), {"t": 60.5, "kind": "lines", "texts": ["İntikam +30 DP", "Öldürme +100 DP"]},
           {"t": 70, "kind": "icon", "icon": "revive", "score": 0.9}, {"t": 90, "kind": "gray"},
           {"t": 90.5, "kind": "killcard", "text": "Pumadrops ÖLDÜREN: Düşman 2-1 Sen"},
           {"t": 120, "kind": "gray"}]  # downed only: no card -> not a death
    ev = df_events(obs)
    multi = [e for e in ev if e["code"] == "df_multikill"]
    assert len(multi) == 1 and multi[0]["value"] == "3" and multi[0]["start"] == 10 and multi[0]["end"] == 15
    codes = [e["code"] for e in ev]
    assert codes.count("df_kill") == 1 and "df_revenge" in codes and "df_revive" in codes
    assert codes.count("df_death") == 1


def test_fit_spans_keeps_whole_event():
    mode = get_mode("gaming")
    # a multikill from 100 to 130 s; the peak window only covers 120-140
    s, e, must = fit_spans(120, 140, 125, [(100, 130, 0.9)], mode, 3600)
    assert s <= 96 and e >= 132 and e - s <= mode.clip_max
    assert must is not None and must[0] <= 101 and must[1] >= 132
    # no event in the window: unchanged
    assert fit_spans(10, 40, 20, [(100, 130, 0.9)], mode, 3600) == (10, 40, None)


def test_scaled_boxes_720p():
    b = scaled_boxes("lol", 1280, 720)["team"]
    assert (b.x, b.y) == (1030, 1) and b.w == 48


def test_region_override_roundtrip():
    save_override("lol", "kda", [1500, 0, 200, 30])
    assert scaled_boxes("lol", 1920, 1080)["kda"].x == 1500
    save_override("lol", "kda", None)
    assert scaled_boxes("lol", 1920, 1080)["kda"].x == 1630


def test_detect_game():
    assert detect("TOPLAM 55 KILL (DELTA FORCE)", None)[0] == "delta_force"
    transcript = {"segments": [{"text": "Darius geldi, Alistar nerede? Teemo ile baronu alalım, Jinx arkada."}]}
    assert detect("RAKİP DARİUSA OYUNU ZEHİR ETTİM", transcript)[0] == "lol"
    assert detect("Minecraft survival", None)[0] is None


def test_sound_file_names():
    known = {"lol_pentakill", "lol_kill", "df_kill"}
    from pathlib import Path

    assert event_code(Path("lol_pentakill_tr 2.mp3"), known) == "lol_pentakill"
    assert event_code(Path("LOL_KILL.wav"), known) == "lol_kill"
    assert event_code(Path("random.wav"), known) is None
