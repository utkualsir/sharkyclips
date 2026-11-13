# SharkyClips durum raporu

**Tarih:** 13 Kasım 2026 · **Sürüm:** 1.2.40 · Kaynak: CHANGELOG.md, docs/EXAM_WEEK_LOG.md, git geçmişi,
GitHub CI, `workspace/` ve `~/.sharkyclips` (sadece okundu, kod değişmedi).

## 1. Özet

SharkyClips, yayın kayıtlarından (Twitch, YouTube, Kick, yerel dosya) en iyi anları bulup altyazılı,
bipli 9:16 Shorts / Reels / TikTok kliplerine çeviren ücretsiz, tamamen yerel çalışan bir masaüstü
uygulaması. Arkada Python (FastAPI, Whisper, FFmpeg, Ollama'da yerel LLM), önde React arayüzü var;
oyunu tanır, başlık-açıklama-hashtag yazar ve YouTube'a kendisi yükler. Kolay mod, otomatik pilot ve
kanalın izlenmelerinden öğrenen bir "zevk" modeli ile yayıncının neredeyse hiç uğraşmamasını hedefliyor.

| | |
|---|---|
| Güncel sürüm | **1.2.40** (11 Kasım 2026) |
| Toplam sürüm | **41 etiket** (v1.0.x - v1.2.40), 103 commit |
| Kod satırı | **~111 bin**: backend 49.9k (Python), arayüz 47.6k (TS/TSX/CSS, 7 dil dahil), testler 12.6k, kurulum 1.3k |
| Test | **630 test** (48 dosya; Windows CI'da 629 geçti, 1 kaldı) |
| CI | 🔴 **Kırmızı** (1.2.39 ve 1.2.40). Son yeşil: 1.2.38. Ayrıntı: bölüm 6 |

## 2. Neler yapıldı

- **Klip bulma:** Hype Map (ses, kahkaha, sohbet patlamaları, anahtar kelime) + LLM ile aday seçimi; mod başına (oyun, sohbet, müzik, ders) ayarlar; canlı işaretleyiciler, anlık tekrar, yayın bitince kendiliğinden klipler.
- **Oyun tanıma:** proje başına tek oyun, oyuna özel kelime bankaları; başlık / Kick kategorisi ipucu; oyun bölgeleri ve Stüdyo'da oyun ekleme.
- **Ses / bip:** küfür tespiti (yüksek duyarlılık), her render sonrası bip kontrolü ve raporu, bipsiz küfürlü klip hiçbir yere gidemez; kendi sesinle İngilizce dublaj (onaylı), müzik görselleştirici.
- **Altyazı:** Whisper ile kelime kelime altyazı, oyuncu Türkçesi sözlüğü, yanlış kelimeye dokunup düzeltme (öğrenir), ders kartları, sohbet balonları, meme yazıları.
- **Düzenleme:** facecam algılama / yerleşimleri, split / crop / fit, aksiyon takibi, zoom (sınırlı), sessiz kısım kesme, uzunluk hedefi, hook skoru + A/B ön testi, başlık bandı, Shorts güvenli alanı.
- **Render / export:** GPU kodlayıcılar (NVENC / VideoToolbox), Shorts / TikTok / Reels hazır ayarları, Best-of montaj, hikâyeler, SRT/VTT, AI kapak stüdyosu (yerel Z-Image-Turbo), Chrome için 10 MB altı MP4.
- **AI başlık-açıklama-hashtag:** yerel LLM (qwen3.5:9b), oyuna duyarlı metinler, "Benim tarzım", başlıklarda küfür / süre yok, her klibe açıklama, başlık oylama.
- **Yayınlama:** YouTube otomatik yükleme + planlama (yerleşik Google istemcisi), tek Publish ile YouTube + Instagram + TikTok, IG/TikTok varsayılan olarak yarı otomatik (adım adım rehber), Yayın Kuyruğu (Claude in Chrome), yapay ses beyanı, TikTok'un zorunlu gönderi ekranı.
- **Kütüphane:** tüm klipler, platform rozetleri, gerçek izlenme / beğeni, filtreler, haftalık özet (digest), takvim (`takvim.json` / `takvim.md`).
- **Otomasyon:** Autopilot (kayıttan planlı Shorts'a), klasör izleyici, OBS, telefonla onay (Telegram), iş kuyruğu (şeritler, duraklat, kesin İptal), kuyruk bitince PC'yi kapatma.
- **Arayüz / Kolay mod:** Kolay mod (varsayılan) + Pro mod, telefon görünümlü önizleme (= render), 7 dil (en, tr, de, hu, ru, ar, zh, RTL dahil), açık/koyu tema, erişilebilirlik (0 axe hatası), LAN erişimi + PIN.
- **Performans / arka plan modu:** Sessiz mod / governor (oyun veya tam ekran video varken duraklar), düşük öncelik, Whisper ve LLM GPU'yu paylaşmaz, önbellek, hızlı açılış (0.5 s import), konsol penceresi yok.
- **Kurulum:** Windows kurucu + kısayollar, macOS `install.sh` + .app (ffmpeg-full), uygulama içi güncelleyici + supervisor ile yeniden başlatma, `doctor`, ClipForge'dan geçiş, Kick VOD / klip içe aktarma.

## 3. Çalışıyor mu

✅ gerçek projelerinde denendi · 🟡 sadece sahte / sentetik veriyle · ❌ çalışmıyor veya yapılmadı

| Alan | Durum | Not |
|---|---|---|
| Klip bulma | ✅ | 8 gerçek oyun projesi (LoL, Delta Force) |
| Oyun tanıma | ✅ | LoL / Delta Force; başka oyun adı karışmıyor (1.2.27'de 40 → 0) |
| Ses / bip | ✅ | Gerçek kliplerde bip kontrolü; dublaj 🟡 (gerçek kullanım kaydı yok) |
| Altyazı | ✅ | Gerçek Türkçe yayınlar |
| Düzenleme | ✅ | Önizleme = render CI'da piksel piksel kontrol ediliyor |
| Render / export | ✅ | 11 klip YouTube'da yayında; Chrome MP4'leri üretildi |
| AI metinler | ✅ | Çalışıyor, ama Türkçe dilbilgisi bazen tuhaf (qwen3.5:9b) |
| YouTube yayınlama | ✅ | 11 herkese açık Short, izlenmeler geri geliyor |
| Instagram API (otomatik) | 🟡 | Sahte sunucu testleri; gerçek token ile yayın kaydı yok |
| TikTok API (otomatik) | 🟡 | Sahte sunucu testleri; inceleme olmadan sadece "Only me" |
| IG / TikTok yarı otomatik + Chrome kuyruğu | 🟡 | Takvimde 2 IG + 2 TikTok "planlandı", gerisi "bekliyor" |
| Kütüphane / digest | ✅ | Gerçek kanal verisiyle çalışıyor (bölüm 7) |
| Autopilot, telefon onayı, canlı işaret | 🟡 | Testler var; gerçek uzun kullanım kaydı yok |
| Kick içe aktarma | ✅ | Gerçek xQc klibi + Destiny VOD (geçici klasörde) |
| Kolay mod / arayüz | ✅ | Kullanılıyor (şu an Pro modda); layout kontrolü 1.2.40'ta 1024 px'te kırmızı |
| Arka plan modu | ✅ | Bu PC'de oyun açıkken işleri gerçekten durdurdu |
| Kurulum Windows | ✅ | Bu PC |
| Kurulum macOS | 🟡 | Sadece macOS CI; gerçek Mac'te hiç denenmedi |
| Kurulum Linux | 🟡 | CI yeşil; tek tık kurucu yok |

## 4. Silme / çöp kutusu özelliği

**Yapılmadı.** Kodda çöp kutusu, geri alma veya "geri dönüşüm" yok.

Var olanlar: tek tek ve **kalıcı** silmeler (export, montaj, hikâye, elle işaretlenmiş klip, AI kapak
modeli, müzik, YouTube videosu, hesap bağlantısı) ve klibi **reddetme** (silmez, gizler). Bir
**projeyi uygulamadan silmek mümkün değil** (API'de proje silme yok); proje klasörünü elle silmek gerekiyor.

## 5. Bekleyen işler

- **Instagram token (system user adımı):** 1.2.37 EAA token'ları destekliyor, ama Meta Business
  portföyünde system user oluşturup token'ı almak senin yapacağın adım. Yapılana kadar Instagram yarı otomatik.
- **TikTok:** yarı otomatik çalışıyor. Otomatik ve herkese açık gönderi için TikTok incelemesi lazım; bu da
  **ortak bir SharkyClips TikTok uygulaması + küçük token relay** gerektiriyor (karar senin, `docs/audits/tiktok-app-review.md` bölüm 0).
- **Buffer entegrasyonu:** **yapılmadı**, kodda hiçbir iz yok.
- **Google OAuth doğrulaması + YouTube API denetimi:** cevaplar hazır (`docs/audits/`), **gönderilmedi**.
  Önce Search Console'da site doğrulaması gerekiyor.
- **README ekran görüntüleri / GIF / social preview:** sentetik demo hazır, çekim **yapılmadı**
  (Sessiz mod durdurmuştu). `docs/social-preview.png` yok; README hâlâ eski görüntüleri gösteriyor.
- **macOS gerçek cihaz testi:** hiç yapılmadı (kurulum, Dock'tan açılış, kapatma izni).
- **Loglardaki diğer açıklar:**
  - Eski commit'lerde e-posta adresin görünüyor (yenileri noreply).
  - v1.2.33 etiketinin CI'ı kırmızı (bilerek bırakıldı).
  - Gerçek ekran okuyucu testi (NVDA / VoiceOver) yapılmadı.
  - macOS'ta tam ekran / video algılama yok.
  - Roadmap'te imzalı kurucu, Linux kurucu, AMD/Intel GPU, kanal toplu içe aktarma bekliyor.

## 6. Bilinen sorunlar ve riskler

- **CI kırmızı (iki sürümdür):**
  - `test_semi_publish.py::test_long_paths_are_shortened_and_errors_show_on_the_clip` Windows ve
    macOS'ta düşüyor, Ubuntu'da geçiyor (1.2.39'dan beri).
  - 1.2.40'ta Layout kontrolü düşüyor: Türkçe, 1024×700'de 15 ekran yana kayıyor
    (1026 > 1024 px, `button.btn`; büyük olasılıkla üst bardaki 7. menü bağlantısı).
- **Testler gerçek İndirilenler klasörüne yazıyor:** `~/Downloads/SharkyClips` içinde 11 Kasım
  tarihli 16 adet "Stream pub-mp-*" klasörü var (çoğu `test_multipost`'tan; testler `SHARKYCLIPS_DOWNLOADS` ayarlamıyor).
- **Kişisel bilgiler koda gömülü (1.2.40):** `pubqueue.py` içinde @utkualsirr / @utkualsirr48,
  #utkualsirr ve Europe/Budapest varsayılan olarak yazılı. Repo herkese açılırsa herkes için bunlar varsayılan olur.
- **Chrome kuyruğu Kütüphane'ye yansımıyor:** Chrome ile planlanan YouTube videosu
  (`2ghZg4Y96JQ`) `uploads.json`'da yok, yani digest ve Kütüphane onu saymıyor.
- **Takvim güncel değil:** 12-13 Kasım için planlanmış 10 IG/TikTok gönderisi hâlâ "bekliyor":
  ya yapılmadılar ya da durumları içe aktarılmadı.
- **Platform bağımlılığı:** IG/TikTok yükleme sayfası, Kick sitesi veya yt-dlp değişirse akışlar
  bozulabilir. Planlı IG/TikTok gönderileri için PC'nin açık olması gerekiyor.
- **YouTube kotası:** doğrulanmamış istemci ve günlük kota (digest: günde 5 yükleme sınırı).
- **AI Türkçesi:** başlıklarda zaman zaman tuhaf dilbilgisi.
- **Eski Python kodu:** güncellemeden sonra yeniden başlatma unutulursa çalışan uygulama eski kodla
  devam eder (1.2.9 / 1.2.22 dersleri). Şu an uygulama çalışmıyor.

## 7. Kanal verileri

Son senkron: **11 Kasım 2026, 18:37 UTC** (o zamandan beri uygulama kapalı, sayılar daha yüksek olabilir).

- **Yayında:** 11 herkese açık YouTube Short (1-8 Kasım). 2 test yüklemesi iptal / silindi. Uygulama
  üzerinden yapılmış IG / TikTok gönderisi kaydı yok.
- **Toplam:** **11,270 izlenme, 75 beğeni.**
- **En iyi klip:** "50 PİNG'li saldırı, Miss Fortune'un sonu! 💀": **1,592 izlenme**, 17 s
  (https://youtu.be/pOJYWoCbIos).
- **Oyunlara göre:**
  - LoL klipleri (7 adet): 1,292-1,592 izlenme, toplam ≈10,200.
  - Delta Force klipleri (4 adet): 119-375 izlenme, toplam ≈1,050.
  - Klip başına LoL, Delta Force'un **yaklaşık 5-6 katı** izleniyor.

| Klip | İzlenme | Beğeni |
|---|---|---|
| 50 PİNG'li saldırı, Miss Fortune'un sonu! 💀 | 1,592 | 7 |
| Bu kadar şansa mı güvendi? 😱 | 1,574 | 10 |
| Demir mi bu el? Abi inanmıyor kanka! 💀 | 1,525 | 9 |
| Komut verdim ama Renekton'a ölüm düştü! 💀 | 1,497 | 8 |
| Akali'yle kaçırılan combo suçlu kanka mıydı? | 1,373 | 5 |
| Kanka sıkıntım var derken beni yakaladılar amman! | 1,369 | 9 |
| Direkt DOUBLE KILL aldık! İşte buna deniyor 🔥 | 1,292 | 12 |
| Mermi bitti, şimdi ne yapacağız? | 375 | 2 |
| Roketi attım ve aniden çok iyi bir durum yarattım | 349 | 4 |
| Düşmanı 3'ten vururken destekçi beni mi yedi? | 205 | 5 |
| Ben arabadayken adam neden koşuyordu kanka? | 119 | 4 |

**Digest ne öğrendi** (4-11 Kasım haftası: 10 Short, 9,901 izlenme):

- **20 saniyeden kısa klipler ortalamanın 1.51 katı izlendi** (2 klip, ortalama 1,544). Haftanın tek önerisi bu.
- Buna karşın kanala göre ayarlanan uzunluk hedefi **30-45 s** (oyun modu). İki sinyal ters yönü
  gösteriyor ve örnek çok küçük (2 klip).
- Hook tarzı: 9 "statement", 2 "question" başlık. Fark çıkarmak için veri yetersiz.

## 8. Sonraki 5 adım (öncelik sırasıyla)

1. **CI'ı yeşile döndür:**
   - Windows / macOS'ta uzun yol testini düzelt.
   - 1024 px'te Türkçe üst barı sığdır.
   - Testlerin gerçek İndirilenler klasörüne yazmasını engelle ve 16 test klasörünü temizle.
2. **Chrome kuyruğunun sonucunu kapat:**
   - Bekleyen 10 IG/TikTok gönderisinin durumunu içe aktar.
   - Chrome ile yapılan yüklemeleri Kütüphane / digest'e bağla, ki kanal verisi tam olsun.
   - Kişisel hesap adlarını ve saat dilimini koddan çıkarıp ayara taşı.
3. **Instagram system user token'ını al ve bağla:** IG'de gerçek otomatik yayın, en ucuz büyük kazanım.
4. **Google doğrulamasını ve YouTube denetimini gönder:**
   - Önce Search Console, sonra `docs/audits/README.md` kontrol listesi.
   - Aynı hafta README ekran görüntülerini ve social preview'u sentetik demodan çek.
5. **Veriye göre içerik:** LoL ağırlıklı devam et ve <20 s ile 30-45 s klipleri bilinçli A/B dene
   (her birinden 5+). Ondan sonra TikTok relay kararını ve **çöp kutusu + proje silme** özelliğini planla.
