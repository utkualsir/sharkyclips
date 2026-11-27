# Phase D4 (1.2.74): logo, website, feedback, extension stores, full test

## Kısa rapor (Türkçe)

**Sürüm 1.2.74 yayında** (etiket v1.2.74, GitHub sürümü, CI ve kurulum dosyası testi).

**Neler değişti**
- **Logo:** uygulama ikonu, saatin yanındaki ikon, kurulum görselleri, açılış ekranı, slayt gösterisinin
  sonu, site ve favicon'lar artık uygulamanın Klasik görünümünde. `docs/logo-120.png` değişmedi.
- **Web sitesi (docs/site):** 11 dilde 88 sayfa: ana sayfa (tek cümlelik özet, büyük İndir düğmesi,
  3 adım, kısa demo, ekran görüntüleri), özellikler (slayt gösterisi, TikTok yardımcısı, kişiselleştirme
  dahil), indirme (sistem gereksinimleri, SmartScreen yardımı), SSS, güncellemeler, gizlilik, koşullar,
  iletişim; dil seçici, koyu/açık tema. SEO (başlık, açıklama, OG görseli, sitemap, robots, yapılandırılmış
  veri), harici font veya izleyici yok. Erişilebilirlik testi (axe) 88 sayfada iki temada da temiz,
  Lighthouse mobil ve masaüstünde 96-100. Google'ın incelediği gizlilik metni korundu, yalnızca değişen
  gerçekler düzeltildi (diğer dillerde çevrilmiş özet + bağlayıcı İngilizce metin).
- **Geri bildirim:** Ayarlar > Hakkında'da "Hata bildir / Fikir öner" ve her hata mesajında "Bildir"
  düğmesi; önceden doldurulmuş GitHub formu açar (yalnızca sürüm ve sistem; hata metnindeki yollar,
  e-postalar, bağlantılar temizlenir). Sitede de aynı bağlantılar var. Hata ve özellik şablonları güncellendi.
- **Eklenti mağaza paketleri:** Edge ve Firefox paketleri hazır (GitHub sürümüne eklendi), mağaza
  metinleri ve görselleri hazır, gönderim rehberi: `docs/extension-stores.md`. Mağaza kopyası 6 haneli
  kodla bir kez bağlanır; gerçek Edge'de denendi. Firefox kullanıcıları da artık doldurma alabilecek.

**Bulunan ve düzeltilen hatalar** (her birine test eklendi)
- Kaydırılmış bir sayfada pencereler ekran dışında, üst çubuğun altında açılıyordu.
- Rusça, telefon genişliğinde Ayarlar'daki bir seçim kesiliyordu.
- (Yayından önce yakalandı) Bu oturumdaki bir değişiklik yüzünden SharkyClips'in kendi Yardımcı kopyası
  tarayıcıya yüklenmiyordu; düzeltildi, gerçek Edge testleri 18/18 geçti.

**Testler:** tüm test paketi (~1290 test), gerçek tarayıcılı yardımlı yükleme testleri, ekran düzeni
(4 görünüm, 11 dil, 9 ekran boyutu, koyu/açık; ~4400 görünüm), önizleme = çıktı kontrolü, erişilebilirlik
(4 görünüm), Chromium/Firefox/WebKit, site kontrolleri. Gerçek hesaplara hiçbir şey yüklenmedi.

**Senin elle yapman gerekenler**
1. **Eklentiyi mağazalara gönder** (ücretsiz): `docs/extension-stores.md` adım adım anlatıyor
   (Edge Partner Center + addons.mozilla.org). Onay gelince söyle, uygulamadaki Firefox metnini ve siteye
   mağaza bağlantılarını ekleyeyim. Chrome Web Store isteğe bağlı (tek seferlik 5 $).
2. **GitHub sosyal önizleme görseli:** repo Settings → General → Social preview → `docs/social-preview.png`
   yükle (yeni Klasik görünüm).
3. İstersen sitedeki ekran görüntülerine ve dil metinlerine bir göz at; yerel konuşucu düzeltmeleri
   `docs/sitegen/i18n/<dil>.json` dosyalarında.

## Decisions log

### 1. Logo
- `installer/make_icons.py` now draws the Classic look (themes.css `--mark-*`): navy rounded tile
  `#0E1A33` with a thin `#2B3E66` border, white fin, blue `#5B9BFF` water line; light version = white
  tile, blue fin. The tile proportions copy the header logo (30 px tile, 20 px mark, 8 px radius). At
  16-32 px the mark is drawn bigger (GLYPH_SMALL) so the favicon / tray icon stays readable.
- Regenerated: app icon (.ico/.icns/.png), tray icon, PWA icons, favicons, Inno wizard images, the
  website's icons, and the photo slideshow's logo outro (slideshow.py, same constants, test checks).
- The launcher splash already followed the theme (welcome.SPLASH_DEFAULT is Classic): no change.
- `docs/logo-120.png` (Google brand review) is untouched: only `--google` redraws it (md5 checked).

### 2. Website (docs/sitegen -> docs/site)
- One Python generator (`docs/sitegen/build.py`) + one JSON text file per language. The build fails on a
  missing key or a changed `{placeholder}` in any language, so a half-translated site can't ship.
- English at the site root (so `privacy.html` / `terms.html` keep the URLs Google knows), the other 10
  languages in `/<lang>/`. No automatic redirect by browser language (search engines crawl in English);
  a small dismissable "this page is also in X" bar instead. The choice is remembered in localStorage.
- Pages: Home (one-sentence promise, big Download button, 3 steps, demo video, screenshots, features,
  the reviewed "How SharkyClips uses YouTube" section), Features, Download (requirements, SmartScreen
  help, SHA-256), FAQ (FAQPage data), Updates (last 12 versions from CHANGELOG.md in that language),
  Contact, Privacy, Terms, 404.
- Legal pages: the English text Google reviewed stays as it is. Only facts that changed were fixed:
  projects folder (Videos\SharkyClips with the installer), photos/slideshows, first-run component
  downloads, channel monitoring, the SharkyClips Helper (fills the page, never posts, talks only to
  127.0.0.1), Instagram automation switched off, the feedback button, the site's localStorage, a missing
  ")" and the "last updated" date. Other languages show a translated summary plus the full English text
  marked `lang="en"` as the binding version (no machine-translated legal text).
- One language-neutral Open Graph image (logo, name, English line, screenshot) for every language;
  titles/descriptions are translated per page.
- Screenshots and the demo video come from a throwaway SharkyClips on a fresh settings folder with the
  synthetic demo stream (docs/demo/make_demo.py) and the drawn slideshow photos: no real person, game or
  account. `docs/sitegen/capture-site.mjs` retakes them.
- No external fonts, scripts or trackers (test_website.py checks). No personal e-mail on the site or in
  the app (privacy): contact goes through GitHub issues and GitHub's private security reporting.
- Checks: `docs/sitegen/check-site.mjs` = axe (WCAG 2.1 A/AA + best practices) on all 88 pages in dark
  and light, sideways scroll at 360 px, console errors, broken internal links: all clean. Phones at
  320 px: no sideways scroll on any page. Lighthouse (headless Edge, local server): 96-100 in
  performance, accessibility, best practices and SEO on mobile and desktop for every tested page; the
  only remaining hints are compression/caching, which GitHub Pages provides.

### 3. Feedback
- `frontend/src/feedback.ts` builds a pre-filled GitHub issue URL: app version + a short OS label from
  the server (`feedback.system_label()`, e.g. "Windows 11 (AMD64, build 26300)"; no user/computer name,
  no paths). For an error, the message is added after scrubbing paths, e-mails, links and long ids.
  Nothing is sent by the app: the person submits the form on GitHub.
- Buttons: Settings → About (Easy and Pro) "Report a bug" / "Suggest an idea"; every error toast gets a
  "Report" button. The website's Contact page links the same forms (`source=website`).
- Issue templates: bug (what, steps, version, os, mode, hardware, logs, source) and feature (area list
  updated), config links to the FAQ and private security reporting. The `os` field is now a text input
  so the app can fill it in.
- E-mail link: not added (the only address available is the owner's private one).

### 4. Extension store packages
- A store copy can't carry the per-install key (`config.js`). It pairs once: Settings → Helper guide →
  "Show connection code" (6 digits, 10 minutes, 5 tries, one use). `/api/assist/ext/pair` is the only
  key-less path and only answers an extension origin (`chrome-extension://`, `moz-extension://`).
- bg.js works as a service worker (Edge/Chrome) and as a Firefox background script; the key comes from
  config.js (SharkyClips' own copy) or from storage (paired store copy). New toolbar popup with status
  and the code field, 11 `_locales`.
- Two copies in one browser: only the first copy that has its key fills the page (DOM mark).
- Firefox fills once the store add-on has spoken to SharkyClips from there (`can_fill`).
- `installer/build_extension.py` makes reproducible Edge / Firefox / source zips and refuses a package
  with config.js, remote code or a host permission beyond 127.0.0.1/localhost. Firefox: gecko id
  `sharkyclips-helper@utkualsir.github.io`, `data_collection_permissions: none`, min Firefox 142;
  `web-ext lint`: 0 errors, 0 warnings. Real headless Edge: the Edge package paired (wrong code refused,
  right code connected).
- Store texts, images and the step-by-step guide: `docs/extension-stores.md`, `docs/extension-store/`.

### 5. Full test (in progress)
- Bug found and fixed: dialogs on a scrolled page opened off-screen under the top bar. `.page-fx` (the
  page-enter animation) kept an identity transform (`animation-fill-mode: both`), which made it the
  containing block of every `position: fixed` dialog. Now `backwards` (also on the top bar items and the
  welcome body). Regression test: test_dialog_position.py.
- Bug found (introduced in this session, never shipped) and fixed: SharkyClips' own unpacked copy of the
  Helper got a `_locales/` folder but its manifest had no `default_locale`, so Chromium refused to load
  it and every assisted upload would have waited forever (the 4 real-Edge tests timed out). Manifest now
  has `default_locale: "en"`; test_extension_store.py checks it, and a direct headless-Edge load
  confirmed the service worker starts.

## Release
Done 2026-11-27: v1.2.74 tagged and pushed, GitHub release with the extension zips, CI green (the Windows
backend job first failed on a Chocolatey 503 while installing FFmpeg, before any test; green on re-run),
Windows installer workflow green (clean install / launch / uninstall), website published and checked live.
Extra checks after the resume: layout-check in the 8 other languages found a cut-off Russian choice on
phones (fixed, test_phone_choices.py); preview-check OK; axe OK (224 views, 4 presets); Chromium, Firefox
and WebKit OK (one WebKit run reported cancelled requests during navigation; two re-runs clean).
No SharkyClips was running on 8000-8010 at release: nothing to restart.
