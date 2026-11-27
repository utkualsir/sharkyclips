# Destekli yükleme (Assisted upload) – 1.2.70

## Kısa rapor (Türkçe)

**Ne yapıldı**

- **0. "Paylaşılıyor…"da takılma yaması daha önce yapılmamıştı, önce o yapıldı:**
  - küfür beklemesi (bleep_hold) artık kartta yazıyor ("Bekliyor: klipte bir küfür hâlâ duyuluyor");
  - başlamayan render 60 sn sonra "Yeniden dene"li bir hataya dönüyor (watchdog);
  - **Yeniden dene** her zaman gerçek bir iş başlatıyor ya da açık bir hata veriyor;
  - elle paylaşılan platformlar (TikTok/Instagram) YouTube'u asla bekletmiyor;
  - işi kaybolmuş elle paylaşım 60 sn sonra hata + Yeniden dene gösteriyor;
  - yayın kuyruğunda "cancelled" durumu ve **"Bekleyen her şeyi iptal et"** var;
  - Google'ın 100 kullanıcı sınırı mesajı netleşti: kendi Google projesi rehberine götüren bir buton ve "Uygulamayı yayınla"ya tıkla adımı eklendi.
- **TikTok için yeni varsayılan: Destekli yükleme.** "Paylaş"a basınca SharkyClips kullanıcının **kendi tarayıcısını** (Chrome / Edge / Opera GX / Opera / Brave; varsayılan tarayıcı, Ayarlar'dan değiştirilebilir) **ayrı bir SharkyClips profiliyle** açıyor. Sırayla:
  - videoyu yüklüyor;
  - açıklamayı (başlık + hashtag'ler, hashtag'ler sonda) yazıyor;
  - "Herkes" ve "Şimdi"yi seçiyor;
  - **durup** sayfada ve uygulamada "Her şey hazır. Kontrol et ve Paylaş'a tıkla." yazıyor.

  **Paylaş'a asla kendisi tıklamıyor.** Kullanıcı paylaşınca linki bulup "TikTok'ta paylaşıldı ✓" işaretliyor. Emin olamazsa tek tıkla "Paylaştın mı? Evet / Hayır" soruyor.
- **Teknik karar:** hata ayıklama portu (CDP) kullanılmadı. Chrome/Edge 158'de `--remote-debugging-port` tek başına `navigator.webdriver`'ı **true** yapıyor (ölçüldü). Bunu gizleyen bayrak da "desteklenmeyen komut satırı işareti" çubuğu gösteriyor. Onun yerine küçük bir **yardımcı eklenti** ("SharkyClips Helper") yazıldı: düz başlatılan tarayıcı, hiçbir şey bağlı değil, `navigator.webdriver` = false.
  - **Edge / Opera / Brave** eklentiyi kendiliğinden yüklüyor.
  - **Chrome** 137'den beri `--load-extension`'ı yok sayıyor. İlk seferde uygulama 4 adımlı bir rehber gösteriyor (Geliştirici modu → Paketlenmemiş öğe yükle → klasör). Bu bir kez yapılıyor.
  - **Firefox** imzasız eklenti çalıştırmıyor: sayfa orada açılıyor, klip elle paylaşma akışına düşüyor (açık mesajla).
- Giriş hiç otomatikleştirilmedi: o pencerede bir kez giriş yapılıyor. CAPTCHA/doğrulama çıkarsa "Lütfen bunu tarayıcıda tamamla" yazıp bekliyor.
- **Toplu paylaşım:** klipler sırayla hazırlanıyor. Bir sonraki, öncekisi paylaşılınca açılıyor; arada 60 sn ara var (Ayarlar'dan 20–600 sn).
- **Instagram (Reels, instagram.com)** aynı akışla **seçenek** olarak var (varsayılan elle). Paylaş'a yine kullanıcı tıklıyor.
- Sayfa değişip doldurma başarısız olursa **asla sessiz kalmıyor**: dosya + metinler Downloads'ta hazır, kopyalama butonlarıyla elle paylaşma akışına nedeniyle birlikte düşüyor. Tam elle mod Ayarlar'da bir tık.
- Testler: modlar, tarayıcı seçimi, eklenti anahtarı, sekme sahiplenme kuralı, tüm iş akışı sahte raporlarla çalıştırıldı. Gerçek eklentiyle Edge (headless) üzerinde sahte TikTok Studio ve sahte Instagram uçtan uca test edildi: "kişi" Paylaş'a basmadan hiçbir şey paylaşılmıyor. Ayrıca "stuck Sharing" testleri eklendi.

**Gerçek TikTok testi (bu bilgisayarda, Paylaş'tan ÖNCE durdu)**

- Hesabın girişli TikTok profilinde, sentetik 6 saniyelik bir test videosuyla yapıldı.
  - **2. deneme:** 11 saniyede yükleme → açıklama → "hazır". Açıklama doğru yazıldı, görünürlük "Herkes", "Şimdi" seçili, Paylaş butonu çerçeveli, şerit görünüyor. **Hiçbir şey paylaşılmadı**, taslak testten sonra "At" ile silindi.
  - **1. deneme:** TikTok %99'da uzun süre bekledi. Bu yüzden yükleme sırasında eklentiye "hâlâ yüklüyorum" sinyali eklendi.
- Not: Chrome `--load-extension`'ı yok saydığı için **yalnızca bu test** eklentiyi yüklemek üzere Chrome'u bir hata ayıklama portuyla açtı (uygulama bunu asla yapmaz).
- Senin tarafında bir kez yapılacak: SharkyClips ilk TikTok paylaşımında rehberi gösterecek. Chrome'da "Paketlenmemiş öğe yükle" ile eklentiyi ekle (veya Ayarlar'dan tarayıcı olarak Edge'i seç: orada kendiliğinden yükleniyor).

**Sürüm:** 1.2.70 + 1.2.71 (VERSION, CHANGELOG 11 dil, README rozeti, etiket, release). 1.2.71: CI'da Windows'ta aynı anda iki paylaşım hesap token'ını kaydederken çakışıyordu (WinError 5), düzeltildi. Gerçek Edge testleri yalnızca Windows'ta çalışıyor (Linux runner'da zaman aşımı). **CI yeşil**, çalışan uygulama 1.2.71'e yeniden başlatıldı (TikTok modu: assist).

---

## Decisions (English log)

Each decision was taken unattended; the reasons are here so they can be revisited.

1. **No remote debugging port, a companion extension instead.** Measured on this PC (Chrome 158 /
   Edge 158, plain launch on a fresh profile, page reports `navigator.webdriver` to a local HTTP
   beacon):
   - plain launch: `false`
   - `--remote-debugging-port=0`: **`true`** (with nothing attached at all)
   - port + `--disable-blink-features=AutomationControlled`: `false`, but Chrome shows the yellow
     "You are using an unsupported command-line flag" bar on every start.

   Both break "no navigator.webdriver, no automation flags". An extension needs neither: the browser
   is started as a plain program (`procs.launch_app`), nothing attached.
2. **How the extension gets in.**
   - Edge 158: `--load-extension` works (measured: the content script ran, no warning bar,
     `webdriver` false). Opera / Opera GX / Brave get the same switch.
   - Google Chrome 137+ ignores `--load-extension` in branded builds (measured on 158, also with
     `--disable-features=DisableLoadExtensionCommandLineSwitch`). Chrome users get a one-time 4-step
     guide: open chrome://extensions, Developer mode, Load unpacked, the folder SharkyClips shows,
     with copy / open-folder buttons. The unpacked extension stays in that profile.
   - The app notices the extension by itself: the first report from the extension, the "seen"
     time per browser. If a page never answers within 25 s and the extension was never seen, the
     guide opens.
3. **Firefox.** Release Firefox only runs signed extensions (signing needs a Mozilla account:
   the user's decision, not ours), and its remote protocol sets `webdriver`. So Firefox opens the
   upload page in its own SharkyClips profile and the clip goes the by-hand way with a clear note
   ("Chrome, Edge, Opera GX and Brave can be filled in"). TikTok's default mode only becomes
   "assist" when a browser that can be filled in is installed.
4. **Profile.** One SharkyClips profile per browser (`<settings>/browser/assist-<browser>`).
   Chrome reuses the 1.2.43 TikTok profile, so the earlier TikTok login (made by a plain Chrome)
   is kept. Cookies of one browser can't be read by another, hence one per browser.
5. **The extension talks only to 127.0.0.1.** Its own random key (`<settings>/browser/assist_token`,
   not the UI's API token) opens only `/api/assist/ext/*`. The security guard lets those paths
   through from the extension's origin only with that key; with it, every other API path is still
   refused. The key and the server's address are written into the extension folder (`config.js`).
   The service worker tries the noted address, then ports 8000–8010, and skips a SharkyClips with
   other settings (wrong key → 403).
6. **Only the upload page takes a post.** A TikTok / Instagram tab the user browses in that
   profile never claims a waiting post: only `/tiktokstudio/upload` (or the login it redirects to)
   on TikTok, and the home page on Instagram. One tab per post. A tab closed after "ready" leads
   to "Did you post it? Yes / No".
7. **The file reaches the page through the extension.** The service worker fetches it from
   SharkyClips and sends it in 1 MB base64 pieces over a port; the page sets it with
   `DataTransfer` on TikTok's own file input. It never opens the native file picker. Real TikTok
   Studio accepted it.
8. **Filling uses the 1.2.42 selectors** (TikTok's `data-e2e` attributes, so every UI language
   works):
   - the caption goes in as a paste event (Draft.js keeps the line breaks), then `insertText` as a
     fallback, and is read back;
   - visibility "Everyone" and "Now";
   - the AI-content switch when the clip has an AI voice;
   - TikTok's known hint dialogs are closed; a leftover draft of our own profile is discarded.

   A missing file box / caption box / Post button stops the filling (fallback). Visibility, "Now" or
   the AI switch that won't move only add a note to the banner: the person checks the page anyway.
9. **Never clicks Post / Share.** The Post / Share button is only outlined and watched for the
   person's own click (`isTrusted`). A test reads the extension code and fails if the Post or
   Share button is ever pressed. CAPTCHA, verification and login are never touched: the banner asks
   the person and the script waits (30 min, then the by-hand fallback).
10. **Success detection.**
    - TikTok: the page moves to the content list, or the form resets to "select a video" after the
      person's click. The link is read from the content list by the title.
    - Instagram: its "Your reel has been shared" screen, or the dialog closed after the click (no
      link).
    - Not sure (tab closed after "ready", nothing 2 min after the click, or 2 h without a click):
      "Did you post it? Yes / No" on the card and in the bar.
11. **Batch pacing.** The jobs of one platform already run one after another (the "tiktok" /
    "reels" slot of the network lane), so a post waits for the previous one to finish. Before
    opening, a pause of `assist_pause_s` (default 60 s, 20–600) after the last finished one.
    YouTube runs in its own slot and is never held up.
12. **Fallback is instant.** The assisted job first writes the same Downloads copy + caption .txt
    as "by hand"; any stop turns the post into a by-hand post (mode "semi", `fallback` with the
    reason) with the usual copy buttons / upload page / folder. Retry goes back to "assist".
13. **Instagram as an option only.** 1.2.50 switched Meta automation off after the account was
    restricted. The user asked for the assisted Reels flow as an option, so it stays opt-in
    (Settings > Accounts > Instagram > Assisted). It only fills in the dialog; the person shares. The
    Instagram flow is tested against a local fake dialog only (no real Instagram account was used,
    on purpose). Words are matched in the 11 UI languages, because Instagram has no stable
    attributes.
14. **Existing users.** 1.2.68 set TikTok to "by hand" for everyone. A one-time migration
    (`tiktok_assist_default_v1`) moves "by hand" to "assist" when a fillable browser is installed.
    Automatic modes and later choices stay.
15. **Planned times.** An assisted post planned for later opens filled in at that time (the
    publish loop starts it). The person still clicks Post.
16. **A killed browser.** Edge doesn't load a `--load-extension` extension again on a profile whose
    browser was killed (seen in tests). Normal closing is fine. The app falls back after 2 min with
    "close the browser fully once, then Retry". Tests use a fresh profile each time.
17. **The real-page test** needed the extension inside the logged-in Chrome profile. Chrome ignores
    `--load-extension`, so the test harness (not the app) started Chrome with a debugging port and
    `--enable-unsafe-extension-debugging` only to call `Extensions.loadUnpacked` for that one
    session. The upload was a synthetic test video, the post was never sent, and the draft was
    discarded right after.

## "Stuck Sharing…" patch (part 0)

- `next_step()` returned "wait" silently while a swear was still heard. Now the plan item gets
  `waiting = bleep_check`, the clip says why, and Retry answers with that reason.
- An Easy clip whose render never starts: `render_missing`. After 60 s (watchdog) it becomes
  an error with Retry ("rerender"). A running render is waited for, never cut off.
- Retry (YouTube): starts the next step at once (render / cover / upload job) and answers with
  the job id, or raises a clear error (not connected, uploads used up, swear still heard, no
  clip). Retry (TikTok / Instagram): clears an earlier Cancel of that post and always returns a
  real job or an error.
- A platform finished by hand (semi / assist) never holds up the automatic ones. Its caption
  problems are fixed when it starts; too long / too short holds back only that platform.
- A by-hand post "preparing" with no job behind it for 60 s becomes "failed" with Retry.
- Publish queue: status `cancelled`, `POST /api/pubqueue/cancel` ("Cancel everything pending"
  = pending, overdue and failed entries; posts already out or planned on the platform stay).
- Google's user cap: the message says it is the shared app's 100-user limit, and the button
  opens the own-project wizard. The consent-screen step now says to click "Publish app".
