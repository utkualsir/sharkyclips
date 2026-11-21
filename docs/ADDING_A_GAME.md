# Adding a game to SharkyClips

SharkyClips finds the best moments of a stream by listening (loud reactions, laughter, keywords,
chat) and, for known games, by **reading the game's screen** (OCR on the HUD: "ACE", "VICTORY
ROYALE", "WASTED"...). Everything game-specific lives in one small JSON file, so you can add or
fix a game without writing code.

## 1. Where the profile goes

```
backend/sharkyclips/game/profiles/<game_id>/profile.json     <- built in (send a pull request)
~/.sharkyclips/game_profiles/<game_id>/profile.json          <- only on your PC (try it first)
```

A profile in your settings folder wins over a built-in one with the same id. Restart SharkyClips
after you add or change one.

## 2. A minimal profile

```json
{
  "id": "rocket_league",
  "name": "Rocket League",
  "status": "beta",
  "engine": "banners",
  "kind": "sports",
  "aliases": ["rocket league"],
  "hints": ["boost", "aerial", "kickoff", "demo"],
  "regions": {
    "banner": {"box": [460, 120, 1000, 220], "label": "Goal banner"}
  },
  "ocr": {
    "banner": {
      "rl_goal": ["goal", "gol"],
      "rl_save": ["epic save", "save", "-assist"]
    }
  },
  "events": {
    "rl_goal": {"strength": 0.7, "label": "Goal", "dedupe": 20, "pre": 8, "post": 3},
    "rl_save": {"strength": 0.5, "label": "Epic save", "dedupe": 15}
  },
  "hashtags": {"all": ["#rocketleague", "#rlclips"], "tr": ["#rocketleaguetr"]},
  "terms": ["Octane", "Dominus", "DFH Stadium"],
  "vocabulary": {"en": ["what a save"], "tr": ["golü attım"]},
  "title_style": {"en": "Say the play: 'Ceiling shot GOAL in overtime'."}
}
```

## 3. The fields

| Field | What it does |
| --- | --- |
| `id` | Short name, lowercase letters, numbers and `_`. Also the folder name. |
| `name` | The game's name as players write it. |
| `status` | `verified` (checked on real videos), `beta` (not checked yet) or `preview` (the game is new and its screen is still a guess). Beta and preview games show a **beta** badge in the app. |
| `engine` | `banners`: SharkyClips reads your `regions` when text appears in them. |
| `kind` | `tactical_shooter`, `battle_royale`, `moba`, `hero_shooter`, `open_world`, `sandbox`, `sports`, `extraction_shooter` or `other`. |
| `aliases` | Names in a stream title or Kick category that mean this game. |
| `hints` | Words streamers say while playing it. Used to find the game when the title doesn't say it. |
| `regions` | Boxes on the screen to read, as `[x, y, width, height]` on a **1920x1080** frame. Other sizes are scaled. |
| `ocr` | For each region: event code -> texts that mean it. Write texts in lowercase without accents. Add the English and the Turkish (or your language's) text. A text starting with `-` must **not** be there (`"-assist"`). Small OCR mistakes are allowed automatically. |
| `events` | For each event code: `strength` 0..1 (how big the moment is: an ace is 1.0, a single kill 0.3), `label` (shown in the app), `dedupe` (seconds: the same banner stays on screen, count it once), `pre` / `post` (seconds of build-up before and reaction after the moment in the clip). |
| `hashtags` | `all` = for every language, plus lists per content language (`tr`, `es`, `pt`, `fr`, `ja`, ...). |
| `terms` | Map, character and item names, spelled exactly. Titles only use them when they are said in the clip. |
| `vocabulary` | Typical reactions per language (helps find the moments). |
| `title_style` | A short hint per language for the AI title writer. |
| `checked` | `{"events": [...], "on": "which videos"}`: the events you saw read correctly on real videos. The app lists them next to the beta badge. |

## 4. Finding the boxes and texts

1. Import a video of the game and pick the game in the project (Game: your game).
2. Open **Game detection** in Pro mode: it shows the boxes on a frame and the raw OCR text.
   Move a box with the mouse until the banner text is inside, then copy the numbers.
3. Check the raw text the OCR reads for each banner and put those words into `ocr`.
4. Run **Find highlights** again. The events list should show your events at the right times.

Tips: keep boxes small (only where the banner appears) so gameplay behind them is not read. Big
centre texts (victory, defeat) can share one `center` region.

## 4b. Animated graphics (optional)

Since 1.2.58 clips can show short animated graphics for your game's moments (a kill counter,
banners like ACE or CLUTCH, round wins). Map your event codes in `graphics`:

```json
"graphics": {
  "kills": ["mygame_kill"],
  "events": {
    "mygame_ace": {"type": "banner", "text": "ACE", "icon": "crown"},
    "mygame_round_won": {"type": "score", "text": "ROUND WON", "icon": "flag"},
    "mygame_multikill": {"type": "banner", "text": "{n}x KILL", "icon": "skull"}
  }
}
```

- `kills`: events that count up the kill counter.
- `type`: `banner` (a big moment) or `score` (a score, round or match result). Banners win when two
  moments are close together; only one graphic is ever on screen.
- `text`: at most 24 characters, usually the game's own word in capitals. `{n}` becomes the event's
  number (for example the kills of a multikill).
- `icon`: one of `skull`, `crown`, `star`, `flag`, `flame`, `trophy`, `target`.

SharkyClips places the graphic itself (never over the facecam, the captions, the middle of the game
picture or the platform's buttons), so there is nothing to position.

## 4c. The game's own HUD (optional, recommended)

Since 1.2.59 a profile can mark where the game draws its own HUD, so the animated graphics never
cover it (the kill feed, the score, the minimap ...). Boxes are `[x, y, w, h]` on a 1920x1080 frame:

```json
"hud_areas": {
  "kill_feed": {"box": [1440, 80, 460, 260], "label": "Kill feed", "guess": true},
  "minimap":   {"box": [0, 0, 420, 420], "label": "Minimap", "guess": true},
  "kill_text": {"box": [760, 760, 400, 200], "label": "Kill banner", "guess": false}
}
```

Names: `kill_feed`, `kill_text`, `score`, `minimap`, `health`, `ammo`, `abilities`, `timer`,
`objective`, `chat`, `scoreboard` (add `.2` for a second box of the same kind, e.g. `score.2`). Set
`"guess": true` until you have checked the box on real footage. One box may cover at most a fifth of
the screen. When no free spot is left, a graphic is drawn a little smaller, or not at all.

## 5. Check it before you send it

```
.venv/Scripts/python -m pytest -q backend/tests/test_game_profiles.py
```

The test loads every profile and checks the boxes, the event codes and the strengths. In your pull
request, say which videos you checked it on (game version, language of the game client, 1080p or
not) and list the events you saw in `checked`. If you could not check it on a real video, keep
`"status": "beta"`.
