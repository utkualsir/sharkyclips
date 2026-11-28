"""Merge a phase D7 text patch (patches/<lang>.json) into docs/sitegen/i18n/<lang>.json.

The result has exactly the English key order: new keys from the patch, removed keys dropped,
everything else keeps the existing translation.
"""
import json
import sys
from pathlib import Path

I18N = Path(r"C:\Users\redmo\Desktop\projeler\ClipForge\docs\sitegen\i18n")
PATCHES = Path(__file__).resolve().parent / "patches"
en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))


def ordered_like(ref: dict, cur: dict) -> dict:
    return {k: cur[k] for k in ref if k in cur}


def merge(code: str) -> None:
    cur = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
    p = json.loads((PATCHES / f"{code}.json").read_text(encoding="utf-8"))
    cur["common"].update(p["common"])
    h = cur["home"]
    ph = p["home"]
    for k in ("desc", "kick", "kick_more", "promise_label", "promise", "demo_alt", "demo_cap", "captions",
              "yt_short", "yt_show"):
        h[k] = ph[k]
    for card in h["cards"]:
        if card["icon"] == "palette":
            card["h"], card["p"] = ph["card_palette"]["h"], ph["card_palette"]["p"]
        if card["icon"] == "puzzle":
            card["p"] = ph["card_puzzle_p"]
    cur["home"] = ordered_like(en["home"], h)
    res = dict(p["results"])
    old_items = cur.get("results", {}).get("items")
    res["items"] = p["results"].get("items") or old_items or en["results"]["items"]
    cur["results"] = ordered_like(en["results"], res)
    cur["compare"] = ordered_like(en["compare"], p["compare"])
    dl = cur["download"]
    dl.update(p["download"])
    if len(dl["more"]) == 3:  # the macOS card moved into its own section
        dl["more"] = dl["more"][:2]
    cur["download"] = ordered_like(en["download"], dl)
    f = cur["features"]
    for s in f["sections"]:
        if s["id"] == "looks":
            s.update(p["features"]["looks"])
        if s["id"] == "helper":
            s["items"][1] = p["features"]["helper_item1"]
    out = ordered_like(en, cur)
    missing = [k for k in en if k not in out]
    assert not missing, missing
    (I18N / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("merged", code)


for code in sys.argv[1:]:
    merge(code)
