# Phase B notes (1.2.59)

## Kısa rapor (Türkçe)

**Sürüm 1.2.59**: iki iş bitti. Testler, düzen (layout), erişilebilirlik (axe) ve yeni mini oyun
tarayıcı kontrolü yerelde geçti; CI sonucu aşağıda.

1. **Beklerken mini oyun: "Shark Snack".** Bir proje işlenirken (Kolay ve Pro modda) sol altta küçük
   bir "Beklerken oyna" düğmesi çıkıyor. Kompakt panel üst çubuğu ve iş ilerlemesini kapatmıyor, işin
   ilerlemesini kendisi de gösteriyor. Köpekbalığı küçük balıkları yiyip büyüyor; büyük balıklar,
   kırmızı gözlü avcılar, denizanaları ve dikenli kestaneler can yakıyor; kombo, baloncuk güçleri
   (mıknatıs, çift puan, kalkan, +5 sn), giderek artan zorluk, 30-90 sn turlar, 3 can. Parçacıklar,
   hafif ekran sarsıntısı (hareket azaltılınca yok), sentezlenmiş sesler (varsayılan kapalı), en iyi
   skor + bugünün en iyisi, oynayarak açılan 7 görünüm, ilk açılışta "nasıl oynanır". Klavye, fare,
   dokunma. Reklam, satın alma, seri baskısı yok; tüm çizim ve sesler kodla üretiliyor (resim/ses
   dosyası yok). Ayarlar'dan kapatılabiliyor, oradan "Şimdi oyna" ile her zaman açılabiliyor.
   - **İşlemeyi yormaz:** sadece tur oynanırken çalışıyor; panel gizlenince, pencere arka plana
     geçince ya da odak kaybolunca (ör. Delta Force'a geçince) duruyor. 60 fps sınırı, yavaşlarsa
     görüntü sadeleşiyor. Ölçüm (Edge): kare başına ~0,22 ms, oynarken ana iş parçacığı ~%5-6,
     gizliyken ~%0,3. Oyun kodu ayrı bir parça olarak sadece açılınca yükleniyor (33 KB JS + 4 KB
     CSS, kurulumu neredeyse hiç büyütmüyor). İnternete hiçbir istek yok.
   - **Tuşlar:** oyun panelinde odak varken A / X / Boşluk / ? vb. uygulama kısayollarına asla
     ulaşmıyor; oyun kapalıyken veya odak dışarıdayken de oyun hiçbir tuşu duymuyor (tarayıcı
     testiyle iki yönde doğrulandı).
   - **İş bitince:** panelde "Kliplerin hazır!" bildirimi; "Kliplerimi göster" projeyi açıyor, "Oynamaya
     devam" turu sürdürüyor. Skor korunuyor. Panel kapalıysa düğmenin kendisi kliplere götürüyor.
2. **Faz A devamı: HUD bölgeleri.** Oyun profilleri artık kill akışı, skor, mini harita vb. bölgeleri
   işaretleyebiliyor (`hud_areas`); hareketli grafikler bunların üstüne asla gelmiyor. 16 profilin
   hepsi dolduruldu; beta/önizleme profillerindeki kutular tahmin ve `guess: true` ile işaretli.
   Delta Force'ta öldürme ikonları + puan satırları gerçek tarayıcı kutularından (doğrulanmış).
   **Belirgin + bölünmüş düzen hatası düzeltildi:** grafik artık alttaki Delta Force öldürme yazısının
   üstüne değil, aksiyonun üstündeki boş alana (gerekirse biraz küçülerek) geçiyor. Yan etki olarak
   Shorts/TikTok/Reels güvenli alanlı kliplerde daha önce hiç gösterilemeyen Belirgin grafikler artık
   gösteriliyor. Testler eklendi (16 profil × 3 düzen × 2 stil, hatanın kendisi dahil).

**Denemeler:** Delta Force projenin 3 klibi (c01, c06, c10) Belirgin + bölünmüş düzende önce (HUD
bilgisi yok, 1.2.58) ve sonra (HUD bölgeleriyle) yeniden render edildi. Kareler:
`workspace/_phase_b_frames/` (yüzün göründüğü için git'e eklenmedi). Önce: "3x KILL" oyunun
"Çifte Öldürme +20 DP" yazısını kapatıyor; sonra: yazı açıkta. Gerçek proje dosyalarına dokunulmadı
(geçici kopya, video sabit bağlantıyla).

**Senin yapman gereken:** hiçbir şey zorunlu değil. İstersen Ayarlar'da "Beklerken mini oyun" →
"Şimdi oyna" ile dene.

---

## Decisions log (English)

Unattended work: every choice that would normally be a question is recorded here.

### Mini game
- **Name:** "Shark Snack" (original; kept untranslated as a name in all 11 languages, like a title).
  All art is drawn on a 2D canvas in code (shark, fish, a barracuda-like hunter, jellyfish, urchins,
  bubbles, light rays, kelp); sounds are WebAudio oscillators. No image, sound or font files.
- **Where:** a pill button at the bottom inline-start corner (bottom-left; bottom-right in Arabic so
  it mirrors the layout and never meets the toasts at the other corner). Shown while any job with a
  project is queued/running, except background upkeep jobs (stats refresh, publish queue, posts,
  updates, setup, benchmark). Both Easy and Pro mode. The panel also shows the running job's label and
  progress, so it never hides the progress you are waiting for.
- **Settings:** one switch (`minigame` in the Easy settings API, config `minigame_enabled`, default
  on) in Easy Settings and in a small card in Pro Settings, with "Play now" to open the game anytime.
  The browser checks use "Play now" because the CI fixture has no running job.
- **Numbers are stored by the local server** (config key `minigame`), not in localStorage: the app
  can run on ports 8000-8010 (different browser origins) and the player may switch browsers. This is
  the only server traffic, to localhost. "No network" = nothing goes to the internet (checked: the
  game code has no fetch/URLs; the browser check fails on any outside request except the app's own
  UI fonts, which predate the game).
- **Today's best** uses the player's local date sent with each round; only the latest day is kept
  (no history, no streaks). Skins: Classic (free), Reef (3 rounds), Tiger (3000 in a round), Neon
  (250 fish in total), Ghost (x15 combo), Deep sea (15 rounds), Gold (8000 in a round). Thresholds
  were tuned with a simple bot over 30 simulated rounds (average ~6000 points).
- **Rules:** 60 s rounds; golden fish +2 s, clock bubble +5 s, never more than 90 s in total; 3
  lives; a too-big normal fish just bumps you, hunters / jellyfish / urchins cost a life (and a bit of
  size and the combo). Combo multiplier x1-x5 every 4 quick bites; frenzy doubles.
- **Performance design:** the engine is pure TS with fixed 1/60 s steps (max 4 per frame, then skip);
  rAF capped at 60 fps also on 120/144 Hz screens; hard caps (22 fish, 7 hazards, 2 power-ups, 160
  particles); adaptive quality (fewer particles, no light rays) after 20 slow frames (> 6 ms);
  canvas pixel ratio capped at 1.5; the loop only runs in the "play" state of an open, visible,
  focused panel; start/pause/end screens are a single still frame. Pauses on `visibilitychange`,
  window `blur` and panel hide.
- **Budget tests:** `test_minigame.py` runs the engine with Node over 60 bot rounds (average step
  < 0.05 ms, 99th percentile < 0.5 ms; measured ~0.003 ms) and checks the built chunk (< 45 KB, not
  in the start bundle). The single-step maximum was dropped as a metric: one GC/scheduling stall of
  108 ms appeared while browser checks ran at the same time. `minigame-check.mjs` (CI Layout job)
  measures the real browser: frame cost < 6 ms, fps capped, main-thread CPU < 50 % playing (CI runs
  software rendering; locally ~5-6 %) and < 6 % hidden (locally 0.3 %).
- **Keys:** `keyguard.ts` adds window capture listeners before React mounts; keys whose target is
  inside `[data-game-root]` go only to the game's handler and stop there (`stopImmediatePropagation`;
  default actions kept, so Tab and Enter/Space on buttons still work). The game never listens on
  window itself. Verified in the browser on the Pro Project page (?, A, X, Space, J/K/L, F, I, O in the
  game: no dialog, no decision; P outside the game: the game doesn't react; ? outside: the app's sheet
  opens).
- **When the job ends:** an in-panel alert (pauses the round, the score is kept) with "See my clips"
  and "Keep playing"; on failure "Processing stopped" + "Open the project". If the panel is closed,
  the dock button turns into "See my clips". The toast is only for projects that were processing
  while the game was open (no surprise popups for people who never opened it). This flow was not
  driven end to end in the browser (the CI fixture has no short real job); the logic is small and
  reviewed, noted as a gap.
- **Accessibility:** pause / sound / how-to / hide buttons with labels, `role="application"` game
  area with a description of the controls, readable HUD text in the DOM (not on the canvas), a polite
  live region for "round over" and "clips ready", focus moves into the game on open. Reduced motion:
  no shake, no flashes, fewer particles. axe: how-to, skins (Pro) and paused round (Easy), both themes.

### HUD areas (Phase A follow-up)
- Profile field `hud_areas: {name: {box [x,y,w,h] on 1920x1080, label, guess}}`, names from a fixed
  list (kill_feed, kill_text, score, minimap, health, ammo, abilities, timer, objective, chat,
  scoreboard; `.2` suffix for a second box), one box at most a fifth of the screen. Documented in
  docs/ADDING_A_GAME.md.
- Boxes are mapped per layout into the clip: split = through the gameplay crop (parts cut away are
  dropped), fit = the picture band, crop = the filled picture (a tracking crop excludes the whole
  height band); with zoom / shake both the normal and the 1.25x zoomed place count.
- Verified profiles (Delta Force, LoL): the boxes the built-in scanners already use are
  `guess: false` (DF event icons + score lines; LoL team score / KDA, announcer, ability bar); every
  other box, and all boxes of beta/preview profiles, are `guess: true` (a test enforces this).
  Short-lived kill banners the OCR profiles already know (Fortnite / PUBG / Valorant / Overwatch
  kill texts, Warzone medals) were reused as `kill_text`.
- The Bold fix: `place()` now tries 100 %, 88 %, 76 % size before skipping a graphic. Unknown games
  (no HUD info) keep the old placement whenever the full size fits.
- The HUD list is part of the graphics fingerprint, so clips re-render when a profile's HUD changes.
- Delta Force frames: rendered from a scratch copy (video hard-linked, never written), without the
  bleep re-check pass (not needed for still frames). Added a guessed DF "objective" box after seeing
  the objective bar at the top of the gameplay picture in the real frames.

### Skipped / needs the user
- Nothing needed the user's accounts. Making the repo public stays with the user.
