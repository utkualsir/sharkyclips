# Changelog

All notable changes to SharkyClips (called ClipForge before 1.2.1). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Every update bumps the patch version by 0.0.1.

Each entry is in English, then Turkish; short summaries in the other UI languages follow in
`<!-- lang:xx -->` blocks. The app's "What's new" window shows the block of the UI language.

## [1.2.9] - 2026-11-01

**Connect with Google** now works out of the box, and loading your own Google client file works
again.

### Fixed
- **Advanced → load your own Google client file**: a valid `client_secret….json` could show an
  empty warning with the Save button greyed out. That happened when SharkyClips was updated
  while an older copy was still running in the background. The file box now never blocks a
  valid file, and files saved as UTF-8 with a BOM, UTF-16 ("Unicode" in Notepad) or with
  Windows line endings all load.
- Opening SharkyClips after an update now restarts an older copy that's still running (when
  it's not busy), so you always get the new version.

### Added
- If an older copy of SharkyClips is still running after an update, a bar at the top says so,
  with a **Restart now** button.
- **Connect with Google** is ready to use: SharkyClips now ships its own Google connection, so
  you don't need a Google Cloud project. Google is still reviewing the app, so for now it shows
  its "unverified app" screen first.

<!-- lang:tr -->
**Türkçe**

**Google ile bağlan** artık kurulumsuz çalışıyor ve kendi Google istemci dosyanı yüklemek yine
çalışıyor.

### Düzeltildi
- **Gelişmiş → kendi Google istemci dosyanı yükle**: geçerli bir `client_secret….json` boş bir
  uyarı gösterip Kaydet düğmesini soluk bırakabiliyordu. Bu, SharkyClips güncellenirken eski bir
  kopyası arka planda çalışmaya devam ettiğinde oluyordu. Dosya kutusu artık geçerli bir dosyayı
  asla engellemiyor; BOM'lu UTF-8, UTF-16 (Not Defteri'nde "Unicode") ya da Windows satır sonlarıyla
  kaydedilmiş dosyalar da yükleniyor.
- Güncellemeden sonra SharkyClips'i açmak, hâlâ çalışan eski kopyayı (meşgul değilse) yeniden
  başlatıyor; böylece her zaman yeni sürümü kullanıyorsun.

### Eklendi
- Güncellemeden sonra SharkyClips'in eski bir kopyası hâlâ çalışıyorsa, üstte bunu söyleyen ve
  **Şimdi yeniden başlat** düğmesi olan bir şerit çıkıyor.
- **Google ile bağlan** kullanıma hazır: SharkyClips artık kendi Google bağlantısıyla geliyor,
  Google Cloud projesine gerek yok. Google uygulamayı hâlâ inceliyor; şimdilik önce "doğrulanmamış
  uygulama" ekranını gösteriyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
**Mit Google verbinden** funktioniert jetzt ohne Einrichtung.

- Behoben: Eine gültige `client_secret….json` (Erweitert) zeigte eine leere Warnung, wenn nach
  einem Update noch eine alte SharkyClips-Version lief. Dateien mit BOM, UTF-16 oder
  Windows-Zeilenenden werden jetzt auch geladen.
- Läuft nach einem Update noch die alte Version, startet SharkyClips sie neu (wenn sie nichts
  zu tun hat) oder zeigt eine Leiste mit **Jetzt neu starten**.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A **Csatlakozás Google-lal** most beállítás nélkül működik.

- Javítva: egy érvényes `client_secret….json` (Speciális) üres figyelmeztetést mutatott, ha
  frissítés után még a régi SharkyClips futott. A BOM-os, UTF-16-os vagy Windows-sorvégű fájlok
  is betöltődnek.
- Ha frissítés után még a régi verzió fut, a SharkyClips újraindítja (ha épp nem dolgozik), vagy
  egy sávot mutat **Újraindítás most** gombbal.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
**Подключить через Google** теперь работает без настройки.

- Исправлено: корректный `client_secret….json` (Дополнительно) показывал пустое предупреждение,
  если после обновления ещё работала старая версия SharkyClips. Файлы с BOM, в UTF-16 или с
  переводами строк Windows тоже загружаются.
- Если после обновления ещё работает старая версия, SharkyClips перезапускает её (когда она не
  занята) или показывает полосу с кнопкой **Перезапустить**.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
صار **الربط عبر Google** يعمل دون أي إعداد.

- تم الإصلاح: كان ملف `client_secret….json` صالح (في متقدم) يُظهر تحذيرًا فارغًا إذا بقي إصدار
  قديم من SharkyClips يعمل بعد التحديث. تُحمَّل الآن أيضًا الملفات بترميز UTF-8 مع BOM أو UTF-16 أو
  بنهايات أسطر Windows.
- إذا بقي الإصدار القديم يعمل بعد التحديث، يعيد SharkyClips تشغيله (إن لم يكن مشغولًا) أو يُظهر
  شريطًا بزر **أعد التشغيل الآن**.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
**通过 Google 连接**现在无需任何设置即可使用。

- 已修复：更新后如果旧版 SharkyClips 仍在运行，有效的 `client_secret….json`（高级）会显示空白警告。
  带 BOM、UTF-16 或 Windows 换行的文件现在也能加载。
- 更新后旧版本仍在运行时，SharkyClips 会将其重启（空闲时），或显示带有**立即重启**按钮的提示条。

</details>

## [1.2.8] - 2026-11-01

Connecting YouTube now takes one click and about 10 seconds. No Google Cloud setup, no codes to
copy.

### Added
- **Connect with Google**: one button in Settings → YouTube. Your browser opens Google's own
  sign-in page, you pick your account and click Allow, and SharkyClips shows your channel name
  and picture right away. The browser tab says "Connected!" and closes by itself where it can.
- Before Google's page opens, a short illustrated tip shows what to click on Google's
  "unverified app" warning (Advanced → Go to SharkyClips), until Google has reviewed the app.
- **First launch**: the welcome screens have a new, optional "Connect YouTube" step.
- **Publish dialogs**: if YouTube isn't connected yet, the dialog offers to connect right there.
- If Google ends the sign-in (for example you removed access in your Google account), a banner
  on every screen says so with a one-click **Reconnect** button.
- Handled for you: cancelling on Google's page, an account without a YouTube channel (with a
  "Create a channel" link and **Check again**), accounts with several channels, and
  **Use another account**.
- Settings shows Google's review status of the built-in connection and its user limit.

### Changed
- Using your own Google Cloud project is still possible, under **Advanced**: a new guide with
  one step per screen, a drawing for each step, buttons that open the exact Google Cloud page
  and a check for each step. Drop the downloaded `client_secret….json` on the app or paste its
  contents; SharkyClips checks it and says in plain words what's wrong if it's the wrong file.

<!-- lang:tr -->
**Türkçe**

YouTube'u bağlamak artık tek tık ve yaklaşık 10 saniye. Google Cloud kurulumu yok, kopyalanacak
kod yok.

### Eklendi
- **Google ile bağlan**: Ayarlar → YouTube'da tek bir düğme. Tarayıcın Google'ın kendi giriş
  sayfasını açar, hesabını seçip İzin ver'e tıklarsın ve SharkyClips kanal adını ve resmini hemen
  gösterir. Tarayıcı sekmesi "Bağlandı!" der ve mümkünse kendiliğinden kapanır.
- Google'ın sayfası açılmadan önce kısa, resimli bir ipucu, Google'ın "doğrulanmamış uygulama"
  uyarısında nereye tıklayacağını gösterir (Gelişmiş → SharkyClips'e git). Google uygulamayı
  inceleyene kadar.
- **İlk açılış**: karşılama ekranlarında yeni, isteğe bağlı bir "YouTube'u bağla" adımı var.
- **Yayın pencereleri**: YouTube henüz bağlı değilse pencere orada bağlanmayı önerir.
- Google girişi sonlandırırsa (örneğin Google hesabından erişimi kaldırdıysan) her ekranda tek
  tıkla **Yeniden bağlan** düğmeli bir şerit çıkar.
- Senin için halledilenler: Google sayfasında iptal etmek, YouTube kanalı olmayan hesap ("Kanal
  oluştur" bağlantısı ve **Tekrar kontrol et**), birden çok kanalı olan hesaplar ve **Başka hesap
  kullan**.
- Ayarlar, yerleşik bağlantının Google inceleme durumunu ve kullanıcı sınırını gösterir.

### Değişti
- Kendi Google Cloud projenle bağlanmak hâlâ mümkün, **Gelişmiş** altında: her ekranda tek adım,
  her adım için bir çizim, tam doğru Google Cloud sayfasını açan düğmeler ve her adım için bir
  kontrol içeren yeni bir rehber. İndirdiğin `client_secret….json` dosyasını uygulamaya bırak ya da
  içeriğini yapıştır; SharkyClips dosyayı kontrol eder, yanlış dosyaysa sorunu sade bir dille söyler.

<details><summary>Deutsch</summary>

<!-- lang:de -->
YouTube verbinden geht jetzt mit einem Klick in etwa 10 Sekunden, ohne Google-Cloud-Einrichtung.

- **Mit Google verbinden**: Google-Anmeldung im Browser, Konto wählen, Zulassen, fertig: Kanalname
  und Bild erscheinen sofort.
- Ein bebilderter Tipp zeigt vorher, was auf Googles Warnbildschirm zu klicken ist.
- Optionaler Schritt „YouTube verbinden“ beim ersten Start und direkt in den Veröffentlichen-Dialogen.
- Banner mit **Neu verbinden**, wenn Google die Anmeldung beendet; Hilfe bei Abbruch, fehlendem
  Kanal und mehreren Kanälen.
- Eigenes Google-Projekt weiter unter **Erweitert**, mit neuer Schritt-für-Schritt-Anleitung und
  Prüfung der JSON-Datei (Ablegen oder Einfügen).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A YouTube csatlakoztatása most egy kattintás, kb. 10 másodperc, Google Cloud beállítás nélkül.

- **Csatlakozás Google-lal**: bejelentkezés a böngészőben, fiók kiválasztása, Engedélyezés, és a
  csatorna neve és képe azonnal megjelenik.
- Egy képes tipp előre megmutatja, mire kell kattintani a Google figyelmeztetésén.
- Nem kötelező „YouTube csatlakoztatása” lépés az első indításkor és a közzétételi ablakokban is.
- Sáv **Újracsatlakozás** gombbal, ha a Google megszünteti a bejelentkezést; segítség megszakításnál,
  hiányzó csatornánál és több csatornánál.
- Saját Google-projekt továbbra is a **Speciális** részben, új lépésenkénti útmutatóval és a JSON-fájl
  ellenőrzésével (behúzás vagy beillesztés).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Подключение YouTube теперь — один клик и около 10 секунд, без настройки Google Cloud.

- **Подключить через Google**: вход в браузере, выбор аккаунта, «Разрешить» — и название канала с
  аватаром сразу видны в приложении.
- Иллюстрированная подсказка заранее показывает, что нажать на экране предупреждения Google.
- Необязательный шаг «Подключите YouTube» при первом запуске и прямо в окнах публикации.
- Баннер с кнопкой **Подключить снова**, если Google завершил вход; помощь при отмене, отсутствии
  канала и нескольких каналах.
- Собственный проект Google — по-прежнему в разделе **Дополнительно**, с новой пошаговой инструкцией и
  проверкой JSON-файла (перетаскивание или вставка).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
ربط يوتيوب صار نقرة واحدة ونحو 10 ثوانٍ، دون إعداد Google Cloud.

- **الربط عبر Google**: تسجيل الدخول في المتصفح، اختيار الحساب، «سماح»، فيظهر اسم القناة وصورتها فورًا.
- تلميح مصوّر يوضح مسبقًا ما تضغطه في شاشة تحذير Google.
- خطوة اختيارية «اربط يوتيوب» عند التشغيل الأول وفي نوافذ النشر مباشرة.
- شريط بزر **إعادة الربط** إذا أنهت Google تسجيل الدخول؛ ومساعدة عند الإلغاء أو غياب القناة أو تعدد القنوات.
- مشروعك الخاص على Google ما زال متاحًا في **متقدم**، مع دليل جديد خطوة بخطوة وفحص لملف JSON
  (بالإفلات أو اللصق).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
连接 YouTube 现在只需一键、大约 10 秒，无需设置 Google Cloud。

- **使用 Google 连接**：在浏览器中登录、选择账号、点击“允许”，频道名称和头像立即显示。
- 打开前会有图示提示，告诉你在 Google 警告页面上点哪里。
- 首次启动和发布窗口中都有可选的“连接 YouTube”步骤。
- Google 结束登录时，每个页面都会显示带**重新连接**按钮的提示条；取消、没有频道、多个频道也都有引导。
- 仍可在**高级**中使用自己的 Google 项目，新的分步向导会检查 JSON 文件（拖放或粘贴）。

</details>

## [1.2.7] - 2026-10-30

Publish to YouTube on a schedule: a new Library for every finished clip, one setup screen per
clip, and automatic uploads at your daily limit.

### Added
- **Library** (new tab at the top): every clip that's ready to go out, from all your projects, in
  Drafts, Scheduled, Published, Needs attention and Locked private. Each row shows the thumbnail,
  title, project, length, viral score, status and date; published clips show their views and
  likes. Switch to the **calendar** (week or month) to see what goes out each day against your
  daily limit, and drag a clip to another day to move it.
- **Publish setup in one screen**: pick one of the AI's titles or write your own, edit the
  description, hashtags and tags (the AI fills them, 500-character limit), category (Gaming by
  default), language, "made for kids", visibility and playlist (pick one or create a new one).
- **Covers**: choose an AI cover idea or the **best facecam frame**: SharkyClips finds the moment
  with your strongest reaction and adds the cover text in the app's style. 16:9 videos get it as
  their thumbnail; for Shorts you can put it in as the first 0.3 seconds.
- **Scheduling**: select clips and press **Schedule**. Auto-plan spreads them over the next free
  slots (3 a day at 12:00, 18:00 and 21:00 by default; later learned from your own channel's
  views), or pick a time for each clip. A full day moves the clip to the next free slot.
- SharkyClips uploads scheduled clips **in advance** as private videos with YouTube's own release
  time, so your PC can be off when they go public. Uploads only run while your PC is on and not
  busy, never above your daily limit or Google's API quota (shown in the Library), and never
  twice. If an upload fails it tries again by itself; if it can't, the clip says why and offers a
  fix button.
- Publish now, reschedule, cancel (this also deletes a scheduled video from YouTube), open on
  YouTube and copy the link, right from the Library.
- **Settings → Publishing**: daily limit, release times, learning the best times from your
  channel, and an on/off switch for automatic uploads.
- A clear note while your Google project is unverified (uploads stay private until Google
  approves the audit), with a checklist of what to submit. It disappears by itself once an upload
  really goes public.

### Improved
- Your YouTube sign-in is now stored **encrypted** (Windows DPAPI, the macOS Keychain).
- Views and likes are fetched every 6 hours and teach the viral score, the best release times and
  the A/B hook test by themselves.

### Note
- Scheduling, cancelling and playlists need one more YouTube permission: if you connected before,
  press **Reconnect YouTube** once in Settings.

<!-- lang:tr -->
**Türkçe**

YouTube'a zamanlanmış yayın: her hazır klip için yeni bir Kütüphane, klip başına tek bir ayar
ekranı ve günlük sınırına göre otomatik yükleme.

### Eklendi
- **Kütüphane** (üstte yeni sekme): tüm projelerinden yayına hazır her klip; Taslaklar,
  Zamanlanmış, Yayınlanan, İlgi bekliyor ve Gizli kilitli olarak. Her satırda küçük resim, başlık,
  proje, süre, viral puanı, durum ve tarih var; yayınlananlarda izlenme ve beğeni sayıları da.
  **Takvim** görünümüne (hafta veya ay) geçip her gün neyin yayına gireceğini günlük sınırınla
  birlikte gör, bir klibi başka güne sürükleyerek taşı.
- **Tek ekranda yayın ayarı**: yapay zekânın başlıklarından birini seç ya da kendin yaz;
  açıklama, hashtag'ler ve etiketler (yapay zekâ doldurur, 500 karakter sınırı), kategori
  (varsayılan Oyun), dil, "çocuklara özel", görünürlük ve oynatma listesi (seç ya da yenisini
  oluştur).
- **Kapaklar**: yapay zekânın kapak fikrini ya da **en iyi kamera karesini** seç: SharkyClips en
  güçlü tepkini verdiğin anı bulur ve kapak yazısını uygulamanın tarzında ekler. 16:9 videolarda
  küçük resim olur; Shorts'ta istersen ilk 0,3 saniyeye yerleştirilir.
- **Zamanlama**: klipleri seç ve **Zamanla**'ya bas. Otomatik plan klipleri sonraki boş zamanlara
  yayar (varsayılan günde 3: 12:00, 18:00 ve 21:00; sonra kendi kanalının izlenmelerinden
  öğrenilir) ya da her klibe kendin zaman seçersin. Dolu bir gün, klibi sonraki boş zamana kaydırır.
- SharkyClips zamanlanmış klipleri YouTube'un kendi yayın zamanıyla gizli video olarak **önceden**
  yükler; yayına girdiklerinde bilgisayarın kapalı olabilir. Yüklemeler yalnızca bilgisayar açık ve
  meşgul değilken çalışır; günlük sınırını ya da Google'ın API kotasını (Kütüphane'de görünür) asla
  aşmaz ve aynı klibi asla iki kez yüklemez. Yükleme başarısız olursa kendisi yeniden dener;
  olmazsa klip nedenini söyler ve bir düzeltme düğmesi gösterir.
- Kütüphane'den doğrudan: şimdi yayınla, yeniden zamanla, iptal et (zamanlanmış videoyu
  YouTube'dan da siler), YouTube'da aç ve bağlantıyı kopyala.
- **Ayarlar → Yayınlama**: günlük sınır, yayın saatleri, en iyi saatleri kanalından öğrenme ve
  otomatik yükleme için aç/kapa düğmesi.
- Google projen doğrulanmamışken açık bir not (yüklemeler Google denetimi onaylayana kadar gizli
  kalır) ve neleri göndermen gerektiğini anlatan bir kontrol listesi. Bir yükleme gerçekten herkese
  açılınca not kendiliğinden kaybolur.

### İyileştirildi
- YouTube oturumun artık **şifreli** saklanıyor (Windows DPAPI, macOS Anahtar Zinciri).
- İzlenme ve beğeniler 6 saatte bir alınıyor; viral puanını, en iyi yayın saatlerini ve A/B kanca
  testini kendiliğinden eğitiyor.

### Not
- Zamanlama, iptal ve oynatma listeleri bir YouTube izni daha gerektiriyor: daha önce bağladıysan
  Ayarlar'da bir kez **YouTube'u yeniden bağla**'ya bas.

<details><summary>Deutsch</summary>

<!-- lang:de -->
Geplantes Veröffentlichen auf YouTube: eine neue Bibliothek für alle fertigen Clips, ein
Einrichtungsbildschirm pro Clip und automatische Uploads im Rahmen deines Tageslimits.

- **Bibliothek** (neuer Tab): alle fertigen Clips aus allen Projekten nach Status, mit Aufrufen und
  Likes; **Kalender** (Woche/Monat) mit Tageslimit, Clips per Ziehen verschieben.
- **Alles in einem Bildschirm**: KI-Titel oder eigener Titel, Beschreibung, Hashtags, Tags (von der
  KI, max. 500 Zeichen), Kategorie, Sprache, „für Kinder“, Sichtbarkeit, Playlist.
- **Cover**: KI-Idee oder das **beste Facecam-Bild** (stärkste Reaktion) mit Text; bei 16:9 als
  Thumbnail, bei Shorts optional als erste 0,3 s.
- **Einplanen**: automatisch auf freie Plätze (3 pro Tag um 12, 18 und 21 Uhr, später von deinem
  Kanal gelernt) oder mit eigenen Zeiten. Uploads laufen vorab und nur, wenn der PC frei ist; nie
  über Limit oder Kontingent, nie doppelt; Fehler werden wiederholt oder mit Lösungsknopf gezeigt.
- YouTube-Anmeldung jetzt **verschlüsselt** gespeichert. Einmal **YouTube neu verbinden**, damit
  Einplanen, Abbrechen und Playlists funktionieren.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Időzített közzététel a YouTube-on: új Könyvtár minden kész klipnek, egy beállítóképernyő klipenként
és automatikus feltöltés a napi korláton belül.

- **Könyvtár** (új fül): minden kész klip az összes projektből állapot szerint, nézettséggel és
  kedvelésekkel; **naptár** (hét/hónap) a napi korláttal, a klipek áthúzással mozgathatók.
- **Minden egy képernyőn**: MI-cím vagy saját cím, leírás, hashtagek, címkék (MI tölti ki, max. 500
  karakter), kategória, nyelv, „gyerekeknek szóló”, láthatóság, lejátszási lista.
- **Borító**: MI-ötlet vagy a **legjobb facecam-képkocka** (legerősebb reakció) szöveggel; 16:9-nél
  indexkép, Shortsnál opcionálisan az első 0,3 mp.
- **Időzítés**: automatikusan a szabad időpontokra (napi 3: 12, 18, 21 óra, később a csatornádból
  tanulva) vagy saját időpontokkal. Előre tölt fel, csak ha a gép szabad; sosem lépi túl a korlátot
  vagy a kvótát, sosem tölt fel kétszer; a hibákat újrapróbálja vagy javítógombbal jelzi.
- A YouTube-bejelentkezés most **titkosítva** tárolódik. Egyszer **csatlakoztasd újra a YouTube-ot**
  az időzítéshez, visszavonáshoz és lejátszási listákhoz.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Публикация на YouTube по расписанию: новая Библиотека для всех готовых клипов, один экран настройки
на клип и автоматические загрузки в пределах дневного лимита.

- **Библиотека** (новая вкладка): все готовые клипы из всех проектов по статусам, с просмотрами и
  лайками; **календарь** (неделя/месяц) с дневным лимитом, клипы можно перетаскивать.
- **Всё на одном экране**: заголовок от ИИ или свой, описание, хештеги, теги (заполняет ИИ, до 500
  символов), категория, язык, «для детей», доступ, плейлист.
- **Обложки**: идея ИИ или **лучший кадр с камеры** (самая яркая реакция) с текстом; для 16:9 —
  значок видео, для Shorts — по желанию первые 0,3 с.
- **Расписание**: автоматически по свободным слотам (3 в день в 12:00, 18:00 и 21:00, потом по
  данным вашего канала) или своё время. Загрузка заранее и только когда ПК свободен; без превышения
  лимита и квоты, без повторов; ошибки повторяются или показываются с кнопкой исправления.
- Вход в YouTube теперь хранится **в зашифрованном виде**. Один раз **переподключите YouTube** для
  расписания, отмены и плейлистов.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
النشر المجدول على YouTube: مكتبة جديدة لكل المقاطع الجاهزة، وشاشة إعداد واحدة لكل مقطع، ورفع تلقائي
ضمن حدك اليومي.

- **المكتبة** (تبويب جديد): كل المقاطع الجاهزة من كل المشاريع حسب الحالة، مع المشاهدات والإعجابات؛
  و**تقويم** (أسبوع/شهر) مع الحد اليومي، ويمكن سحب المقاطع لنقلها.
- **كل شيء في شاشة واحدة**: عنوان من الذكاء الاصطناعي أو عنوانك، الوصف، الوسوم، الكلمات المفتاحية
  (يملؤها الذكاء الاصطناعي، حتى 500 حرف)، الفئة، اللغة، «مخصص للأطفال»، الخصوصية، قائمة التشغيل.
- **الأغلفة**: فكرة من الذكاء الاصطناعي أو **أفضل لقطة من الكاميرا** (أقوى رد فعل) مع نص؛ صورة مصغّرة
  لفيديوهات 16:9، وأول 0.3 ثانية اختياريًا في Shorts.
- **الجدولة**: تلقائيًا على المواعيد الفارغة (3 يوميًا في 12:00 و18:00 و21:00، ثم من بيانات قناتك)
  أو بأوقات تختارها. الرفع مسبقًا وفقط عندما يكون الحاسوب متفرغًا؛ دون تجاوز الحد أو الحصة ودون
  تكرار؛ وتُعاد المحاولة عند الخطأ أو يظهر زر إصلاح.
- تسجيل الدخول إلى YouTube محفوظ الآن **مشفرًا**. أعد ربط YouTube مرة واحدة للجدولة والإلغاء وقوائم
  التشغيل.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
定时发布到 YouTube：为所有成品片段新增内容库，每个片段一个设置界面，并在每日上限内自动上传。

- **内容库**（新标签页）：所有项目的成品片段按状态分类，显示观看和点赞；**日历**（周/月）显示每日
  上限，可拖动片段改期。
- **一个界面搞定**：AI 标题或自定义标题、描述、话题标签、标签（AI 填写，最多 500 字符）、类别、
  语言、“面向儿童”、公开范围、播放列表。
- **封面**：AI 创意或**最佳摄像头画面**（反应最强烈的瞬间）加文字；16:9 视频作为缩略图，Shorts
  可选放在前 0.3 秒。
- **排期**：自动分配到空档（默认每天 3 个：12:00、18:00、21:00，之后根据你的频道学习）或手动选
  时间。提前上传且只在电脑空闲时进行；不超上限和配额、不重复上传；失败会自动重试或给出修复按钮。
- YouTube 登录信息现已**加密保存**。请重新连接一次 YouTube，以使用排期、取消和播放列表。

</details>

## [1.2.6] - 2026-10-27

A safer phone mode, a faster start, better accessibility, and fixes for Mac.

### Added
- **Access PIN for other devices.** When you use SharkyClips from your phone (`--lan` mode), you
  can set a PIN or password in **Settings → Other devices** (or with `python cli.py lan-pin`).
  Other devices then log in once; this computer never needs it. Wrong guesses are slowed down,
  and the PIN is stored only as a secure hash. Without a PIN, Settings warns you that anyone on
  your network can open SharkyClips.
- Settings → YouTube now links the YouTube Terms of Service, Google's privacy policy and
  SharkyClips' own privacy policy, and where to remove the access in your Google account.

### Improved
- **Faster start and a lighter app**: the server is ready sooner and uses about 60 MB less memory,
  and the app loads only the language you use, so the first screen appears faster.
- **Accessibility**: better contrast in the light theme and the transcript, every button and list
  has a name for screen readers, and keyboard focus moves into windows like Fast review.
- Uploading a thumbnail or importing a large chat log no longer freezes the live progress for a
  moment.

### Fixed
- **Mac**: SharkyClips now finds FFmpeg, Git and Deno when started from the Dock on new Apple
  Silicon Macs; the uninstaller no longer stops halfway, and it closes SharkyClips before
  removing it.

<!-- lang:tr -->
**Türkçe**

Daha güvenli telefon modu, daha hızlı açılış, daha iyi erişilebilirlik ve Mac düzeltmeleri.

### Eklendi
- **Diğer cihazlar için erişim PIN'i.** SharkyClips'i telefonundan kullanıyorsan (`--lan` modu)
  **Ayarlar → Diğer cihazlar**'dan (ya da `python cli.py lan-pin` ile) bir PIN veya parola
  belirleyebilirsin. Diğer cihazlar bir kez giriş yapar; bu bilgisayar hiç gerekmez. Yanlış
  denemeler yavaşlatılır ve PIN yalnızca güvenli bir özet (hash) olarak saklanır. PIN yoksa Ayarlar,
  ağındaki herkesin SharkyClips'i açabileceği konusunda uyarır.
- Ayarlar → YouTube artık YouTube Hizmet Şartları'na, Google Gizlilik Politikası'na, SharkyClips'in
  kendi gizlilik politikasına ve erişimi Google hesabından nasıl kaldıracağına bağlantı veriyor.

### İyileştirildi
- **Daha hızlı açılış, daha hafif uygulama**: sunucu daha çabuk hazır olur ve yaklaşık 60 MB daha az
  bellek kullanır; uygulama yalnızca kullandığın dili yükler, ilk ekran daha hızlı gelir.
- **Erişilebilirlik**: açık temada ve metin düzenleyicide daha iyi kontrast, ekran okuyucular için
  her düğme ve listenin bir adı var, klavye odağı Hızlı inceleme gibi pencerelerin içine geçiyor.
- Küçük resim yüklemek veya büyük bir sohbet kaydı içe aktarmak artık canlı ilerlemeyi bir anlığına
  dondurmuyor.

### Düzeltildi
- **Mac**: SharkyClips, yeni Apple Silicon Mac'lerde Dock'tan açıldığında FFmpeg, Git ve Deno'yu
  artık buluyor; kaldırma aracı yarıda kalmıyor ve kaldırmadan önce SharkyClips'i kapatıyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
Ein sichererer Handy-Modus, ein schnellerer Start, bessere Barrierefreiheit und Mac-Korrekturen.

- **Neu: Zugangs-PIN für andere Geräte** (`--lan`-Modus): in **Einstellungen → Andere Geräte** oder
  mit `python cli.py lan-pin`. Falsche Versuche werden gebremst, die PIN wird nur als sicherer Hash
  gespeichert. Ohne PIN warnen die Einstellungen.
- **Schneller und leichter**: der Server ist früher bereit, braucht ~60 MB weniger Speicher, und die
  App lädt nur deine Sprache.
- **Barrierefreiheit**: besserer Kontrast im hellen Design, Namen für Screenreader, Tastaturfokus in
  Fenstern.
- **Mac**: FFmpeg, Git und Deno werden beim Start aus dem Dock gefunden; der Deinstaller bricht nicht
  mehr ab.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Biztonságosabb telefonos mód, gyorsabb indulás, jobb akadálymentesség és Mac-javítások.

- **Új: hozzáférési PIN más eszközökhöz** (`--lan` mód): **Beállítások → Más eszközök**, vagy
  `python cli.py lan-pin`. A hibás próbálkozások lassítva vannak, a PIN csak biztonságos hash-ként
  tárolódik. PIN nélkül a Beállítások figyelmeztet.
- **Gyorsabb és könnyebb**: a szerver hamarabb kész, ~60 MB-tal kevesebb memóriát használ, és az
  alkalmazás csak a te nyelvedet tölti be.
- **Akadálymentesség**: jobb kontraszt a világos témában, nevek a képernyőolvasóknak, billentyűzetfókusz
  az ablakokban.
- **Mac**: a Dockból indítva megtalálja az FFmpeg-et, a Gitet és a Denót; az eltávolító nem áll le
  félúton.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Более безопасный режим для телефона, быстрый запуск, улучшенная доступность и исправления для Mac.

- **Новое: PIN-код доступа для других устройств** (режим `--lan`): **Настройки → Другие устройства**
  или `python cli.py lan-pin`. Неверные попытки замедляются, PIN хранится только как безопасный хеш.
  Без PIN-кода настройки предупреждают.
- **Быстрее и легче**: сервер готов раньше, использует на ~60 МБ меньше памяти, а приложение загружает
  только ваш язык.
- **Доступность**: лучший контраст в светлой теме, названия для экранных дикторов, фокус клавиатуры
  внутри окон.
- **Mac**: при запуске из Dock находятся FFmpeg, Git и Deno; деинсталлятор больше не обрывается.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
وضع أكثر أمانًا للهاتف، وتشغيل أسرع، وإمكانية وصول أفضل، وإصلاحات لأجهزة Mac.

- **جديد: رمز PIN للوصول من الأجهزة الأخرى** (وضع `--lan`): من **الإعدادات ← الأجهزة الأخرى** أو
  `python cli.py lan-pin`. تُبطَّأ المحاولات الخاطئة، ويُحفظ الرمز كتجزئة آمنة فقط. وتنبّهك الإعدادات
  إذا لم يكن هناك رمز.
- **أسرع وأخف**: الخادم جاهز أسرع ويستهلك ذاكرة أقل بنحو 60 ميغابايت، والتطبيق يحمّل لغتك فقط.
- **إمكانية الوصول**: تباين أفضل في السمة الفاتحة، وأسماء لقارئات الشاشة، وتركيز لوحة المفاتيح داخل
  النوافذ.
- **Mac**: يجد FFmpeg وGit وDeno عند التشغيل من Dock، ولم يعد برنامج الإزالة يتوقف في المنتصف.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
更安全的手机模式、更快的启动、更好的无障碍体验，以及 Mac 修复。

- **新增：其他设备的访问 PIN**（`--lan` 模式）：在 **设置 → 其他设备** 或用 `python cli.py lan-pin`
  设置。错误尝试会被限速，PIN 只以安全哈希保存。未设置 PIN 时设置页会提醒。
- **更快更轻**：服务器更早就绪，内存少用约 60 MB，应用只加载你使用的语言。
- **无障碍**：浅色主题对比度更好，屏幕阅读器可读出名称，键盘焦点会进入弹出窗口。
- **Mac**：从 Dock 启动时能找到 FFmpeg、Git 和 Deno；卸载程序不再中途停止。

</details>

## [1.2.5] - 2026-10-27

Retention tools: seamless loops, story clips from the whole stream, A/B hooks that learn what
works on your channel, and editor timelines that match the rendered video exactly.

### Added
- **Seamless loop** (render option "Seamless loop"): the end flows back into the start, so viewers
  rewatch without noticing. SharkyClips moves the end (a few seconds at most, never past the
  platform's length limit) into a pause where the sound level, the picture and the motion match
  the opening, never in the middle of a word. What comes right after the end is blended under the
  first moment (sound and picture), the last second is brought to the opening's level, and there
  is no fade to black, no outro card and no hook flash. The local AI can pick the most natural
  ending and write a hook text that works as the end and the beginning. **Loop preview** in the
  editor plays the end into the start again and again, and looped clips repeat in the Clips tab.
  Every loop render measures its seam (click and loudness step).
- **Story clips** (the new **Story** button on a project): the AI reads all moments of the stream
  and proposes 2–3 mini stories ("fail → comeback", "setup → payoff", "running joke"), each 2–4
  moments, 30–60 seconds, with a one-line pitch. Reorder or remove moments, turn the short text
  cards between the acts on or off, and render one Short with quick transitions, captions that
  continue across the moments and the same loudness for every part. Each story gets its own
  titles, description, hashtags and thumbnail prompt, and you can read what the finished story
  says before you post it. A stream with only one good moment gets no story, with the reason.
- **A/B hooks**: any rendered clip can get two versions with different openings (peak flash,
  question, cold open or text hook). A hook model scores the first 3 seconds of both right away
  (motion, loudness, face and smile on your facecam, the on-screen text, trigger words, the AI's
  opinion and your channel's results) and shows the predicted winner with the reasons.
- **Real hook test on YouTube**: when you upload from SharkyClips, the hook styles take turns
  fairly across your clips (Thompson sampling); 48 hours after publishing, views and retention
  are fetched by themselves, and **Stats > Hook styles that work for you** shows each style with
  its number of videos, a likely range and the chance that it's the best. A clip is never uploaded
  twice. If Google keeps your uploads private (an unaudited API project), SharkyClips says so and
  uses only the pre-test. Reconnect YouTube once so it may read retention.

### Fixed
- **Editor timelines (DaVinci Resolve, Final Cut Pro, Premiere Pro) now contain everything the
  render has**: transcript cuts and silence / filler cuts as separate clips with the same
  crossfades, bleeps (their own audio track + markers), zoom keyframes, the music with its
  ducking, the brand kit on separate tracks, the intro / outro cards and the hook flash. Every cut
  sits on the same frame as in the rendered MP4. Final Cut no longer rejects files with captions
  and markers (wrong element order).
- Subtitle files (SRT / VTT) now follow the cuts and the intro card of the exported video.
- The hook flash and intro / outro cards are exactly as long as planned (they could be a frame
  or two longer).

<!-- lang:tr -->
**Türkçe**

İzlenme süresini artıran araçlar: kusursuz döngüler, yayının tamamından hikâye klipleri, kanalında
neyin işe yaradığını öğrenen A/B kancalar ve render ile birebir aynı düzenleyici zaman çizelgeleri.

### Eklendi
- **Kusursuz döngü** (render seçeneği "Kusursuz döngü"): son, başa akıcı şekilde bağlanır; izleyici
  fark etmeden tekrar izler. SharkyClips bitişi (en fazla birkaç saniye, platformun süre sınırını
  asla aşmadan) ses seviyesi, görüntü ve hareketin açılışla uyuştuğu bir duraklamaya taşır; asla bir
  kelimenin ortasına değil. Bitişten hemen sonra gelen kısım ilk ana karışır (ses ve görüntü), son
  saniye açılışın seviyesine getirilir; karartma, kapanış kartı ve kanca flaşı yok. Yerel yapay zekâ
  en doğal bitişi seçip hem son hem başlangıç olarak işe yarayan bir kanca yazısı yazabilir.
  Düzenleyicideki **Döngü önizleme** sonu tekrar tekrar başa bağlayarak oynatır; döngülü klipler
  Klipler sekmesinde de tekrar eder. Her döngü render'ı geçişini ölçer (tık ve ses farkı).
- **Hikâye klipleri** (projedeki yeni **Hikâye** düğmesi): yapay zekâ yayının tüm anlarını okur ve
  2–3 mini hikâye önerir ("başarısızlık → geri dönüş", "hazırlık → karşılık", "tekrar eden şaka");
  her biri 2–4 an, 30–60 saniye ve tek satırlık bir özetle. Anların sırasını değiştir ya da çıkar,
  bölümler arasındaki kısa yazı kartlarını aç / kapat ve hızlı geçişli, altyazısı anlar boyunca
  süren, her bölümü aynı ses seviyesinde tek bir Short oluştur. Her hikâyenin kendi başlıkları,
  açıklaması, hashtag'leri ve kapak istemi var; paylaşmadan önce bitmiş hikâyenin ne söylediğini
  okuyabilirsin. Tek iyi anı olan bir yayın, nedeniyle birlikte hikâyesiz kalır.
- **A/B kancalar**: render edilmiş her klibin farklı açılışlı iki versiyonu olabilir (zirve flaşı,
  soru, doğrudan aksiyon ya da yazı kancası). Bir kanca modeli ikisinin de ilk 3 saniyesini hemen
  puanlar (hareket, ses seviyesi, facecam'deki yüz ve gülümseme, ekrandaki yazı, tetikleyici
  kelimeler, yapay zekânın görüşü ve kanalının sonuçları) ve tahmini kazananı nedenleriyle gösterir.
- **YouTube'da gerçek kanca testi**: SharkyClips'ten yükleme yapınca kanca stilleri klipler arasında
  adil şekilde sırayla denenir (Thompson örneklemesi); yayından 48 saat sonra izlenme ve izleyici
  tutma kendiliğinden alınır, **İstatistikler > Sana uyan kanca stilleri** her stili video sayısı,
  olası aralığı ve en iyi olma olasılığıyla gösterir. Bir klip asla iki kez yüklenmez. Google
  yüklemelerini gizli tutuyorsa (denetlenmemiş API projesi) SharkyClips bunu söyler ve yalnızca ön
  testi kullanır. İzleyici tutmayı okuyabilmesi için YouTube'u bir kez yeniden bağla.

### Düzeltildi
- **Düzenleyici zaman çizelgeleri (DaVinci Resolve, Final Cut Pro, Premiere Pro) artık render'daki
  her şeyi içeriyor**: metin kesimleri ve sessizlik / dolgu kesimleri aynı geçişlerle ayrı klipler
  olarak, bipler (kendi ses izi + işaretçiler), zoom anahtar kareleri, ses kısmalı müzik, ayrı izlerde
  marka kiti, giriş / kapanış kartları ve kanca flaşı. Her kesim, render edilen MP4'teki kareyle aynı
  karede. Final Cut altyazı ve işaretçili dosyaları artık reddetmiyor (yanlış öğe sırası).
- Altyazı dosyaları (SRT / VTT) artık dışa aktarılan videonun kesimlerine ve giriş kartına uyuyor.
- Kanca flaşı ve giriş / kapanış kartları tam planlandığı uzunlukta (bir iki kare uzun olabiliyordu).

<details><summary>Deutsch</summary>

<!-- lang:de -->
Werkzeuge für mehr Wiedergabezeit: nahtlose Loops, Story-Clips aus dem ganzen Stream, A/B-Hooks,
die lernen, was auf deinem Kanal funktioniert, und Editor-Timelines, die genau dem Render entsprechen.

- **Neu: nahtloser Loop**: Das Ende fließt zurück in den Anfang (Ende in einer passenden Pause, nie
  mitten im Wort, kein Schwarzbild), mit **Loop-Vorschau** im Editor und gemessener Naht.
- **Neu: Story-Clips** (Knopf **Story**): 2–3 Mini-Stories aus Momenten des ganzen Streams, 30–60 s,
  umsortierbar, mit schnellen Übergängen, durchgehenden Untertiteln, gleicher Lautstärke und eigenem
  Veröffentlichungspaket.
- **Neu: A/B-Hooks**: zwei Anfänge pro Clip, sofort bewertet mit Begründung; beim Hochladen aus der
  App lernt ein echter Test nach 48 Stunden, welcher Hook-Stil bei dir funktioniert (Statistik).
- **Behoben:** Editor-Timelines enthalten jetzt alles aus dem Render, framegenau; Untertiteldateien
  folgen den Schnitten.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Nézési időt növelő eszközök: zökkenőmentes hurkok, történetklipek az egész streamből, A/B horgok,
amelyek megtanulják, mi működik a csatornádon, és a renderrel pontosan egyező vágóprogram-idővonalak.

- **Új: zökkenőmentes hurok**: a vége visszafolyik az elejébe (illő szünetben, soha nem szó közepén,
  elsötétítés nélkül), **hurok-előnézettel** és mért illesztéssel.
- **Új: történetklipek** (**Történet** gomb): 2–3 mini történet az egész stream pillanataiból,
  30–60 mp, átrendezhető, gyors áttűnésekkel, folyamatos feliratokkal, egyforma hangerővel és saját
  közzétételi csomaggal.
- **Új: A/B horgok**: két kezdés klipenként, azonnali pontozással és indoklással; az alkalmazásból
  feltöltve egy éles teszt 48 óra után megtanulja, melyik horogstílus működik nálad (Statisztika).
- **Javítva:** a vágóprogram-idővonalak mindent tartalmaznak, ami a renderben van, képkockára
  pontosan; a feliratfájlok követik a vágásokat.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Инструменты для удержания: бесшовные петли, клипы-истории из всего стрима, A/B-хуки, которые
учатся на вашем канале, и таймлайны для монтажа, точно совпадающие с рендером.

- **Новое: бесшовная петля**: конец перетекает в начало (стык в подходящей паузе, никогда посреди
  слова, без затемнения), с **предпросмотром петли** и измерением стыка.
- **Новое: клипы-истории** (кнопка **История**): 2–3 мини-истории из моментов всего стрима, 30–60 с,
  с перестановкой, быстрыми переходами, сквозными субтитрами, одинаковой громкостью и своим пакетом
  для публикации.
- **Новое: A/B-хуки**: два начала на клип, сразу с оценкой и причинами; при загрузке из приложения
  реальный тест через 48 часов узнаёт, какой стиль хука работает у вас (Статистика).
- **Исправлено:** таймлайны для монтажа содержат всё, что есть в рендере, с точностью до кадра;
  файлы субтитров следуют за вырезками.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أدوات لزيادة مدة المشاهدة: حلقات سلسة، ومقاطع قصص من البث كله، وخطافات A/B تتعلم ما ينجح على
قناتك، ومخططات زمنية لبرامج المونتاج تطابق الإخراج تمامًا.

- **جديد: حلقة سلسة**: تنساب النهاية إلى البداية (في وقفة مناسبة، لا وسط كلمة أبدًا، بلا تعتيم)،
  مع **معاينة الحلقة** وقياس نقطة الوصل.
- **جديد: مقاطع القصص** (زر **قصة**): 2–3 قصص قصيرة من لحظات البث كله، 30–60 ثانية، قابلة لإعادة
  الترتيب، بانتقالات سريعة وترجمة متصلة ومستوى صوت موحّد وحزمة نشر خاصة.
- **جديد: خطافات A/B**: بدايتان لكل مقطع مع تقييم فوري وأسبابه؛ وعند الرفع من التطبيق يتعلّم اختبار
  حقيقي بعد 48 ساعة أي نمط خطاف ينجح معك (الإحصاءات).
- **إصلاح:** المخططات الزمنية لبرامج المونتاج تحتوي الآن كل ما في الإخراج بدقة الإطار؛ وملفات
  الترجمة تتبع عمليات القص.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
提升观看时长的工具：无缝循环、用整场直播组成的故事剪辑、能学习你频道偏好的 A/B 开头，以及与渲染结果完全一致的剪辑软件时间线。

- **新增：无缝循环**：结尾自然接回开头（落在合适的停顿处，绝不在词语中间，没有黑场），编辑器中可**循环预览**，并测量接缝。
- **新增：故事剪辑**（**故事**按钮）：用整场直播的精彩时刻组成 2–3 个 30–60 秒的迷你故事，可调整顺序，转场快速，字幕连贯，音量统一，并有专属发布素材包。
- **新增：A/B 开头**：每个剪辑两个开头，立即打分并说明原因；从应用上传时，真实测试会在 48 小时后了解哪种开头风格最适合你（统计页）。
- **修复：**剪辑软件时间线现在包含渲染中的全部内容，精确到帧；字幕文件也会跟随剪切。

</details>


## [1.2.4] - 2026-10-26

Editing power tools: bleep swear words, cut silences, smart zoom, edit by transcript, your own
music, a brand kit, manual clips and keyboard shortcuts with a fast review mode.

### Added
- **Swear word bleep** (good for YouTube ads): swear words are found from the transcript in all 7
  languages and get a bleep or silence. Choose Auto / Bleep / Mute / Off per render; Auto bleeps
  vertical videos (Shorts, TikTok, Reels and the Clips tab) and leaves 16:9 videos alone. They can
  be hidden in the captions too ("a**"). The lists are yours to edit in **Studio > Word lists**
  (Turkish ı / i variants are handled: "amına" also finds "amina", but "sik" never finds "sıkıntı").
- **Silence and filler cuts**: Light or Strong cuts pauses (only real silence, not game sounds or
  music) and filler words like "ııı", "eee", "um", "äh", "ну", with tiny crossfades so the jump
  cuts sound natural. Words that are also real words ("şey", "yani", "like") are only cut by Strong
  and only when they stand alone. Nothing is ever cut inside a laugh or a reaction.
- **Smart zoom**: a subtle (or strong) punch-in on the peak moments (game events, loud moments,
  trigger words, laughs) with smooth ease in and out, and on the facecam when you react.
- **Edit by transcript**: under the player you see the clip's words. Click a word to jump there,
  select words and press Delete to cut them out of the video, drag the [ ] handles to trim the
  clip. Undo / redo, and the 9:16 preview plays your edit live (cuts skipped, bleeps, zoom).
- **Background music from your own songs**: drop your songs (for example your AI songs) into
  **Studio > Music** and tag their mood (hype / chill / sad / funny). SharkyClips finds each song's
  strongest part and suggests a fitting song for every clip (you can pick another one or none).
  The music gets quieter under speech and comes back in pauses, fades out at the end, and the
  whole clip is mixed to -14 LUFS. An optional credit line ("Music: <song> by <your channel>") is
  added to the YouTube description.
- **Brand kit**: your channel name and @handle, a logo watermark (position, size, opacity),
  intro / outro cards and your caption font and colors, saved as presets in **Studio > Brand kit**
  and added to every render with one switch.
- **Your own clips**: press I and O (or the buttons under the player) to mark a moment yourself.
  It becomes a candidate like the others, gets the AI analysis, and stays when you re-run the
  highlight search.
- **Keyboard shortcuts**: A keep, X skip, Space play / pause, J / K / L seek, ← / → previous / next
  clip, I / O in / out, Ctrl+Z undo, ? shows the list.
- **Fast review**: one candidate at a time, full screen. Swipe right (or A) to keep, left (or X)
  to skip, and the next clip plays by itself.
- All of it follows the performance mode: in Silent mode renders and music analysis still pause
  for your games and videos.

<!-- lang:tr -->
**Türkçe**

Düzenleme araçları: küfür bip'leme, sessizlik kesme, akıllı zoom, metinden düzenleme, kendi müziğin,
marka kiti, elle klip ekleme ve hızlı inceleme modlu klavye kısayolları.

### Eklendi
- **Küfür bip'leme** (YouTube reklamları için iyi): küfürler 7 dilde metinden bulunur ve bip'lenir
  ya da susturulur. Her render için Otomatik / Bip / Sessiz / Kapalı seç; Otomatik dikey videolarda
  (Shorts, TikTok, Reels ve Klipler sekmesi) bip'ler, 16:9 videolara dokunmaz. İstersen altyazıda da
  gizlenir ("a**"). Listeleri **Stüdyo > Kelime listeleri**'nden düzenleyebilirsin (Türkçe ı / i
  farkı gözetilir: "amına" "amina"yı da bulur ama "sik" asla "sıkıntı"yı bulmaz).
- **Sessizlik ve dolgu kesme**: Hafif veya Güçlü, duraklamaları (sadece gerçek sessizliği; oyun
  sesi veya müzik kalır) ve "ııı", "eee", "um", "äh" gibi dolgu kelimelerini keser; küçük geçişler
  sayesinde kesmeler doğal duyulur. Gerçek kelime de olan dolgular ("şey", "yani") sadece Güçlü'de
  ve tek başına durduklarında kesilir. Gülme veya tepki anının içinde asla kesilmez.
- **Akıllı zoom**: önemli anlarda (oyun olayları, sesin yükseldiği anlar, tepki kelimeleri,
  kahkahalar) yumuşak giriş-çıkışlı hafif (veya güçlü) bir yakınlaştırma; tepki verdiğinde facecam'de de.
- **Metinden düzenleme**: oynatıcının altında klibin kelimeleri var. Bir kelimeye tıkla, oraya
  atla; kelimeleri seçip Delete'e bas, videodan kesilsin; [ ] tutamaçlarını sürükleyip klibi kırp.
  Geri al / yinele var ve 9:16 önizleme düzenlemeni canlı oynatır (kesilen yerler atlanır, bip'ler,
  zoom).
- **Kendi şarkılarınla arka plan müziği**: şarkılarını (örneğin yapay zekâ şarkılarını) **Stüdyo >
  Müzik**'e bırak, havasını etiketle (coşkulu / sakin / hüzünlü / komik). SharkyClips her şarkının en
  güçlü kısmını bulur ve her klibe uygun bir şarkı önerir (başkasını seçebilir ya da müziksiz
  bırakabilirsin). Müzik konuşurken kısılır, aralarda geri gelir, sonda kaybolur; klibin tamamı
  -14 LUFS'a ayarlanır. İstersen YouTube açıklamasına bir künye satırı ("Müzik: <şarkı> - <kanalın>")
  eklenir.
- **Marka kiti**: kanal adın ve @kullanıcı adın, logo filigranı (konum, boyut, opaklık), giriş /
  kapanış kartları ve altyazı yazı tipin ile renklerin; **Stüdyo > Marka kiti**'nde ayar olarak
  saklanır ve tek düğmeyle her render'a eklenir.
- **Kendi kliplerin**: bir anı kendin işaretlemek için I ve O'ya bas (veya oynatıcının altındaki
  düğmeler). Diğerleri gibi aday olur, yapay zekâ analizinden geçer ve öne çıkanları yeniden
  aradığında kaybolmaz.
- **Klavye kısayolları**: A tut, X geç, Boşluk oynat / durdur, J / K / L sar, ← / → önceki / sonraki
  klip, I / O başlangıç / bitiş, Ctrl+Z geri al, ? listeyi gösterir.
- **Hızlı inceleme**: adaylar tek tek, tam ekran. Tutmak için sağa (veya A), geçmek için sola
  (veya X) kaydır; sıradaki klip kendiliğinden oynar.
- Hepsi performans moduna uyar: Sessiz modda render'lar ve müzik analizi oyunların ve videoların
  için yine durur.

<details><summary>Deutsch</summary>

<!-- lang:de -->
Schnittwerkzeuge: Schimpfwörter überpiepen, Pausen schneiden, Smart-Zoom, Schnitt per Transkript,
deine eigene Musik, ein Brand-Kit, eigene Clips und Tastenkürzel mit schneller Sichtung.

- **Neu: Piepton für Schimpfwörter** in allen 7 Sprachen (Auto piept Hochkant-Videos), auf Wunsch
  auch in den Untertiteln verborgen ("a**"); die Listen bearbeitest du unter **Studio > Wortlisten**.
- **Neu: Pausen und Füllwörter** ("äh", "um", "ııı") werden mit kurzen Überblendungen geschnitten,
  nie mitten in einem Lachen; dazu ein dezenter **Smart-Zoom** auf die Höhepunkte und deine Facecam.
- **Neu: Schnitt per Transkript**: Wörter löschen schneidet sie heraus, [ ] ziehen kürzt den Clip,
  mit Rückgängig und Live-Vorschau.
- **Neu: eigene Musik** (Studio > Musik) mit Stimmungen, Vorschlag pro Clip, Start am stärksten Teil,
  leiser beim Sprechen, -14 LUFS und optionalem Song-Credit; **Brand-Kit** mit Logo, @Handle,
  Intro / Outro und Untertitelstil.
- **Neu:** eigene Clips mit I / O, Tastenkürzel (? zeigt sie) und schnelle Sichtung im Vollbild.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Vágóeszközök: káromkodás kisípolása, szünetek kivágása, okos zoom, vágás az átiratból, saját zene,
márkacsomag, saját klipek és billentyűparancsok gyors átnézéssel.

- **Új: sípolás a csúnya szavakra** mind a 7 nyelven (az Auto az álló videókat sípolja), kérésre a
  feliratban is elrejtve ("a**"); a listákat a **Stúdió > Szólisták** alatt szerkesztheted.
- **Új: a szünetek és töltelékszavak** ("ööö", "um", "ııı") rövid áttűnéssel kivágva, nevetés
  közepén soha; finom **okos zoom** a csúcspontokra és a facecamre.
- **Új: vágás az átiratból**: a törölt szavak kikerülnek, a [ ] húzása vágja a klipet,
  visszavonással és élő előnézettel.
- **Új: saját zene** (Stúdió > Zene) hangulatokkal, klipenkénti javaslattal, a legerősebb résztől,
  beszéd alatt halkítva, -14 LUFS, opcionális feltüntetéssel; **márkacsomag** logóval, @névvel,
  intróval / outróval és feliratstílussal.
- **Új:** saját klipek I / O-val, billentyűparancsok (? mutatja) és teljes képernyős gyors átnézés.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Инструменты монтажа: запикивание мата, вырезка пауз, умный зум, монтаж по тексту, своя музыка,
брендинг, свои клипы и горячие клавиши с быстрым просмотром.

- **Новое: запикивание мата** на всех 7 языках (Авто — для вертикальных видео), по желанию скрытие
  в субтитрах ("a**"); списки редактируются в **Студия > Списки слов**.
- **Новое: паузы и слова-паразиты** ("э-э", "ну", "um") вырезаются с короткими переходами, никогда
  посреди смеха; плюс мягкий **умный зум** на ярких моментах и на вебке.
- **Новое: монтаж по тексту**: удалённые слова вырезаются, [ ] обрезают клип, есть отмена и живой
  предпросмотр.
- **Новое: своя музыка** (Студия > Музыка) с настроениями, подбором песни для клипа, стартом с самой
  сильной части, приглушением под речью, -14 LUFS и строкой об авторе; **брендинг** с логотипом,
  @ником, заставками и стилем субтитров.
- **Новое:** свои клипы через I / O, горячие клавиши (? показывает их) и быстрый просмотр на весь экран.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أدوات مونتاج: صفير على الشتائم، وقص الصمت، وتقريب ذكي، ومونتاج من النص، وموسيقاك الخاصة، وهوية
بصرية، ومقاطعك الخاصة، واختصارات لوحة المفاتيح مع مراجعة سريعة.

- **جديد: صفير على الشتائم** بجميع اللغات السبع (التلقائي للفيديوهات العمودية)، مع إخفائها في
  الترجمة إن أردت ("a**")؛ تُعدَّل القوائم في **الاستوديو > قوائم الكلمات**.
- **جديد: قص الصمت وكلمات الحشو** بانتقالات قصيرة، ولا قص أبدًا وسط ضحكة؛ مع **تقريب ذكي** خفيف على
  أبرز اللحظات وعلى كاميرا الوجه.
- **جديد: مونتاج من النص**: حذف الكلمات يقصها، وسحب [ ] يقصّر المقطع، مع تراجع ومعاينة حية.
- **جديد: موسيقاك** (الاستوديو > الموسيقى) مع الطابع واقتراح لكل مقطع وبداية من الجزء الأقوى وخفض
  أثناء الكلام و-14 LUFS وسطر ذكر اختياري؛ و**هوية بصرية** بالشعار و@المعرّف وبطاقات البداية والنهاية
  ونمط الترجمة.
- **جديد:** مقاطعك الخاصة عبر I / O، واختصارات لوحة المفاتيح (? تعرضها)، ومراجعة سريعة بملء الشاشة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
剪辑工具：脏话哔声、剪掉静音、智能缩放、按文字稿剪辑、你自己的音乐、品牌套件、手动片段，以及带快速审阅的键盘快捷键。

- **新增：脏话哔声**，支持全部 7 种语言（自动模式用于竖屏视频），也可在字幕中遮住（a**）；词表在**工作室 > 词表**中编辑。
- **新增：剪掉静音和口头禅**，带短暂交叉淡化，绝不在笑声中间剪；另有轻微的**智能缩放**，在高光时刻和你的摄像头画面上推近。
- **新增：按文字稿剪辑**：删除词语即剪掉，拖动 [ ] 修剪片段，可撤销并实时预览。
- **新增：你自己的音乐**（工作室 > 音乐），可标记情绪、按片段推荐、从最有力的部分开始、说话时自动压低、-14 LUFS，并可添加署名；**品牌套件**包含 Logo、@账号、片头 / 片尾和字幕样式。
- **新增：**用 I / O 标记自己的片段、键盘快捷键（按 ? 查看）以及全屏快速审阅。

</details>

## [1.2.3] - 2026-10-26

A small reliability fix for the Export window.

### Fixed
- The Export window no longer fails to open when ffmpeg is missing or can't encode H.264. It now
  opens and shows the formats as unavailable, and checks again as soon as ffmpeg is installed
  (no restart needed).
- Behind the scenes: the automatic tests now run on clean machines too, so every release is
  checked before it reaches you.

<!-- lang:tr -->
**Türkçe**

Dışa Aktar penceresi için küçük bir güvenilirlik düzeltmesi.

### Düzeltildi
- ffmpeg eksikse veya H.264 kodlayamıyorsa Dışa Aktar penceresi artık açılmamazlık yapmıyor. Pencere
  açılıyor, formatları kullanılamaz olarak gösteriyor ve ffmpeg kurulur kurulmaz yeniden kontrol
  ediyor (yeniden başlatmaya gerek yok).
- Arka planda: otomatik testler artık temiz bilgisayarlarda da çalışıyor; her sürüm sana ulaşmadan
  önce kontrol ediliyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
Eine kleine Zuverlässigkeitskorrektur für das Export-Fenster.

- **Behoben:** Das Export-Fenster öffnet sich jetzt auch ohne ffmpeg (oder ohne H.264-Encoder) und
  zeigt die Formate als nicht verfügbar an. Nach der Installation von ffmpeg wird erneut geprüft,
  ohne Neustart.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egy kis megbízhatósági javítás az Exportálás ablakhoz.

- **Javítva:** Az Exportálás ablak most ffmpeg nélkül (vagy H.264 kódoló nélkül) is megnyílik, és
  nem elérhetőként mutatja a formátumokat. Az ffmpeg telepítése után újraellenőriz, újraindítás nélkül.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Небольшое исправление надёжности окна экспорта.

- **Исправлено:** окно экспорта теперь открывается и без ffmpeg (или без кодировщика H.264) и
  показывает форматы как недоступные. После установки ffmpeg проверка повторяется без перезапуска.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
إصلاح صغير لموثوقية نافذة التصدير.

- **تم الإصلاح:** تُفتح نافذة التصدير الآن حتى بدون ffmpeg (أو بدون مُرمِّز H.264) وتعرض الصيغ على
  أنها غير متاحة، ثم تتحقق مجددًا فور تثبيت ffmpeg دون إعادة التشغيل.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
导出窗口的一个小可靠性修复。

- **修复：** 即使没有 ffmpeg（或没有 H.264 编码器），导出窗口现在也能打开，并将格式显示为不可用；
  安装 ffmpeg 后会自动重新检测，无需重启。

</details>

## [1.2.2] - 2026-10-25

Export your clips for every platform, upload them straight to YouTube, and enjoy a new launch animation.

### Added
- **Export** (Clips tab, or **Export…** under the render button): pick clips, a platform and a format,
  see the estimated file size before anything renders.
  - Formats: MP4 (H.264, plays everywhere), MP4 (HEVC, about 30% smaller), MP4 (AV1, smallest; shown
    when your graphics card can encode it), MOV, WebM (VP9), GIF (optimized colors, with a size limit)
    and MP3 / M4A (audio only). Your graphics card does the work when it can, the CPU otherwise.
  - Platform presets in one click: **YouTube Shorts, TikTok, Instagram Reels, X / Twitter and
    YouTube 16:9**. Each sets the size, frame rate, bitrate and length limit, and keeps subtitles and
    the hook text out of the areas the app covers with its own buttons. Clips that are too long for
    the platform get a warning.
  - **Subtitle files**: SRT and VTT in any of the 7 languages (the local AI translates them when
    needed), next to the video or instead of burned-in subtitles.
  - **Editor timelines**: FCPXML for DaVinci Resolve and Final Cut Pro, and an XML for Premiere Pro,
    with the cut on your original video, the captions and markers for the detected moments (kills,
    laughter, chat spikes...). CapCut has no open project format, so it isn't offered; import the SRT
    file there.
  - Export several clips with one preset in one go; every clip is its own entry in the queue.
- **Direct YouTube upload** with the free, official YouTube API:
  - Settings > YouTube walks you through creating your own free Google key step by step. It is
    stored only on your computer.
  - Per clip: title, description and hashtags filled in from the publish package, visibility
    (private / unlisted / public), scheduled publishing, the "made for kids" answer and a thumbnail
    for 16:9 videos.
  - Uploads run in their own network queue next to rendering (they never wait for the graphics
    card), continue where they stopped after a restart, and the app shows how many uploads are left
    today.
  - SharkyClips remembers each video and fetches its views by itself, so public clips older than
    two days calibrate the viral score automatically (Stats > **Fetch views from YouTube**).
  - Note: Google keeps videos uploaded through a new, unaudited Google Cloud project private until
    the project passes Google's free API audit. Private uploads always work.
- **Launch animation**: a water line draws across the screen, the shark fin rises out of it and
  glides, a quick cut reveals the name, then the logo flies into the header while the app fades in.
  It plays while SharkyClips starts (no extra waiting) and click or Esc skips it.
- **Smoother app**: cards and lists glide in, the Hype Map bars grow on load, scores count up,
  pages fade between each other, and loading spots show soft placeholders instead of spinners.
- Settings > **Animations: Full / Reduced / Off**. Your system's "reduce motion" setting is always
  respected (simple fades only).

### Fixed
- Saving a setting could fail now and then on Windows while the app was reading its settings file.

<!-- lang:tr -->
**Türkçe**

Kliplerini her platform için dışa aktar, doğrudan YouTube'a yükle ve yeni açılış animasyonunun tadını çıkar.

### Eklendi
- **Dışa aktarma** (Klipler sekmesi ya da render düğmesinin altındaki **Dışa aktar…**): klipleri,
  platformu ve formatı seç; render başlamadan tahmini dosya boyutunu gör.
  - Formatlar: MP4 (H.264, her yerde oynar), MP4 (HEVC, ~%30 daha küçük), MP4 (AV1, en küçük; ekran
    kartın kodlayabiliyorsa görünür), MOV, WebM (VP9), GIF (optimize renkler, boyut sınırıyla) ve
    MP3 / M4A (yalnızca ses). Mümkünse işi ekran kartı yapar, değilse işlemci.
  - Tek tıkla platform ayarları: **YouTube Shorts, TikTok, Instagram Reels, X / Twitter ve
    YouTube 16:9**. Her biri boyutu, kare hızını, bit hızını ve süre sınırını ayarlar; altyazıları ve
    kanca metnini uygulamanın kendi düğmeleriyle kapattığı alanlardan uzak tutar. Platform için fazla
    uzun klipler uyarı alır.
  - **Altyazı dosyaları**: 7 dilin herhangi birinde SRT ve VTT (gerekirse yerel yapay zekâ çevirir);
    videonun yanında ya da gömülü altyazı yerine.
  - **Kurgu zaman çizelgeleri**: DaVinci Resolve ve Final Cut Pro için FCPXML, Premiere Pro için XML;
    orijinal videondaki kesim, altyazılar ve bulunan anlar için işaretçiler (kill'ler, kahkaha, sohbet
    patlamaları...). CapCut'ın açık bir proje formatı olmadığı için sunulmuyor; oraya SRT dosyasını aktar.
  - Birden fazla klibi tek ayarla tek seferde dışa aktar; her klip kuyrukta ayrı bir iş olur.
- Ücretsiz, resmî YouTube API'siyle **doğrudan YouTube'a yükleme**:
  - Ayarlar > YouTube, kendi ücretsiz Google anahtarını oluşturman için seni adım adım yönlendirir.
    Anahtar yalnızca bilgisayarında saklanır.
  - Her klip için: yayın paketinden doldurulan başlık, açıklama ve etiketler; görünürlük (gizli /
    liste dışı / herkese açık), zamanlanmış yayın, "çocuklara özel" cevabı ve 16:9 videolar için
    küçük resim.
  - Yüklemeler render ile yan yana kendi ağ kuyruğunda çalışır (ekran kartını hiç beklemez), yeniden
    başlatmadan sonra kaldığı yerden devam eder; uygulama bugün kaç yükleme hakkın kaldığını gösterir.
  - SharkyClips her videoyu hatırlar ve izlenmelerini kendisi alır; iki günden eski herkese açık
    klipler viral puanı otomatik kalibre eder (İstatistikler > **İzlenmeleri YouTube'dan al**).
  - Not: Google, yeni ve denetlenmemiş bir Google Cloud projesiyle yüklenen videoları, proje
    Google'ın ücretsiz API denetiminden geçene kadar gizli tutar. Gizli yüklemeler her zaman çalışır.
- **Açılış animasyonu**: ekrana bir su çizgisi çizilir, köpekbalığı yüzgeci içinden yükselip süzülür,
  hızlı bir kesik adı ortaya çıkarır; ardından logo üst çubuğa uçar ve uygulama belirir. SharkyClips
  açılırken oynar (ek bekleme yok); tıklayınca veya Esc ile geçilir.
- **Daha akıcı uygulama**: kartlar ve listeler kayarak gelir, Heyecan Haritası çubukları yüklenirken
  yükselir, puanlar sayarak artar, sayfalar yumuşak geçer; yükleme yerlerinde dönen simge yerine
  sakin yer tutucular var.
- Ayarlar > **Animasyonlar: Tam / Azaltılmış / Kapalı**. Sistemindeki "hareketi azalt" ayarına her
  zaman uyulur (yalnızca yumuşak geçişler).

### Düzeltildi
- Windows'ta uygulama ayar dosyasını okurken bir ayarı kaydetmek ara sıra başarısız olabiliyordu.

<details><summary>Deutsch</summary>

<!-- lang:de -->
Exportiere Clips für jede Plattform, lade sie direkt auf YouTube hoch, und genieße die neue Startanimation.

- **Neu: Export** mit geschätzter Dateigröße vorab: MP4 (H.264, HEVC, AV1 bei passender Grafikkarte),
  MOV, WebM, GIF mit Größenlimit, MP3/M4A. Ein-Klick-Vorgaben für YouTube Shorts, TikTok, Instagram
  Reels, X und YouTube 16:9 (Größe, fps, Bitrate, Längenlimit, Untertitel außerhalb der App-Buttons).
- **Neu:** SRT/VTT-Untertitel in allen 7 Sprachen (bei Bedarf von der lokalen KI übersetzt) und
  Schnitt-Timelines für DaVinci Resolve, Final Cut Pro (FCPXML) und Premiere Pro (XML) mit Markern.
  CapCut hat kein offenes Projektformat; importiere dort die SRT-Datei.
- **Neu: YouTube-Upload** über die kostenlose offizielle API mit deinem eigenen Google-Schlüssel:
  Titel, Beschreibung, Hashtags, Sichtbarkeit, Planung, „für Kinder“, Thumbnail; eigene
  Netzwerk-Warteschlange, verbleibende Uploads pro Tag, Aufrufe kalibrieren den Viral-Score.
- **Neu:** Startanimation (Flosse taucht auf, Logo fliegt in die Kopfzeile), flüssigere Oberfläche und
  Einstellungen > Animationen: Voll / Reduziert / Aus.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Exportáld a klipjeidet bármely platformra, töltsd fel őket közvetlenül a YouTube-ra, és élvezd az új indítóanimációt.

- **Új: exportálás** előre becsült fájlmérettel: MP4 (H.264, HEVC, AV1 megfelelő videokártyával), MOV,
  WebM, GIF méretkorláttal, MP3/M4A. Egykattintásos beállítások: YouTube Shorts, TikTok, Instagram
  Reels, X és YouTube 16:9 (méret, fps, bitráta, hosszkorlát, feliratok az alkalmazás gombjain kívül).
- **Új:** SRT/VTT feliratok mind a 7 nyelven (szükség esetén a helyi MI fordítja) és vágási idővonalak
  DaVinci Resolve-hoz, Final Cut Pro-hoz (FCPXML) és Premiere Pro-hoz (XML) jelölőkkel. A CapCut-nak
  nincs nyílt projektformátuma; oda az SRT fájlt importáld.
- **Új: YouTube-feltöltés** az ingyenes hivatalos API-val, a saját Google-kulcsoddal: cím, leírás,
  hashtagek, láthatóság, ütemezés, „gyerekeknek” jelölés, bélyegkép; saját hálózati sor, napi
  feltöltési keret, a megtekintések kalibrálják a virális pontszámot.
- **Új:** indítóanimáció (felbukkanó uszony, a logó a fejlécbe repül), gördülékenyebb felület és
  Beállítások > Animációk: Teljes / Csökkentett / Ki.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Экспортируйте клипы для любой платформы, загружайте их прямо на YouTube и встречайте новую анимацию запуска.

- **Новое: экспорт** с оценкой размера файла заранее: MP4 (H.264, HEVC, AV1 при подходящей видеокарте),
  MOV, WebM, GIF с лимитом размера, MP3/M4A. Пресеты в один клик: YouTube Shorts, TikTok, Instagram
  Reels, X и YouTube 16:9 (размер, fps, битрейт, лимит длины, субтитры вне кнопок приложения).
- **Новое:** субтитры SRT/VTT на всех 7 языках (при необходимости переводит локальный ИИ) и таймлайны
  для DaVinci Resolve, Final Cut Pro (FCPXML) и Premiere Pro (XML) с маркерами. У CapCut нет открытого
  формата проектов; импортируйте туда файл SRT.
- **Новое: загрузка на YouTube** через бесплатный официальный API с вашим собственным ключом Google:
  название, описание, хештеги, доступ, расписание, «для детей», превью; своя сетевая очередь,
  остаток загрузок на день, просмотры калибруют вирусный балл.
- **Новое:** анимация запуска (плавник всплывает, логотип улетает в шапку), более плавный интерфейс и
  Настройки > Анимации: Полные / Упрощённые / Выкл.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
صدّر مقاطعك لكل منصة، وارفعها مباشرة إلى YouTube، واستمتع بحركة البدء الجديدة.

- **جديد: التصدير** مع حجم ملف تقديري مسبقًا: MP4 (H.264 وHEVC وAV1 مع بطاقة رسوميات مناسبة) وMOV
  وWebM وGIF بحد للحجم وMP3/M4A. إعدادات بنقرة واحدة: YouTube Shorts وTikTok وInstagram Reels وX
  وYouTube 16:9 (الحجم، الإطارات، معدل البت، حد الطول، والترجمة بعيدًا عن أزرار التطبيق).
- **جديد:** ترجمة SRT/VTT بجميع اللغات السبع (يترجمها الذكاء الاصطناعي المحلي عند الحاجة) وخطوط
  زمنية لـ DaVinci Resolve وFinal Cut Pro (FCPXML) وPremiere Pro (XML) مع علامات. لا يملك CapCut
  صيغة مشاريع مفتوحة؛ استورد ملف SRT فيه.
- **جديد: الرفع إلى YouTube** عبر الواجهة الرسمية المجانية بمفتاح Google الخاص بك: العنوان والوصف
  والوسوم والظهور والجدولة و«مخصص للأطفال» والصورة المصغرة؛ قائمة شبكة خاصة، وعدد مرات الرفع
  المتبقية اليوم، والمشاهدات تعاير درجة الانتشار.
- **جديد:** حركة بدء (يظهر الزعنف ويطير الشعار إلى الشريط العلوي)، واجهة أكثر سلاسة، والإعدادات >
  الحركة: كاملة / مخففة / متوقفة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
为各个平台导出片段、直接上传到 YouTube，并迎来全新的启动动画。

- **新增：导出**，渲染前即可看到预计文件大小：MP4（H.264、HEVC，显卡支持时还有 AV1）、MOV、WebM、
  带大小上限的 GIF、MP3/M4A。一键平台预设：YouTube Shorts、TikTok、Instagram Reels、X 和
  YouTube 16:9（尺寸、帧率、码率、时长上限，字幕避开平台按钮）。
- **新增：** 7 种语言的 SRT/VTT 字幕（需要时由本地 AI 翻译），以及带标记的剪辑时间线：DaVinci
  Resolve、Final Cut Pro（FCPXML）和 Premiere Pro（XML）。CapCut 没有开放的工程格式，请在其中导入 SRT。
- **新增：直接上传到 YouTube**，使用免费的官方 API 和你自己的 Google 密钥：标题、说明、话题标签、
  公开范围、定时发布、“为儿童打造”、缩略图；独立的网络队列，显示今日剩余上传次数，播放量自动
  校准爆款分数。
- **新增：** 启动动画（鱼鳍浮出水面，标志飞入顶栏）、更流畅的界面，以及 设置 > 动画：完整 / 减少 / 关闭。

</details>

## [1.2.1] - 2026-10-25

ClipForge is now **SharkyClips**, with a new logo, a welcome screen and a working publish package.

### Fixed
- **Publish package was empty**: re-running the highlight analysis (for example after the new game
  scan) threw away every clip's AI results, and the follow-up AI analysis was lost when it was paused
  or the app restarted. Clips whose cut didn't change now keep their titles, hashtags and cover
  prompt, and the AI analysis is a saved job that continues after a pause or restart.
- The publish package always says what is going on: "Not analyzed yet" with an **Analyze with AI**
  button, "Waiting: paused (game detected)", "Analyzing 3/15", or the error with **Try again**.
  No more empty grey boxes.
- **No more black console windows** flashing up while SharkyClips works: every helper program runs
  hidden, and the performance governor starts none at all. Ollama's helper programs no longer open
  a window every few seconds while the AI model loads.

### Added
- **YouTube description** for every clip: 2-3 natural sentences in the output language plus the
  hashtags at the end, with a copy button. Clips analyzed before only need one short AI call.
- **New name and logo**: a shark fin that is also a play button. Blue and white for the main logo,
  white on navy for the dark theme, the tray and the app icon (SVG, PNG, ICO, ICNS, favicon).
- **Welcome screen**: a short splash with the slogan "Hunt your best moments." on every start
  (click or Esc skips it; it plays while the server starts, so it never adds waiting time). On the
  first start a 3-step setup follows: language, content types, performance mode + a quick
  hardware check.
- **What's new** window after an update (this one), and the version in the footer and Settings.
- "Update in progress" banner while a new version is being built; heavy jobs ask before they start.

### Changed
- Colors: crisp white for headings, key numbers and secondary buttons in the dark theme (gold is
  the accent only); a cleaner, whiter light theme with more room.
- Settings moved from `~/.clipforge` to `~/.sharkyclips` by themselves (settings, workspace path,
  liked titles, glossary, calibration); desktop and Start menu shortcuts and the Apps & features
  entry are renamed. `CLIPFORGE_HOME` still works.
- The Python package and CLI are now `sharkyclips`. The version lives in one place: `VERSION`.

<!-- lang:tr -->
**Türkçe**

ClipForge artık **SharkyClips**: yeni logo, karşılama ekranı ve düzgün çalışan yayın paketi.

### Düzeltildi
- **Yayın paketi boş görünüyordu**: öne çıkanlar analizi yeniden çalışınca (ör. yeni oyun taraması
  sonrası) tüm kliplerin yapay zekâ sonuçları siliniyordu; ardından gelen yapay zekâ analizi de
  duraklatılınca veya uygulama yeniden başlayınca kayboluyordu. Kesimi değişmeyen klipler artık
  başlıklarını, etiketlerini ve kapak istemlerini korur; yapay zekâ analizi kayıtlı bir iş olarak
  duraklama ya da yeniden başlatma sonrası kaldığı yerden devam eder.
- Yayın paketi her zaman ne olduğunu söyler: **Yapay zekâyla analiz et** düğmesiyle "Henüz analiz
  edilmedi", "Bekliyor: duraklatıldı (oyun algılandı)", "Analiz ediliyor 3/15" ya da **Tekrar dene**
  ile hata. Artık boş gri kutular yok.
- SharkyClips çalışırken **siyah konsol pencereleri artık açılıp kapanmıyor**: tüm yardımcı programlar
  gizli çalışır, performans yöneticisi hiç program başlatmaz. Yapay zekâ modeli yüklenirken Ollama'nın
  yardımcı programları artık birkaç saniyede bir pencere açmıyor.

### Eklendi
- Her klip için **YouTube açıklaması**: çıktı dilinde 2-3 doğal cümle ve sonunda etiketler,
  kopyalama düğmesiyle. Daha önce analiz edilen kliplere tek kısa yapay zekâ çağrısı yeter.
- **Yeni ad ve logo**: aynı zamanda oynat düğmesi olan bir köpekbalığı yüzgeci. Ana logo mavi-beyaz;
  koyu tema, sistem tepsisi ve uygulama simgesi için lacivert üzerine beyaz (SVG, PNG, ICO, ICNS, favicon).
- **Karşılama ekranı**: her açılışta "En iyi anların avlanmaya hazır." sloganıyla kısa bir açılış
  (tıklayınca veya Esc ile geçilir; sunucu başlarken oynar, bekleme eklemez). İlk açılışta 3 adımlı
  kurulum: dil, içerik türleri, performans modu + hızlı donanım kontrolü.
- Güncellemeden sonra **Yenilikler** penceresi (bu pencere); sürüm alt bilgide ve Ayarlar'da.
- Yeni sürüm hazırlanırken "Güncelleme yapılıyor" şeridi; ağır işler başlamadan önce sorar.

### Değişti
- Renkler: koyu temada başlıklar, önemli sayılar ve ikincil düğmeler için net beyaz (altın yalnızca
  vurgu); daha temiz, daha beyaz ve daha ferah açık tema.
- Ayarlar `~/.clipforge` klasöründen `~/.sharkyclips` klasörüne kendiliğinden taşındı (ayarlar,
  çalışma klasörü, beğenilen başlıklar, sözlük, kalibrasyon); masaüstü ve Başlat menüsü kısayolları ile
  Uygulamalar listesindeki kayıt yeniden adlandırıldı. `CLIPFORGE_HOME` hâlâ çalışır.
- Python paketi ve komut satırı artık `sharkyclips`. Sürüm tek bir yerde: `VERSION`.

<details><summary>Deutsch</summary>

<!-- lang:de -->
ClipForge heißt jetzt **SharkyClips**: neues Logo, Begrüßungsbildschirm und ein funktionierendes Veröffentlichungspaket.

- **Behoben:** Das Veröffentlichungspaket war leer, nachdem die Highlight-Analyse erneut lief. Clips mit
  unverändertem Schnitt behalten jetzt ihre KI-Ergebnisse, und die KI-Analyse läuft nach einer
  Pause oder einem Neustart weiter. Das Paket zeigt immer seinen Zustand (nicht analysiert, wartet,
  „Analyse 3/15“, Fehler mit „Erneut versuchen“).
- **Behoben:** Keine aufblitzenden schwarzen Konsolenfenster mehr, während SharkyClips arbeitet.
- **Neu:** YouTube-Beschreibung pro Clip (2-3 Sätze + Hashtags) mit Kopier-Button.
- **Neu:** Logo (Haifischflosse als Play-Button), Startbildschirm mit Slogan, Einrichtung in 3 Schritten
  beim ersten Start, dieses „Neu in“-Fenster, Version in Fußzeile und Einstellungen.
- **Geändert:** Weiß als Markenfarbe im dunklen Design, helleres und luftigeres helles Design.
  Einstellungen wurden automatisch von `~/.clipforge` nach `~/.sharkyclips` verschoben.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A ClipForge mostantól **SharkyClips**: új logó, üdvözlőképernyő és működő közzétételi csomag.

- **Javítva:** a közzétételi csomag üres volt a kiemelések újraelemzése után. A változatlan vágású
  klipek megtartják az MI-eredményeiket, az MI-elemzés pedig szünet vagy újraindítás után folytatódik.
  A csomag mindig mutatja az állapotát (nincs elemezve, várakozik, „Elemzés 3/15”, hiba „Újra” gombbal).
- **Javítva:** nem villannak fel többé fekete konzolablakok, miközben a SharkyClips dolgozik.
- **Új:** YouTube-leírás minden kliphez (2-3 mondat + hashtagek) másolás gombbal.
- **Új:** logó (cápauszony, ami lejátszás gomb is), indítóképernyő szlogennel, 3 lépéses beállítás az első
  indításkor, ez az „Újdonságok” ablak, verzió a láblécben és a Beállításokban.
- **Változott:** fehér márkaszín a sötét témában, tisztább és levegősebb világos téma. A beállítások
  maguktól átkerültek a `~/.clipforge` mappából a `~/.sharkyclips` mappába.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
ClipForge теперь называется **SharkyClips**: новый логотип, экран приветствия и рабочий пакет публикации.

- **Исправлено:** пакет публикации был пустым после повторного поиска лучших моментов. Клипы с
  неизменной нарезкой сохраняют результаты ИИ, а ИИ-анализ продолжается после паузы или перезапуска.
  Пакет всегда показывает состояние (не проанализировано, ожидание, «Анализ 3/15», ошибка с «Повторить»).
- **Исправлено:** во время работы SharkyClips больше не мелькают чёрные окна консоли.
- **Новое:** описание для YouTube у каждого клипа (2-3 предложения + хештеги) с кнопкой копирования.
- **Новое:** логотип (плавник акулы, он же кнопка воспроизведения), заставка со слоганом, настройка
  в 3 шага при первом запуске, это окно «Что нового», версия в подвале и в настройках.
- **Изменено:** белый как фирменный цвет в тёмной теме, более чистая и просторная светлая тема.
  Настройки автоматически перенесены из `~/.clipforge` в `~/.sharkyclips`.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح ClipForge الآن **SharkyClips**: شعار جديد وشاشة ترحيب وحزمة نشر تعمل بشكل صحيح.

- **إصلاح:** كانت حزمة النشر فارغة بعد إعادة تحليل اللقطات المميزة. تحتفظ المقاطع التي لم يتغير قصّها
  الآن بنتائج الذكاء الاصطناعي، ويستمر التحليل بعد الإيقاف المؤقت أو إعادة التشغيل. وتعرض الحزمة
  حالتها دائمًا (لم يُحلَّل بعد، في الانتظار، «جارٍ التحليل 3/15»، خطأ مع «إعادة المحاولة»).
- **إصلاح:** لم تعد نوافذ وحدة التحكم السوداء تظهر وتختفي أثناء عمل SharkyClips.
- **جديد:** وصف YouTube لكل مقطع (2-3 جمل + الوسوم) مع زر نسخ.
- **جديد:** شعار (زعنفة قرش هي أيضًا زر تشغيل)، شاشة بداية مع الشعار النصي، إعداد من 3 خطوات عند
  التشغيل الأول، نافذة «ما الجديد» هذه، ورقم الإصدار في التذييل والإعدادات.
- **تغيير:** الأبيض لون أساسي في السمة الداكنة، وسمة فاتحة أنظف وأكثر اتساعًا. نُقلت الإعدادات
  تلقائيًا من `~/.clipforge` إلى `~/.sharkyclips`.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
ClipForge 现更名为 **SharkyClips**：新标志、欢迎界面，以及正常工作的发布包。

- **修复：** 重新运行高光分析后发布包为空。剪辑范围未变的片段现在会保留 AI 结果，AI 分析在暂停或重启后会继续。
  发布包始终显示当前状态（尚未分析、等待中、“正在分析 3/15”、出错时可“重试”）。
- **修复：** SharkyClips 工作时不再闪现黑色控制台窗口。
- **新增：** 每个片段的 YouTube 简介（2-3 句 + 话题标签），可一键复制。
- **新增：** 标志（鲨鱼鳍同时也是播放按钮）、带标语的启动画面、首次启动的 3 步设置、本“新功能”窗口，页脚和设置中显示版本号。
- **变更：** 深色主题以白色为品牌色，浅色主题更干净、更留白。设置已自动从 `~/.clipforge` 迁移到 `~/.sharkyclips`。

</details>

## [1.2.0] - 2026-10-25

SharkyClips must never slow down the PC.

### Added
- **Performance modes**: Silent (default), Balanced and Turbo, in Settings, the top bar and the
  tray menu. Silent works at idle priority on half the CPU threads, throttled, and pauses while a
  game (editable list, prefilled with League of Legends + its client, Delta Force, CS2, Valorant
  and more), OBS/streaming software, a fullscreen app or a video is on, or other apps keep the
  PC busy. Full speed when you're away (3 min without input, or a locked screen).
- **Resource governor**: priority, low I/O priority and CPU limits for every child process
  (Windows Job Object; macOS background QoS); ~2 GB of VRAM always kept free (Whisper and Ollama
  adapt); thermal guard; pauses resume exactly where they stopped and unload the AI model first.
- **Resource monitor** in the top bar: CPU, GPU, VRAM, RAM, GPU temperature, mode and state with
  "Resume anyway"; click for 5-minute charts split into SharkyClips vs. other apps.
- **Tray icon** and a window-less launcher (pythonw): Open, performance mode, Quit. Log file in
  `~/.sharkyclips/logs/sharkyclips.log`. Old shortcuts are switched over on the next start.
- Setting "Start Ollama with Windows" (off by default).

### Changed
- Ollama is unloaded (`keep_alive 0`) after every GPU job and as soon as a pause starts; an
  Ollama server SharkyClips starts is stopped with it.
- Idle cost: with no job and no visible UI tab, SharkyClips reads only CPU/RAM every 10 s and never
  touches the GPU.
- Every subprocess starts without a console window on Windows.

### Fixed
- Ollama's installer/updater made it start with Windows; its Startup shortcut is now parked in
  `~/.sharkyclips/disabled-startup/` unless you enable autostart.

## [1.1.0] - 2026-10-25

### Added
- **Game awareness for Delta Force and League of Legends** (new `game` highlight signal). SharkyClips
  samples the video at 2 fps (NVDEC on NVIDIA GPUs, only the frames it needs) and reads the game's
  HUD with OCR (PaddleOCR models via RapidOCR, CPU), only where something changed:
  - League of Legends: the K/D/A counter gives every kill, death and assist; double / triple /
    quadra / pentakill from the kill timing (any client language), first blood, shutdown / ace /
    baron / dragon (steal or secure) from the announcer banner, victory / defeat screens, and the
    champion (from the HUD portrait, matched against Riot's Data Dragon icons).
  - Delta Force: kills, multikills and revives from the icons above the score counter (counted with
    the score lines: "Öldürme +100 DP", "Çifte Öldürme"), revenge kills, assists, own deaths (the
    red "killed by" card; being downed doesn't count) and extraction results.
  - A full scan runs at about 20-45x realtime with NVDEC (a 4 h stream in roughly 6-12 minutes).
  - Big game moments (triple kill and up, steals, extractions) always become a clip candidate.
  - Events become reason chips (translated in all 7 languages) and lift the hype curve by their size
    (pentakill >> double kill). A clip always contains the whole event, e.g. every kill of a
    multikill, plus its build-up.
  - The local AI gets the events as facts for titles and descriptions ("Quadra kill with Yasuo").
  - Optional sound matching: short reference clips in `~/.sharkyclips/game_sounds/<game>/<event>.mp3`
    are found in the stream audio.
- Game picker per project (Auto / Delta Force / League of Legends / Other) next to the mode.
- **Game detection page** (gamepad button on a project): sampled frames with the HUD boxes drawn
  on them, every detected event, the OCR text around each moment, "Read this frame", and box editing
  saved per computer (`~/.sharkyclips/game_regions.json`) for when a game update moves the HUD.

## [1.0.0] - 2026-10-24

The first public release: everything below, plus a one-click installer and self-updates.

### Added
- **One-click install.** Windows: `install.bat`, or the standalone `SharkyClips-Setup.bat` from the
  release, which downloads SharkyClips first. macOS: `install.sh`. The installer lists what it will set
  up (Python, FFmpeg, Git, Deno, Ollama, Python packages, AI models), asks once, reuses what is
  already installed, and shows messages in Turkish or English.
- **Desktop shortcut and Start menu entry** (Windows) or `SharkyClips.command` + `SharkyClips.app` (macOS)
  with the new icon. They open SharkyClips in the browser, reuse an already running SharkyClips, and pick a
  free port if 8000 is taken (`cli.py launch`).
- **Uninstaller** (Windows: Apps & features or `installer\windows\uninstall.bat`; macOS:
  `installer/macos/uninstall.sh`). It asks before deleting projects, settings or AI models.
- **Settings → Updates**: checks GitHub for a new version and installs it (`git pull` + new packages),
  then SharkyClips restarts by itself.
- `cli.py doctor --download-models` fetches the Whisper model during setup instead of on the first
  transcription.
- New app icon (gold diamond on navy) as `.ico`, `.icns`, `.png` and favicon, also used in the header.
- README with screenshots in dark and light theme and a demo GIF; detailed reference in
  `docs/how-it-works.md`.
- Tests (pytest), lint (ruff), GitHub Actions CI (backend on Windows + Linux, frontend type check,
  translations check and build, installer script checks), issue templates.

### Earlier milestones (before 1.0.0, unreleased)
- **Batch queue, best-of video, calibration**: one render job per clip with reorder / retry / cancel,
  the queue survives restarts, optional shutdown when done; 16:9 best-of videos with title cards,
  crossfades, loudness normalization and AI chapters; channel calibration from real YouTube views;
  Fast analysis with the smaller model.
- **Natural AI titles**: few-shot examples per language, glossary, proofreading pass, offline
  dictionary check, Turkish vowel harmony fixes, thumbs up/down that teach your style.
- **Chat signal + local LLM** (Ollama, Qwen 3.5): chat replay from YouTube / Twitch / log files, viral
  score, refined cuts, titles, hashtags, hook text, cover prompt, subtitle translation.
- **Web UI + 9:16 rendering**: library, project review with Hype Map and live 9:16 preview, facecam
  detection and editor, burned-in word-timed subtitles (incl. right-to-left Arabic), 7 UI languages,
  dark/light theme, LAN mode.
- **Highlight engine**: loudness, keywords, laughter/shouting, speech rhythm, music signals combined
  into a hype curve with word-snapped, non-overlapping clip candidates.
- **Foundations**: hardware detection, `doctor` with a real GPU smoke test and automatic fixes,
  ingest from URL or file, resumable multilingual transcription with word timestamps.

[1.0.0]: https://github.com/utkualsir/sharkyclips/releases/tag/v1.0.0
