# Handoff: game-aware metadata (1.2.25 / 1.2.26), 2026-11-07

## Done (on main, tagged v1.2.25 and v1.2.26, pushed)
- Bug fixed: LoL clips got #Warzone / #CoD because the LLM guessed the game for each clip.
  The project now has one game (`titles/banks.py: project_game`: override > HUD pick / detection
  > title + transcript). Every prompt gets it, and `other_game()` rejects any other game's name.
- Per-game banks `titles/game_banks/{lol,delta_force,cs2,valorant,generic}.json`. User overrides go
  in `<settings>/game_banks.json`, editable in Studio > Games.
- Hashtags: #channel first, #shorts, the game, 2-4 about the clip, 5-8 in total. 10-20 YouTube tags
  (`build_tags`). Descriptions end with a question. Socials block from Brand kit > Channel text
  (`edit/brand.py`) on YouTube / best-of / TikTok / Reels / Easy txt.
- Punchy gaming titles (6 formulas, CAPS key words, 1 emoji at the end, max one "!"). New few-shot
  examples in all 7 languages.
- Metadata-only analyze (`analyze_project(meta_only=True)`, API `meta_only`), project "Texts" picker
  (`PUT /api/projects/{id}/metadata-game`).
- 1.2.26: swear roots glued into names ("Deepfuck") are caught. Clip timings ("+7s", "5.7 saniye")
  are rejected. Clips left with too few titles get their old clean titles back.
- The user's channel text is set in their config: #utkualsirr plus the Kick / Instagram / Facebook block.
- Tests: `backend/tests/test_game_metadata.py`. Full suite and layout check pass locally.

## Not done
- Second metadata re-run (1.2.26 rules) was STOPPED for the PC shutdown. Done: 2026-11-06-19-25-41,
  rakip-dariusa, mf-nati-duosu, 2026-11-06-21-28-04 (all LoL). The Delta Force project (toplam-55-kill...)
  is partly done: its file is valid and finished clips have the new texts, the rest still have 1.2.25 texts.
- Two clips have no description (LLM kept failing checks): 2026-11-06-19-25-41 #9, and one clip
  (#5) in the project that was running when the run stopped (probably 2026-11-06-21-28-04).
- The 5+5 before/after report has not been rebuilt for the 1.2.26 texts.
- The user's app was NOT running during the release, so no restart was needed. Start it normally:
  the launcher runs 1.2.26.
- CI: the Ubuntu job fails on `test_cancel_final.py::test_track_kills_a_process_started_after_cancel`.
  This was already failing in 1.2.24, before this work, and it is Linux only.

## Next steps
1. Finish the Delta Force project and fill the missing descriptions (cached clips are instant):
   `analyze_project(get_project("toplam-55-kill-44-revive-lobiyi-tek-basi-2e13dedc"), meta_only=True)`,
   then `meta_only=True, ranks=[...]` for the clips with `description: None`.
2. Rebuild the before/after report: compare with the backups of the pre-1.2.25 `highlights.json`
   (scratchpad `backup/`, may be gone after the reboot; else use git-ignored workspace history).
3. Title quality is limited by qwen3.5:9b Turkish (some odd grammar). Use 👍/👎 on titles so it learns.
4. Look into the Linux-only cancel test failure.
