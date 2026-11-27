"""1.2.74: full-width choices (.segmented.block) on phones must fit long single words.

Russian "Полуавтоматически" (TikTok's "Semi-auto" choice in Settings) has no space to wrap at, so the
two-option switch was 9 px wider than a 390 px phone and got cut off (layout-check, ru, 390x844).
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "styles.css"


def test_phone_choice_buttons_break_long_words():
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    m = re.search(r"@media \(max-width: 520px\) \{\s*\.segmented\.block button \{([^}]*)\}", css)
    assert m, "phone rule for .segmented.block buttons is missing"
    rule = m.group(1)
    assert "white-space: normal" in rule and "min-width: 0" in rule
    assert "overflow-wrap: anywhere" in rule  # a word longer than the button still breaks
