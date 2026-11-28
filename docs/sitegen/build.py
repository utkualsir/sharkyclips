"""Build the SharkyClips website (docs/site) in 11 languages from one set of templates.

    python docs/sitegen/build.py                 build every page (fails on a missing translation)
    python docs/sitegen/build.py --shots <dir>   also convert fresh app screenshots (PNG) to WebP
    python docs/sitegen/build.py --og            also redraw the Open Graph image (img/og.png)
    python docs/sitegen/build.py --stats         also refresh stats.json (GitHub stars, downloads, checksums; gh CLI)

Sources: docs/sitegen/i18n/<lang>.json (texts; English is the reference, every other file must
have the same keys), docs/sitegen/legal/*.html (the English privacy policy and terms, the text
Google reviewed), docs/sitegen/site.css, CHANGELOG.md (Updates page) and VERSION. Output:
English at the site root (index.html, privacy.html and terms.html keep the URLs Google knows),
the other languages in /<lang>/, plus sitemap.xml, robots.txt and 404.html. Publish with
`bash docs/publish-site.sh "message"`. No external fonts, scripts or trackers: everything is
served from the site itself, and the only script is a small inline one (theme + language).
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "docs" / "site"
sys.path.insert(0, str(REPO / "backend"))

BASE = "https://utkualsir.github.io/sharkyclips-site/"
GH = "https://github.com/utkualsir/sharkyclips"
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
SETUP_URL = f"{GH}/releases/download/v{VERSION}/SharkyClips-Setup-{VERSION}.exe"
RELEASES = f"{GH}/releases"
SETUP_MB = 375
SETUP_NAME = f"SharkyClips-Setup-{VERSION}.exe"
INSTALL_SH_URL = f"{GH}/releases/download/v{VERSION}/install.sh"

# docs/sitegen/stats.json: GitHub stars + download count + the SHA-256 of each release's installers,
# refreshed with `--stats` (gh api). Drawn into the page at build time: no badge service, no request
# from the visitor's browser to anyone but this site.
STATS_FILE = HERE / "stats.json"
# docs/sitegen/benchmarks.json: processing times measured on a real PC (docs/phase-d7.md)
BENCH_FILE = HERE / "benchmarks.json"
# the demo video's captions: (start, end) in seconds for each text of home.captions
DEMO_CUES = [(0.0, 3.5), (3.5, 7.5), (7.5, 13.5), (13.5, 19.5), (19.5, 25.0), (25.0, 31.0)]
# the "Real results" pictures: img/results/<n>-before.webp (16:9) and <n>-after.webp (9:16)
RESULTS = 6
DEMO_SIZE = (1280, 720)
DEMO_DATE = "2026-11-28"
# the comparison table (home page): official pages only, read on this date (docs/phase-d7.md lists the quotes)
COMPARE_CHECKED = "2026-11-28"
COMPARE_SOURCES = [
    "https://eklipse.gg/",
    "https://eklipse.gg/help/how-much-does-eklipse-premium-cost/",
    "https://eklipse.gg/help/what-are-the-main-differences-between-the-free-and-premium-plans/",
    "https://eklipse.gg/help/will-my-exported-video-have-a-watermark/",
    "https://eklipse.gg/help/import-kick-streams-to-eklipse/",
    "https://eklipse.gg/features/ai-edit/",
    "https://www.opus.pro/pricing",
    "https://help.opus.pro/docs/article/plans-and-credits.md",
    "https://help.opus.pro/docs/article/video-sources-supported.md",
    "https://help.opus.pro/docs/article/video-languages-supported.md",
    "https://streamladder.com/pricing",
    "https://www.streamladder.com/clipgpt/import-from-kick",
    "https://www.streamladder.com/clip-editor/word-censoring",
    "https://www.streamladder.com/clip-editor/captions",
]


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def fetch_stats() -> None:
    """Stars, downloads and this version's checksums from GitHub (needs the gh CLI)."""
    import subprocess

    def gh(*args: str) -> str:
        kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8", **kw).stdout

    from datetime import date

    stats = load_json(STATS_FILE)
    repo = json.loads(gh("api", "repos/utkualsir/sharkyclips"))
    rels = json.loads(gh("api", "--paginate", "--slurp", "repos/utkualsir/sharkyclips/releases?per_page=100"))
    rels = [r for page in rels for r in page] if rels and isinstance(rels[0], list) else rels
    # what people download: installers, install.sh and the extension packages (not the .sha256 files)
    downloads = sum(a["download_count"] for r in rels for a in r.get("assets", [])
                    if not a["name"].endswith((".sha256", ".txt", ".json")))
    sums = dict(stats.get("sha256", {}))
    for r in rels:
        if r.get("tag_name") != f"v{VERSION}":
            continue
        for a in r.get("assets", []):
            if a["name"] in (f"{SETUP_NAME}.sha256", "install.sh.sha256"):
                txt = gh("api", "-H", "Accept: application/octet-stream", f"repos/utkualsir/sharkyclips/releases/assets/{a['id']}")
                h = txt.split()[0].lower()
                if not re.fullmatch(r"[0-9a-f]{64}", h):
                    raise SystemExit(f"bad checksum file {a['name']}")
                sums.setdefault(VERSION, {})["setup" if a["name"].startswith("SharkyClips") else "install_sh"] = h
    stats.update(stars=int(repo["stargazers_count"]), downloads=int(downloads), checked=date.today().isoformat(),
                 sha256=dict(sorted(sums.items(), key=lambda kv: [int(x) for x in kv[0].split(".")])[-5:]))
    STATS_FILE.write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"stats: {stats['stars']} stars, {stats['downloads']} downloads, checksums for {sorted(stats['sha256'])}")


def sha_for(kind: str) -> str | None:
    return load_json(STATS_FILE).get("sha256", {}).get(VERSION, {}).get(kind)


def compact_number(n: int, code: str) -> str:
    """1234 -> 1.2k (the same short form in every language, as on GitHub)."""
    if n < 1000:
        return str(n)
    s = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
    return (s.replace(".", ",") if code in ("tr", "es", "pt", "de", "fr", "hu", "ru") else s) + "k"

# code, name in its own language, html lang / hreflang, Open Graph locale, text direction
LANGS = [
    ("en", "English", "en", "en_US", "ltr"),
    ("tr", "Türkçe", "tr", "tr_TR", "ltr"),
    ("es", "Español", "es", "es_LA", "ltr"),
    ("pt", "Português (Brasil)", "pt-BR", "pt_BR", "ltr"),
    ("de", "Deutsch", "de", "de_DE", "ltr"),
    ("fr", "Français", "fr", "fr_FR", "ltr"),
    ("hu", "Magyar", "hu", "hu_HU", "ltr"),
    ("ru", "Русский", "ru", "ru_RU", "ltr"),
    ("ar", "العربية", "ar", "ar_AR", "rtl"),
    ("zh", "中文", "zh-Hans", "zh_CN", "ltr"),
    ("ja", "日本語", "ja", "ja_JP", "ltr"),
]
if os.environ.get("SITE_LANGS"):  # preview while writing texts: SITE_LANGS=en,tr (never for publishing)
    LANGS = [x for x in LANGS if x[0] in os.environ["SITE_LANGS"].split(",")]
CODES = [x[0] for x in LANGS]
PAGES = ["index", "features", "download", "faq", "updates", "contact", "privacy", "terms"]
NAV = ["index", "features", "download", "faq", "updates", "contact"]
UPDATES_SHOWN = 12

LIGHT = """color-scheme: light;
    --bg: #f9fafc; --bg-2: #f1f4f9; --surface: #ffffff; --surface-2: #eef2f8; --border: #e1e6ef;
    --border-strong: #c6cfdf; --text: #0e1a33; --strong: #0b1530; --muted: #55617a; --gold: #d4ae5c;
    --gold-text: #7a5a1f; --gold-soft: rgba(212, 174, 92, 0.16); --link: #1650c8; --primary-bg: #0e1a33;
    --primary-text: #ffffff; --primary-hover: #1d3461; --chip-bg: #eaf0fb; --chip-text: #1d3461; --wave: #1f6fe5;
    --ok: #1a724c; --glow: radial-gradient(900px 420px at 80% -10%, rgba(31, 111, 229, 0.10), transparent 70%);
    --focus: 0 0 0 3px rgba(22, 80, 200, 0.4); --shadow: 0 24px 64px -28px rgba(14, 26, 51, 0.35);"""

# Phosphor-style 24 px icons (stroke = currentColor), drawn here so nothing is fetched
ICONS = {
    "download": '<path d="M12 3v12m0 0-5-5m5 5 5-5M4 17v3h16v-3"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z"/>',
    "wave": '<path d="M3 15c3-3 6 3 9 0s6 3 9 0M7 11l5-7 2.5 7"/>',
    "game": '<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 11v3m-1.5-1.5h3M15.5 12h.01M18 13.5h.01"/>',
    "mute": '<path d="M4 9h4l5-4v14l-5-4H4zM17 9l4 6m0-6-4 6"/>',
    "share": '<path d="M12 15V3m0 0L7 8m5-5 5 5M5 12v8h14v-8"/>',
    "puzzle": '<path d="M5 8h3a2 2 0 1 1 4 0h3v3a2 2 0 1 1 0 4v3h-3a2 2 0 1 0-4 0H5v-3a2 2 0 1 0 0-4z"/>',
    "photos": '<rect x="3" y="5" width="15" height="13" rx="2"/><path d="M7 21h12a2 2 0 0 0 2-2V8M6 15l3.5-4 3 3 2-2 3.5 3"/>',
    "palette": '<path d="M12 3a9 9 0 0 0 0 18c1.4 0 2-1 2-2s-1-1.5-1-2.5 1-2 2.5-2H18a3 3 0 0 0 3-3c0-4.7-4-8.5-9-8.5Z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10.5" cy="7" r="1"/><circle cx="15" cy="7.5" r="1"/>',
    "lang": '<path d="M4 5h9M8.5 3v2m3 0c-1 4-4 7-7.5 8.5m2.5-5c1.4 2 3.3 3.7 5.5 4.5M13 21l4-10 4 10m-6.5-3.5h5"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "wand": '<path d="m4 20 11-11m2-5 .8 2.2L20 7l-2.2.8L17 10l-.8-2.2L14 7l2.2-.8zM5 4l.5 1.5L7 6l-1.5.5L5 8l-.5-1.5L3 6l1.5-.5z"/>',
    "bug": '<rect x="7" y="7" width="10" height="13" rx="5"/><path d="M9 7a3 3 0 0 1 6 0M3 13h4m10 0h4M4 8l3 2m13-2-3 2M4 19l3-2m13 2-3-2"/>',
    "bulb": '<path d="M9 18h6m-5 3h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3Z"/>',
    "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "windows": '<path d="M3 5.5 10.5 4.5v7H3zM12 4.3 21 3v8.5h-9zM3 12.5h7.5v7L3 18.5zM12 12.5h9V21l-9-1.3z"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "arrow": '<path d="M4 12h15m0 0-6-6m6 6-6 6"/>',
    "plug": '<path d="M9 3v5m6-5v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m5 0h5"/>',
}


def icon(name: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    fill = (' fill="currentColor" stroke="none"' if name == "windows"
            else ' fill="none" stroke="currentColor"')
    return (f'<svg{c} viewBox="0 0 24 24" aria-hidden="true" focusable="false"{fill} stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


# ===================================================================== texts


def load_texts() -> dict[str, dict]:
    texts = {}
    for code in CODES:
        p = HERE / "i18n" / f"{code}.json"
        texts[code] = json.loads(p.read_text(encoding="utf-8"))
    return texts


def check_texts(texts: dict[str, dict]) -> list[str]:
    """Every language has every English key (same type, same list lengths, same {placeholders})."""
    problems = []

    def walk(ref, other, path, code):
        if isinstance(ref, dict):
            if not isinstance(other, dict):
                problems.append(f"{code}: {path} should be an object")
                return
            for k, v in ref.items():
                if k not in other:
                    problems.append(f"{code}: missing {path}{k}")
                else:
                    walk(v, other[k], f"{path}{k}.", code)
            for k in other:
                if k not in ref:
                    problems.append(f"{code}: extra key {path}{k}")
        elif isinstance(ref, list):
            if not isinstance(other, list) or len(other) != len(ref):
                problems.append(f"{code}: {path} should be a list of {len(ref)}")
                return
            for i, (a, b) in enumerate(zip(ref, other)):
                walk(a, b, f"{path}{i}.", code)
        else:
            if not isinstance(other, str) or not other.strip():
                problems.append(f"{code}: {path} is empty")
                return
            want = sorted(set(re.findall(r"\{[a-z_]+\}", ref)))
            have = sorted(set(re.findall(r"\{[a-z_]+\}", other)))
            if want != have:
                problems.append(f"{code}: {path} placeholders {have} != {want}")

    for code in CODES[1:]:
        walk(texts["en"], texts[code], "", code)
    return problems


# ===================================================================== helpers


def page_path(code: str, page: str) -> str:
    """Path from the site root."""
    return (f"{page}.html" if code == "en" else f"{code}/{page}.html").replace("index.html", "") or ""


def url(code: str, page: str) -> str:
    return BASE + page_path(code, page)


def rel(code: str, target_code: str, page: str) -> str:
    """A link from a page of `code` to `page` of `target_code` (relative, works on any host)."""
    up = "" if code == "en" else "../"
    p = page_path(target_code, page)
    return up + (p or "./") if p else (up or "./")


def fill(s: str, ctx: dict) -> str:
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), s)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def md_inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_block(md: str) -> str:
    """The small Markdown of CHANGELOG entries: lists, paragraphs, bold, code, links."""
    out, items, para = [], [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{md_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
        if para:
            out.append(f"<p>{md_inline(' '.join(para))}</p>")
            para.clear()

    for line in md.splitlines():
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if para:
                flush()
            items.append(m.group(1).strip())
        elif not line.strip():
            flush()
        elif items and line.startswith("  "):
            items[-1] += " " + line.strip()
        else:
            if items:
                flush()
            para.append(line.strip())
    flush()
    return "".join(out)


# ===================================================================== shell


def head(code: str, page: str, t: dict, title: str, desc: str, extra_ld: list[dict]) -> str:
    _, _, hl, og_loc, _ = next(x for x in LANGS if x[0] == code)
    root = "" if code == "en" else "../"
    alts = "".join(f'<link rel="alternate" hreflang="{x[2]}" href="{url(x[0], page)}">' for x in LANGS)
    alts += f'<link rel="alternate" hreflang="x-default" href="{url("en", page)}">'
    og_alt = "".join(f'<meta property="og:locale:alternate" content="{x[3]}">' for x in LANGS if x[0] != code)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False, separators=(",", ":"))}</script>'
                 for d in extra_ld)
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url(code, page)}">
{alts}
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0a1020" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f9fafc" media="(prefers-color-scheme: light)">
<link rel="icon" href="{root}favicon.ico" sizes="48x48">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preload" href="{root}fonts/archivo-latin-standard-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}site.css?v={VERSION}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SharkyClips">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url(code, page)}">
<meta property="og:image" content="{BASE}img/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(t['ui']['og_alt'])}">
<meta property="og:locale" content="{og_loc}">
{og_alt}
<meta name="twitter:card" content="summary_large_image">
<script>try{{var s=localStorage.getItem("sc-theme");if(s==="light"||s==="dark")document.documentElement.dataset.theme=s}}catch(e){{}}</script>
{ld}
</head>"""


CUR_PAGE = ' aria-current="page"'  # (no backslashes inside f-strings: Python 3.11 can't read them)
CUR_TRUE = ' aria-current="true"'


def header(code: str, page: str, t: dict) -> str:
    root = "" if code == "en" else "../"
    links = "".join(
        f'<a href="{rel(code, code, p)}"{CUR_PAGE if p == page else ""}>{esc(t["nav"][p])}</a>'
        for p in NAV)
    cur_name = next(x[1] for x in LANGS if x[0] == code)
    langs = "".join(
        f'<li><a href="{rel(code, x[0], page)}" hreflang="{x[2]}" lang="{x[2]}" data-setlang="{x[0]}"'
        f'{CUR_TRUE if x[0] == code else ""}>{esc(x[1])}</a></li>' for x in LANGS)
    return f"""<a class="skip" href="#main">{esc(t['ui']['skip'])}</a>
<aside class="langhint" id="langhint" aria-label="{esc(t['ui']['lang_label'])}" hidden><div class="wrap"><span id="langhint-text"></span><a id="langhint-go" href="#"></a><button type="button" class="iconbtn" id="langhint-x"></button></div></aside>
<header class="top">
  <div class="wrap">
    <a class="brand" href="{rel(code, code, 'index')}">
      <img class="logo-dark" src="{root}img/logo-dark.svg" width="32" height="32" alt="">
      <img class="logo-light" src="{root}img/logo-light.svg" width="32" height="32" alt="">
      SharkyClips
    </a>
    <nav class="links" aria-label="{esc(t['ui']['nav_label'])}">{links}</nav>
    <div class="tools">
      <details class="lang">
        <summary>{icon('globe')}<span>{esc(code.upper())}</span><span class="vh"> - {esc(t['ui']['lang_label'])}: {esc(cur_name)}</span></summary>
        <ul>{langs}</ul>
      </details>
      <button type="button" class="iconbtn" id="theme" aria-label="{esc(t['ui']['theme_toggle'])}" title="{esc(t['ui']['theme_toggle'])}">{icon('sun', 'theme-light-icon')}{icon('moon', 'theme-dark-icon')}</button>
    </div>
  </div>
</header>"""


def footer(code: str, t: dict) -> str:
    f = t["footer"]
    return f"""<footer>
  <div class="wrap">
    <span>SharkyClips {esc(VERSION)}<span class="sep" aria-hidden="true"></span>{esc(f['license'])}</span>
    <nav aria-label="{esc(f['label'])}">
      <a href="{rel(code, code, 'privacy')}">{esc(f['privacy'])}</a>
      <a href="{rel(code, code, 'terms')}">{esc(f['terms'])}</a>
      <a href="{rel(code, code, 'contact')}">{esc(f['feedback'])}</a>
      <a href="{GH}">{esc(f['source'])}</a>
    </nav>
  </div>
</footer>"""


def script(code: str, page: str, texts: dict) -> str:
    hints = {c: {"t": texts[c]["ui"]["langhint"], "go": texts[c]["ui"]["langhint_go"], "x": texts[c]["ui"]["close"],
                 "h": rel(code, c, page)} for c in CODES}
    js = """(function(){var d=document.documentElement,b=document.getElementById("theme");
function cur(){return d.dataset.theme||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark")}
b.addEventListener("click",function(){var n=cur()==="light"?"dark":"light";d.dataset.theme=n;try{localStorage.setItem("sc-theme",n)}catch(e){}});
var l=document.querySelector(".lang");document.addEventListener("click",function(e){if(l.open&&!l.contains(e.target))l.open=false});
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&l.open){l.open=false;l.querySelector("summary").focus()}});
var v=document.getElementById("demo");if(v&&matchMedia("(prefers-reduced-motion: reduce)").matches){v.removeAttribute("autoplay");v.pause()}
function yt(){var y=document.getElementById("youtube-details");if(y&&/^#youtube/.test(location.hash))y.open=true}yt();addEventListener("hashchange",yt);
document.querySelectorAll("[data-setlang]").forEach(function(a){a.addEventListener("click",function(){try{localStorage.setItem("sc-lang",a.dataset.setlang)}catch(e){}})});
var H=%s,me="%s",pick=null;try{if(localStorage.getItem("sc-lang"))return}catch(e){return}
(navigator.languages||[navigator.language||""]).some(function(x){var c=String(x).slice(0,2).toLowerCase();if(H[c]){pick=c;return true}return false});
if(!pick||pick===me)return;var h=H[pick],bar=document.getElementById("langhint"),go=document.getElementById("langhint-go"),x=document.getElementById("langhint-x");
document.getElementById("langhint-text").textContent=h.t;go.textContent=h.go;go.href=h.h;go.lang=pick;bar.lang=pick;x.textContent=h.x;
go.addEventListener("click",function(){try{localStorage.setItem("sc-lang",pick)}catch(e){}});
x.addEventListener("click",function(){bar.hidden=true;try{localStorage.setItem("sc-lang",me)}catch(e){}});bar.hidden=false})();"""
    return "<script>" + js % (json.dumps(hints, ensure_ascii=False, separators=(",", ":")), code) + "</script>"


def document(code: str, page: str, texts: dict, title: str, desc: str, body: str, ld: list[dict] | None = None) -> str:
    t = texts[code]
    _, _, hl, _, direction = next(x for x in LANGS if x[0] == code)
    return (f'<!doctype html>\n<html lang="{hl}" dir="{direction}">\n'
            + head(code, page, t, title, desc, ld or [])
            + "\n<body>\n" + header(code, page, t) + f'\n<main id="main">\n{body}\n</main>\n'
            + footer(code, t) + "\n" + script(code, page, texts) + "\n</body>\n</html>\n")


# ===================================================================== pieces


def ctx_for(code: str) -> dict:
    return {"version": VERSION, "size": SETUP_MB, "releases": RELEASES, "gh": GH, "setup": SETUP_URL,
            "issues": f"{GH}/issues", "bug": bug_url("website"), "idea": idea_url(),
            "security": f"{GH}/security/advisories/new", "site_issues": "https://github.com/utkualsir/sharkyclips-site/issues",
            "privacy": rel(code, code, "privacy"), "terms": rel(code, code, "terms"), "faq": rel(code, code, "faq"),
            "download": rel(code, code, "download"), "features": rel(code, code, "features"),
            "contact": rel(code, code, "contact"), "updates": rel(code, code, "updates"),
            "own_google": f"{GH}/blob/main/docs/youtube-own-project.md"}


def bug_url(source: str) -> str:
    from urllib.parse import urlencode

    return f"{GH}/issues/new?" + urlencode({"template": "bug_report.yml", "source": source})


def idea_url() -> str:
    return f"{GH}/issues/new?template=feature_request.yml&source=website"


def download_button(code: str, t: dict, big: bool = True) -> str:
    c = t["common"]
    sub = fill(c["download_sub"], ctx_for(code))
    return (f'<a class="btn primary{" big" if big else ""}" href="{SETUP_URL}">{icon("windows")}'
            f'<span class="t">{esc(c["download_btn"])}<small>{esc(sub)}</small></span></a>')


def picture(code: str, name: str, alt: str, w: int, h: int, eager: bool = False, sizes: str = "(min-width: 980px) 560px, 100vw") -> str:
    root = "" if code == "en" else "../"
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return (f'<img src="{root}img/shots/{name}-1280.webp" srcset="{root}img/shots/{name}-640.webp 640w, '
            f'{root}img/shots/{name}-1280.webp 1280w" sizes="{sizes}" width="{w}" height="{h}" alt="{esc(alt)}" {load}>')


SHOT_SIZE = (1280, 800)  # every screenshot is captured at 1440 x 900 (16:10) and stored at 1280 / 640 wide


def ld_app(code: str, t: dict) -> dict:
    return {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "SharkyClips",
            "description": strip_tags(t["home"]["desc"]), "url": url(code, "index"),
            "applicationCategory": "MultimediaApplication", "applicationSubCategory": "Video editing",
            "operatingSystem": "Windows 10, Windows 11", "softwareVersion": VERSION, "downloadUrl": SETUP_URL,
            "fileSize": f"{SETUP_MB} MB", "image": BASE + "img/og.png", "screenshot": BASE + "img/shots/easy-project-1280.webp",
            "license": "https://opensource.org/license/mit", "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "inLanguage": [x[2] for x in LANGS], "author": {"@type": "Person", "name": "utkualsir", "url": "https://github.com/utkualsir"}}


# ===================================================================== pages


def trust_badges(code: str, t: dict) -> str:
    """GitHub stars + downloads, drawn from stats.json at build time (no badge service)."""
    st = load_json(STATS_FILE)
    if not st.get("stars") and not st.get("downloads"):
        return ""
    c = t["common"]
    out = []
    if st.get("stars"):
        out.append(f'<a class="badge" href="{GH}/stargazers">{icon("star")}<span>{esc(c["stars"])}</span>'
                   f'<b>{compact_number(st["stars"], code)}</b></a>')
    if st.get("downloads"):
        out.append(f'<a class="badge" href="{RELEASES}">{icon("download")}<span>{esc(c["downloads"])}</span>'
                   f'<b>{compact_number(st["downloads"], code)}</b></a>')
    return f'<div class="badges">{"".join(out)}</div>'


def demo_video(code: str, t: dict) -> str:
    """The demo: autoplays muted and loops (paused for reduced motion), captions in every language."""
    root = "" if code == "en" else "../"
    h = t["home"]
    tracks = "".join(
        f'<track kind="captions" srclang="{x[2]}" label="{esc(x[1])}" src="{root}img/demo-{x[0]}.vtt"'
        f'{" default" if x[0] == code else ""}>' for x in LANGS)
    return (f'<figure class="shot demo"><video id="demo" autoplay muted loop playsinline controls preload="auto" '
            f'width="{DEMO_SIZE[0]}" height="{DEMO_SIZE[1]}" poster="{root}img/demo-poster.webp" '
            f'aria-label="{esc(h["demo_alt"])}"><source src="{root}img/demo.mp4" type="video/mp4">{tracks}</video>'
            f'<figcaption>{esc(h["demo_cap"])}</figcaption></figure>')


def vtt(code: str, texts: dict) -> str:
    def ts(s: float) -> str:
        return f"{int(s // 60):02d}:{s % 60:06.3f}"

    caps = texts[code]["home"]["captions"]
    return "WEBVTT\n\n" + "\n".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{strip_tags(c)}\n"
                                     for i, ((a, b), c) in enumerate(zip(DEMO_CUES, caps)))


def results(code: str, t: dict) -> str:
    """Before -> after pairs: a frame of the long stream and the same moment in the finished clip."""
    root = "" if code == "en" else "../"
    r = t["results"]
    items = []
    for i, it in enumerate(r["items"][:RESULTS], 1):
        items.append(
            f'<li class="ba"><figure><div class="ba-pair">'
            f'<div class="ba-before"><img src="{root}img/results/{i}-before.webp" width="640" height="360" '
            f'alt="{esc(fill(r["before_alt"], {"time": it["time"]}))}" loading="lazy" decoding="async">'
            f'<span class="tag">{esc(r["before"])} · {esc(it["time"])}</span></div>'
            f'<span class="ba-arrow" aria-hidden="true">{icon("arrow")}</span>'
            f'<div class="ba-after"><img src="{root}img/results/{i}-after.webp" width="270" height="480" '
            f'alt="{esc(fill(r["after_alt"], {"title": it["title"]}))}" loading="lazy" decoding="async">'
            f'<span class="tag">{esc(r["after"])}</span></div></div>'
            f'<figcaption><b>{esc(it["title"])}</b><span>{esc(it["why"])}</span></figcaption></figure></li>')
    return f"""<section id="results" aria-labelledby="res-h">
  <h2 id="res-h">{esc(r['h'])}</h2>
  <p class="lead">{esc(r['lead'])}</p>
  <ul class="results">{''.join(items)}</ul>
  <p class="muted small">{esc(r['note'])}</p>
</section>"""


def fmt_date(iso: str, t: dict) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return fill(t["common"]["date"], {"d": d, "m": t["common"]["months"][m - 1], "y": y})


def short_url(u: str) -> str:
    return re.sub(r"^https://(www[.])?", "", u).rstrip("/")


def compare(code: str, t: dict) -> str:
    k = t["compare"]
    cols = ["SharkyClips", "Eklipse", "OpusClip", "StreamLadder"]
    head_ = "".join(f'<th scope="col">{esc(x)}</th>' for x in cols)
    rows = "".join(
        f'<tr><th scope="row">{esc(r[0])}</th>' + "".join(f"<td>{esc(x)}</td>" for x in r[1:]) + "</tr>"
        for r in k["rows"])
    src = "".join(f'<li><a href="{u}">{esc(short_url(u))}</a></li>' for u in COMPARE_SOURCES)
    return f"""<section id="compare" aria-labelledby="cmp-h">
  <h2 id="cmp-h">{esc(k['h'])}</h2>
  <p class="lead">{esc(fill(k['lead'], {'date': fmt_date(COMPARE_CHECKED, t)}))}</p>
  <div class="tablewrap compare" tabindex="0" role="region" aria-labelledby="cmp-h"><table>
    <thead><tr><th scope="col"><span class="vh">{esc(k['corner'])}</span></th>{head_}</tr></thead><tbody>{rows}</tbody></table></div>
  <p class="muted small">{esc(k['note'])}</p>
  <details class="more small"><summary>{esc(fill(k['sources'], {'n': len(COMPARE_SOURCES)}))}</summary><ul class="sources">{src}</ul></details>
</section>"""


def page_index(code: str, texts: dict) -> str:
    t = texts[code]
    h = t["home"]
    c = ctx_for(code)
    promise = "".join(f"<li>{icon('check')}{esc(x)}</li>" for x in h["promise"])
    steps = "".join(f"<li><h3>{esc(s['h'])}</h3><p>{fill(s['p'], c)}</p></li>" for s in h["steps"])
    cards = "".join(
        f'<div class="card"><span class="ico">{icon(k["icon"])}</span><h3>{esc(k["h"])}'
        f'{"<span class=new>" + esc(t["common"]["new"]) + "</span>" if k.get("new") == "1" else ""}</h3><p>{fill(k["p"], c)}</p></div>'
        for k in h["cards"])
    gallery = "".join(
        f'<figure class="shot">{picture(code, g["img"], g["alt"], *SHOT_SIZE, sizes="(min-width: 1080px) 340px, (min-width: 700px) 50vw, 100vw")}'
        f'<figcaption>{esc(g["cap"])}</figcaption></figure>' for g in h["gallery"])
    sha_line = (f'<a class="sha-link" href="{c["download"]}#checksum">{icon("shield")}{esc(t["common"]["sha_link"])}</a>'
                if sha_for("setup") else "")
    body = f"""<div class="wrap">
<section class="hero">
  <div class="hero-text">
    <p class="kick"><b>{icon('check')}{esc(h['kick'])}</b><span>{esc(h['kick_more'])}</span></p>
    <h1>{esc(h['h1'])}</h1>
    <p class="lead">{fill(h['lead'], c)}</p>
    <ul class="promise" aria-label="{esc(h['promise_label'])}">{promise}</ul>
    <div class="cta">{download_button(code, t)}<a class="btn" href="{c['features']}">{esc(h['see_features'])}</a></div>
    <div class="trust">{trust_badges(code, t)}{sha_line}</div>
  </div>
  {demo_video(code, t)}
</section>
{results(code, t)}
<section id="how" aria-labelledby="how-h">
  <h2 id="how-h">{esc(h['how_h'])}</h2>
  <p class="lead">{fill(h['how_lead'], c)}</p>
  <ol class="steps">{steps}</ol>
  <div class="gallery">{gallery}</div>
</section>
<section aria-labelledby="feat-h">
  <h2 id="feat-h">{esc(h['feat_h'])}</h2>
  <div class="grid">{cards}</div>
  <p><a class="btn" href="{c['features']}">{esc(h['all_features'])}</a></p>
</section>
{compare(code, t)}
<section id="youtube" aria-labelledby="yt-h">
  <h2 id="yt-h">{esc(h['yt_h'])}</h2>
  <p>{fill(h['yt_short'], c)}</p>
  <details class="more" id="youtube-details"><summary>{esc(h['yt_show'])}</summary><div class="more-body">{fill(h['yt_html'], c)}</div></details>
</section>
<section aria-labelledby="oss-h">
  <h2 id="oss-h">{esc(h['oss_h'])}</h2>
  <p>{fill(h['oss_p'], c)}</p>
  <div class="cta">{download_button(code, t, big=False)}<a class="btn" href="{GH}">{esc(t['footer']['source'])}</a></div>
</section>
</div>"""
    ld = [ld_app(code, t), {"@context": "https://schema.org", "@type": "WebSite", "name": "SharkyClips", "url": BASE,
                            "inLanguage": next(x[2] for x in LANGS if x[0] == code)},
          {"@context": "https://schema.org", "@type": "VideoObject", "name": h["demo_alt"], "description": h["demo_cap"],
           "thumbnailUrl": BASE + "img/demo-poster.webp", "contentUrl": BASE + "img/demo.mp4",
           "uploadDate": DEMO_DATE, "duration": f"PT{round(DEMO_CUES[-1][1])}S"}]
    return document(code, "index", texts, h["title"], strip_tags(h["desc"]), body, ld)


def page_features(code: str, texts: dict) -> str:
    t = texts[code]
    f = t["features"]
    c = ctx_for(code)
    secs = []
    for i, s in enumerate(f["sections"]):
        items = "".join(f"<li>{fill(x, c)}</li>" for x in s["items"])
        badge = f'<span class="new">{esc(t["common"]["new"])}</span>' if s.get("new") == "1" else ""
        media = (f'<figure class="shot">{picture(code, s["img"], s["alt"], *SHOT_SIZE, eager=i == 0)}</figure>' if s.get("img")
                 else f'<div class="card"><span class="ico">{icon(s["icon"])}</span><p>{fill(s["aside"], c)}</p></div>')
        secs.append(f"""<div class="feature{' flip' if i % 2 else ''}" id="{s['id']}">
  <div><p class="eyebrow">{esc(s['eyebrow'])}</p><h2>{esc(s['h'])}{badge}</h2><p class="muted">{fill(s['p'], c)}</p><ul>{items}</ul></div>
  {media}
</div>""")
    body = f"""<div class="wrap">
<div class="page-head"><h1>{esc(f['h1'])}</h1><p class="lead">{fill(f['lead'], c)}</p><div class="cta">{download_button(code, t)}</div></div>
<section class="features-list">{''.join(secs)}</section>
</div>"""
    return document(code, "features", texts, f["title"], strip_tags(f["desc"]), body)


def fmt_duration(seconds: float, t: dict) -> str:
    """About 7 min / about 1 h 25 min, rounded the way people read times (from benchmarks.json)."""
    m = seconds / 60
    m = max(1, round(m)) if m < 15 else 5 * round(m / 5)
    c = t["common"]
    return fill(c["dur_min"], {"m": m}) if m < 60 else fill(c["dur_h"] if m % 60 else c["dur_h0"], {"h": m // 60, "m": m % 60})


def speed_table(code: str, t: dict) -> str:
    b = load_json(BENCH_FILE)
    runs = b.get("runs", {})
    if not all(k in runs for k in ("gpu60", "gpu180", "light60", "light180")):
        return ""
    d = t["download"]
    rows = "".join(
        f'<tr><th scope="row">{esc(label)}</th><td>{esc(fmt_duration(runs["gpu" + n], t))}</td>'
        f'<td>{esc(fmt_duration(runs["light" + n], t))}</td></tr>'
        for label, n in ((d["time_rows"][0], "60"), (d["time_rows"][1], "180")))
    ctx = {"cpu": b["machine"]["cpu"], "gpu": b["machine"]["gpu"], "ram": b["machine"]["ram_gb"],
           "date": fmt_date(b["checked"], t), "clips": b.get("clips", 6)}
    return f"""<section id="speed" aria-labelledby="time-h"><h2 id="time-h">{esc(d['time_h'])}</h2><p class="muted">{esc(fill(d['time_p'], ctx))}</p>
  <div class="tablewrap"><table><thead><tr><th scope="col"><span class="vh">{esc(d['time_cols'][0])}</span></th><th scope="col">{esc(d['time_cols'][1])}</th><th scope="col">{esc(d['time_cols'][2])}</th></tr></thead><tbody>{rows}</tbody></table></div>
  <ul class="notes muted small">{''.join(f'<li>{esc(fill(x, ctx))}</li>' for x in d['time_notes'])}</ul></section>"""


def checksum_box(t: dict, kind: str, file: str, sha_url: str, cmd: str, how: str) -> str:
    h = sha_for(kind)
    if not h:
        return ""
    d = t["download"]
    return (f'<div class="checksum"><p class="sum-h">{icon("shield")}<span>{esc(fill(d["sha_label"], {"file": file}))}</span></p>'
            f'<code class="hash" translate="no">{h}</code>'
            f'<p class="small muted">{fill(d[how], {"cmd": "<code>" + esc(cmd) + "</code>", "sha_url": sha_url})}</p></div>')


def page_download(code: str, texts: dict) -> str:
    t = texts[code]
    d = t["download"]
    c = ctx_for(code)
    root = "" if code == "en" else "../"
    steps = "".join(f"<li><h3>{esc(s['h'])}</h3><p>{fill(s['p'], c)}</p></li>" for s in d["steps"])
    rows = "".join(f"<tr><th scope=\"row\">{esc(r[0])}</th><td>{fill(r[1], c)}</td><td>{fill(r[2], c)}</td></tr>"
                   for r in d["req_rows"])
    smart = "".join(f"<li>{fill(x, c)}</li>" for x in d["smart_steps"])
    setup_box = checksum_box(t, "setup", SETUP_NAME, f"{SETUP_URL}.sha256",
                             f"Get-FileHash $HOME\\Downloads\\{SETUP_NAME}", "sha_how_win")
    mac_box = checksum_box(t, "install_sh", "install.sh", f"{INSTALL_SH_URL}.sha256", "shasum -a 256 ~/Downloads/install.sh",
                           "sha_how_mac")
    mac_steps = "".join(f"<li>{fill(x, c)}</li>" for x in d["mac_steps"])
    body = f"""<div class="wrap">
<div class="page-head"><h1>{esc(d['h1'])}</h1><p class="lead">{fill(d['lead'], c)}</p>
  <div class="cta">{download_button(code, t)}<a class="btn" href="{RELEASES}">{esc(d['all_releases'])}</a></div>
  <ul class="facts">{''.join(f'<li>{esc(fill(x, c))}</li>' for x in d['facts'])}</ul>
  <div class="trust">{trust_badges(code, t)}</div>
  <div id="checksum">{setup_box}</div></div>
<section aria-labelledby="st-h"><h2 id="st-h">{esc(d['steps_h'])}</h2><ol class="steps">{steps}</ol></section>
<section id="requirements" aria-labelledby="req-h"><h2 id="req-h">{esc(d['req_h'])}</h2><p class="muted">{fill(d['req_p'], c)}</p>
  <div class="tablewrap"><table><thead><tr><th scope="col"><span class="vh">{esc(d['req_cols'][0])}</span></th><th scope="col">{esc(d['req_cols'][1])}</th><th scope="col">{esc(d['req_cols'][2])}</th></tr></thead><tbody>{rows}</tbody></table></div></section>
{speed_table(code, t)}
<section id="smartscreen" aria-labelledby="ss-h"><div class="feature">
  <div><h2 id="ss-h">{esc(d['smart_h'])}</h2><p>{fill(d['smart_p'], c)}</p><ol class="howto">{smart}</ol><p class="muted small">{fill(d['smart_note'], c)}</p></div>
  <figure class="shot"><img src="{root}img/smartscreen.webp" width="1280" height="499" alt="{esc(d['smart_alt'])}" loading="lazy" decoding="async"><figcaption>{esc(d['smart_cap'])}</figcaption></figure>
</div></section>
<section id="mac" aria-labelledby="mac-h"><h2 id="mac-h">{esc(d['mac_h'])}</h2><p>{fill(d['mac_p'], c)}</p>
  <ol class="howto">{mac_steps}</ol>
  <p><a class="btn" href="{INSTALL_SH_URL}">{icon('terminal')}{esc(d['mac_btn'])}</a></p>{mac_box}
  <p class="muted small">{fill(d['linux_p'], c)}</p></section>
<section aria-labelledby="more-h"><h2 id="more-h">{esc(d['more_h'])}</h2><div class="grid">
  {''.join(f'<div class="card"><h3>{esc(x["h"])}</h3><p>{fill(x["p"], c)}</p></div>' for x in d['more'])}
</div></section>
</div>"""
    return document(code, "download", texts, d["title"], strip_tags(d["desc"]), body, [ld_app(code, t)])


def page_faq(code: str, texts: dict) -> str:
    t = texts[code]
    f = t["faq"]
    c = ctx_for(code)
    items = "".join(f'<details id="{q["id"]}"><summary>{esc(q["q"])}</summary><div class="a">{fill(q["a"], c)}</div></details>'
                    for q in f["items"])
    ld = {"@context": "https://schema.org", "@type": "FAQPage",
          "mainEntity": [{"@type": "Question", "name": q["q"],
                          "acceptedAnswer": {"@type": "Answer", "text": strip_tags(fill(q["a"], c))}} for q in f["items"]]}
    body = f"""<div class="wrap narrow">
<div class="page-head"><h1>{esc(f['h1'])}</h1><p class="lead">{fill(f['lead'], c)}</p></div>
<section class="faq">{items}</section>
<section><h2>{esc(f['more_h'])}</h2><p>{fill(f['more_p'], c)}</p></section>
</div>"""
    return document(code, "faq", texts, f["title"], strip_tags(f["desc"]), body, [ld])


def page_updates(code: str, texts: dict) -> str:
    from sharkyclips import welcome

    t = texts[code]
    u = t["updates"]
    c = ctx_for(code)
    hist = welcome.release_history(code)[:UPDATES_SHOWN]
    rels = []
    for i, r in enumerate(hist):
        hl = next(x[2] for x in LANGS if x[0] == r["summary_lang"])
        dl = next(x[2] for x in LANGS if x[0] == r["details_lang"])
        groups = "".join(f"<h3>{esc(u['groups'].get(g['kind'], u['groups']['other']))}</h3>{md_block(g['markdown'])}"
                         for g in r["groups"])
        lang_s = f' lang="{hl}"' if r["summary_lang"] != code else ""
        lang_d = f' lang="{dl}"' if r["details_lang"] != code else ""
        details = (f'<div{lang_d}>{groups}</div>' if i < 2 else
                   f'<details><summary>{esc(u["show"])}</summary><div{lang_d}>{groups}</div></details>')
        rels.append(f'<article class="rel" id="v{esc(r["version"])}"><h2>{esc(u["version"])} {esc(r["version"])}'
                    f'<time datetime="{esc(r["date"] or "")}">{esc(r["date"] or "")}</time></h2>'
                    f'<p class="sum"{lang_s}>{md_inline(r["summary"])}</p>{details}</article>')
    body = f"""<div class="wrap narrow">
<div class="page-head"><h1>{esc(u['h1'])}</h1><p class="lead">{fill(u['lead'], c)}</p></div>
<section>{''.join(rels)}<p class="muted">{fill(u['older'], c)}</p></section>
</div>"""
    return document(code, "updates", texts, u["title"], strip_tags(u["desc"]), body)


def page_contact(code: str, texts: dict) -> str:
    t = texts[code]
    k = t["contact"]
    c = ctx_for(code)
    cards = "".join(
        f'<div class="card"><span class="ico">{icon(x["icon"])}</span><h2 class="h3">{esc(x["h"])}</h2><p>{fill(x["p"], c)}</p>'
        f'<p style="margin-top:14px"><a class="btn" href="{fill(x["href"], c)}">{esc(x["btn"])}</a></p></div>'
        for x in k["cards"])
    body = f"""<div class="wrap">
<div class="page-head"><h1>{esc(k['h1'])}</h1><p class="lead">{fill(k['lead'], c)}</p></div>
<section><div class="grid">{cards}</div>
<div class="callout"><p>{fill(k['app_note'], c)}</p><p>{fill(k['privacy_note'], c)}</p></div></section>
</div>"""
    return document(code, "contact", texts, k["title"], strip_tags(k["desc"]), body)


def page_legal(code: str, texts: dict, which: str) -> str:
    t = texts[code]
    k = t[which]
    c = ctx_for(code)
    english = (HERE / "legal" / f"{which}.html").read_text(encoding="utf-8")
    english = english.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
    english = english.replace("{privacy}", c["privacy"]).replace("{home}", rel(code, code, "index")).replace(
        "{contact}", c["contact"])
    if code == "en":
        body = f'<div class="wrap narrow doc">\n{english}\n</div>'
    else:
        # the English text's h1 becomes an h2 under the translated page title
        english = english.replace("<h1>", '<h2 style="font-size:30px">', 1).replace("</h1>", "</h2>", 1)
        body = (f'<div class="wrap narrow doc"><div class="page-head" style="padding-bottom:0"><h1>{esc(k["h1"])}</h1></div>'
                f'<div class="callout"><h2 style="margin-top:0;font-size:20px">{esc(k["summary_h"])}</h2>{fill(k["summary"], c)}'
                f'<p class="small muted">{fill(t["common"]["english_binding"], c)}</p></div>'
                f'<div lang="en">{english}</div></div>')
    return document(code, which, texts, k["title"], strip_tags(k["desc"]), body)


def page_404(texts: dict) -> str:
    t = texts["en"]
    k = t["notfound"]
    langs = " ".join(f'<a href="{x[0] + "/" if x[0] != "en" else "./"}" lang="{x[2]}">{esc(texts[x[0]]["notfound"]["back"])}</a><span class="sep" aria-hidden="true"></span>'
                     for x in LANGS)
    body = f"""<div class="wrap narrow"><div class="page-head"><h1>{esc(k['h1'])}</h1><p class="lead">{esc(k['p'])}</p>
<p>{langs}</p></div></div>"""
    doc = document("en", "index", texts, k["title"], k["p"], body)
    # GitHub Pages serves 404.html for any missing path, so its links must be absolute
    doc = re.sub(r'(href|src|srcset)="(?!https?:|#|data:)([^"]*)"', lambda m: f'{m.group(1)}="{_abs(m.group(2))}"', doc)
    doc = doc.replace('<link rel="canonical" href="' + BASE + '">', "")
    return doc.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)


def _abs(v: str) -> str:
    parts = [p.strip() for p in v.split(",")]
    return ", ".join(BASE + p.lstrip("./") if p and not p.startswith("http") else p for p in parts)


# ===================================================================== extras


def sitemap() -> str:
    from datetime import date

    today = date.today().isoformat()
    rows = []
    for page in PAGES:
        for x in LANGS:
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{y[2]}" href="{url(y[0], page)}"/>' for y in LANGS)
            alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{url("en", page)}"/>'
            prio = "1.0" if page == "index" else "0.8" if page in ("download", "features") else "0.5"
            rows.append(f"<url><loc>{url(x[0], page)}</loc><lastmod>{today}</lastmod><priority>{prio}</priority>{alts}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(rows) + "\n</urlset>\n")


def build_css() -> str:
    css = (HERE / "site.css").read_text(encoding="utf-8")
    css = css.replace("@ROOT@", "").replace("@LIGHT@", LIGHT)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)  # (":" keeps its space: "a :is()" selectors need it)
    css = css.replace(";}", "}")
    return css.strip() + "\n"


def convert_shots(src: Path) -> None:
    """App screenshots (1440 x 900 PNG) -> img/shots/<name>-1280.webp and -640.webp."""
    from PIL import Image

    dest = OUT / "img" / "shots"
    dest.mkdir(parents=True, exist_ok=True)
    for png in sorted(src.glob("*.png")):
        im = Image.open(png).convert("RGB")
        for w in (1280, 640):
            h = round(im.height * w / im.width)
            im.resize((w, h), Image.Resampling.LANCZOS).save(dest / f"{png.stem}-{w}.webp", "WEBP", quality=80, method=6)
        print("shot", png.stem)


def make_og() -> None:
    """1200 x 630 Open Graph image: the logo, the name, the promise, a screenshot (one for every language:
    no text that needs translating beyond the product name and a short English line)."""
    import importlib.util

    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    spec = importlib.util.spec_from_file_location("make_icons", REPO / "installer" / "make_icons.py")
    mi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mi)
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), mi._hex(mi.NAVY))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([700, -300, 1500, 400], fill=90)
    img.paste((34, 58, 110), (0, 0), glow.filter(ImageFilter.GaussianBlur(120)))
    shot = OUT / "img" / "shots" / "easy-project-1280.webp"
    if shot.is_file():
        s = Image.open(shot).convert("RGB")
        s = s.resize((760, round(s.height * 760 / s.width)), Image.Resampling.LANCZOS)
        mask = Image.new("L", s.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, s.width - 1, s.height - 1], radius=16, fill=255)
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).rounded_rectangle([560, 150, 560 + s.width, 150 + s.height], radius=16, fill=150)
        img.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(24)))
        img.paste(s, (540, 130), mask)
        ImageDraw.Draw(img).rounded_rectangle([540, 130, 540 + s.width - 1, 130 + s.height - 1], radius=16,
                                              outline=mi._hex(mi.EDGE_DARK), width=2)
    logo = mi.render(120, "dark")
    img.paste(logo, (64, 92), logo)
    font = REPO / "backend" / "sharkyclips" / "assets" / "fonts" / "ArchivoSC-ExtraBold.ttf"
    d = ImageDraw.Draw(img)
    d.text((64, 250), "SharkyClips", font=ImageFont.truetype(str(font), 66), fill="#ffffff")
    small = ImageFont.truetype(str(font), 30)
    for i, line in enumerate(("Stream highlights", "to Shorts, TikTok", "and Reels.")):
        d.text((64, 350 + i * 42), line, font=small, fill="#c9d6f2")
    d.rectangle([64, 500, 164, 506], fill=mi._hex(mi.GOLD))
    d.text((64, 530), "Free  ·  open source  ·  on your PC", font=ImageFont.truetype(str(font), 22), fill=mi._hex(mi.GOLD))
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    img.save(OUT / "img" / "og.png", optimize=True)
    print("og image written")


def main(argv: list[str]) -> int:
    texts = load_texts()
    problems = check_texts(texts)
    if problems:
        print("\n".join(problems[:60]))
        print(f"{len(problems)} translation problem(s)")
        return 1
    if "--shots" in argv:
        convert_shots(Path(argv[argv.index("--shots") + 1]))
    if "--og" in argv:
        make_og()
    if "--stats" in argv:
        fetch_stats()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "site.css").write_text(build_css(), encoding="utf-8", newline="\n")
    n = 0
    for code in CODES:
        folder = OUT if code == "en" else OUT / code
        folder.mkdir(parents=True, exist_ok=True)
        pages = {"index": page_index, "features": page_features, "download": page_download, "faq": page_faq,
                 "updates": page_updates, "contact": page_contact}
        for name, fn in pages.items():
            (folder / f"{name}.html").write_text(fn(code, texts), encoding="utf-8", newline="\n")
            n += 1
        for which in ("privacy", "terms"):
            (folder / f"{which}.html").write_text(page_legal(code, texts, which), encoding="utf-8", newline="\n")
            n += 1
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    for code in CODES:
        (OUT / "img" / f"demo-{code}.vtt").write_text(vtt(code, texts), encoding="utf-8", newline="\n")
    (OUT / "404.html").write_text(page_404(texts), encoding="utf-8", newline="\n")
    (OUT / "sitemap.xml").write_text(sitemap(), encoding="utf-8", newline="\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8", newline="\n")
    print(f"{n} pages written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
