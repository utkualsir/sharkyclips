# Phase D3: Photo slideshow (1.2.72)

## Kısa rapor (Türkçe)

**Ne yapıldı:** Yeni "Fotoğraf slayt gösterisi" özelliği. Kolay ve Pro modda ana ekranda ayrı bir
düğme var. 2–20 fotoğraf (JPG, PNG, HEIC, WebP) bırakılıyor; çekim tarihine göre (EXIF, yoksa dosya
tarihi) sıralanıyor, sürükleyerek ya da oklarla yeniden sıralanabiliyor. Çıktı: 1080x1920 H.264 +
sessiz AAC MP4 (Reels / Shorts / TikTok uyumlu, faststart, yuv420p). Her fotoğraf varsayılan 3 sn
(2–5 sn kaydırıcı), geçiş: yumuşak geçiş (varsayılan), kaydırma, yakınlaştırma. Hafif Ken Burns
zoom'u en fazla %6 (her kenardan en çok %3 dışarıda kalır, ortadaki %94 hep görünür). Dikey olmayan
fotoğraflar esnetilmeden sığdırılıyor, boşluk aynı fotoğrafın bulanık ve koyulaştırılmış kopyasıyla
doluyor. EXIF dönüşü düzeltiliyor. İsteğe bağlı kısa yazı (ör. "ÖNCE", "3. GÜN", "SONUÇ") ve tek
düğmeyle 11 dilde Önce / Süreç / Sonuç etiketleri; yazı uygulamanın kendi fontuyla (Archivo) ve
Shorts/Reels güvenli alanının içinde. Sonda ~1,5 sn'lik özgün, hareketli SharkyClips logo kapanışı
(varsayılan açık, kapatılabilir). Müzik eklenmiyor; dışa aktarma ekranında tek satırla söyleniyor.
Ön izleme (aynı render, 1/3 boyut, CPU, birkaç saniye) → dışa aktarma (NVENC, olmazsa CPU; yavaş
bilgisayarda x264'ün hızlı ayarı). Sonra Kaydet (İndirilenler/SharkyClips), Klasörü aç ve normal
Paylaş akışı (YouTube Shorts, Instagram/TikTok yardımlı yükleme veya elle), başlık/açıklama senin
tarzında (içerik dili, My style CTA satırı, Shorts için büyük harf + emoji + #Shorts).

**Nasıl test edildi:** 77 yeni test (`test_slideshow.py`): tarih/sürükle sıralaması, kaldır/geri al,
20 fotoğraf sınırı, bozuk dosyalar, EXIF dönüşü, 10 farklı/uç boyut (1x1, 7x5000, 5000x7 ...),
HEIC, süre matematiği (2–20 fotoğraf, 2–5 sn, logolu/logosuz), Ken Burns sınırı, 11 dilde etiketler,
güvenli alan, logo geometrisinin uygulama logosuyla aynı olması, logo animasyonu, 1080x1920 tam
render (ffprobe ile codec/profil/ses/süre/faststart), 20 fotoğraflık render, geçişler ve API'den
Paylaş panosuna kadar uçtan uca akış. Arayüz: 11 dil i18n kontrolü, layout kontrolü (yeni 3 ekran,
9 boyut, tr/ar/en, açık/koyu) ve axe erişilebilirlik kontrolü. Hiçbir gerçek hesaba bir şey
yayınlanmadı.

**Örnek video:** `docs/demo/slideshow-sample.mp4` (25,5 sn) — tamamen kodla çizilmiş "duvar fayansı"
resimlerinden (`docs/demo/make_slideshow_sample.py`), gerçek fotoğraf yok.

**Bilmen gerekenler:** HEIC için yeni bağımlılık `pi-heif` (güncellemede otomatik kurulur; kurulana
kadar HEIC dışındaki her şey çalışır). Etiketlerin dili "İçerik dili" ayarını izler (varsayılan
arayüz dili). Slayt gösterileri normal proje listelerinde görünmez, kendi ekranlarında listelenir.

## Decisions (logged while working unattended)

1. **A slideshow is a small project of kind "slideshow".** Its export is the project's one rendered
   clip (`c01`, `clips.json` + `highlights.json`). That way the existing Share board, the publish
   engine (YouTube upload, Instagram / TikTok assisted or by hand), the Library, History and the
   trash work without a second code path. The stream project lists (`/api/projects`,
   `/api/easy/projects`) leave slideshows out; they have their own list (`/api/slideshow`).
2. **Rendering = ffmpeg filter graph, not Python frames.** Each photo is composed once into a 9:16
   still (PIL: blurred fill + fitted photo + soft shadow), cached per photo and size. ffmpeg then
   loops each still, zooms it with `perspective` (sub-pixel, eval=frame: smooth, no 1-pixel steps
   like `zoompan`), joins the photos with `xfade` (fade / slideleft / zoomin), draws the text with
   libass and adds the outro. One encoder run; works on any PC, NVENC when it works.
3. **Timing rule:** photo k starts at k × seconds; its stream also covers the next transition
   (0.6 s, at most a third of a photo's time). Total = photos × seconds (+ 1.5 s outro). The
   duration shown in the UI is exactly the file's duration (tests check it with ffprobe).
4. **"Never cuts important parts":** the zoom is centred and capped at 1.06, so at most 2.8 % of each
   edge leaves the frame and the middle 94 % is always visible. Even photos zoom in, odd ones out.
5. **Font:** libass cannot read the UI's WOFF2 fonts, so the app ships a static Archivo ExtraBold
   TTF instance (OFL, 85 KB, Latin + Latin-ext: Turkish, Hungarian, French ... letters) as
   "Archivo SC". Russian, Arabic, Chinese and Japanese use a system font (libass shapes Arabic).
6. **Label style:** ink text on a sign-yellow box (the logo's colours), centred in the Shorts /
   Reels safe zone (70 / 250 / 170 / 520 px margins on 1080x1920), pops in after the photo settles
   and fades out into the transition. Long texts get a smaller size to fit one line.
7. **Labels language = content language** (the language SharkyClips writes titles in; by default
   the UI language), because the text is for the viewers.
8. **Outro:** drawn frame by frame with PIL from the same geometry as `installer/make_icons.py`
   (a test keeps them equal): the tile swings in, the water line draws, the fin surfaces, the play
   triangle opens, a ripple, then the wordmark. Ends on a clean still logo (good for loops).
9. **Silent audio track:** `anullsrc` stereo 48 kHz AAC 96 kb/s, because Instagram and some players
   expect an audio stream; the music is added in the platform apps.
10. **HEIC:** `pi-heif` (decode-only build of pillow-heif: LGPL libheif + libde265, BSD wrapper)
    instead of `pillow-heif`, whose wheels also carry the GPL x265 encoder that would end up in the
    Windows installer. The decoder applies the HEIC rotation itself and resets the EXIF flag.
11. **Removing a photo keeps the file** (marked "removed", Undo brings it back); nothing is deleted
    directly. Deleting a whole slideshow goes through the normal trash (30 days, Restore).
12. **Preview = the same render at 360x640, CPU x264 ultrafast**, cached with a fingerprint of the
    settings; the UI says when the preview or the export is older than the settings.
13. **Title / description "in my style":** the slideshow gets a publish package in the content
    language (subject the user typed, else "Before and after" in that language; "N photos, from
    start to finish."; the My style template's CTA line when the template is on; a few hashtags).
    The share step makes the YouTube Shorts title the same way as for every clip (caps, emoji,
    #Shorts) and adds the channel hashtags / social block.
14. **Jobs:** preview and export run in the GPU lane (never next to Whisper / the LLM), the preview
    jumps the queue, both are explicit (a cancelled one can be started again with the button).
15. **YouTube category for slideshows:** People & Blogs (22) instead of Gaming.
16. **Layout check:** new `LAYOUT_SCREENS` filter for local runs; the fixture gets a synthetic
    slideshow (10 generated pictures) so CI checks the list, the editor (Pro + Easy) and axe.
