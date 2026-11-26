# Faz D1 (1.2.68): paylaşım gerçekten çalışsın

## Kısa rapor (Türkçe)

**Ne bozuktu:**

1. **YouTube kotası eski sayılarla hesaplanıyordu.** Uygulama her yüklemeyi 1.600 birim sayıp günde en
   fazla 6 (ayarla 5) yüklemeye izin veriyordu. Google 1 Haziran 2026'dan beri yüklemeleri ayrı bir
   kovada sayıyor: **günde 100 yükleme, yükleme başına 1 birim**. Yani uygulama kendini boşuna
   durduruyordu.
2. **Fazlası sessizce sonraki günlere kayıyordu.** Günlük sınır dolunca klipler kendiliğinden ertesi
   güne planlanıyordu (22 Kasım: 4 klipten 3'ü 23 Kasım'a kaydı).
3. **Sessiz bekleme.** 22 Kasım'da bir klip ("2026-11-20 18-03-12", c01) "şimdi yükle" durumunda bir saat
   bekledi ve hiç yüklenmedi: kota bitmek üzereydi (8.054 / 10.000), uygulama "yarın dene" diye not
   düştü ama ekranda **hiçbir şey söylemedi**. YouTube bağlı değilken, oyun oynarken (duraklatma) ve
   otomatik yükleme kapalıyken de aynı sessizlik vardı.
4. **Gizli kalan video "yayında" görünüyordu.** Bir kez herkese açık yükleme olduysa, sonradan gizli
   kalan videolar uygulamada "yayında" diye görünüyordu.
5. **Instagram:** hesabın askıya alındığı için (1.2.62) otomatik paylaşım kapalı, sadece Elle mod var;
   ayrıca 4 saat kuralı gönderiyi sessizce saatler sonrasına bir hatırlatmaya kaydırıyordu.
6. **TikTok:** otomatik paylaşım (TikTok Studio'yu tarayıcıda süren) kırılgan: CAPTCHA / giriş
   ekranında duruyor; günlük 3 sınırı fazlasını sonraki günlere kaydırıyordu. Kayıtlarda şimdiye kadar
   sadece 1 TikTok gönderisi var (22 Kasım).
7. Kolay modun kendi ayrı yükleme yolu vardı ("Otomatik" = en iyi saatlere plan).

**Bunlar sorun değildi (kontrol ettim):** YouTube girişin çalışıyor (token 26 Kasım'da yenilendi).
Projen yüklemeleri **gizli tutmuyor**: kanaldaki bütün videolar herkese açık, ve Google 2 Kasım 2026'dan
beri doğrulanmamış projelerin yüklemelerini gizli tutmuyor.

**0. madde, 1.2.66 test paylaşımı:** gerçek hesaplarına **hiçbir şey yüklenmedi ve planlanmadı**.
Kanalın son 50 videosunu YouTube'dan okudum: son yükleme 22 Kasım (senin yüklediğin 5 klip, hepsi şu an
herkese açık). Ayarlar klasöründeki YouTube / Instagram / TikTok dosyaları 22 Kasım'dan beri hiç
değişmemiş, 1.2.66 testleri geçici bir test klasöründe çalışmış. Silinecek ya da iptal edilecek bir
şey yok.

**Ne düzeldi (1.2.68):**

- **Hemen paylaş:** seçilen bütün klipler hemen gider. Günlük sınır ayarı ve sonraki günlere kaydırma
  kaldırıldı. Tek sınır YouTube'un bugünkü gerçek izni (günde 100); üstte her zaman "Bugün X YouTube
  yüklemesi kaldı".
- Fazlası seçilirse iki seçenekli uyarı: **kalanları şimdi elle yükle** ya da **yarına koy** (YouTube
  sıfırlanınca kendiliğinden, herkese açık). Ya da kendin bir gün seç. Asla daha ileri kaydırılmaz.
- **Kolay mod 3 adım:** videoyu bırak → bütün Shorts'lar tek büyük ızgarada → YouTube / Instagram /
  TikTok'u işaretle → "Paylaş". Ekranda başka bir şey yok.
- **Her klip için bildirim** (uygulamada ve Windows bildirimi): bağlantısıyla "YouTube'da paylaşıldı ✓"
  ya da neyin yanlış gittiği. Hiçbir şey artık sessizce beklemiyor; her bekleyen klip nedenini kartında
  söylüyor.
- YouTube bir videoyu gizli tutarsa: "Gizli yüklendi" + **YouTube Studio'da aç** butonu.
- **Elle yükle**, her klip ve her platform için: doğru video kaydedilir, başlık / açıklama / etiketler
  için ayrı kopyala butonları, yükleme sayfası ve klasör açılır, "Paylaştım" ile işaretlenir.
- **TikTok artık varsayılan olarak elle** (otomatik paylaşım deneme özelliği olarak açıkça yazıyor).
  Senin ayarın tarayıcı otomasyonundaydı; bir kez elle moduna çevrildi. Ayarlar'dan geri açabilirsin.
- **Başlıklar:** TAMAMI BÜYÜK HARF (Türkçe İ/Ş/Ğ doğru), uygun emoji, YouTube'da #Shorts,
  Instagram'da en fazla 5 etiket, her video için başlık dili seçilebiliyor.
- **Biçim kontrolü:** yüklemeden önce 9:16, süre, H.264/AAC, boyut kontrol edilir; gerekirse otomatik
  düzeltilir.
- **"Bunu zaten yükledim mi?":** her kaynak video dosya parmak iziyle tanınır; tekrar içe aktarırsan
  "Bu videodan klipler 22 Kasım'da paylaşıldı: YouTube'da 5" uyarısı. Yeni **Yükleme geçmişi** sayfası
  (tarih, oyun, klip, platform, bağlantı, arama); proje silinse bile kalır. Eski projelerin yüklemeleri
  de içine alındı.
- **Yer aç:** bütün klipler paylaşılınca "X GB yer aç" butonu, net bir onay penceresiyle; yayın videosu
  ve hazırlanan dosyalar kalıcı silinir, geçmiş ve gönderiler kalır.
- Google kullanıcı sınırı yüzünden giriş engellenirse uygulama bunu açıkça söylüyor.

**Senin yapman gerekenler:**

1. **Google kullanıcı sınırını kontrol et** (ben Google Cloud'a giremiyorum): Google Cloud Console →
   Google Auth Platform → **Audience** → "OAuth user cap". Orada "**N users / 100 user cap**" yazar:
   ilk sayı bugüne kadar giriş yapan kişi sayısı. **N gerçekten 100 ise** yeni kimse giriş yapamaz
   (senin girişin çalışmaya devam eder); çözüm doğrulama (docs/google-verification.md). N küçükse
   sorun yok.
2. **TikTok otomatik paylaşımı** istersen Ayarlar → Platformlar'dan tekrar aç (deneme özelliği).
3. **Instagram** hesabın askıda olduğu sürece sadece elle; hesap düzelince yine "Elle yükle" ile.
4. 22 Kasım'da takılı kalan klip ("2026-11-20 18-03-12", c01) uygulamada artık "dikkat" durumunda,
   nedeniyle birlikte duruyor; istersen kartından **Yeniden dene** ile şimdi yükle. 4 gün sonra
   kendiliğinden herkese açık yüklenmesin diye bekletiyorum.
5. Uygulamayı yeniden başlat (çalışan uygulama yoktu; bir sonraki açılışta 1.2.68 gelir).

**Gerçek uçtan uca test (12. madde):** kendi kanalında, ayrı bir test klasöründe (YouTube girişinin
bir kopyasıyla, gerçek kaydın sabit bağlantısıyla, yani ekstra disk yok): uygulamanın kendi render
işiyle klip hazırlandı → Paylaş motoruyla YouTube'a **gizli** yüklendi (`kldB4mDpZus`, başlık
`"ROKET GELMEYE BAŞLASAN!" İŞTE O ANDA ÖLEN ADAMIN HİKAYESİ 😵‍💫🔥 #Shorts`) → "YouTube'da paylaşıldı ✓"
bildirimi, geçmiş satırı ve kartta "paylaşıldı" rozeti geldi → TikTok için "Elle yükle" dosyası ve
metinleri hazırlandı → test videosu YouTube'dan **silindi** ve silindiği doğrulandı. Instagram (hesap
askıda) ve TikTok otomatik paylaşım (herkese açık paylaşır, gizli test mümkün değil) denenmedi:
ikisi de artık varsayılan olarak elle.

---

## Root causes (with the evidence)

Evidence: `~/.sharkyclips/publish/plan.json`, `youtube/quota.json`, the two remaining projects'
`uploads.json` / `platform_uploads.json`, `logs/sharkyclips.log` (last written 22 Nov 21:11: the app has
not run since), and a read-only YouTube Data API listing of the channel's last 50 uploads (3 units).

| # | Cause | Evidence | Fix |
|---|---|---|---|
| 1 | Uploads counted at 1,600 units + 300 reserve + 50 thumbnail: 6/day max, 5 by default | `youtube.COST["upload"] = 1600`, `publishing.DAILY_MAX = 6`; Google: since 2026-06-01 `videos.insert` has its own bucket, 100/day, 1 unit ([quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), [revision history](https://developers.google.com/youtube/v3/revision_history)) | two buckets (`uploads_left()` 100/day, units 10,000 for the rest); a thumbnail that doesn't fit never blocks an upload |
| 2 | Silent quota wait | 22 Nov: quota 8,054 used; `92b0e513:c01` `now: true`, no `video_id`, no error, since 20:11 until the app closed (21:11). Scheduler wrote only `next_try_at` | the clip says "Today's YouTube uploads are used up" + "Upload it by hand now, or it goes up tomorrow by itself" |
| 3 | Daily limit + automatic rollover | 22 Nov batch: c02 now, c03/c09/c11 planned 23 Nov 04:30 / 11:00 / 21:00 | removed; everything now; a choice for what doesn't fit |
| 4 | Other silent waits | scheduler: `governor:` (paused while gaming), not connected / `publish_auto` off returned without a word | `waiting` / `error` on the clip, shown on the card |
| 5 | Private shown as published | `row_status` only said "locked" when the lock state wasn't "unlocked" | always "private" + YouTube Studio button |
| 6 | Instagram never automatic | 1.2.50 `META_AUTOMATION=False`, 1.2.62 off by default (account suspended); 4 h pace moved "now" to a reminder hours later | stays Manual (honest); pace = a warning only; "Upload manually" everywhere |
| 7 | TikTok automation fragile + cap moved posts to later days | `platform_modes.tiktok = browser`; one TikTok post ever (22 Nov); `browser_slot` moved posts to the next day with room | by hand by default (once, `tiktok_manual_default_v1`); a full day says "upload this one by hand" |
| 8 | Easy had its own upload path ("Auto" = best-time plan) | `web/easy.upload(when="auto")` | Easy = the Share board (same engine as Pro) |
| - | NOT a cause: forced private | channel: all 50 latest uploads public; `unlocked.json` since 1 Nov; Google 2026-11-02: unverified projects are no longer restricted to private | detection kept (a channel setting can still keep one private) |
| - | NOT a cause: expired token | token refreshed fine on 26 Nov | - |

Item 0 (1.2.66 test batch on real accounts): none. YouTube: newest upload 23 Nov (scheduled on 22 Nov
by the user); `youtube/*`, `platforms/*`, `browser/*`, `publish/plan.json` unchanged since 22 Nov;
Instagram quota file 15 Nov. Nothing to delete or cancel.

## Decisions log (unattended run)

1. **Quota model = Google's current one.** `COST["upload"] = 1` in a separate Video Uploads bucket
   (`youtube_daily_uploads`, default 100, for projects Google gave more / less); the units bucket
   (10,000) keeps the 300-unit reserve for deletes/edits. `quotaExceeded` / `uploadLimitExceeded` on
   an upload empties the upload bucket, on any other call the units bucket.
2. **No daily limit setting.** `publishing.daily_limit()` = `effective_limit()` = YouTube's upload
   bucket; the setting and its UI are gone. TikTok's automatic number is its own again (default 3,
   max 6), not tied to YouTube.
3. **"X uploads left today"** = Google's bucket minus today's uploads minus clips already marked
   "now" that haven't uploaded yet (honest count).
4. **Overflow choice is required** (`over_limit` error code until the user picks). "Tomorrow" =
   uploads after Google's reset (midnight Pacific + 5 min) and goes public at once
   (`item.after` + `next_try_at`; it can't use `publishAt` because that would upload today). A picked
   day = 12:00 local that day, never before the reset. "By hand now" = the manual-upload files.
5. **Library "auto" = now; a picked time is kept exactly.** `schedule(mode="auto")` no longer spreads
   over release times; manual times are never moved to another slot (Pro can still schedule a date).
6. **Instagram pace**: a warning row in the plan + a notice in the confirm dialog; never a delay.
   Instagram stays Manual (Meta suspended the account; never re-enable automation without being asked).
7. **TikTok by hand by default**: a one-time migration switched the user's `browser` mode to `semi`
   (`tiktok_was_auto` remembers it). Automatic posting is labelled a test feature in the Share bar.
8. **One manual mechanism for all platforms** (`web/manual.py`, `<project>/manual.json`), separate
   from the old TikTok/Instagram "semi" records but shown on the same board (`manual.overlay`).
   "I posted it" on TikTok/Instagram also marks the platform record published, so automation never
   posts it again.
9. **Notices** go through `easy.push_notice` (the tray already turns every notice into a Windows
   notification); `ShareNotices` turns the same feed into toasts with "Open" / "Open in YouTube
   Studio". Hooked centrally: the YouTube upload job (success + failure) and `platforms.record`
   (any TikTok / Instagram status change; automatic retries don't notify).
10. **History** = `<settings>/history/history.json`, fingerprint = SHA-256 of size + 3 × 1 MiB
    samples. Backfilled once from every existing project at start-up (a background thread).
11. **Free up space** goes through `trash.free_space`: files move into a trash item that is purged at
    once (really frees space; app deletes stay in trash.py). Blocked while a post still needs the
    files. The original recording is offered only when it's a different file (not a hard link) and
    not in the settings folder; on another disk it is deleted where it is.
12. **Titles for views** (`titles/shortform.py`) reuse My style's `finish_title` (ALL CAPS with the
    language's letters, emoji by the moment, `#Shorts` on YouTube, ≤ 100). Only generated titles:
    a title the user typed stays as typed. Instagram ≤ 5 hashtags (`igpace.HASHTAGS`).
13. **Format check** (`shortsfmt.py`) before every automatic upload and every manual file; a fix is
    a cached copy in `<project>/cache/shortsfix`; up to 20 s too long is cut at the limit, more is
    refused with the reason.
14. **Google user cap**: the sign-in maps Google's error to status `blocked` with a clear message;
    when Google shows its own block page (no redirect), the "stuck?" help explains the cap.
15. **The stuck 22 Nov clip** (`92b0e513:c01`) is set to "needs attention" with the reason instead
    of letting 1.2.68 upload it publicly by itself four days late.
16. **Housekeeping**: `docs/sharkyclips-demo-captions-en.srt` committed; the old untracked
    `frontend/scripts/redesign-shots.mjs` deleted (asked for by name; nothing used it).
