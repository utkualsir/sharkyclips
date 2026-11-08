"""Long-video metadata in the creator's style (My style, Brand kit): the full stream / match as
a 16:9 YouTube video, or a best-of montage.

From the analyzed clips (what happens, facts, moment type) the local LLM writes 6 titles and
the long description ("... ile karşınızdayım!" opener, one story paragraph, "İyi seyirler!",
like / subscribe / comment CTA), checked against the style rules and written again when they
fail; hashtags and tags follow the creator's long-video pattern. Without a profile the generic
sample style is used.

Saved in highlights.json -> "long_metadata" (cached per clip list, style and model).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from . import config, languages
from .errors import SharkyClipsError
from .project import Project, read_json, write_json_atomic
from .textutil import sentences
from .titles import style as style_mod

MAX_ITEMS = 12
VERSION = 1


def _merge_facts(facts: list[dict]) -> dict:
    events, terms, seen_e, seen_t = [], [], set(), set()
    for f in facts:
        for e in f.get("events") or []:
            if e["key"] not in seen_e:
                seen_e.add(e["key"])
                events.append(e)
        for t in f.get("terms") or []:
            if t["term"].casefold() not in seen_t:
                seen_t.add(t["term"].casefold())
                terms.append(t)
    return {"events": events, "terms": terms}


def _moment(items: list[dict]) -> str:
    counts: dict[str, int] = {}
    for c in items:
        m = (c.get("llm") or {}).get("moment_type") or "other"
        counts[m] = counts.get(m, 0) + 1
    return max(counts, key=counts.get) if counts else "other"


def context(meta: dict, game: dict, items: list[dict], facts: dict, kind: str) -> str:
    from .titles import banks

    lines = []
    for i, c in enumerate(items, start=1):
        llm = c.get("llm") or {}
        lines.append(f"{i}. ({llm.get('moment_type') or 'moment'}) {llm.get('what_happens') or (c.get('text') or '')[:200]}")
    what = "the whole match / stream as one long video" if kind == "full" else "a best-of compilation of these moments"
    return f"""Video: {what}
Stream / video title: {meta.get('title', '')}
Game: {game['name'] if game.get('known') else 'unknown (never name or guess a game)'}
Match facts (from the game screen and the words, reliable): {banks.facts_text(facts) or 'none'}

The best moments, in order:
{chr(10).join(lines)}"""


def write(project: Project, items: list[dict] | None = None, *, kind: str = "full", lang: str | None = None,
          force: bool = False, on_stage: Callable[[str], None] | None = None, model_name: str | None = None) -> dict:
    """{titles, description, hashtags, tags, checks}; items: candidates (default: the top analyzed clips)."""
    from . import llm
    from .analyze import SYSTEM, _forbidden, game_names, lang_name, too_similar
    from .titles import banks, feedback, glossary as glossary_mod

    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise SharkyClipsError("No highlights yet for this project.")
    hl = read_json(hl_path)
    meta = project.load_meta()
    lang = languages.require(lang or (hl.get("analysis") or {}).get("language") or config.get("output_language") or "tr").code
    if items is None:
        items = sorted([c for c in hl["candidates"] if (c.get("publish") or {}).get("available")],
                       key=lambda c: c["rank"])[:MAX_ITEMS]
        items = sorted(items, key=lambda c: c["start"])
    if not items:
        raise SharkyClipsError("Analyze the clips with the AI first.")
    mine = style_mod.active(lang) or style_mod.sample()
    game = banks.project_game(project)
    gid = game["id"]
    bank = banks.get(gid)
    transcript = project.load_transcript() if project.transcript_path.is_file() else {}
    facts = _merge_facts([banks.clip_facts(bank, c, transcript) for c in items])
    clip_text = "\n".join(x["text"] for c in items for x in sentences(transcript, c["start"], c["end"]))[:4000]
    strong = llm.metadata_boost()
    name = model_name or (llm.choose_model(ignore_fast=True) if strong else llm.choose_model())
    payload = [VERSION, kind, name, lang, gid, style_mod.digest(lang, gid, "long") if style_mod.active(lang) else "sample",
               [[c["id"], c["start"], c["end"], (c.get("llm") or {}).get("what_happens")] for c in items]]
    key = hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:20]
    cache = project.cache_dir / "llm" / f"long_{key}.json"
    if cache.is_file() and not force:
        return read_json(cache)
    if on_stage:
        on_stage("long_writing")
    gl = glossary_mod.build(transcript, lang, meta.get("title", ""), game["name"], game=game["name"] or None,
                            game_terms=banks.glossary_terms(bank), extra_allowed=banks.caps_words(bank))
    used: list[str] = []  # a full-match title names the same champions as its clips: that's fine
    ctx = context(meta, game, items, facts, kind)
    moment = _moment(items)
    what = "; ".join(((c.get("llm") or {}).get("what_happens") or "")[:160] for c in items[:6])
    known = bool(game.get("known"))
    with llm.session(name) as model:
        tw = style_mod.write_titles(
            model, mine, system=SYSTEM, context=ctx, lang=lang, lang_label=lang_name(lang), fmt="long",
            gid=gid if known else None, game_name=game["name"] if known else "", what_happens=what,
            facts=banks.facts_text(facts), clip_text=clip_text, glossary=gl, used_titles=used,
            too_similar=too_similar, forbidden=_forbidden(gid), moment=moment,
            liked=feedback.examples(lang, "gaming")[0], strong=strong, game_names=game_names())
        title = (tw["titles"] or [{"text": meta.get("title") or ""}])[0]["text"]
        d = style_mod.write_description(
            model, mine, system=SYSTEM, context=ctx, lang=lang, lang_label=lang_name(lang), fmt="long",
            gid=gid if known else None, game_name=game["name"] if known else "", what_happens=what,
            facts=banks.facts_text(facts), clip_text=clip_text, title=title, glossary=gl, forbidden=_forbidden(gid),
            strong=strong)
    j = {"moment_type": moment}
    hashtags = style_mod.build_hashtags(mine, fmt="long", gid=gid if known else None,
                                        game_name=game["name"] if known else "", facts=facts, moment=moment,
                                        clip_text=clip_text, llm=d["mood_hashtags"], lang=lang,
                                        forbidden=_forbidden(gid))
    tags = style_mod.build_tags(mine, fmt="long", gid=gid if known else None, game_name=game["name"] if known else "",
                                facts=facts, moment=j["moment_type"], llm=d["search_tags"],
                                bank_tags=banks.build_tags(bank, facts, moment, lang), forbidden=_forbidden(gid))
    out = {"kind": kind, "titles": [t["text"] for t in tw["titles"]], "title_styles": [t["style"] for t in tw["titles"]],
           "description": style_mod.compose(d["text"], hashtags) if d["text"] else "", "body": d["text"],
           "hashtags": hashtags, "tags": tags, "language": lang, "model": name, "strong": strong,
           "game": {"id": gid, "name": game["name"]}, "clips": [c["id"] for c in items],
           "checks": {**tw["checks"], "description": d["problems"]},
           "profile": "my_style" if style_mod.active(lang) else "sample",
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write_json_atomic(cache, out)
    if kind == "full":
        hl = read_json(hl_path)  # re-read: other jobs may have saved meanwhile
        hl["long_metadata"] = out
        write_json_atomic(hl_path, hl)
    return out


def saved(project: Project) -> dict | None:
    p = project.dir / "highlights.json"
    return (read_json(p).get("long_metadata") if p.is_file() else None) or None
