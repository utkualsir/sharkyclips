# Handoff: game-aware metadata (1.2.25 - 1.2.27) - DONE, 2026-11-08

All finished in 1.2.27; nothing open.

- 1.2.25 / 1.2.26: one game per project (`titles/banks.py: project_game`), per-game banks,
  hashtags / tags / channel text, punchy titles, metadata-only re-run, swear and clip-time checks.
- 1.2.27: swear words are scrubbed from the AI's notes (`analyze.scrub_profanity`) before titles
  and descriptions are written (a "teammate named Deepfuck" made every description fail).
  `publish.titles_original` keeps a clip's titles from before its first rewrite, so `_top_up`
  can still reach 4 titles after several rewrites. Linux Cancel: `procs._kill_tree` lets the Popen
  reap its own child (psutil's wait stole the exit status, so a killed process reported 0).
- The user's 5 LoL / Delta Force projects all have 1.2.26-rule texts, a description and at least
  4 titles per clip; no other game is named anywhere (40 such mentions before, 0 after).
- Title quality is limited by qwen3.5:9b Turkish (some odd grammar): use thumbs up / down on titles.
