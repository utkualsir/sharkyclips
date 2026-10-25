# Changelog

All notable changes to SharkyClips (called ClipForge before 1.2.1). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Every update bumps the patch version by 0.0.1.

Each entry is in English, then Turkish; short summaries in the other UI languages follow in
`<!-- lang:xx -->` blocks. The app's "What's new" window shows the block of the UI language.

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
