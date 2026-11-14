"""Stands in for the user's own Chrome in the TikTok login tests (1.2.43): started as a plain
program with --user-data-dir=<profile> and the login URL, like the real chrome.exe. It "logs in"
on the fake TikTok Studio (opens /__autologin in that profile, which sets the session cookie) and
then quits, like the user closing the window. Argument --stay=<s>: keep running that long first."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main(argv: list[str]) -> int:
    profile = next(a.split("=", 1)[1] for a in argv if a.startswith("--user-data-dir="))
    url = next(a for a in argv if a.startswith("http"))
    stay = float(next((a.split("=", 1)[1] for a in argv if a.startswith("--stay=")), "0"))
    login = "--no-login" not in argv
    state = Path(profile).parent / "tiktok.json"
    channel = next((a.split("=", 1)[1] for a in argv if a.startswith("--channel=")), None)
    if channel is None:
        try:
            channel = json.loads(state.read_text(encoding="utf-8")).get("channel")
        except (OSError, ValueError):
            channel = None
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    time.sleep(stay)
    if login:
        with sync_playwright() as pw:
            for ch in [channel] if channel else ["chrome", "msedge", "chromium"]:
                try:
                    kw = {"channel": ch} if ch != "chromium" else {}
                    ctx = pw.chromium.launch_persistent_context(profile, headless=True, **kw)
                    break
                except Exception:  # noqa: BLE001
                    continue
            else:
                return 3
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(base + "/__autologin")
            ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
