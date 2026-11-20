# Phase A notes (1.2.58)

## Kısa rapor (Türkçe)

**Sürüm 1.2.58** — üç iş bitti, testler, düzen (layout), erişilebilirlik (axe) ve önizleme kontrolleri geçti.

1. **Varsayılan dil İngilizce.** Bu zaten 1.2.53'ten beri böyleydi; şimdi testlerle güvence altında:
   yeni kurulum İngilizce açılıyor, senin gibi dil seçmiş kullanıcıların dili (`tr`) hiçbir kayıtta,
   onboarding atlamasında veya "görüldü" çağrısında sıfırlanmıyor. Dil düğmesi ana ekranda, üst
   çubukta ve artık Pro kütüphane başlığında da var. Arayüz metinlerindeki son iki "tr" geri
   dönüşü İngilizce yapıldı.
2. **Güncellemeler sayfası.** Menüde (Kolay + Pro) yeni **Güncellemeler** öğesi; güncellemeden sonra
   sayfa açılana kadar küçük "Yeni" rozeti. Ayarlar > Hakkında'da ve alt bilgide bağlantı. Tüm
   sürümler en yenisi başta: tarih, 1-2 satır özet, açılır ayrıntılar (Yeni / İyileştirmeler /
   Düzeltmeler), arama, UI dilinde (çeviri yoksa İngilizce). "What's new" penceresi aynen duruyor.
   **CHANGELOG.md yeniden yazıldı:** 60 sürümün hepsine basit İngilizce özet + gruplanmış ayrıntılar,
   11 dilde özet, Türkçe ayrıntılar da gruplu; dosya adları ve teknik jargon temizlendi (test
   kontrol ediyor). CLAUDE.md'deki CHANGELOG kuralı yeni biçime göre güncellendi.
3. **Kliplerde hareketli grafikler.** Kill sayacı (artarak sayar), multikill / ACE / CLUTCH vb.
   bantları, raund / maç sonuçları, transkriptten söylenen büyük sayılar ("21 KILL", "1v4"), basit
   simgeler, marka renkleri. Stiller: Sade (varsayılan) / Belirgin / Kapalı; Kolay modda tek anahtar.
   Her oyun için eşleme oyun profillerinde (`graphics`, 16 profilin hepsi). Aynı anda tek grafik,
   en fazla 1,5 sn; yüz kamerası, altyazı, başlık/bant, oyun görüntüsünün ortası, sohbet
   baloncukları, bip rozeti ve platform düğmeleri (Shorts/TikTok/Reels) asla kapanmıyor. İşlemcide
   çiziliyor (libass), Hafif ayarda basit geçişler. Önizleme render ile birebir: aynı fonksiyon her
   karede (Python + TS kopyası, testli; CI önizleme kontrolüne grafik adımı eklendi). Altyazı ve bip
   zamanlaması değişmiyor (testli).

**Denemeler:** Delta Force projende (gerçek video) 3 klip render edildi, önce/sonra kareleri
`workspace/_phase_a_frames/` klasöründe (yüzün göründüğü için git'e eklenmedi). **LoL projelerin
çöp kutusunda ve videoları silinmiş** — geri yüklemedim; onların gerçek olay verisiyle (sadece olay
kodları ve zamanlar) test yazdım, görseller için sentetik video kullandım. Ek olarak VALORANT ve CS2
profilleri sentetik videoda denendi: kareler `docs/phase-a/frames/`.

**Senin yapman gereken:** hiçbir şey zorunlu değil. Bakmak istersen: Ayarlar > Kolay modda
"Hareketli grafikler" anahtarı; Pro'da efektlerin altında stil seçimi. Eski Kolay projeleri
görünümünü korur (anahtara dokunana kadar grafik eklenmez), yeni projeler Sade ile gelir.

**Bilinen sınır:** Belirgin stil büyük olduğu için bölünmüş (split) düzende alta yerleşiyor ve
bazı oyunlarda oyunun kendi alt HUD yazısının (ör. Delta Force puan satırı) üstüne gelebiliyor.
Öneri (sonraki faz): oyun profillerine "HUD bölgesi" ekleyip grafiklerin oradan da kaçması.

---

## Decisions log (English)

Work was unattended; every choice that would normally be a question is recorded here.

### Task 1: English by default
- Found the default was already English since 1.2.53 (`languages.DEFAULT_UI_LANGUAGE = "en"`, i18n
  `DEFAULT = "en"`). Existing users keep their choice because `config.save()` always writes the full
  config, so anyone who ever saved has `ui_language` stored. No migration needed; added regression
  tests (`test_english_default.py`) instead of changing behaviour.
- Changed the two remaining UI-text fallbacks that still defaulted to Turkish (`pubqueue.calendar_md`,
  `fullvideo.link_line` with no language). Left content-language fallbacks in the Turkish-only
  Channel style feature alone (it is Turkish by design).
- Added the language switcher to the Pro library header so "home screen" holds in both modes.

### Task 2: Updates page + CHANGELOG
- Source of truth stays CHANGELOG.md (one file, already shipped with the app). New format per entry:
  summary paragraph, `### New / Improved / Fixed`, the same in Turkish (`Yeni / İyileştirmeler /
  Düzeltmeler`), other languages in `<details>` blocks. `welcome.GROUP_HEADINGS` knows the heading
  words in all 11 languages (with the Turkish dotted-İ casefold quirk handled).
- Rewrote all 60 entries with a script instead of retyping: each old section was assigned to
  New / Improved / Fixed (the parallel Turkish section moved the same way — section counts matched
  for every entry), jargon and file names were replaced bullet by bullet, and the four oldest,
  developer-oriented entries (1.0.0–1.2.1) were rewritten in plain English.
- Translations of OLD entries: every version got a 1–2 line summary in all 10 other languages. Their
  existing short translated notes stay as the details (shown under "Changes"); where a language has
  no notes (es/pt/fr/ja before 1.2.53, everything before 1.2.1) the details fall back to English with
  a one-line notice. Writing full grouped details in 10 languages for 60 old versions was not worth
  the size; new entries (1.2.58+) are fully grouped in every language.
- "New" badge: config `updates_seen`; new users are marked seen at onboarding; the page marks it
  seen when opened. Menu item added to both top bars (the nav scrolls when narrow, layout check OK).
- Group headings on the page are `h2` (axe heading-order).

### Task 3: animated graphics
- Rendered as ASS subtitle events drawn by libass (CPU; the subtitle pass already exists, so no new
  ffmpeg inputs and no GPU). For exact preview parity the motion is not ASS `\t`/`\move` easing:
  one event per output frame is generated from `graphics.state_at()`, and the canvas preview
  evaluates the TS copy (`previewMath.gfxStateAt`) at the same frame. Still parts collapse into one
  event. Pixel test: libass draws pill and icon within ~1 px of the plan.
- Light preset (`perf.light()`): fade-only (3 events per graphic). Reduced motion (OS/app setting)
  only affects the preview (fade only); the exported file is never changed by a UI setting.
- Placement is computed, not configured: exclusion rects for platform safe zones, captions (±130 px),
  hook/banner, facecam (split panel, or the cam rect inside fit/crop; the whole band when the crop
  tracks the action), the key action (middle 40 % × 40 % of the gameplay picture), chat bubbles and
  the bleep badge; spots are tried nearest to a per-layout anchor, centre preferred. If nothing fits,
  the graphic is skipped (never covers anything). Tested over every layout × safe zone × style.
- Only gaming clips. Banner texts are the games' own (English) terms in every UI language, as in the
  games themselves; no translation.
- Default `minimal` for ClipOptions (Pro) as asked. Easy mode: new projects get it; projects made
  before 1.2.58 keep their look until the switch is flipped (same rule as 1.2.17's effects) so
  nothing re-renders by surprise.
- Spoken numbers: digits / English + Turkish number words followed by a kill word (2–99), and
  duels `1v4`, `1 v 4`, `one versus four`, Turkish `1'e 4` (1–5 each). Conservative on purpose.
- Graphics never straddle an instant replay / freeze insert (they would be cut in two).
- Testing on the user's projects: the two League of Legends projects are in the trash with their
  videos deleted (deletes are intentional — not restored). Their real event data (codes + times
  only, no speech) is in `backend/tests/data/gfx_real_events.json` together with the Delta Force
  project's. Real Delta Force renders were made from a scratch copy (video hard-linked read-only);
  frames are in `workspace/_phase_a_frames/` (not committed: they show the user's facecam).
  Synthetic frames for LoL, VALORANT, CS2 and Delta Force event sets: `docs/phase-a/frames/`.
- Scratch-folder note: the temp cleaner deleted old-dated files of a scratch project copy during
  the session (copies keep their dates). Real project untouched; copies are now re-dated on creation.

### Skipped / needs the user
- Nothing needed the user's accounts. Making the repo public stays with the user.
- Follow-up idea: per-game "HUD regions" in profiles so graphics also avoid the game's own kill feed.
