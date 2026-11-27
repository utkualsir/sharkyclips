# SharkyClips Helper: mağaza paketleri ve gönderim rehberi (1.2.74)

Hazırlandı, **gönderilmedi**. Aşağıdaki adımları sen yapacaksın. Microsoft Edge Add-ons ve Firefox Add-ons
ücretsiz; Chrome Web Store tek seferlik ücretli (en altta, isteğe bağlı).

## Neden mağaza sürümü, ne kazandırır?

| Tarayıcı | Bugün (mağazasız) | Mağaza sürümüyle |
|---|---|---|
| Edge, Opera, Brave | SharkyClips Yardımcıyı kendisi yüklüyor (`--load-extension`) | Değişen bir şey yok; mağaza sayfası güven ve görünürlük sağlar |
| Firefox | Doldurmuyor, elle paylaşım | **Dolduruyor**: kullanıcı eklentiyi SharkyClips'in açtığı Firefox penceresine Firefox Add-ons'tan kurar, bir kez kodla bağlar |
| Chrome | Bir kez "Paketlenmemiş öğe yükle" gerekiyor | (Chrome Web Store'a koyarsan) tek tıkla kurulur |

Mağaza kopyasında kuruluma özel anahtar (`config.js`) **yok**. Bunun yerine bir kez eşleşir: SharkyClips
Ayarlar → Yardımcı rehberi → **Bağlantı kodunu göster** 6 haneli bir kod gösterir (10 dakika, 5 deneme, tek
kullanım), kullanıcı bu kodu Yardımcı'nın araç çubuğu menüsüne yazar. Kod yalnızca bir tarayıcı eklentisinden
gelen istekle kabul edilir (sayfalar kendi Origin'lerini taklit edemez).

## Paketleri üret

```
.venv\Scripts\python installer\build_extension.py
```

Çıktı `installer/dist/extension/`:

- `sharkyclips-helper-<sürüm>-edge.zip` → Edge Add-ons
- `sharkyclips-helper-<sürüm>-firefox.zip` → Firefox Add-ons
- `sharkyclips-helper-<sürüm>-source.zip` → istenirse kaynak (kod küçültülmemiş, derleme adımı yok)

Aynı dosyalar 1.2.74 GitHub sürümüne de eklendi. Kontroller: Mozilla'nın `web-ext lint` aracı 0 hata, 0 uyarı;
`test_extension_store.py` paket içeriğini, eşleştirmeyi ve "Post'a asla tıklamaz" kuralını denetliyor;
gerçek headless Edge'de mağaza paketi kodla eşleşti (yanlış kod reddedildi, doğru kod bağlandı).

Görseller `docs/extension-store/` içinde (yeniden üretmek için `make_store_images.py`):
`logo-300.png` (300×300), `promo-440x280.png`, `screenshot-1..3.png` (1280×800).

---

## A) Microsoft Edge Add-ons (ücretsiz)

1. https://partner.microsoft.com/dashboard/microsoftedge/overview adresine Microsoft hesabınla gir.
   İlk seferde **Edge program** kaydı ister: geliştirici adı olarak `SharkyClips` (ya da kendi adın), ülke,
   e-posta. Ücret yok.
2. **Create new extension** → `sharkyclips-helper-<sürüm>-edge.zip` dosyasını yükle. Paket denetimi geçince
   devam et.
3. **Availability**: Visibility = *Public*, Markets = *All markets*.
4. **Properties**:
   - Category: *Productivity*
   - Privacy policy requirements: "Does your extension access, collect or transmit personal information?" →
     **No**. Yine de Privacy policy URL alanına şunu yaz:
     `https://utkualsir.github.io/sharkyclips-site/privacy.html`
   - Website: `https://utkualsir.github.io/sharkyclips-site/`
   - Support contact: `https://github.com/utkualsir/sharkyclips/issues`
   - Mature content: No
5. **Store listings** → *English (United States)* ekle (istersen Türkçe de: metinler aşağıda):
   - Description: aşağıdaki "Uzun açıklama (EN)"
   - Extension Store logo: `docs/extension-store/logo-300.png`
   - Small promotional tile: `docs/extension-store/promo-440x280.png`
   - Screenshots: `screenshot-1.png`, `screenshot-2.png`, `screenshot-3.png`
   - Short description: "Kısa açıklama (EN)"
   - Search terms: `SharkyClips, TikTok upload, Instagram upload, stream clips, Shorts`
6. **Notes for certification** (çok önemli: denetçi masaüstü uygulaması olmadan test edemez) → aşağıdaki
   "Denetçiye notlar (EN)" metnini yapıştır.
7. **Publish**. İnceleme genelde birkaç iş günü sürer (en fazla ~7). Sonuç e-postayla gelir.

## B) Firefox Add-ons / AMO (ücretsiz)

1. https://addons.mozilla.org/developers/ → Firefox hesabınla gir (yoksa ücretsiz oluştur). Geliştirici
   sözleşmesini kabul et.
2. **Submit a New Add-on** → *On this site* (listelenen) seç.
3. `sharkyclips-helper-<sürüm>-firefox.zip` dosyasını yükle. Platform: yalnızca **Firefox (masaüstü)**;
   Firefox for Android işaretini kaldır.
4. "Do you need to submit source code?" sorusu: **No** (küçültücü, paketleyici, derleme adımı yok; dosyalar
   olduğu gibi okunabilir). Sorarlarsa `-source.zip` dosyasını yükleyebilirsin.
5. Listing:
   - Name: `SharkyClips Helper` (paketten gelir)
   - Add-on URL: `sharkyclips-helper`
   - Summary: "Kısa açıklama (EN)" (≤ 250 karakter)
   - Description: "Uzun açıklama (EN)"
   - Categories: *Photos, Music & Videos* ve *Social & Communication*
   - Support website: `https://utkualsir.github.io/sharkyclips-site/contact.html`
   - License: **MIT License**
   - Privacy policy: "Gizlilik metni (EN)" bölümünü yapıştır (eklenti veri toplamıyor; manifestte
     `data_collection_permissions: none` tanımlı)
   - Screenshots: `screenshot-1..3.png`; Icon: paketten gelir
6. **Notes to Reviewer**: "Denetçiye notlar (EN)".
7. Gönder. Otomatik denetim hemen yapılır; insan incelemesi sonradan gelebilir. Eklenti kimliği sabittir:
   `sharkyclips-helper@utkualsir.github.io` (değiştirme: güncellemeler bu kimliğe bağlı).

## Onaydan sonra (benim yapacağım iş, bana söylemen yeterli)

- Firefox onaylanınca: uygulamadaki Firefox uyarısı ("doldurulamaz, Chrome/Edge seç") metnini "Firefox
  Add-ons'tan SharkyClips Helper'ı kur" bağlantısıyla güncellemek ve site SSS'sine mağaza bağlantılarını
  eklemek.
- Edge onaylanınca: siteye "Edge Add-ons'ta" bağlantısı.
- Her yeni sürümde: `build_extension.py` ile yeni zip, mağazalara "yeni sürüm yükle" (sürüm numarası
  VERSION dosyasından gelir).

## C) Chrome Web Store (isteğe bağlı, sonra)

Chrome geliştirici hesabı **tek seferlik 5 ABD doları** kayıt ücreti ister
(https://chrome.google.com/webstore/devconsole). Kazancı: Chrome kullanıcıları "Paketlenmemiş öğe yükle"
adımı olmadan tek tıkla kurar. Edge paketi (`-edge.zip`) Chrome'da da aynen çalışır (aynı Manifest V3).
Listeleme metinleri ve görseller yukarıdakilerle aynı. Hazır olunca söyle, uygulamadaki Chrome rehberini
mağaza bağlantısına çevireyim.

---

## Mağaza metinleri

### Kısa açıklama (EN)
Fills in your TikTok and Instagram upload for the free SharkyClips app. You check it and click Post yourself.

### Kısa açıklama (TR)
Ücretsiz SharkyClips uygulaması için TikTok ve Instagram yüklemeni doldurur. Kontrol eder, Paylaş'a kendin tıklarsın.

### Uzun açıklama (EN)
SharkyClips Helper is the companion extension of SharkyClips, a free and open-source desktop app that turns
stream recordings into vertical clips for YouTube Shorts, TikTok and Instagram Reels.

When you share a clip from SharkyClips, the app opens TikTok's (or Instagram's) upload page in your browser.
The Helper then puts in the video and the caption you prepared, and stops. You check the post and click
Post yourself: the Helper never clicks Post or Share, never types or stores a password, and never solves
or skips a CAPTCHA or verification. If TikTok asks you to log in, you do it yourself, once.

How to connect: in SharkyClips open Settings, then the Helper guide, and click "Show connection code".
Click the Helper's icon in the toolbar and type the 6-digit code. That's it.

Privacy: the Helper only runs on tiktok.com and instagram.com, and it only talks to the SharkyClips app on
your own computer (http://127.0.0.1). It collects no data, sends nothing to us or anyone else, has no
server and shows no ads. Source code (MIT license): https://github.com/utkualsir/sharkyclips

You need the SharkyClips desktop app (free): https://utkualsir.github.io/sharkyclips-site/

### Uzun açıklama (TR)
SharkyClips Yardımcısı, yayın kayıtlarını YouTube Shorts, TikTok ve Instagram Reels için dikey kliplere
çeviren ücretsiz ve açık kaynak SharkyClips masaüstü uygulamasının eşlikçi eklentisidir.

SharkyClips'ten bir klip paylaştığında uygulama TikTok'un (ya da Instagram'ın) yükleme sayfasını
tarayıcında açar. Yardımcı hazırladığın videoyu ve açıklamayı yerleştirir ve durur. Gönderiyi kontrol eder,
Paylaş'a kendin tıklarsın: Yardımcı asla Paylaş'a tıklamaz, şifre yazmaz ya da saklamaz, CAPTCHA veya
doğrulamaları asla çözmez ya da atlamaz. TikTok giriş isterse bir kez kendin giriş yaparsın.

Nasıl bağlanır: SharkyClips'te Ayarlar'ı, sonra Yardımcı rehberini aç ve "Bağlantı kodunu göster"e tıkla.
Araç çubuğundaki Yardımcı simgesine tıkla ve 6 haneli kodu yaz. Bu kadar.

Gizlilik: Yardımcı yalnızca tiktok.com ve instagram.com'da çalışır ve yalnızca kendi bilgisayarındaki
SharkyClips uygulamasıyla (http://127.0.0.1) konuşur. Veri toplamaz, bize ya da başkasına hiçbir şey
göndermez, sunucusu ve reklamı yoktur. Kaynak kodu (MIT lisansı): https://github.com/utkualsir/sharkyclips

SharkyClips masaüstü uygulaması (ücretsiz) gerekir: https://utkualsir.github.io/sharkyclips-site/tr/

### Gizlilik metni (EN)
SharkyClips Helper does not collect, store or transmit any personal data. It runs only on tiktok.com and
instagram.com upload pages. It exchanges data only with the SharkyClips desktop app on the same computer
(http://127.0.0.1, ports 8000-8010): it receives the video file and caption you prepared there and reports
the state of the upload page (for example "ready" or "login needed") back to the app. It stores one
value in the browser: the connection key it receives when you pair it with SharkyClips. Nothing is sent to
the developers or to any third party. Full policy: https://utkualsir.github.io/sharkyclips-site/privacy.html

### Denetçiye notlar (EN)
This extension is the companion of the SharkyClips desktop app (free, open source, Windows):
https://utkualsir.github.io/sharkyclips-site/download.html — source: https://github.com/utkualsir/sharkyclips
(extension code: backend/sharkyclips/assist_ext/).

What it does: on TikTok Studio's / Instagram's upload page it fills in the video and caption that the user
prepared in the desktop app, then stops. It never clicks Post/Share, never handles passwords, and never
interacts with CAPTCHAs (it pauses and asks the user). Host permissions are only http://127.0.0.1/* and
http://localhost/* (the desktop app's local server); content scripts only match www.tiktok.com and
www.instagram.com. No remote code, no eval, no analytics.

How to test: install SharkyClips, open Settings → the Helper guide (TikTok section) → "Show connection
code", then open this extension's toolbar popup and enter the 6-digit code; the popup shows "Connected to
SharkyClips on this PC". Without the desktop app running, the popup shows "SharkyClips isn't running on this
PC" and the content scripts do nothing.
