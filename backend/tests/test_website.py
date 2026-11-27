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
