# Audits and reviews

| Review | File | Status |
|---|---|---|
| Google OAuth app verification | [google-oauth-verification.md](google-oauth-verification.md) | ready to submit |
| YouTube API Services audit + quota | [youtube-api-audit.md](youtube-api-audit.md) | ready to submit (after / with OAuth) |
| TikTok app review + Content Posting audit | [tiktok-app-review.md](tiktok-app-review.md) | **blocked**: needs a shared TikTok app + token relay (decision) |
| Demo video scripts + shot lists | [demo-videos.md](demo-videos.md) | ready to record |

App changes made for these reviews in 1.2.38: YouTube API data is refreshed or deleted within
30 days and deleted on Disconnect (`backend/sharkyclips/ytdata.py`); TikTok Disconnect revokes
the token at TikTok; the TikTok post screen loads creator info fresh when it opens and uses
TikTok's exact English wording for the disclosure notices; the privacy policy describes all of
it (effective 10 Nov 2026).

## Kontrol listesi (Türkçe)

**Google / YouTube**

1. [ ] Search Console'da `https://utkualsir.github.io/sharkyclips-site/` adresini doğrula (HTML
   dosyası yöntemi: dosyayı `docs/site/` içine koy, `bash docs/publish-site.sh "verify"` çalıştır).
2. [ ] Cloud Console → Google Auth Platform → Branding: ad **SharkyClips**, destek e-postası,
   ana sayfa / gizlilik / şartlar linkleri, yetkili alan `utkualsir.github.io`, logo **boş**.
3. [ ] Data access: yalnızca `youtube` ve `yt-analytics.readonly` kapsamları.
4. [ ] Demo videoyu çek ([demo-videos.md](demo-videos.md), bölüm A), YouTube'a **liste dışı** yükle.
5. [ ] Verification Center → formu [google-oauth-verification.md](google-oauth-verification.md)
   metinleriyle doldur, video linkini ekle, gönder.
6. [ ] YouTube API denetim formunu ([youtube-api-audit.md](youtube-api-audit.md)) doldur: proje
   numarası, beklenen kullanıcı sayısı, istenen kota (öneri 100.000/gün), aynı video linki.
7. [ ] Onay gelince `backend/sharkyclips/google_client.json` içindeki `verification` alanını
   `verified` yap ve bir güncelleme yayınla.

**TikTok**

1. [ ] Karar ver: ortak **SharkyClips** TikTok uygulaması + küçük token aktarıcısı (öneri B,
   [tiktok-app-review.md](tiktok-app-review.md) bölüm 0). Karar verilmeden inceleme geçmez.
2. [ ] Ortak uygulamayı aç: Login Kit (Desktop) + Content Posting API (Direct Post açık);
   kapsamlar `user.info.basic`, `video.publish`, (isteğe bağlı) `video.list`; başka ürün yok.
3. [ ] Uygulama bilgileri: ad, ikon `assets/icon/sharkyclips.png`, açıklama, şartlar / gizlilik /
   site linkleri (dosyadaki tablo).
4. [ ] Sandbox'a test hesabını ekle (hesap **gizli** olmalı), demo videoyu çek (bölüm B, en fazla
   50 MB), App review'a gönder.
5. [ ] Onaydan sonra Content Posting API denetim başvurusunu yap (kullanım tahmini + UX tablosu
   + ekran görüntüleri).
6. [ ] Denetim geçince ayarda `audited` açılır: gönderiler artık "Only me" ile sınırlı değil.

Süreler: Google doğrulama genelde birkaç gün - birkaç hafta; YouTube denetimi birkaç hafta;
TikTok incelemesi birkaç gün - iki hafta.
