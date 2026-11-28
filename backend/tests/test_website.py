"""1.2.74: the website (docs/sitegen -> docs/site) in 11 languages."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITEGEN = ROOT / "docs" / "sitegen"

# sentences of the privacy policy / home page that Google reviewed for the YouTube API (keep them)
GOOGLE_REVIEWED = [
    "adheres to the <a href=\"https://developers.google.com/terms/api-services-user-data-policy\">Google\n    API Services User Data Policy</a>, including the Limited Use requirements",
    "SharkyClips uses the <b>YouTube API Services</b>",
    "Any number that was not refreshed for <b>30 days</b> is deleted automatically.",
    "We do not receive, sell, rent or share YouTube data or any other data.",
]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("sitegen_build", SITEGEN / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("site")
    # the static files (fonts, images) are not copied: the HTML is what is checked here
    mod.OUT = out
    assert mod.main([]) == 0
    return mod, out


def test_every_language_has_every_text():
    spec = importlib.util.spec_from_file_location("sitegen_build2", SITEGEN / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    texts = mod.load_texts()
    assert sorted(texts) == sorted(["en", "tr", "es", "pt", "de", "fr", "hu", "ru", "ar", "zh", "ja"])
    assert mod.check_texts(texts) == []


def test_all_pages_are_written_with_alternates(site):
    mod, out = site
    pages = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html"))
    assert len(pages) == 11 * 8 + 1  # 8 pages per language + 404
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<loc>") == 88 and 'hreflang="x-default"' in sitemap
    assert "Sitemap: https://utkualsir.github.io/sharkyclips-site/sitemap.xml" in (out / "robots.txt").read_text(encoding="utf-8")
    home = (out / "index.html").read_text(encoding="utf-8")
    for lang in ("en", "tr", "pt-BR", "zh-Hans", "ar", "x-default"):
        assert f'hreflang="{lang}"' in home
    assert '<html lang="ar" dir="rtl">' in (out / "ar" / "index.html").read_text(encoding="utf-8")
    assert '"@type":"SoftwareApplication"' in home and '"@type":"FAQPage"' in (out / "faq.html").read_text(encoding="utf-8")


def test_privacy_and_terms_keep_the_reviewed_text_and_urls(site):
    mod, out = site
    privacy = (out / "privacy.html").read_text(encoding="utf-8")  # same URL Google knows
    for s in GOOGLE_REVIEWED:
        assert s in privacy or s in (out / "index.html").read_text(encoding="utf-8"), s[:60]
    assert (out / "terms.html").is_file()
    tr = (out / "tr" / "privacy.html").read_text(encoding="utf-8")
    assert '<div lang="en">' in tr and GOOGLE_REVIEWED[1] in tr  # the binding English text, below a summary
    home = (out / "index.html").read_text(encoding="utf-8")
    assert "How SharkyClips uses YouTube" in home and "yt-analytics.readonly" in home


def test_no_external_fonts_scripts_or_trackers(site):
    mod, out = site
    allowed = ("https://utkualsir.github.io/sharkyclips-site/",)  # canonical / og / alternate links
    for page in out.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        for tag, attr in (("script", "src"), ("link", "href"), ("img", "src"), ("source", "src"), ("iframe", "src")):
            for m in re.finditer(rf"<{tag}\b[^>]*\b{attr}=\"(https?://[^\"]+)\"", html):
                if tag == "link" and re.search(r'rel="(canonical|alternate)"', m.group(0)):
                    continue
                assert m.group(1).startswith(allowed), f"{page.name}: {m.group(0)[:120]}"
        assert "googletagmanager" not in html and "google-analytics" not in html and "fonts.googleapis" not in html
    css = (out / "site.css").read_text(encoding="utf-8")
    assert "http" not in css  # fonts come from the site itself


def test_feedback_links_prefill_the_issue_form(site):
    mod, out = site
    contact = (out / "contact.html").read_text(encoding="utf-8")
    assert "issues/new?template=bug_report.yml&source=website" in contact
    assert "template=feature_request.yml&source=website" in contact and "security/advisories/new" in contact
    assert "@gmail" not in contact  # no personal e-mail address on the site


def test_favicon_is_the_app_logo():
    spec = importlib.util.spec_from_file_location("make_icons", ROOT / "installer" / "make_icons.py")
    mi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mi)
    assert (ROOT / "docs" / "site" / "favicon.svg").read_text(encoding="utf-8") == mi.svg("dark")
    assert (ROOT / "frontend" / "public" / "favicon.svg").read_text(encoding="utf-8") == mi.svg("dark")
    assert mi.TILE_DARK.lower() in mi.svg("dark").lower() and "FFD23F" not in mi.svg("dark")  # Classic, not 1.2.65


# ---- phase D7: proof on the website (demo video, real results, comparison, requirements, download trust)


def test_hero_shows_kick_promise_and_the_demo_video_first(site):
    mod, out = site
    home = (out / "index.html").read_text(encoding="utf-8")
    hero = home[home.index('<section class="hero">'):home.index("</section>", home.index('<section class="hero">'))]
    assert "Works with Kick" in hero
    for s in ("100% free", "No watermark", "No limits", "Runs on your PC"):
        assert s in hero, s
    # the demo is part of the hero (above the fold), autoplays muted, has a poster and captions in every language
    video = re.search(r"<video\b[^>]*>", hero).group(0)
    for attr in ("autoplay", "muted", "loop", "playsinline", "controls", 'poster="img/demo-poster.webp"'):
        assert attr in video, attr
    assert hero.count('<track kind="captions"') == 11 and 'srclang="en" label="English" src="img/demo-en.vtt" default' in hero
    for code in mod.CODES:
        vtt = (out / "img" / f"demo-{code}.vtt").read_text(encoding="utf-8")
        assert vtt.startswith("WEBVTT") and vtt.count("-->") == len(mod.DEMO_CUES)
    assert mod.DEMO_CUES[-1][1] == 31.0  # the video's length (docs/phase-d7.md)
    # reduced motion pauses it
    assert "prefers-reduced-motion: reduce" in home


def test_real_results_gallery_has_before_and_after_pairs(site):
    mod, out = site
    home = (out / "index.html").read_text(encoding="utf-8")
    assert home.index('id="results"') < home.index('id="how"')  # right after the hero
    assert 4 <= home.count('class="ba"') <= 6
    for n in range(1, home.count('class="ba"') + 1):
        assert f"img/results/{n}-before.webp" in home and f"img/results/{n}-after.webp" in home
        assert (mod.REPO / "docs" / "site" / "img" / "results" / f"{n}-before.webp").is_file()
        assert (mod.REPO / "docs" / "site" / "img" / "results" / f"{n}-after.webp").is_file()
    texts = mod.load_texts()
    for code in mod.CODES:
        for it in texts[code]["results"]["items"]:
            assert it["title"] not in ("TITLE", "") and it["why"] not in ("WHY", ""), code


def test_comparison_table_is_dated_and_sourced(site):
    mod, out = site
    home = (out / "index.html").read_text(encoding="utf-8")
    table = home[home.index('id="compare"'):home.index("</section>", home.index('id="compare"'))]
    for name in ("SharkyClips", "Eklipse", "OpusClip", "StreamLadder"):
        assert f'<th scope="col">{name}</th>' in table
    assert "28 November 2026" in table and table.count("<tr>") == 1 + 9
    for row in ("Price", "Watermark", "Clip limits", "Kick", "Swear-word bleeping", "Languages", "Game-aware detection"):
        assert f'<th scope="row">{row}</th>' in table
    # official pages only
    for u in mod.COMPARE_SOURCES:
        assert u.startswith(("https://eklipse.gg/", "https://www.opus.pro/", "https://help.opus.pro/",
                             "https://streamladder.com/", "https://www.streamladder.com/")) and f'href="{u}"' in table


def test_youtube_section_stays_on_the_home_page_collapsed(site):
    mod, out = site
    home = (out / "index.html").read_text(encoding="utf-8")
    sec = home[home.index('<section id="youtube"'):home.index("</section>", home.index('<section id="youtube"'))]
    assert "How SharkyClips uses YouTube" in sec and "yt-analytics.readonly" in sec
    assert '<details class="more" id="youtube-details">' in sec and "<details class=\"more\" id=\"youtube-details\" open" not in sec
    assert "Your look" not in home and "Themes and colours" in home
    assert "Edge, Chrome, Opera and Brave" in home


def test_download_page_has_checksums_requirements_times_and_mac(site):
    mod, out = site
    dl = (out / "download.html").read_text(encoding="utf-8")
    stats = mod.load_json(mod.STATS_FILE)
    sums = stats["sha256"][mod.VERSION]
    assert re.fullmatch(r"[0-9a-f]{64}", sums["setup"]) and f'<code class="hash" translate="no">{sums["setup"]}</code>' in dl
    assert sums["install_sh"] in dl and "bash ~/Downloads/install.sh" in dl and mod.INSTALL_SH_URL in dl
    assert dl.index('id="checksum"') < dl.index('id="requirements"')  # right below the download button
    for part in ("Processor", "Memory", "Graphics card", "Disk"):
        assert f'<th scope="row">{part}</th>' in dl
    bench = mod.load_json(mod.BENCH_FILE)
    assert set(bench["runs"]) >= {"gpu60", "gpu180", "light60", "light180"}
    assert 'id="speed"' in dl and "1-hour stream" in dl and "3-hour stream" in dl and bench["machine"]["cpu"] in dl
    assert "smartscreen.webp" in dl
    # the badges are drawn at build time: no request to a badge service
    assert "shields.io" not in dl and f"{mod.GH}/stargazers" in (out / "index.html").read_text(encoding="utf-8")


def test_durations_read_like_people_say_them():
    spec = importlib.util.spec_from_file_location("sitegen_build3", SITEGEN / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    t = mod.load_texts()["en"]
    assert mod.fmt_duration(7 * 60 + 20, t) == "about 7 min"
    assert mod.fmt_duration(42 * 60, t) == "about 40 min"
    assert mod.fmt_duration(83 * 60, t) == "about 1 h 25 min"
    assert mod.fmt_duration(119 * 60, t) == "about 2 h"
    assert mod.compact_number(2827, "en") == "2.8k" and mod.compact_number(2827, "de") == "2,8k"
    assert mod.compact_number(37, "tr") == "37"
