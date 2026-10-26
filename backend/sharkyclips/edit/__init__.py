"""Editing power tools (Phase 10, 1.2.4).

  words.py      language-aware word matching (Turkish dotted/dotless i, accents, CJK)
  profanity.py  swear word lists (7 languages, user-editable) -> bleeps / masked captions
  fillers.py    filler words ("ııı", "um", "äh", ...) per language
  silence.py    quiet gaps in the audio
  plan.py       EditPlan: what one clip keeps, cuts, bleeps and zooms (render + live preview)
  zoom.py       punch-in zoom pulses -> ffmpeg expressions
  audiomix.py   the clip's sound: cuts with crossfades, bleeps, music with ducking, -14 LUFS
  loudness.py   ITU-R BS.1770 loudness (LUFS) + a peak limiter
  music.py      the user's own music library (moods, strong part, suggestions)
  brand.py      brand kit presets (logo watermark, handle, intro/outro cards, caption style)
  manual.py     clips the user marks by hand (I/O)
"""
