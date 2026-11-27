"""1.2.74: dialogs inside a page must stay fixed to the window.

A CSS animation that moves an element (transform) and keeps its last frame ("both"/"forwards")
leaves a transform on that element after it ends, which makes it the containing block of every
position:fixed child. .page-fx (the page-enter animation) wraps every page, so on a scrolled page
(Settings > the SharkyClips Helper guide) the dialog opened above the window, under the top bar.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "styles.css"
# elements that wrap whole pages / screens (dialogs and popups can open inside them)
WRAPPERS = ("page-fx", "welcome-body", "topbar", "app-shell", "ez-page")


def _keyframes_with_transform(css: str) -> set[str]:
    out = set()
    for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        if "transform" in css[m.end():i] or "translate" in css[m.end():i] or "scale" in css[m.end():i]:
            out.add(m.group(1))
    return out


def test_page_wrappers_do_not_keep_a_transform_after_their_animation():
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    moving = _keyframes_with_transform(css)
    assert "m-rise" in moving
    bad = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if not any(re.search(rf"\.{w}\b", sel) for w in WRAPPERS):
            continue
        for decl in re.findall(r"animation\s*:\s*([^;]+)", body):
            names = set(re.findall(r"[\w-]+", decl)) & moving
            if names and re.search(r"\b(both|forwards)\b", decl):
                bad.append(f"{sel.strip()} {{ animation: {decl.strip()} }}")
    assert not bad, "use animation-fill-mode backwards on page wrappers:\n" + "\n".join(bad)
