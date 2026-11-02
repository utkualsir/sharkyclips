"""Hear every speaker: multi-track audio, voice separation, speaker diarization and extra
transcription passes, merged into one transcript with speaker labels (voices.json).

The normal transcript (transcribe.py) is one Whisper pass over the mixed audio: a friend on
Discord, quiet under the game sound, is often skipped. The voice pass works on the clip
ranges (or the whole video) and:

1. Multi-track videos (OBS: mic, Discord, game...): every voice track is transcribed on
   its own, labelled me / friends (labels remembered per channel, tracks.py).
2. Single-track videos: the voices are separated from game sound (UVR MDX-Net), quiet
   voices are levelled up, and "who speaks when" comes from speaker diarization
   (pyannote segmentation + WeSpeaker, all sherpa-onnx, no token needed).
3. Each speaker turn is transcribed again from the mix and from the separated voices; the
   best reading of each turn wins (hallucinations like "Altyazı M.K." are dropped).
4. Speakers are matched across the whole video by voice fingerprint; the one who talks
   most is "me" (on multitrack: the mic track).
5. Words with low confidence are listened to once more on the separated voices with the
   swear words as decoder hints (acoustic keyword check) -> swear hints for the bleeps.

CPU models run first (governor thread count), then Whisper alone on the GPU; everything is
released at the end. Results: <project>/voices.json, used by edit/plan.py (captions with
speakers, bleeps) and the transcript editor.
"""

from .pipeline import (  # noqa: F401
    covered,
    hints_for,
    load,
    run_voice_pass,
    speaker_names,
    words_for,
)
