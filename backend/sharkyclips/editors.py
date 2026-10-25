"""Editor timelines for one clip: the cut on the original video, captions, event markers.

  fcpxml    FCPXML 1.9 - DaVinci Resolve (File > Import > Timeline) and Final Cut Pro.
            Captions are a real caption track (<caption>, lane 1); markers for detected events.
  premiere  Final Cut Pro 7 XML (xmeml 4), which Premiere Pro imports (File > Import).
            Markers on the sequence. FCP7 XML has no caption track, so the captions come as
            the .srt next to it (Premiere: File > Import, drag onto the timeline = caption track).

Both reference the ORIGINAL video file (full quality, handles to trim), not a rendered clip.
All times sit on frame boundaries, which Final Cut requires.

CapCut is not supported: its project format (draft_content.json) is undocumented, changes
between versions and is encrypted in current releases. CapCut can import the .srt file.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from .project import Project

MARKER_TEXT = {
    "loudness_spike": "Loud moment", "keyword": "Reaction word", "laughter": "Laughter", "shouting": "Shouting",
    "cheering": "Cheering", "fast_speech": "Fast talking", "pause_then_burst": "Silence then outburst",
    "steady_explanation": "Explanation", "chorus": "Chorus", "drop": "Drop", "chat_spike": "Chat spike",
    "chat_reactions": "Chat reactions", "llm_explanation": "Explanation",
    "lol_pentakill": "Pentakill", "lol_quadrakill": "Quadra kill", "lol_triplekill": "Triple kill",
    "lol_doublekill": "Double kill", "lol_kill": "Kill", "lol_assist": "Assist", "lol_death": "Death",
    "lol_first_blood": "First blood", "lol_shutdown": "Shutdown", "lol_ace": "Ace", "lol_baron_steal": "Baron steal",
    "lol_dragon_steal": "Dragon steal", "lol_baron": "Baron", "lol_dragon": "Dragon", "lol_victory": "Victory",
    "lol_defeat": "Defeat", "df_multikill": "Multikill", "df_kill": "Kill", "df_revenge": "Revenge kill",
    "df_knock": "Knock", "df_revive": "Revive", "df_assist": "Assist", "df_death": "Death",
    "df_extracted": "Extracted", "df_extract_failed": "Extraction failed",
}


def frame_rate(fps: float) -> tuple[int, int]:
    """(numerator, denominator) of the frame rate: 29.97 -> 30000/1001."""
    for nominal in (24, 30, 60, 120):
        if abs(fps - nominal * 1000 / 1001) < 0.02:
            return nominal * 1000, 1001
    return max(1, round(fps)), 1


class Clock:
    def __init__(self, fps: float):
        self.num, self.den = frame_rate(fps)
        self.timebase = round(self.num / self.den)
        self.ntsc = self.den == 1001

    def frames(self, t: float) -> int:
        return int(round(t * self.num / self.den))

    def rt(self, t: float) -> str:
        """FCPXML rational time on a frame boundary, e.g. '1001/30000s' or '45/30s'."""
        f = Fraction(self.frames(t) * self.den, self.num)
        return "0s" if f == 0 else (f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s")

    @property
    def frame_duration(self) -> str:
        return f"{self.den}/{self.num}s"


def markers(cand: dict) -> list[dict]:
    """Detected events inside the clip: [{t (source seconds), name, note}], one per second at most."""
    out: list[dict] = []
    for r in sorted(cand.get("reasons", []), key=lambda r: r.get("t", 0)):
        t = float(r.get("t", -1))
        if not cand["start"] <= t <= cand["end"]:
            continue
        name = MARKER_TEXT.get(r["code"], r["code"].replace("_", " ").capitalize())
        if r.get("value") and (r["code"] in ("keyword", "df_multikill", "chat_reactions") or r["code"].startswith("lol_")):
            name = f"{name}: {r['value']}"
        if out and abs(out[-1]["t"] - t) < 1.0 and out[-1]["name"] == name:
            continue
        out.append({"t": t, "name": name[:60], "note": f"{r['code']} · strength {round(float(r.get('strength') or 0), 2)}"})
    return out


def _media(project: Project) -> dict:
    meta = project.load_meta()
    src = project.source_path
    assert src is not None
    return {"path": src.resolve(), "name": src.name, "width": int(meta.get("width") or 1920),
            "height": int(meta.get("height") or 1080), "fps": float(meta.get("fps") or 30),
            "duration": float(meta.get("duration") or 0), "audio": meta.get("audio_codec") is not None,
            "title": meta.get("title") or project.id}


def _pretty(root: ET.Element, doctype: str) -> str:
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + doctype + "\n" + ET.tostring(root, encoding="unicode") + "\n"


def fcpxml(project: Project, cand: dict, cues: list[dict], lang: str | None) -> str:
    m = _media(project)
    clk = Clock(m["fps"])
    start, end = float(cand["start"]), float(cand["end"])
    dur = end - start
    name = f"SharkyClips #{cand['rank']:02d} - {m['title']}"[:120]
    root = ET.Element("fcpxml", version="1.9")
    res = ET.SubElement(root, "resources")
    ET.SubElement(res, "format", id="r1", frameDuration=clk.frame_duration, width=str(m["width"]),
                  height=str(m["height"]), colorSpace="1-1-1 (Rec. 709)")
    asset = ET.SubElement(res, "asset", id="r2", name=m["name"], start="0s", duration=clk.rt(m["duration"] or end),
                          hasVideo="1", format="r1", videoSources="1")
    if m["audio"]:
        asset.set("hasAudio", "1")
        asset.set("audioSources", "1")
        asset.set("audioChannels", "2")
        asset.set("audioRate", "48000")
    ET.SubElement(asset, "media-rep", kind="original-media", src=m["path"].as_uri())
    lib = ET.SubElement(root, "library")
    event = ET.SubElement(lib, "event", name="SharkyClips")
    proj = ET.SubElement(event, "project", name=name)
    seq = ET.SubElement(proj, "sequence", format="r1", duration=clk.rt(dur), tcStart="0s", tcFormat="NDF",
                        audioLayout="stereo", audioRate="48k")
    spine = ET.SubElement(seq, "spine")
    clip = ET.SubElement(spine, "asset-clip", ref="r2", offset="0s", name=m["name"], start=clk.rt(start),
                         duration=clk.rt(dur), format="r1", tcFormat="NDF")
    if m["audio"]:
        clip.set("audioRole", "dialogue")
    # Children of a clip use the clip's own (source) time: start + offset inside the clip.
    for mk in markers(cand):
        ET.SubElement(clip, "marker", start=clk.rt(mk["t"]), duration=clk.frame_duration, value=mk["name"],
                      note=mk["note"])
    role = f"SRT?captionFormat=SRT.{lang or 'en'}"
    for i, c in enumerate(cues, 1):
        a = max(0.0, min(c["start"], dur))
        b = max(a, min(c["end"], dur))
        if clk.frames(b) <= clk.frames(a):
            continue
        cap = ET.SubElement(clip, "caption", lane="1", offset=clk.rt(start + a), name=c["text"][:40],
                            start="3600s", duration=clk.rt(b - a), role=role)
        text = ET.SubElement(cap, "text", placement="bottom")
        ts = ET.SubElement(text, "text-style", ref=f"ts{i}")
        ts.text = c["text"]
        tdef = ET.SubElement(cap, "text-style-def", id=f"ts{i}")
        ET.SubElement(tdef, "text-style", font=".AppleSystemUIFont", fontSize="13", fontFace="Regular",
                      fontColor="1 1 1 1", backgroundColor="0 0 0 1")
    return _pretty(root, "<!DOCTYPE fcpxml>")


def _rate(parent: ET.Element, clk: Clock) -> None:
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(clk.timebase)
    ET.SubElement(rate, "ntsc").text = "TRUE" if clk.ntsc else "FALSE"


def premiere_xml(project: Project, cand: dict, cues: list[dict], lang: str | None) -> str:
    """FCP7 xmeml (Premiere Pro imports it). Frame counts at the nominal timebase."""
    m = _media(project)
    clk = Clock(m["fps"])
    fr = clk.frames  # real frames (29.97 fps: timebase 30 + ntsc TRUE)
    start, end = float(cand["start"]), float(cand["end"])
    a, b = fr(start), fr(end)
    length = b - a
    total = fr(m["duration"] or end)
    name = f"SharkyClips #{cand['rank']:02d} - {m['title']}"[:120]
    root = ET.Element("xmeml", version="4")
    seq = ET.SubElement(root, "sequence", id="sequence-1")
    ET.SubElement(seq, "name").text = name
    ET.SubElement(seq, "duration").text = str(length)
    _rate(seq, clk)
    tc = ET.SubElement(seq, "timecode")
    _rate(tc, clk)
    ET.SubElement(tc, "string").text = "00:00:00:00"
    ET.SubElement(tc, "frame").text = "0"
    ET.SubElement(tc, "displayformat").text = "NDF"
    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    fmt = ET.SubElement(video, "format")
    sc = ET.SubElement(fmt, "samplecharacteristics")
    _rate(sc, clk)
    ET.SubElement(sc, "width").text = str(m["width"])
    ET.SubElement(sc, "height").text = str(m["height"])
    ET.SubElement(sc, "pixelaspectratio").text = "square"
    vtrack = ET.SubElement(video, "track")

    def clipitem(parent: ET.Element, cid: str, kind: str) -> ET.Element:
        ci = ET.SubElement(parent, "clipitem", id=cid)
        ET.SubElement(ci, "name").text = m["name"]
        ET.SubElement(ci, "enabled").text = "TRUE"
        ET.SubElement(ci, "duration").text = str(total)
        _rate(ci, clk)
        ET.SubElement(ci, "start").text = "0"
        ET.SubElement(ci, "end").text = str(length)
        ET.SubElement(ci, "in").text = str(a)
        ET.SubElement(ci, "out").text = str(b)
        if kind == "video":
            f = ET.SubElement(ci, "file", id="file-1")
            ET.SubElement(f, "name").text = m["name"]
            ET.SubElement(f, "pathurl").text = m["path"].as_uri().replace("file:///", "file://localhost/")
            _rate(f, clk)
            ET.SubElement(f, "duration").text = str(total)
            fm = ET.SubElement(f, "media")
            fv = ET.SubElement(ET.SubElement(fm, "video"), "samplecharacteristics")
            _rate(fv, clk)
            ET.SubElement(fv, "width").text = str(m["width"])
            ET.SubElement(fv, "height").text = str(m["height"])
            if m["audio"]:
                fa = ET.SubElement(fm, "audio")
                ET.SubElement(fa, "channelcount").text = "2"
        else:
            ET.SubElement(ci, "file", id="file-1")
            st = ET.SubElement(ci, "sourcetrack")
            ET.SubElement(st, "mediatype").text = "audio"
            ET.SubElement(st, "trackindex").text = "1"
        return ci

    v = clipitem(vtrack, "clipitem-1", "video")
    if m["audio"]:
        audio = ET.SubElement(media, "audio")
        atrack = ET.SubElement(audio, "track")
        clipitem(atrack, "clipitem-2", "audio")
        for cid, kind in (("clipitem-1", "video"), ("clipitem-2", "audio")):
            link = ET.SubElement(v, "link")
            ET.SubElement(link, "linkclipref").text = cid
            ET.SubElement(link, "mediatype").text = kind
    for mk in markers(cand):
        mel = ET.SubElement(seq, "marker")
        ET.SubElement(mel, "name").text = mk["name"]
        ET.SubElement(mel, "comment").text = mk["note"]
        ET.SubElement(mel, "in").text = str(fr(mk["t"] - start))
        ET.SubElement(mel, "out").text = "-1"
    return _pretty(root, "<!DOCTYPE xmeml>")


def write(kind: str, project: Project, cand: dict, cues: list[dict], stem: Path, lang: str | None) -> Path:
    if kind == "fcpxml":
        path = stem.with_name(stem.name + ".fcpxml")
        path.write_text(fcpxml(project, cand, cues, lang), encoding="utf-8")
    else:
        path = stem.with_name(stem.name + ".premiere.xml")
        path.write_text(premiere_xml(project, cand, cues, lang), encoding="utf-8")
    return path


def validate(text: str, kind: str) -> list[str]:
    """Structural checks (no DTD on Windows): returns problems, [] = looks importable."""
    problems = []
    try:
        root = ET.fromstring(text.split("\n", 2)[2] if text.startswith("<?xml") else text)
    except ET.ParseError as exc:
        return [f"not well-formed XML: {exc}"]
    if kind == "fcpxml":
        if root.tag != "fcpxml" or not root.get("version"):
            problems.append("root must be <fcpxml version=...>")
        ids = {e.get("id") for e in root.iter() if e.get("id")}
        for e in root.iter():
            for attr in ("ref", "format"):
                if e.get(attr) and e.tag not in ("text-style",) and e.get(attr) not in ids:
                    problems.append(f"<{e.tag} {attr}={e.get(attr)}> points at nothing")
        for e in root.iter():
            for attr in ("offset", "start", "duration"):
                val = e.get(attr)
                if val is not None and not (val == "0s" or val.endswith("s")):
                    problems.append(f"<{e.tag} {attr}={val}> is not a rational time")
        clip = root.find(".//asset-clip")
        if clip is None:
            problems.append("no clip in the timeline")
        src = root.find(".//media-rep")
        if src is None or not (src.get("src") or "").startswith("file:"):
            problems.append("media file reference missing")
    else:
        if root.tag != "xmeml":
            problems.append("root must be <xmeml>")
        ci = root.find(".//clipitem")
        if ci is None:
            problems.append("no clip in the sequence")
        else:
            a, b = int(ci.findtext("in") or -1), int(ci.findtext("out") or -1)
            if not 0 <= a < b:
                problems.append("clip in/out points are wrong")
        if root.find(".//pathurl") is None:
            problems.append("media file reference missing")
    return problems
