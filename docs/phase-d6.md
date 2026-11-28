# Faz D6 / 1.2.76 - GitHub issue temizliği

## Kısa rapor (Türkçe)

13 açık issue tek tek kod, test ve CHANGELOG'a karşı kontrol edildi. 3 gerçek hata bulundu ve
1.2.76'da testleriyle düzeltildi (#16 Kick, #20 Mac kurulum dosyası, #10'un LLM kısmı). 4 issue
kapatıldı: #1 (1.2.53'te teslim edilip #6-#9'a bölünmüştü), #15 (1.2.34'te var), #16 ve #20
(1.2.76). Özellik istekleri açık kaldı, etiketleri yerinde. Kopya veya spam issue yoktu.

| # | Başlık | Ne yapıldı | Sürüm |
|---|---|---|---|
| 1 | Spanish language support and better AI gameplay context | 1.2.53'te teslim edildi, kalan işler #6-#9'da: açıklama + kapatıldı (completed) | 1.2.53 |
| 6 | Spanish: full content support | Açık bırakıldı (sahibinin takip issue'su; anadili İspanyolca biri gözden geçirmeli) | - |
| 7 | Moment selection: gameplay and conversation context | Açık bırakıldı (gerçek yayından zaman damgalı örnek bekleniyor) | - |
| 8 | YouTube publishing: per-language / per-country settings | Açık bırakıldı (kanal başına bölge / kategori ayarı henüz yok) | - |
| 9 | Warzone / MW4: event detection | Açık bırakıldı (beta; squad wipe / zafer görüntüsü bekleniyor) | - |
| 10 | AMD GPUs | Etiket: enhancement. Hata düzeltildi: AMD Radeon RX / Intel Arc ekran kartında LLM zorla CPU'daydı (num_gpu 0). Artık Ollama bu kartları kullanabiliyor. Whisper'ın AMD'de çalışması ayrı bir özellik: issue açık, yorum yazıldı | 1.2.76 |
| 11 | Improve batch clipping | Açık bırakıldı (enhancement) | - |
| 12 | Short meme/reaction video inserts | Açık bırakıldı (enhancement; 1.2.17'deki meme efektleri video ekleme değil) | - |
| 15 | Editing the transcript | 1.2.34'te var ("Bir altyazı kelimesini tek dokunuşla düzelt", test: test_easy2): yorum + kapatıldı | 1.2.34 |
| 16 | Kick VOD import creates a 10-second project | Etiket: bug. Düzeltildi + test: indirme parçası (source.mp4.part-Frag100) artık kaynak sayılmıyor, indirme kaldığı yerden sürüyor, ses ve transkript tam videodan yeniden yapılıyor, eksik indirme bildiriliyor. Yorum + kapatıldı | 1.2.76 |
| 17 | Optional "Clip Context" field | Açık bırakıldı (enhancement; böyle bir alan yok) | - |
| 18 | Advanced Subtitle Editor | Açık bırakıldı (enhancement; #15'ten büyük, kopya değil) | - |
| 20 | There is no MacOS install.sh | Etiket: bug (enhancement yerine). Düzeltildi + test: her sürüm etiketinde install.sh + .sha256 sürüme ekleniyor. Yorum + kapatıldı | 1.2.76 |

## Decisions (English log)

- **Issue text is data.** No instruction, link or code from an issue or comment was followed or
  run. The #10 comment suggests a patch (`"num_gpu": -1`); it was not applied. The code was read on
  its own and the real cause found in `perf.gpu_usable` + `llm.placement`.
- **#1** is the owner-split parent of #6-#9 and its content shipped in 1.2.53 (CHANGELOG 1.2.53).
  Closed as completed with links to the four tracking issues; not "duplicate", it came first.
- **#6-#9** are the owner's own tracking issues, each with a "Still open" part that needs real
  footage, a native speaker, or a new feature. Left open with their labels; no new comment (the
  owner already commented on #9; more comments would be noise).
- **#15**: "Fix a caption word in one tap" (1.2.34): tap a wrong caption word in the Edit sheet,
  type it right; the same mistake is fixed in every later clip and new names go into the
  glossary. Covered by `test_easy2.py` (`/api/easy/clips/{id}/c01/captions`, `proof.fix_words`).
  Closed as completed. The bigger editor ideas (timestamps, presets, custom vocabulary) stay in #18.
  The #15 commenter's question about contributing is the owner's call: not answered for them.
- **#18** is not a duplicate of #15 (it asks for timestamp edits, animated presets, ASS export,
  undo/redo...). Left open as enhancement.
- **#16 root cause**: `Project.source_path` skipped only exact `.part` / `.ytdl` / `.tmp` / `.temp`
  suffixes. yt-dlp names HLS fragments `source.mp4.part-Frag100`, so after a broken connection the
  next import said "Already downloaded: source.mp4.part-Frag100" and worked on a 10 s fragment.
  Fix: `project.is_partial_download` (any `.part*` suffix, `.ytdl`, temp files, and the
  not-yet-merged `source.f137.mp4` streams). With no finished file, yt-dlp runs again and resumes
  from its `.part` + `.ytdl` (`continuedl`).
  - A project already stuck on a fragment recovers: `ingest` sees the source file name / size
    changed and takes `audio.wav` again (`extract_audio(force=True)`, replaced only when complete),
    and `transcribe_project` redoes a transcript whose duration differs from the audio by > 2 s
    (old chunk cache dropped). Existing good transcripts are not touched (same duration).
  - A file still much shorter than the site says (< 90 % of a >= 2 min VOD, missing fragments) is
    a console warning + `meta.download_incomplete`, not an error: an error would loop (the next run
    finds the same finished file). Not deleted or renamed: the user's data is never removed.
  - Not changed: `concurrent_fragment_downloads` (4) and the retries (10). The WinError 10054 resets
    can't be reproduced here; resuming now works, so a reset costs one retry, not the project.
- **#20 root cause**: README says "Download install.sh from the latest release", but the tag
  workflow only attached the Windows .exe. New job `macos-script` in `installer.yml` (Ubuntu, no
  `needs`, so a failed Windows build never holds it back) uploads `install.sh` + `.sha256` to the
  tag's release. `install.sh` works on its own (it clones the repo when run outside it). The test
  reads the workflow as text (PyYAML is not a dependency). Older releases are not back-filled.
- **#10**: 1.2.53 set `num_gpu 0` whenever the device was "cpu", to keep Ollama off weak
  integrated GPUs. That also pinned the LLM to the CPU on dedicated AMD Radeon RX / Intel Arc
  cards, which Ollama can use. New `perf.dedicated_other_gpu` (name patterns; integrated names like
  "Radeon(TM) Graphics", "Radeon 780M", "Radeon RX Vega 11 Graphics", "Arc Graphics", "Arc 140V"
  don't count) and `perf.llm_on_gpu` ("CPU only" in Settings still forces the CPU). Whisper
  (faster-whisper / CTranslate2) has no AMD / Intel GPU path, so the issue stays open as
  enhancement for that part. The Settings screen still says "no GPU" on these PCs (UI text, 11
  locales): left for a later phase.
- **Labels**: #16 got `bug`; #20 `enhancement` -> `bug` (it is a broken promise in the README);
  #10 got `enhancement`. The others already had fitting labels.
