"""Phase C (1.2.63): My style template on 5 synthetic sample projects, with the local AI.

    SHARKYCLIPS_HOME=<new temp dir> python docs/phase-c/samples.py <template.json> [profile.json] > out.md

Runs in a throwaway settings folder (never the real one): the creator's template (and style
examples) are copied in, 5 projects are made from short made-up Turkish transcripts (LoL,
Battlefield 6, Rematch, a Spider-Man 2 story episode, a LoL Short), then the normal analysis
writes the Shorts metadata and longmeta writes the long-video metadata. Prints Markdown.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
home = Path(os.environ.get("SHARKYCLIPS_HOME") or "")
tmp_root = Path(tempfile.gettempdir()).resolve()
if not home.parts or tmp_root not in home.resolve().parents:
    raise SystemExit("set SHARKYCLIPS_HOME to a new folder inside the temp folder")
os.environ["SHARKYCLIPS_NO_MIGRATE"] = "1"

from sharkyclips import analyze, config, longmeta  # noqa: E402
from sharkyclips.edit import brand  # noqa: E402
from sharkyclips.project import Project, write_json_atomic  # noqa: E402
from sharkyclips.titles import mytemplate  # noqa: E402

SAMPLES = [
    ("lol", "League of Legends dereceli Master Yi jungle", "long",
     "Kanka bu maç Master Yi jungle aldım. Duom Jax top lane'de. Bak şimdi ganka giriyorum. "
     "Dörtte dört! İnanılmaz ya, takım savaşında dördünü de ben aldım. Jax de kuleyi yıktı. "
     "Ejderhayı da aldık, Baron'a gidiyoruz. Maçı kazandık beyler, rakip takım darmadağın oldu."),
    ("bf6", "Battlefield 6 conquest gecesi", "long",
     "Battlefield 6'ya girdik, conquest haritası. Tanka bindim, köprüyü tuttum. "
     "Arkadaşım helikopterle geldi, beni aldı. Üç kişiyi tek şarjörle indirdim. "
     "Bayrağı aldık, son saniyede B noktasını savunduk ve maçı kazandık."),
    ("rematch", "Rematch izleyicilerle maç", "long",
     "Rematch'te izleyicilerle takım kurduk. Kaleci benim bu maç. "
     "İlk yarı iki sıfır gerideydik. Sonra üç gol üst üste attık! "
     "Son dakikada penaltıyı kurtardım, maçı üç ikiyle bitirdik."),
    ("sm2", "Marvel's Spider-Man 2 hikaye", "long",
     "Spider-Man 2 hikayesine devam ediyoruz. Kraven bu bölümde çok sinirli. "
     "Scorpion'la kapıştık, Kraven geldi ve Scorpion'u öldürdü. İnanılmaz bir sahne. "
     "Peter ve Miles birlikte şehirde sallanıyor. Bölüm burada bitti."),
    ("short", "League of Legends Master Yi short", "short",
     "Sadece dümdüz tıklıyorum bak. Bir, iki, üç, dört! Dörtte dört attım hiç efor yok. Master Yi bozuk ya."),
]


def make(pid: str, title: str, text: str) -> Project:
    d = config.workspace_dir() / pid
    d.mkdir(parents=True, exist_ok=True)
    words = [{"word": w, "start": 5 + i * 0.35, "end": 5.3 + i * 0.35} for i, w in enumerate(text.split())]
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": [
        {"start": 5, "end": 5 + len(words) * 0.35, "text": text, "words": words}]})
    dur = 5 + len(words) * 0.35 + 5
    write_json_atomic(d / "meta.json", {"id": pid, "title": title, "mode": "gaming", "game": "auto",
                                        "transcript": {"words": len(words), "language": "tr"}, "duration": dur})
    cand = {"id": "c01", "rank": 1, "start": 5.0, "end": round(5 + len(words) * 0.35, 2),
            "duration": round(len(words) * 0.35, 2), "hype_score": 90, "hype_raw": 0.5, "signal_scores": {},
            "text": text, "reasons": []}
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "duration": dur, "candidates": [cand]})
    return Project(id=pid, dir=d)


def main() -> None:
    tpl_src = Path(sys.argv[1])
    style_dir = config.config_dir() / "style"
    style_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tpl_src, style_dir / "template.json")
    if len(sys.argv) > 2:
        shutil.copyfile(sys.argv[2], style_dir / "profile.json")
    # the projects go into the throwaway folder too, never the real workspace
    config.update(output_language="tr", llm_enabled=True, workspace_dir=str(config.config_dir() / "ws"))
    out = ["# My style template: 5 sample projects", ""]
    for key, title, fmt, text in SAMPLES:
        p = make(f"sample-{key}", title, text)
        analyze.analyze_project(p, out_lang="tr", translate=False)
        hl = json.loads((p.dir / "highlights.json").read_text(encoding="utf-8"))
        pub = hl["candidates"][0]["publish"]
        out += [f"## {title} ({'Short' if fmt == 'short' else 'long video'})", ""]
        if fmt == "short":
            titles, desc, tags = pub["titles"], pub.get("description") or "", pub["hashtags"]
            full = brand.with_socials(desc, "tr", limit=4900, short=True)
        else:
            m = longmeta.write(p, force=True)
            titles, tags = m["titles"], m["hashtags"]
            full = brand.with_socials(m["description"], "tr", limit=4800)
        ep = (p.load_meta().get("episode") or {}).get("n")
        out += ["Titles:", ""] + [f"{i}. `{t}` ({len(t)} chars)" for i, t in enumerate(titles, 1)]
        out += ["", f"Hashtags ({len(tags)}): {' '.join(tags)}" + (f" · episode {ep}" if ep else ""), "",
                "Description (as posted):", "", "```text", full, "```", ""]
    out.append(f"Template: {mytemplate.path()}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
