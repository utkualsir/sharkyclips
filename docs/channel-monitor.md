# Kanal izleme (channel monitoring), 1.2.57

## Kısa rapor (Türkçe)

**Ne çalışıyor**
- **Ayarlar > Kanallar** (Pro ve Kolay mod) ve Kolay mod ana ekranında **"Kanalımı bağla"** kartı:
  Kick, Twitch veya YouTube kanalı link ya da adla eklenir; avatar, ad, canlı durumu görünür.
  Kanal başına: içerik türü ve oyun (varsayılan otomatik), otomatik yayın (varsayılan **kapalı**),
  kaynak videonun ne olacağı (varsayılan: kliplerden **7 gün sonra çöp kutusuna**), "Bu benim kanalım",
  izlemeyi duraklatma, "Şimdi bak", **"Son X yayını içe aktar"**, kaldır.
- Kanal eklenince **eski yayınlar işlenmez** (o anda canlı olan yayın sayılır).
- Algılama: yayındayken / yayın bittikten sonraki 3 saat / VOD hâlâ hazırlanırken **5 dakikada bir**,
  diğer zamanlarda **30 dakikada bir**; ±%10 sapma, hata olursa 5 dk·2ⁿ (en fazla 6 saat) geri çekilme,
  HTTP 429'da Retry-After'a uyulur. Geç gelen VOD, hazırlanan VOD, silinen VOD (3 bakışta yoksa),
  abonelere özel / yaş sınırlı VOD (açık notla atlanır), 6 saat+ yayın (disk tahmini) ele alınır.
- Bilgisayar kapalı / uykudaysa uyanınca **kaçan yayınlar en eskiden başlayarak** işlenir.
- İşleme: **aynı anda tek indirme**, kaldığı yerden devam (yt-dlp parça dosyaları + sabit proje kimliği),
  bitince **süre kontrolü** (yayının en az %90'ı). Başlamadan önce: kuyruk duraklatılmış mı, **oyun açık mı**,
  **ölçülü bağlantı** (varsayılan: duraklat), **boş disk** (yayın süresine göre tahmin + 5 GB pay; yetmezse
  bir kez uyarır ve bekler). Sonra normal Kolay mod hattı: sohbet tekrarı (heyecan sinyali), bipler ve
  render sonrası bip kontrolü, senin tarzında başlıklar, kapaklar, oyun algılama, Hafif ön ayar, governor.
- Aynı VOD **asla iki kez** işlenmez (VOD kimlikleri kalıcı saklanır; kanal silinip yeniden eklense bile).
- Klipler hazır olunca: **"Yayının bitti, 6 klip hazır."** (sistem tepsisi + eşleştirilmişse Telegram).
  Kütüphane her klibin hangi kanal ve yayından geldiğini gösterir.
- Başkalarının kanalları: **"Benim değil"** işaretli, izin notu gösterilir, otomatik yayın varsayılan kapalı.

**Gerçekten test edilenler**
- Senin kanalın `kick.com/utkualsirr` gerçek ağla bulundu (ad, avatar, VOD açık, şu an VOD yok).
- Herkese açık 10 dakikalık bir Kick VOD'u (ElZeein, "HOY COMENZAMOS EL GTA V") ayrı, geçici bir
  ayar klasöründe çalışan gerçek bir sunucuda baştan sona: algılama → sıra → indirme → klipler.
  **Sonuç: başarılı.** VOD algılandı, sıraya girdi, indirildi (440 MB, 597,6 sn; süre kontrolü geçti),
  Kolay mod hattı çalıştı (yazıya çevirme, klip bulma, başlıklar, ses ayrıştırma, küfür kontrolü,
  3 klip render + bip kontrolü) ve bildirim geldi: **"ElZeein yayını bitti, 3 klip hazır."**
  Proje kanal ve yayın bilgisini taşıyor, tam video YouTube'a yüklenmedi. Hiçbir şey yayınlanmadı.
- Bu test, **bugün tüm Kick VOD içe aktarmalarını bozan bir hata** buldu: yt-dlp'nin Kick çıkarıcısı ve
  uygulamanın yedek uç noktası "NOT_FOUND" diyor, uygulama da herkese açık VOD'a yanlışlıkla "abonelere
  özel" diyordu. Düzeltildi (kick.com/api/v1/video). Aynı testte Kick **sohbet tekrarının boş** geldiği
  görüldü (uç nokta artık sohbet odası değil kanal kimliği istiyor); düzeltildi, aynı VOD'un ilk dakikasında
  85 mesaj geldi.
- Sahte uç noktalarla 40'tan fazla test: canlı → bitti → geç gelen VOD, silinen VOD, abonelere özel, ağ hatası,
  hız sınırı, disk dolu, uyku sonrası telafi, mükerrer koruması, yeniden başlatma, API.

**Sınırlar**
- Bilgisayarın açık ve SharkyClips'in çalışıyor olması gerekir (sunucu tarafı izleme yok).
- Resmî API'ler kullanılmadı: Kick'in resmî API'si ve Twitch Helix bir geliştirici uygulaması
  (client id/secret) ister, YouTube Data API anahtar/kota ister; bunlar senin hesabını gerektirdiği için
  atlandı. Bunun yerine herkese açık sayfalar kullanılıyor; bunlar belgelenmemiş olabilir ve platform
  değiştirince bozulabilir (o zaman hata görünür ve geri çekilerek tekrar denenir).
- Abonelere özel, üyelere özel ve yaş sınırlı VOD'lar bilerek indirilmez (giriş/çerez yok).
- Twitch'te "Geçmiş yayınları sakla" açık olmalı; Kick ve Twitch VOD'ları sınırlı süre saklar.
- YouTube RSS en yeni 15 videoyu gösterir; YouTube sohbet tekrarı yalnızca canlı yayınlarda vardır.
- Oyun oynarken yeni indirme başlamaz; zaten süren bir indirme durdurulmaz (ağır işleri governor duraklatır).
- Otomatik yayın Otopilot yolunu kullanır (YouTube planlama, günlük limitler); TikTok/Instagram için
  normal Yayınla akışı geçerlidir.

---

## How it works (English, for developers)

Files: `backend/sharkyclips/channels.py` (store, platform adapters, decisions; pure functions with an
injectable HTTP client and clock), `backend/sharkyclips/web/channels_api.py` (background loop, job
hooks, notices, REST API), `frontend/src/components/Channels.tsx`. State: `<settings>/channels.json`
(`channels`, `vods` keyed `"<platform>:<id>"`, a 200-entry `log`). Tests: `backend/tests/test_channels.py`
with `backend/tests/fake_channels.py`.

VOD states: `baseline` (back catalog) · `live` / `processing` / `upcoming` (watched) · `queued` / `retry`
/ `waiting_disk` / `waiting_metered` / `waiting_game` (waiting) · `downloading` · `clipping` · `done` ·
`skipped` / `gone` / `error` (final, "Try again" possible).

Flow: loop every 30 s → catch-up check → poll due channels (network outside the lock, merge under it)
→ oldest waiting VOD → gates → `app.submit_import(url, extra={"easy", "mode_auto", "channel_vod",
"expect_duration", "full_upload": False})` → the import verifies the length → `on_job_finished` tags the
project (`meta.channel`, channel game) → the normal Easy pipeline → `web/easy.on_job_finished` calls
`channels_api.on_clips_ready` (own notice, per-channel auto-publish) → `cleanup_sources` after keep days.

## Decisions log (unattended session, 2026-11-20)

Every decision taken without asking, with the reason.

1. **No official APIs.** Kick's public API (api.kick.com) and Twitch Helix need a registered developer
   app (client id + secret) on the owner's account; the YouTube Data API needs a key and quota. All three
   need the owner's account, so they were skipped. Used instead: Kick `kick.com/api/v2/channels/<slug>` and
   `/videos` (the same family the app already used for chat), Twitch GQL with the public web client id
   (already used by `chat.py`), YouTube channel page (consent cookie) + public RSS feed + yt-dlp metadata
   for new entries only (at most 4 lookups per poll). No login, no cookies.
2. **Intervals:** 5 min while live, for 3 h after a stream ended (late VODs) and while a VOD is
   processing; 30 min otherwise (all platforms). ±10 % jitter. Errors: 5 min · 2ⁿ, max 6 h. HTTP 429:
   at least Retry-After. The loop itself wakes every 30 s but only polls due channels.
3. **Back catalog:** a VOD that started before the channel was added and isn't live = `baseline`, never
   processed. A stream live at add time counts (it ends afterwards). A stream first seen as a live
   stand-in (no VOD id yet) keeps counting when its VOD appears, even if it started before the add.
4. **Deleted detection:** a VOD gone from a not-full listing on 3 polls in a row = deleted (one miss could
   be a hiccup). A full page (Kick/Twitch ≥ 20, YouTube 15) can't prove deletion of older items.
5. **Download order:** one at a time, oldest stream first (catch-up order). GPU work of the previous VOD
   may overlap the next download (different job lanes).
6. **Gates:** queue paused; a game from the governor's list running (only in the governor's Silent mode,
   like its own pauses; a running download isn't killed, heavy jobs pause through the governor);
   metered connection via Windows' NetworkCostType (Fixed/Variable), cached 10 min, **pause on by
   default**; disk: 1 MB per stream second (≈3.6 GB/h) + 5 GB reserve, warns once per VOD and waits.
7. **Verification:** the imported file must be ≥ 90 % of the stream's length, else the partial source
   goes to the trash and the VOD is retried. Up to 4 attempts, 15 min · 2ⁿ apart.
8. **Failure classes:** login / subscriber / age markers → `skipped` (clear note); deleted / not found →
   `gone`; disk full → `waiting_disk`; else retry. Cancel in the queue = `skipped` (Cancel is final).
9. **No full-video upload** for channel VODs (`full_upload: False`): re-uploading a whole stream to
   YouTube is a big action nobody asked for here.
10. **Auto-publish:** per channel, off by default, off for other people's channels unless switched on.
    When on: `autopilot.on_clips_ready` with the top `watch_publish_top` clips (default 3), `when="auto"`
    = the normal planning and daily limits.
11. **Source video:** through `trash.trash_source` (CLAUDE.md: deletes go through trash.py), a restorable
    cleanup item that stays at most 2 days in the trash (so the space really comes back); default 7 days
    after the clips, options 0/1/3/7/14/30 days or keep. The browser proxy copy goes with it. Never while
    a job of that project is active.
12. **Notices:** kind `channel_ready` (tray) + `phone.send_text` (Telegram, if paired and sending is on);
    the generic "clips ready" notice and the OBS auto-clip publish rule are skipped for channel VODs; the
    phone still gets its clip cards. Disk-low notice once per VOD; skipped / failed: tray only.
13. **Library:** project `meta.channel` (platform, name, own, stream title, start) → shown in the project
    cards, Easy library, clip library and Easy home recents.
14. **Game per channel:** written to `meta.game` after the import (only if the project has no explicit
    choice); "auto" keeps the detector, which already uses Kick's category as a hint.
15. **Content type:** "auto" = the Easy detector (`mode_auto`), else the chosen mode.
16. **YouTube kinds:** live streams + uploads by default (the request); uploads/Shorts shorter than the
    minimum (5 min) are skipped.
17. **Limits:** 20 channels; `channels.json` keeps ≤ 3000 VOD records (never drops done/downloading ones).
18. **Broken IPv6 (found on the dev PC):** each IPv6 connection to Kick waited ~10 s before IPv4. One
    2.5 s probe per run; if IPv6 fails and IPv4 works, urllib3 goes IPv4-only and yt-dlp gets
    `source_address=0.0.0.0`. First Kick call 13.2 s → 4.6 s.
19. **Kick VOD download bug (found by the real test):** yt-dlp 2026.10.26 `kick:vod` and
    `web.kick.com/api/v1/stream/<id>/playback` answer NOT_FOUND for public VODs; the app then said
    "subscriber-only". `kick.com/api/v1/video/<uuid>` still returns the public HLS `source`: `kick.resolve`,
    `canonical` and the chat replay timing use it first. This also fixes manual Kick imports.
20. **Skipped, needs the owner:** official API apps (see 1); publishing anything (the real test published
    nothing; auto-publish stays off); OAuth for subscriber-only VODs (never, by design).
21. **Real test setup:** a throwaway settings folder (scratchpad) and server on port 8811, never the
    user's app or settings. The channel was stored with its baseline 60 s before the chosen VOD (as if it
    had been added before that stream), so the normal detection path picked it up; the newer multi-hour
    streams of that channel were skipped through the API.

22. **Kick chat replay (found by the real test):** `kick.com/api/v2/channels/<id>/messages` returns an
    empty list for the chatroom id and the messages for the channel id; `kick.chat_plan` uses the channel id.
23. **Governor during the real test:** the throwaway server paused for ~15 min because a video played in
    Chrome on this PC (Silent mode, as designed). Only that throwaway server was then set to Balanced
    (low priority, throttled) to finish; the user's own settings were not touched.
24. **Layout fixture:** two channels (own live Kick, someone else's paused YouTube) with every finished
    state; nothing in it can go online or start a download (next check in 2100, no waiting VOD of an
    enabled channel). Its first version pointed a "done" stream at the layout project with a September
    date, so the monitor correctly trashed that project's source 7 days "after the clips": the fixture
    channel now keeps its sources.

## Real test (2026-11-20)

Throwaway settings folder + server on port 8811, real network, no publishing.

| Step | Result |
|---|---|
| `kick.com/utkualsirr` lookup | found: name, avatar, `vod_enabled`, not live, 0 VODs right now |
| Channel listing (ElZeein) | 23 entries incl. one live; the target VOD (10 min, "HOY COMENZAMOS EL GTA V") queued, the newer multi-hour ones skipped via the API, the live one tracked |
| 1st download | failed: yt-dlp `kick:vod` NOT_FOUND, old fallback said "subscriber-only" -> classified `skipped`, Turkish tray notice "Yayın atlandı" (correct handling of a wrong message) |
| Fix + "Try again" | downloaded via `kick.com/api/v1/video` HLS: 440 MB, 597.6 s of 598 s (verified) |
| Easy pipeline | transcribe, highlights, titles (local LLM), voices, proofread, swear scan, 3 renders + bleep check |
| Finish | VOD `done`, 3 clips, `meta.channel` set, full upload `skipped`, notice "ElZeein yayını bitti, 3 klip hazır." |
| Total | ~30 min (15 of them paused by the governor for a video in Chrome) |
| Chat replay | 0 messages (bug, see 22); after the fix 85 messages in the first minute of the same VOD |

Not tested for real: Twitch and YouTube downloads (adapters tested against fakes built from real answers
of 2026-11-20; lookups / listings of both answered for real during development), Telegram (no phone
paired in the throwaway folder), a real metered connection, a real sleep/wake (fake clock).
