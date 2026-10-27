# Security policy

## Reporting a problem

Please **don't open a public issue** for a security problem. Use GitHub's private
[security advisory form](https://github.com/utkualsir/sharkyclips/security/advisories/new)
instead. You'll get an answer within a week. Fixes ship as a normal update (Settings → Updates).

Only the latest version is supported.

## What SharkyClips exposes

- **Default:** the web UI listens on `127.0.0.1` only. Nothing outside your computer can reach it.
- **`--lan` mode** (`python cli.py serve --lan`) listens on your local network so a phone can open
  the UI. Anyone on that network can then reach it, so set an **access PIN or password** in
  Settings → Network (SharkyClips warns you when LAN mode runs without one). The PIN is stored only
  as a salted hash (scrypt), login attempts are rate-limited, and the session cookie is
  `HttpOnly` and `SameSite=Strict`. LAN mode uses plain HTTP: use it only on networks you trust,
  never on public Wi-Fi.
- Some actions are refused from other devices even when logged in: browsing local file paths,
  connecting a YouTube account, quitting, and shutting the PC down.
- **YouTube:** your OAuth client and tokens are stored in your settings folder
  (`~/.sharkyclips/youtube/`) and are only sent to Google.

## Out of scope

Anything that needs an attacker to already run code on your computer or to control your settings
folder.
