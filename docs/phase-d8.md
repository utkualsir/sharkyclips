# Phase D8: moments that aren't kills (release 1.2.77)

## Kısa rapor (Türkçe)

- **CI:** Faz 7 push'u yeşildi (16,5 dk), düzeltme gerekmedi.
- **Yeni kalıcı kural (CLAUDE.md, kural 6):** süreçler asla isimle öldürülmez (Ollama, ffmpeg, python, tarayıcılar…).
  Yalnızca bu oturumun başlattığı süreç, kendi PID'iyle durdurulur. Çalışan SharkyClips'e ve işlerine dokunulmaz
  (tek izin: boştayken kural 3'teki yeniden başlatma).
- **Çeviri hatası düzeltildi:** "Light" performans ayarı Macarcada "Világos" → **"Könnyű"**, Rusçada "Светлая" →
  **"Лёгкий"**. 11 dilin hepsi kontrol edildi. İspanyolca, Fransızca ve Portekizcede üç metin daha "modo claro /
  mode clair" diyordu, düzeltildi. Japoncada "ライト" → "軽量" oldu ve çevrilmemiş bir "fewer" kelimesi vardı. Hata bir
  daha olursa test yakalıyor.
- **Kill olmayan anlar:** yeni "ses" sinyali eklendi; yayıncının kendi sesine göre perde ve şiddet yükselmesi,
  çığlık ve uzun sessizlikten sonra gelen patlamayı ölçüyor. GPU kullanmıyor, model indirmiyor; 3 saatlik yayında
  yaklaşık 18 sn CPU tutuyor. Ayrıca 11 dilde komik ve fail sözleri var ("ne yaptım ben", "nasıl öldüm", "hahaha"
  gibi). Just Chatting / IRL yayınları kategori ya da başlıktan otomatik tanınıyor ve "talk" profiliyle
  işleniyor: kahkaha, ses ve sohbet daha ağır basıyor, hikâyenin girişi klipte kalıyor.
- **Sohbet:** "GOOOL", "ahaha", "ICANT", "jajaja", "kkkk", "mdr", "ㅋㅋ" ve yeni Twitch/Kick emote'ları tepki
  sayılıyor. Kartlarda tek bir **başlık nedeni** gösteriliyor: "Sohbet çıldırdı", "Büyük kahkaha", "Clutch",
  "Fail", "Çığlık"…
- **Bağlam:** akıllı ön kısım, aksiyonun başladığı yerden başlıyor (en çok 22 sn geriye, talk için 28 sn) ve hiçbir
  zaman cümle ortasından başlamıyor. Bitiş artık cümle ya da kahkaha ortasında kesilmiyor, sondaki ölü sessizlik
  kısalıyor. Easy'de "Sonra başlasın / Önce bitsin" eklendi; Pro'da metin düzenleyicide 4 adet ±2 sn düğmesi var.
- **Sesli işaret:** kayıtta "clip it" veya "klip al" (ya da Ayarlar'da kendi ifaden) dendiğinde o an her zaman klip
  oluyor. İfade sonradan transkriptte bulunuyor; canlı mikrofon dinleyen bir süreç yok. Klip, ifade söylenmeden
  hemen önce bitiyor. Kısayol tuşu aynen çalışıyor.
- **Ölçüm** (30 dk kuralına uyuldu; tamamı CPU'da ~2 dk sürdü, projelerine hiç yazılmadı; gölge kopyalarla
  yapıldı): 8 LoL projesi, 265 dk, 65 klip. 43 klip kaldı, 22 klip değişti. Değişenler çoğunlukla zayıf "sadece
  gürültü" anları; yerlerine kahkaha, çığlık, fail ve sessizlik-sonrası tepkiler geldi. İlk 3 nedeninde kill
  dışı bir sinyal olan klip sayısı **7 → 43**. Düşen oyun olayları: 1 zafer ekranı, 1 baron, 3 ölüm ve 1 kill
  (hepsi zayıf olaylar; üçlü kill ve üstü ile çalmalar zaten her zaman klip). Sentetik Just Chatting örneğinde
  (12 dk, Windows sesi) ilk 6 klipte yerleştirilen 6 anın 6'sı da bulundu; eski motor 4'ünü buluyordu (çığlık ve
  "clip it" yoktu).
- **Dürüst not:** LoL projelerinde "Birden patladı" (sessizlik sonrası tepki) başlığı hâlâ en sık başlık (22/65).
  Bu sessiz oynayan destek oyuncularında gerçek bir örüntü; transkriptte bakılan örnekler gerçekten tepkiydi
  ("Uff, of of ultiye bak!", "dördüncü ejderi çaldı ya"). Projelerin hiçbirinde sohbet kaydı yok, o yüzden sohbet
  yalnızca sentetik örnekte ölçüldü.
- **Sürüm:** 1.2.77, testler (hızlı yerel + CI), 11 dil, layout/axe, CHANGELOG, etiket, push, CI ve yeniden
  başlatma: sonuçlar en altta.

## What changed

| Area | Before | Now |
|---|---|---|
| Non-kill moments | loudness, laughter model, keywords, fast speech | + **voice** signal (pitch / loudness vs the streamer's own baseline: `voice_excited`, `scream`, `silence_break`), + `funny_line` / `fail_line` (11 languages, written-out laughter) |
| Talk streams | treated like a game | **talk profile** inside Gaming mode: auto from category / title (Just Chatting, IRL, sohbet, podcast, 雑談 …), more weight on laughter / voice / chat, longer setup |
| Chat | KEKW, LUL, ??? … | + GOOOL / gol, ahaha, ICANT, KEKL, xdd, EZ Clap, jajaja, kkkk, mdr, ptdr, ㅋㅋ, 草 … |
| Card | up to 4 reason chips | **one headline first** ("Chat went wild", "Big laugh", "Clutch", "Fail", "Scream", "You said “clip it”" …), Pro and Easy |
| Start | 6-10 s before the peak | from where the build-up began (≤ 22 s; talk ≤ 28 s + up to 2 setup sentences), never mid-sentence |
| End | word edge | + a running laugh / scream isn't cut, no mid-sentence end, dead silent tail cut, quiet point (not into the next word) |
| Nudges | Easy: earlier / later / short / long | + Easy "Start later" / "End sooner" (never into the big moment); Pro: 4 × 2 s buttons in the text editor |
| Markers | hotkey, chat "!clip" | + **spoken** "clip it" / "klip al" (Settings > Live markers, up to 8 phrases), found in the transcript afterwards |

## Measurement

Old engine = `git archive HEAD backend` (1.2.76), new engine = this release, same inputs. Script:
[docs/phase-d8/compare_picks.py](phase-d8/compare_picks.py) (`shadow` / `run` / `diff`). Nothing was written into
the owner's projects: every project was copied (meta, transcript, audio, laughter and HUD-scan caches) into a
throwaway folder, the game signal could only use the cached HUD scan, and the run used a throwaway settings
folder. The whole run took about 2 minutes of CPU at below-normal priority, while no game was running. The owner's
app had GPU jobs queued, so nothing here used the GPU. Three projects that the app was still processing (no
transcript yet) were skipped.

### The owner's projects (8 LoL streams, Turkish, no chat replay)

| project | min | HUD scan | clips | kept | added | dropped | start shift s | end shift s | mean length s | clips with a non-kill reason in their top 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| adc-cassi-sup-nati | 36 | yes | 9 | 5 | 4 | 4 | -1.2 | -0.2 | 21.8 -> 23.7 | 3 -> 6 |
| camille-sup | 34 | yes | 8 | 5 | 3 | 3 | -1.8 | -0.8 | 23.2 -> 23.6 | 0 -> 2 |
| efsane-thresh-luci | 28 | yes | 7 | 6 | 1 | 1 | -2.1 | -3.1 | 27.0 -> 26.1 | 0 -> 2 |
| jung-rengar-sup-nati | 29 | yes | 7 | 5 | 2 | 2 | -1.8 | -0.9 | 21.5 -> 24.2 | 0 -> 4 |
| seraphine-support-tek | 45 | no | 11 | 7 | 4 | 4 | -1.2 | -3.5 | 24.5 -> 24.0 | 1 -> 11 |
| top-jax-sup-camille | 25 | no | 6 | 4 | 2 | 2 | -0.5 | -1.9 | 25.2 -> 26.0 | 0 -> 4 |
| yorick-rengar-bot | 39 | yes | 10 | 7 | 3 | 3 | -0.4 | -1.8 | 22.4 -> 20.5 | 2 -> 9 |
| yorick-sup-adc-cassi | 29 | no | 7 | 4 | 3 | 3 | -0.2 | +2.4 | 23.2 -> 22.1 | 1 -> 5 |
| **total** | 265 | | 65 | 43 | 22 | 22 | | | | **7 -> 43** |

"Start shift" is for the kept clips (negative = earlier). Kept clips mostly have strong events whose build-up the
old code already kept, so the average moved only about 1 s; the large changes are in the added clips.

Headlines of the new picks: Out of nowhere 22, Big laugh 13, Hyped voice 10, Fail 8, Big reaction 5, Scream 5,
Clutch 1, game event 1.

**Added** (22): mostly a laugh, a scream, a fail line or a reaction after a long silence. For example: camille
257-285 s and 1030-1054 s *Big laugh*, camille 427-444 s *Fail* (a fail line), jung-rengar 931-959 s *Scream*,
efsane 1355-1386 s *Hyped voice* (a double kill with an excited voice), yorick 2082-2108 s *Scream*, seraphine
821-848 s *Fail* ("ben nasıl öldüm"). Some *Out of nowhere* picks checked in the transcript: "Uff. Of of ultiye
bak!", "Abi adam dördüncü ejderi çaldı ya", "Sweet dodge ya bu".

**Dropped** (22): mostly plain loud moments with fast talk and keywords but no laugh, scream or game event (16).
Game-event clips that dropped out of the top N: 1 victory screen (with nothing else), 1 baron (with one keyword),
3 deaths and 1 single kill. Triple kills and up, steals and extractions are still always offered (unchanged rule).

### Synthetic Just Chatting sample

[docs/phase-d8/make_talk_sample.py](phase-d8/make_talk_sample.py): 12 minutes of calm talk by Windows' offline
voice, with six planted moments (anchors found in the Whisper transcript) and a synthetic chat replay. Transcribed
on the CPU (Whisper small, 1.5 min). Profile picked: **talk** ("title / category: just chatting").

| moment | old, default 3 clips | new, default 4 clips* | old, top 6 | new, top 6 (+1 marker) |
|---|---|---|---|---|
| joke + laughter + "I'm crying" | ✓ | ✓ (*Chat went wild*) | ✓ | ✓ |
| 22 s silence, then "WHAT? No way!" | ✓ | ✓ | ✓ | ✓ |
| fail: "what did I just do" | ✗ | ✓ | ✓ | ✓ |
| scream (jump scare) | ✗ | ✗ | ✗ | ✓ (*Scream*) |
| chat-only moment (KEKW wave) | ✓ | ✗ | ✓ | ✓ |
| spoken "clip it" | ✗ | ✓ (*You said “clip it”*) | ✗ | ✓ |
| **found** | 3 / 6 | 4 / 6 | 4 / 6 | **6 / 6** |

\* a marked moment is always a clip, on top of the normal count.

The joke clip now ends right after "I'm crying, I can't breathe, that's so funny." (118 s) instead of running into
the next, unrelated sentence (129 s): mean clip length 25.8 s → 18.0 s here, with the same moments in them.

Limits of the sample: the voice is synthetic (SAPI speaks "AAAAH" as silence, so a generated scream is spliced in;
spoken "ha ha" is not real laughter for the laughter model), and the chat is generated.

## Decisions (unattended run, logged as they were made)

1. **No fourth mode.** "Just Chatting / IRL" is a *profile* inside Gaming mode (`talk`), not a new mode: a new
   mode touches ~76 places (channel style, YouTube category, full-video upload, layout fixtures, mode pickers).
   The profile is picked automatically from the stream's category / title (Kick gives the category; "just
   chatting", "irl", "sohbet", "podcast", "雑談" ...) when no game is recognised; a recognised game always wins.
   `meta.profile` = `game` | `talk` overrides it (no UI switch yet: the auto choice is shown in highlights.json).
2. **Voice excitement without a model.** Pitch by autocorrelation on the CPU (first peak within 90 % of the best:
   no octave errors), measured against the speaker's own 2-minute baseline. No download, no GPU, ~18 s CPU for a
   3 h stream. Only seconds within 3 s of a transcribed word count as "voice" (game music is periodic too);
   the 3 s pad keeps wordless screams, which Whisper drops.
3. **Silence break needs the streamer's voice.** First version: any 5 s pause followed by a jump -> 68 events in
   39 min on a quiet LoL player, and every card said "Out of nowhere". Now: >= 8 s without words, and the burst
   must be louder (+3 dB) or clearly higher (+4 semitones) than the streamer usually talks. Strength = how much.
4. **Scream** = >= 7 semitones up AND >= 9 dB louder, voiced, held 2 s. Rises over 2 octaves are tracking
   errors (game sounds) and ignored. The laughter model's "Screaming" class is split out of "Shouting" too.
5. **Funny / fail lines are word lists** (11 languages, `funny` / `fail` categories) plus written-out laughter
   ("hahaha", "jajaja", "хаха", "ههه") as its own pattern. Too-common words were left out (pt "para", es "qué",
   fr "quoi"). No LLM pass for this (it would need the GPU on every run).
6. **Headline = one reason per card**, order: your marker > clutch (said "clutch" or a baron / dragon steal) > a big
   game event (its own label) > the strongest *specific* reason (chat went wild, big laugh, funny, scream, fail)
   > context (hyped voice, out of nowhere) > "Big reaction". A kill alone is not called "Clutch".
7. **Smart pre-roll**: walk back from the peak while the hype stays above 30 % of it (the fight / setup), keep 2 s
   of calm before, at most `setup_max` (22 s gaming, 28 s talk), then back to the start of the running sentence
   (<= 6 s); talk streams also take up to 2 sentences of setup (not across a >= 2.5 s pause). If the clip gets too
   long, the setup is trimmed, never the payoff.
8. **Clean ending**: a laugh / excited voice still going keeps the clip open (<= 20 s after the peak); an end on a
   word in the middle of a sentence moves back to the last finished sentence (<= 8 s, never before the payoff) or
   forward to the end of the running one (<= 6 s); a silent tail (> 2.5 s, 10 dB under the speech) is cut to 0.8 s;
   without a word nearby the end goes to the quietest half second, never into the next word.
9. **Spoken markers** are found in the normal transcript (default "clip it", "klip al", configurable, up to 8,
   with a few Whisper spellings like "clipit", "klipal"). No second Whisper pass, no hotwords (they make Whisper
   hear the phrase where it wasn't said), no live microphone process. The clip ends just before the phrase. Like
   hotkey markers they are always clips and always first.
10. **One-tap trims**: Easy gets "Start later" / "End sooner" (3 s, never into the clip's big moment); Pro's text
    editor gets four 2 s buttons, always onto a word edge.
11. **Calibration features unchanged** (no `sig_voice`): adding a feature would make the owner's learned calibration
    model stale. The voice signal still feeds the hype score and the reasons.
12. **Light preset fix** covers all 11 languages: hu "Világos" -> "Könnyű", ru "Светлая" -> "Лёгкий", es / fr / pt
    three texts each said "modo claro / mode clair / modo claro", ja "ライト" -> "軽量" (+ an untranslated "fewer").
    A test now fails if the preset ever uses the colour word again.
13. **The measurement never touches the owner's projects**: shadow copies (meta, transcript, audio, laughter + HUD
    caches) in the scratchpad; the game signal may only use the cached HUD scan; the old engine is `git archive
    HEAD backend`. The owner's app had GPU jobs queued (LLM analysis), so the synthetic sample was transcribed on
    the CPU (small model, 1.5 min) and nothing used the GPU. Total measurement time ~2-4 min per run.
14. **Synthetic Just Chatting sample** (no third-party content): Windows' offline voice (SAPI). It speaks "AAAAH" as
    silence and barely changes volume, so a generated scream is spliced in; laughter is spoken "ha ha ha" (the
    laughter model doesn't take it as real laughter: an honest limit of the sample).

## Tests and release

- New tests: `backend/tests/test_phase_d8.py` (20 tests: pitch tracker, voice signal on synthetic speech with a
  scream and a silence break, no false alarms on steady talk, funny / fail lines and written laughter, trigger
  lists in all 11 languages, chat patterns, spoken markers + their clip ending before the phrase, smart pre-roll,
  a running laugh not cut, clean sentence ends, setup sentences, headline order, headline / reason texts in all 11
  languages, talk profile, highlights.json profile + headlines, Easy "Start later" / "End sooner", the marker
  phrases settings API, and the Light preset never being the colour word).
- Local: `quick-check.py` (changed files) OK in 11 min; `quick-check.py --full` 9.8 min: everything green except
  one website test that broke on any version bump (it read this version's download checksums, which only exist
  after the release is built). Fixed: it checks the checksum box when the version has checksums and otherwise
  that no other version's checksum is shown.
- Layout check (project, easy-project, settings, easy-settings, updates, easy-updates at 1024x700, 1280x720,
  1920x1080 and phone width, tr / ar / de / hu) and axe (all screens and dialogs, both themes): pass. The layout
  fixture's clips now carry headlines, the longest ("You said “klip al”") included, so CI checks them too.
- i18n check: 3498 keys in all 11 locales. UI rebuilt after the version bump.
- Not done on purpose: nothing was posted to any account; the public website was not republished (its download
  checksums for 1.2.77 appear with the next `build.py --stats` after this release).
