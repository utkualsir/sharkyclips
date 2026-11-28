"""Gallery stills + the new demo video for the website, from the demo project (synthetic stream).

python make_media.py <project-dir> <old-demo.mp4> <out-dir>
-> out/results/<n>-before.webp (640x360), <n>-after.webp (270x480), out/demo.mp4 (1280x720), out/demo-poster.webp,
   out/results.json (rank, start, peak, title, text) to write the captions from
"""
import json
import subprocess
import sys
from pathlib import Path

proj, old_demo, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
(out / "results").mkdir(parents=True, exist_ok=True)
work = out / "_work"
work.mkdir(exist_ok=True)
src = proj / "source.mp4"
h = json.loads((proj / "highlights.json").read_text(encoding="utf-8"))
cands = {c["id"]: c for c in h["candidates"]}
clips = sorted((proj / "clips").glob("*_c*.mp4"))
NOWIN = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, **NOWIN)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True, **NOWIN).stdout)


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


meta = []
for n, clip in enumerate(clips[:6], 1):
    cid = clip.stem.split("_")[1]
    c = cands[cid]
    llm = c.get("llm") or {}
    title = llm.get("title") or (c.get("publish") or {}).get("title") or ""
    # the same moment in both: a second after the peak (the reaction is on screen and in the subtitles)
    t_src = c["peak"] + 1.0
    offset = dur(clip) - (c["end"] - c["start"])  # > 0 when a hook (flash) was put in front
    t_clip = max(0.0, offset) + (t_src - c["start"])
    ff("-ss", f"{t_src:.2f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=640:360", "-c:v", "libwebp",
       "-quality", "80", str(out / "results" / f"{n}-before.webp"))
    ff("-ss", f"{t_clip:.2f}", "-i", str(clip), "-frames:v", "1", "-vf", "scale=270:480", "-c:v", "libwebp",
       "-quality", "82", str(out / "results" / f"{n}-after.webp"))
    meta.append({"n": n, "id": cid, "rank": c["rank"], "start": c["start"], "end": c["end"], "peak": c["peak"],
                 "time": mmss(t_src), "title": title, "text": c.get("text", ""), "clip": str(clip),
                 "offset": round(offset, 2), "t_clip": round(t_clip, 2)})
(out / "results.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

# ---- the demo video (31 s, 1280x720, no sound): app home -> project -> 3 x side by side -> Share window
BG = "0x0a1020"
segs = []
# 0-3.5 s home screen and 3.5-7.5 s the project with its clips, from the old tour (1280x760 -> crop the top 720)
ff("-ss", "0", "-t", "3.5", "-i", str(old_demo), "-vf", "crop=1280:720:0:0,fps=30,format=yuv420p", "-an",
   "-c:v", "libx264", "-preset", "slow", "-crf", "24", str(work / "s0.mp4"))
ff("-ss", "4.2", "-t", "4.0", "-i", str(old_demo), "-vf", "crop=1280:720:0:0,fps=30,format=yuv420p", "-an",
   "-c:v", "libx264", "-preset", "slow", "-crf", "24", str(work / "s1.mp4"))
segs += ["s0.mp4", "s1.mp4"]
# three side-by-side pairs, 6 / 6 / 5.5 s: stream on the left (16:9), the finished clip on the right (9:16), in sync
lengths = [6.0, 6.0, 5.5]
for i, (m, L) in enumerate(zip(meta[:3], lengths)):
    a = max(m["start"], m["peak"] - 2.5)
    a_clip = m["offset"] + (a - m["start"])
    graph = (f"color=c={BG}:s=1280x720:r=30:d={L}[bg];"
             f"[0:v]scale=816:459,setsar=1,fps=30[l];[1:v]scale=371:660,setsar=1,fps=30[r];"
             f"[bg][l]overlay=x=40:y=130[t];[t][r]overlay=x=877:y=30,"
             # a small arrow between the two (drawn, so there is no text to translate)
             f"drawbox=x=858:y=355:w=12:h=10:color=0xd4ae5c:t=fill,format=yuv420p[v]")
    ff("-ss", f"{a:.2f}", "-t", str(L), "-i", str(src), "-ss", f"{a_clip:.2f}", "-t", str(L), "-i", m["clip"],
       "-filter_complex", graph, "-map", "[v]", "-an", "-t", str(L), "-c:v", "libx264", "-preset", "slow", "-crf", "24",
       str(work / f"p{i}.mp4"))
    segs.append(f"p{i}.mp4")
# 25-31 s: the Share window, the last 6 s of the old tour
D = dur(old_demo)
ff("-ss", f"{D - 6.0:.2f}", "-t", "6.0", "-i", str(old_demo), "-vf", "crop=1280:720:0:0,fps=30,format=yuv420p", "-an",
   "-c:v", "libx264", "-preset", "slow", "-crf", "24", str(work / "s9.mp4"))
segs.append("s9.mp4")
(work / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs), encoding="utf-8")
ff("-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-c:v", "libx264", "-preset", "slow", "-crf", "27",
   "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out / "demo.mp4"))
# poster: the first side-by-side pair (the "proof" frame), so the still picture already says what the app does
ff("-ss", "9.0", "-i", str(out / "demo.mp4"), "-frames:v", "1", "-c:v", "libwebp", "-quality", "78", str(out / "demo-poster.webp"))
print(json.dumps(meta, indent=1, ensure_ascii=False))
print("demo", dur(out / "demo.mp4"))
