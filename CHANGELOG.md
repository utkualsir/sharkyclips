# Changelog

All notable changes to SharkyClips (called ClipForge before 1.2.1). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Every update bumps the patch version by 0.0.1.

Each entry is in English, then Turkish; short summaries in the other UI languages follow in
`<!-- lang:xx -->` blocks. The app's "What's new" window shows the block of the UI language.

## [1.2.25] - 2026-11-07

### Fixed
- **No more hashtags from other games.** A League of Legends clip could get hashtags like
  #Warzone or #CallofDuty. The AI guessed the game again for every single clip, and on a stream
  without a clear title it sometimes guessed wrong (Valorant, Call of Duty, Overwatch...). Now the
  game is decided once for the whole video (the game you picked, the game screen, the title and
  what you say) and every title, description, hashtag and tag is about that game only. Anything
  that names a different game is thrown out. When the game is unknown, only general gaming
  hashtags are used, never a guess.

### New
- **Hashtags in the right order:** your channel hashtag first (#yourchannel), then #shorts, then
  the game (#leagueoflegends, #deltaforce...), then 2-4 about the clip itself (#pentakill,
  #yasuo, #extraction...), Turkish and English mixed. YouTube shows the first three above the
  title. 5-8 hashtags in total.
- **Real YouTube tags:** 10-20 tags people actually search for ("lol pentakill", "yasuo montage",
  "delta force türkçe"...), with your channel name, and never another game.
- **Livelier descriptions:** 2-3 sentences about what happens in this clip, in a streamer's tone,
  ending with a question for the comments ("What would you have done?").
- **Socials block:** set your links once in **Studio > Brand kit > Channel text**; they go at the
  end of every YouTube description, best-of, TikTok and Reels caption (heading in the video's
  language). Short captions drop whole lines from the bottom, a link is never cut.
- **Stronger titles:** 1-2 KEY WORDS IN CAPITALS (CLUTCH, PENTAKILL, 1v4, ACE), curiosity or
  emotion, at most one "!", sometimes one emoji at the end, 40-60 characters. Six different kinds
  per clip (shock, question, "nobody expected", number, story, short and punchy). Hook and cover
  texts follow the same style. Your 👍 / 👎 still teach it your taste.
- **Studio > Games:** the words for League of Legends, Delta Force, CS2, Valorant and unknown games
  (hashtags, tags, champions, operators, maps, weapons, key words) as editable lists.
- **Project page:** a "Texts" picker sets the game for a project's titles and hashtags; changing it
  writes them again without rendering the clips again.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- **Artık başka oyunların hashtag'leri yok.** Bir League of Legends klibine #Warzone ya da
  #CallofDuty gibi hashtag'ler gelebiliyordu. Yapay zeka oyunu her klip için yeniden tahmin
  ediyordu ve başlığı belli olmayan bir yayında bazen yanlış tahmin ediyordu (Valorant, Call of
  Duty, Overwatch...). Artık oyun tüm video için bir kez belirleniyor (senin seçtiğin oyun, oyun
  ekranı, başlık ve söylediklerin) ve her başlık, açıklama, hashtag ve etiket sadece o oyunla
  ilgili. Başka bir oyunun adını geçiren her şey atılıyor. Oyun bilinmiyorsa sadece genel oyun
  hashtag'leri kullanılıyor, asla tahmin yok.

### Yeni
- **Doğru sırada hashtag'ler:** önce kanal hashtag'in (#kanalın), sonra #shorts, sonra oyun
  (#leagueoflegends, #deltaforce...), sonra klibin kendisiyle ilgili 2-4 tane (#pentakill,
  #yasuo, #extraction...), Türkçe ve İngilizce karışık. YouTube ilk üçünü başlığın üstünde
  gösterir. Toplam 5-8 hashtag.
- **Gerçek YouTube etiketleri:** insanların gerçekten aradığı 10-20 etiket ("lol pentakill",
  "yasuo montage", "delta force türkçe"...), kanal adınla birlikte, asla başka bir oyun yok.
- **Daha canlı açıklamalar:** bu klipte ne olduğunu anlatan, yayıncı ağzıyla 2-3 cümle; sonunda
  yorumlar için bir soru ("Sen olsan ne yapardın?").
- **Sosyal medya bloğu:** bağlantılarını bir kez **Stüdyo > Marka kiti > Kanal metni** içinde
  gir; her YouTube açıklamasının, best-of videonun, TikTok ve Reels metninin sonuna eklenir
  (başlığı videonun dilinde). Kısa metinlerde alttan bütün satırlar düşülür, bağlantı asla kesilmez.
- **Daha güçlü başlıklar:** 1-2 BÜYÜK HARF ANAHTAR KELİME (CLUTCH, PENTAKILL, 1v4, ACE), merak
  ya da duygu, en fazla bir "!", bazen sonda bir emoji, 40-60 karakter. Her klip için altı farklı
  tür (şok, soru, "kimse beklemiyordu", sayı, hikâye, kısa ve vurucu). Hook ve kapak yazıları da
  aynı tarzda. 👍 / 👎 oyların hâlâ zevkini öğretiyor.
- **Stüdyo > Oyunlar:** League of Legends, Delta Force, CS2, Valorant ve bilinmeyen oyunlar için
  kelimeler (hashtag'ler, etiketler, şampiyonlar, operatörler, haritalar, silahlar, anahtar
  kelimeler) düzenlenebilir listeler olarak.
- **Proje sayfası:** "Metinler" seçicisi projenin başlık ve hashtag'lerinin hangi oyun için
  olduğunu belirler; değiştirince klipler yeniden render edilmeden hepsi yeniden yazılır.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Keine Hashtags anderer Spiele mehr:** das Spiel wird einmal für das ganze Video bestimmt;
  Titel, Beschreibungen, Hashtags und Tags handeln nur von diesem Spiel (unbekanntes Spiel: nur
  allgemeine Gaming-Hashtags).
- **Neu:** Hashtags in fester Reihenfolge (Kanal, #shorts, Spiel, 2-4 zum Clip), 10-20 echte
  YouTube-Tags, lebendigere Beschreibungen mit einer Frage am Ende, Social-Media-Block aus dem
  Brand-Kit, stärkere Titel mit 1-2 Schlüsselwörtern in GROSSBUCHSTABEN, Studio > Spiele.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **Nincs több más játékból származó hashtag:** a játékot egyszer, az egész videóra határozzuk
  meg; a címek, leírások, hashtagek és címkék csak erről a játékról szólnak (ismeretlen játéknál
  csak általános gamer hashtagek).
- **Új:** hashtagek fix sorrendben (csatorna, #shorts, játék, 2-4 a klipről), 10-20 valódi
  YouTube-címke, élénkebb leírások kérdéssel a végén, közösségi blokk a Márkacsomagból, erősebb
  címek 1-2 NAGYBETŰS kulcsszóval, Stúdió > Játékok.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Больше никаких хештегов других игр:** игра определяется один раз для всего видео; названия,
  описания, хештеги и теги — только про эту игру (если игра неизвестна — только общие игровые
  хештеги).
- **Новое:** хештеги в чётком порядке (канал, #shorts, игра, 2-4 про клип), 10-20 настоящих тегов
  YouTube, живые описания с вопросом в конце, блок соцсетей из «Брендинга», сильные названия с
  1-2 КЛЮЧЕВЫМИ словами капсом, Студия > Игры.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **لا وسوم من ألعاب أخرى بعد الآن:** تُحدَّد اللعبة مرة واحدة للفيديو كله، والعناوين والأوصاف
  والوسوم والعلامات كلها عن هذه اللعبة فقط (لعبة غير معروفة: وسوم ألعاب عامة فقط).
- **جديد:** وسوم بترتيب ثابت (القناة، #shorts، اللعبة، 2-4 عن المقطع)، 10-20 علامة يوتيوب حقيقية،
  أوصاف أكثر حيوية تنتهي بسؤال، كتلة التواصل من الهوية البصرية، عناوين أقوى بكلمة أو كلمتين
  مفتاحيتين بالأحرف الكبيرة، الاستوديو > الألعاب.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **不再出现其他游戏的话题标签：** 整个视频只确定一次游戏；标题、简介、话题标签和标签都只围绕
  这个游戏（游戏未知时只用通用游戏标签）。
- **新增：** 固定顺序的话题标签（频道、#shorts、游戏、2-4 个关于片段的）、10-20 个真实的 YouTube
  标签、结尾带问题的更生动简介、来自品牌套件的社交媒体区块、带 1-2 个大写关键词的更有力标题、
  工作室 > 游戏。

</details>


## [1.2.24] - 2026-11-07

### Fixed
- **Cancel is final.** Cancelling a render on the Queue screen could look like it worked and then
  the clip started rendering again a moment later: in Easy projects the automatic "render the best
  clips" step saw the clip wasn't rendered and queued it once more. Now a cancelled job stays
  cancelled: nothing automatic brings it back (not Easy, not scheduled publishing, not a restart
  of the app). Only you can start it again, with **Retry** (or by editing the clip / pressing
  Try again).
- **Cancel stops the work right away.** The video encoder of a cancelled job is stopped at once,
  even while SharkyClips is paused for a game, it no longer switches to a second (CPU) attempt,
  and half-written files are deleted.

### New
- **Pause queue:** nothing new starts while the queue is paused (a job that is already running
  finishes). It stays paused after a restart until you press **Resume queue**.
- **Cancel all** now asks once before it cancels everything in the queue.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- **İptal kesindir.** Kuyruk ekranında bir render'ı iptal etmek işe yaramış gibi görünüp birkaç
  saniye sonra klibin yeniden render edilmeye başlamasına yol açabiliyordu: Kolay projelerde
  otomatik "en iyi klipleri render et" adımı klibin render edilmediğini görüp onu tekrar kuyruğa
  ekliyordu. Artık iptal edilen iş iptal edilmiş olarak kalır: hiçbir otomatik adım onu geri
  getirmez (Kolay mod, zamanlanmış yayın ya da uygulamanın yeniden başlaması). Yalnızca sen
  **Tekrar dene** ile (ya da klibi düzenleyerek / Tekrar dene'ye basarak) yeniden başlatabilirsin.
- **İptal işi hemen durdurur.** İptal edilen işin video kodlayıcısı anında durdurulur (SharkyClips
  bir oyun yüzünden duraklamışken bile), artık ikinci bir (CPU) denemesine geçmez ve yarım kalan
  dosyalar silinir.

### Yeni
- **Kuyruğu duraklat:** kuyruk duraklatılmışken yeni iş başlamaz (çalışmakta olan iş biter).
  Uygulama yeniden başlasa da **Kuyruğu sürdür**'e basana kadar duraklatılmış kalır.
- **Hepsini iptal et** artık her şeyi iptal etmeden önce bir kez sorar.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Abbrechen ist endgültig:** ein abgebrochener Render startet nicht mehr von selbst neu (auch
  nicht im Einfach-Modus, beim geplanten Veröffentlichen oder nach einem Neustart). Nur **Erneut
  versuchen** startet ihn wieder. Der Encoder stoppt sofort, halbe Dateien werden gelöscht.
- **Neu:** „Warteschlange pausieren“ (bleibt nach einem Neustart pausiert) und „Alle abbrechen“
  mit Rückfrage.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **A megszakítás végleges:** a megszakított renderelés magától már nem indul újra (Egyszerű
  módban, ütemezett közzétételnél és újraindítás után sem). Csak az **Újra** indítja el. A kódoló
  azonnal leáll, a félkész fájlok törlődnek.
- **Új:** „Sor szüneteltetése” (újraindítás után is szünetel) és „Összes megszakítása” megerősítéssel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Отмена окончательна:** отменённый рендер больше не запускается сам (ни в простом режиме, ни
  при запланированной публикации, ни после перезапуска). Запустить снова можно только кнопкой
  **Повторить**. Кодировщик останавливается сразу, недописанные файлы удаляются.
- **Новое:** «Приостановить очередь» (пауза сохраняется после перезапуска) и «Отменить всё» с
  подтверждением.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **الإلغاء نهائي:** لم يعد العرض الملغى يبدأ من جديد تلقائيًا (لا في الوضع السهل ولا في النشر
  المجدول ولا بعد إعادة التشغيل). وحده زر **إعادة المحاولة** يشغّله مجددًا. يتوقف المُرمِّز فورًا
  وتُحذف الملفات غير المكتملة.
- **جديد:** "إيقاف قائمة الانتظار مؤقتًا" (يبقى بعد إعادة التشغيل) و"إلغاء الكل" مع تأكيد.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **取消即最终：** 已取消的渲染不会再自行重新开始（简易模式、定时发布、重启应用后都不会）。
  只有 **重试** 才能再次开始。编码器立即停止，未写完的文件会被删除。
- **新增：** "暂停队列"（重启后仍保持暂停）和带确认的"全部取消"。

</details>


## [1.2.23] - 2026-11-07

### Fixed
- **The 9:16 preview no longer zooms in and shifts.** On some clips the preview next to the
  player suddenly showed a huge, cut-off part of the picture. The cause was one strange "word"
  in the transcript: on silence or snoring the speech recognition sometimes writes hundreds of
  letters in a row ("Zzzzzz…"). That one word made the transcript box extremely wide, which
  stretched the player and, with it, the preview. Such words are now shortened ("Zzz") or
  removed everywhere (transcript, captions, titles), also in existing projects, and the page
  layout can't be stretched by a long word any more.
- **The preview shows exactly what the clip will look like.** It now cuts the facecam and the
  gameplay with the same numbers as the render, and shows smart zoom, meme punches and shakes
  the same way (with the same 1.25× limit). Checked against real renders.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- **9:16 önizleme artık yakınlaşıp kaymıyor.** Bazı kliplerde oynatıcının yanındaki önizleme
  birden görüntünün devasa, kesik bir parçasını gösteriyordu. Sebebi transkriptteki tek bir
  garip "kelime"ydi: ses tanıma, sessizlikte ya da horlamada bazen art arda yüzlerce harf yazıyor
  ("Zzzzzz…"). Bu tek kelime transkript kutusunu aşırı genişletiyor, oynatıcıyı ve onunla birlikte
  önizlemeyi büyütüyordu. Bu tür kelimeler artık her yerde (transkript, altyazı, başlıklar)
  kısaltılıyor ("Zzz") ya da çıkarılıyor, mevcut projelerde de; sayfa düzeni de artık uzun bir
  kelimeyle genişleyemez.
- **Önizleme klibin tam olarak nasıl görüneceğini gösteriyor.** Kamerayı ve oyunu render ile aynı
  sayılarla kırpıyor; akıllı zoom, meme vuruşları ve sarsıntıları da aynı şekilde (aynı 1,25×
  sınırıyla) gösteriyor. Gerçek render'larla karşılaştırılarak kontrol edildi.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Die 9:16-Vorschau zoomt und verrutscht nicht mehr:** schuld war ein endloses „Wort“ der
  Spracherkennung („Zzzzzz…“), das die Seite gedehnt hat. Solche Wörter werden jetzt gekürzt oder
  entfernt, auch in bestehenden Projekten.
- **Die Vorschau zeigt genau den fertigen Clip:** gleicher Ausschnitt, gleicher Zoom (max. 1,25×).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **A 9:16-os előnézet már nem nagyít és csúszik el:** a beszédfelismerés egy végtelen „szava”
  („Zzzzzz…”) nyújtotta meg az oldalt. Az ilyen szavakat most lerövidítjük vagy töröljük, a
  meglévő projektekben is.
- **Az előnézet pontosan a kész klipet mutatja:** ugyanaz a kivágás és zoom (legfeljebb 1,25×).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Превью 9:16 больше не увеличивается и не съезжает:** виновато было бесконечное «слово»
  распознавания речи («Zzzzzz…»), растягивавшее страницу. Такие слова теперь сокращаются или
  удаляются, и в старых проектах тоже.
- **Превью показывает ровно готовый клип:** та же обрезка и тот же зум (максимум 1,25×).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **معاينة 9:16 لم تعد تتكبّر وتنزاح:** السبب "كلمة" لا نهائية من التعرّف على الكلام
  ("Zzzzzz…") كانت تمدّ الصفحة. تُختصر هذه الكلمات أو تُحذف الآن، في المشاريع القديمة أيضًا.
- **المعاينة تعرض المقطع النهائي تمامًا:** نفس القصّ ونفس التكبير (حتى 1.25×).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **9:16 预览不再放大和偏移：** 原因是语音识别写出的一个无限长的"词"（"Zzzzzz…"）把页面撑宽了。
  这类词现在会被缩短或删除，旧项目也一样。
- **预览与成片完全一致：** 相同的裁剪和缩放（最多 1.25×）。

</details>

## [1.2.22] - 2026-11-07

### Fixed
- **Captions say exactly what you said again.** In 1.2.21 the new swear check could mark a
  normal word next to a possible swear as censored ("Orası" became "O****"). Now the swear check
  only adds bleeps and never changes caption text: captions come from the transcript (and
  proofreading) as before, and only words that really are swears show as "****".
- **Never zero bleeps by mistake.** If the swear check runs into a problem (for example a model
  that couldn't be downloaded), the clip uses the basic detector from 1.2.20 and the swear list
  shows a warning. A swear the basic detector finds is always bleeped.
- **Zoom can't run away any more.** Smart zoom, meme punches and shakes now share one limit
  (1.25× in total), the shake never moves the picture out of the frame, and the crop is worked
  out from the video's real picture size (also for rotated phone videos and unusual pixel
  shapes). A facecam box that doesn't fit the video is kept inside the picture.
- **After an update, restart the app once:** the "a newer version is installed" bar does it with
  one click (the old app kept running the old version after 1.2.21).

### Changed
- **Bleeps are on for every clip by default, at Strict**, in Easy and Pro, vertical and 16:9.
- **A more professional bleep:** one level for the whole clip, just under your voice, quick
  fades with no clicks; classic beep, soft "boop" or mute.
- **A visual cue:** a bleeped word shows as "****" in red with a short pop, and a small "#@!"
  badge pops up next to the facecam while the bleep plays (both on by default, switchable next
  to the swear settings).
- **Every bleep is checked after the render:** it must really be in the sound, and no swear may
  still be heard; otherwise the clip is rendered again.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- **Altyazılar yine tam olarak söylediğini yazıyor.** 1.2.21'de yeni küfür kontrolü, olası bir
  küfrün yanındaki normal bir kelimeyi sansürlü gösterebiliyordu ("Orası" "O****" oluyordu).
  Artık küfür kontrolü yalnızca bip ekler, altyazı metnini asla değiştirmez: altyazılar eskisi gibi
  transkriptten (ve düzeltmeden) gelir, sadece gerçekten küfür olan kelimeler "****" görünür.
- **Yanlışlıkla sıfır bip asla.** Küfür kontrolü bir sorunla karşılaşırsa (örneğin indirilemeyen
  bir model) klip 1.2.20'deki temel algılayıcıyı kullanır ve küfür listesinde bir uyarı çıkar.
  Temel algılayıcının bulduğu bir küfür her zaman bip'lenir.
- **Zoom artık kontrolden çıkamaz.** Akıllı zoom, meme vuruşları ve sarsıntılar tek bir sınırı
  paylaşır (toplam 1,25×), sarsıntı görüntüyü asla kadrajın dışına taşımaz ve kırpma videonun
  gerçek görüntü boyutundan hesaplanır (döndürülmüş telefon videoları ve alışılmadık piksel
  biçimleri dahil). Videoya uymayan bir kamera kutusu görüntünün içinde tutulur.
- **Güncellemeden sonra uygulamayı bir kez yeniden başlat:** "daha yeni bir sürüm yüklü" çubuğu
  bunu tek tıkla yapar (1.2.21'den sonra eski uygulama eski sürümü çalıştırmaya devam etti).

### Değişti
- **Bip'ler varsayılan olarak her klipte açık, Sıkı seviyede**; Kolay ve Pro modda, dikey ve 16:9.
- **Daha profesyonel bip:** tüm klip için tek seviye, sesinin biraz altında, tıkırtısız hızlı
  geçişler; klasik bip, yumuşak "boop" ya da sessiz.
- **Görsel ipucu:** bip'lenen kelime altyazıda kırmızı "****" olarak kısa bir zıplamayla görünür,
  bip çalarken kameranın yanında küçük bir "#@!" rozeti belirir (ikisi de varsayılan açık, küfür
  ayarlarının yanından kapatılabilir).
- **Her bip render'dan sonra kontrol edilir:** sesin içinde gerçekten olmalı ve hiçbir küfür hâlâ
  duyulmamalı; yoksa klip yeniden render edilir.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Untertitel stimmen wieder genau:** die Schimpfwort-Prüfung fügt nur Pieptöne hinzu und ändert
  nie den Untertiteltext; nur echte Schimpfwörter erscheinen als „****“.
- **Nie versehentlich null Pieptöne:** bei einem Problem greift die einfache Erkennung aus 1.2.20,
  mit Hinweis.
- **Zoom bleibt im Rahmen:** alle Zooms zusammen höchstens 1,25×, Ausschnitt aus der echten
  Bildgröße, Facecam immer im Bild.
- **Pieptöne standardmäßig in jedem Clip (Streng)**, gleichmäßiger Pegel knapp unter der Stimme,
  rotes „****“ mit kleinem Pop und „#@!“-Abzeichen neben der Facecam; nach dem Rendern geprüft.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **A feliratok újra pontosak:** a káromkodás-ellenőrzés csak sípolást ad hozzá, a felirat szövegét
  sosem változtatja meg; csak a valódi káromkodások jelennek meg „****”-ként.
- **Sosem lesz véletlenül nulla sípolás:** hiba esetén az 1.2.20-as alap felismerő dolgozik,
  figyelmeztetéssel.
- **A zoom a képen belül marad:** az összes zoom együtt legfeljebb 1,25×, a vágás a valódi
  képméretből, a kamera mindig a képen belül.
- **Alapból minden klipben sípolás (Szigorú)**, egyenletes hangerő a hang alatt, piros „****”
  kis ugrással és „#@!” jelvény a kamera mellett; renderelés után ellenőrizve.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Субтитры снова точные:** проверка ругательств только добавляет запикивание и никогда не меняет
  текст субтитров; «****» показываются только настоящие ругательства.
- **Никогда случайно без запикивания:** при ошибке работает простой детектор из 1.2.20, с
  предупреждением.
- **Зум не выходит из кадра:** все зумы вместе максимум 1,25×, обрезка по реальному размеру
  кадра, вебкамера всегда в кадре.
- **Запикивание по умолчанию в каждом клипе (строго)**, ровная громкость чуть ниже голоса,
  красные «****» с анимацией и значок «#@!» у вебкамеры; проверка после рендера.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **الترجمة دقيقة من جديد:** فحص الشتائم يضيف الصفير فقط ولا يغيّر نص الترجمة أبدًا؛ تظهر الشتائم
  الحقيقية فقط كـ «****».
- **لا مقطع بلا صفير عن طريق الخطأ:** عند حدوث مشكلة يعمل الكاشف الأساسي من 1.2.20 مع تنبيه.
- **التكبير يبقى داخل الإطار:** كل التكبيرات معًا 1.25× كحد أقصى، والقص من الحجم الحقيقي للصورة،
  والكاميرا داخل الصورة دائمًا.
- **الصفير مفعّل افتراضيًا في كل مقطع (صارم)**، بمستوى ثابت تحت الصوت، و«****» حمراء مع حركة قصيرة
  وشارة «#@!» قرب الكاميرا؛ مع فحص بعد التصيير.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **字幕重新准确：** 脏话检查只增加哔声，绝不修改字幕文字；只有真正的脏话才显示为“****”。
- **不会意外地一个哔声都没有：** 出现问题时改用 1.2.20 的基础检测器，并显示提示。
- **缩放不会超出画面：** 所有缩放合计最多 1.25 倍，按视频真实画面尺寸裁剪，摄像头始终在画面内。
- **默认每个片段都加哔声（严格）**，音量统一、略低于人声，红色“****”带弹出效果，摄像头旁显示“#@!”徽章；渲染后自动检查。

</details>

## [1.2.21] - 2026-11-07

### Added
- **Much stricter swear detection: almost no swear gets through any more.** A new deep check
  listens to your clips again: every voice (also quiet friends and short "aq!" bursts the
  transcript skipped), with quiet voices turned up, in several passes with the full Whisper
  large-v3 model. It also understands Turkish word forms (siktir, sikerler, amına, götünü...),
  spellings with ı instead of i, stretched letters ("siiiiktir"), short forms (amk, aq) and words
  Whisper wrote censored ("s**"), in all seven app languages. Real words that look similar
  ("sıkıntı", "götür", "aman") are left alone. On our test stream the bleeps now catch 14 of 14
  swears, up from 8 of 14.
- **Bleeps sit exactly on the word.** The exact start and end of every swear are found with a
  free local alignment model, a little margin is added, and every bleep is listened to again:
  if part of the word is still audible, the bleep gets wider. After a render, the bleeps are
  checked once more (and the clip is rendered again if needed). Partly audible bleeps on our
  test stream: 1 of 14, down from 4 of 8.
- **Strictness:** Normal, Strict (the default for Shorts, TikTok and Reels) and Paranoid (bleeps
  every candidate), next to the swear settings. In Easy mode: one switch, "Check swears
  strictly" (on). Easy mode runs the deep check by itself on the clips it makes.
- **It learns from you.** Every word you bleep by hand (B key, the waveform, the swear list) is
  remembered for its language and bleeped from then on; every word you unbleep counts as "not a
  swear". See and edit them in Studio > Word lists > Learned from you.
- **"Check thoroughly"** button in the swear list of every clip, and a review page in Studio >
  Word lists to listen to each found swear (as said and with the bleep).

### Notes
- The deep check downloads the Whisper large-v3 model (3.1 GB) and the alignment model (290 MB)
  once. On computers without a strong graphics card it uses the normal model instead.

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Çok daha sıkı küfür tespiti: artık neredeyse hiçbir küfür kaçmıyor.** Yeni derin kontrol
  kliplerini yeniden dinler: her sesi (transkriptin atladığı sessiz arkadaşları ve kısa "aq!"
  patlamalarını da), sessiz sesleri yükselterek, tam Whisper large-v3 modeliyle birkaç geçişte.
  Türkçe kelime biçimlerini (siktir, sikerler, amına, götünü...), i yerine ı ile yazılanları,
  uzatılmış harfleri ("siiiiktir"), kısaltmaları (amk, aq) ve Whisper'ın sansürlü yazdıklarını
  ("s**") da anlar; uygulamanın yedi dilinin hepsinde. Benzeyen gerçek kelimelere ("sıkıntı",
  "götür", "aman") dokunmaz. Test yayınımızda bip'ler artık 14 küfürden 14'ünü yakalıyor (önce 8).
- **Bip tam kelimenin üstünde.** Her küfrün tam başlangıcı ve bitişi ücretsiz, yerel bir hizalama
  modeliyle bulunur, biraz pay eklenir ve her bip yeniden dinlenir: kelimenin bir kısmı hâlâ
  duyuluyorsa bip genişler. Render'dan sonra bip'ler bir kez daha kontrol edilir (gerekirse klip
  yeniden render edilir). Test yayınımızda kısmen duyulan bip: 14'te 1 (önce 8'de 4).
- **Sıkılık:** Normal, Sıkı (Shorts, TikTok ve Reels için varsayılan) ve Çok sıkı (her adayı
  bip'ler), küfür ayarlarının yanında. Kolay modda tek anahtar: "Küfürleri sıkı denetle" (açık).
  Kolay mod yaptığı kliplerde derin kontrolü kendisi çalıştırır.
- **Senden öğrenir.** Elle bip'lediğin her kelime (B tuşu, dalga formu, küfür listesi) diline göre
  hatırlanır ve bundan sonra bip'lenir; bip'ini kaldırdığın her kelime "küfür değil" sayılır.
  Stüdyo > Kelime listeleri > Senden öğrenilenler'de görüp düzenleyebilirsin.
- Her klibin küfür listesinde **"Derinlemesine kontrol et"** düğmesi ve Stüdyo > Kelime
  listeleri'nde bulunan her küfrü (söylendiği gibi ve bip'li) dinleyebileceğin bir inceleme sayfası.

### Notlar
- Derin kontrol Whisper large-v3 modelini (3,1 GB) ve hizalama modelini (290 MB) bir kez indirir.
  Güçlü ekran kartı olmayan bilgisayarlarda normal modeli kullanır.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Viel strengere Schimpfwort-Erkennung:** eine gründliche Prüfung hört die Clips neu an (alle
  Stimmen, auch leise und sehr kurze), mit Whisper large-v3 in mehreren Durchgängen, versteht
  Wortformen, Schreibvarianten, gedehnte Buchstaben, Abkürzungen und zensierte Wörter in allen
  sieben Sprachen. Testvideo: 14 von 14 Schimpfwörtern gepiept (vorher 8).
- **Pieptöne genau auf dem Wort:** exakte Wortzeiten mit einem lokalen Ausrichtungsmodell, jeder
  Piepton wird erneut angehört und bei Bedarf breiter, auch nach dem Rendern. Teilweise hörbar:
  1 von 14 (vorher 4 von 8).
- **Strenge:** Normal, Streng (Standard für Shorts / TikTok / Reels), Paranoid. Im Easy-Modus ein
  Schalter „Schimpfwörter streng prüfen“ (an).
- **Lernt von dir:** von Hand gepiepte Wörter werden gemerkt, entfernte zählen als „kein
  Schimpfwort“ (Studio > Wortlisten).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **Sokkal szigorúbb káromkodás-felismerés:** az alapos ellenőrzés újrahallgatja a klipeket (minden
  hang, a halk és nagyon rövid is), Whisper large-v3-mal több menetben, és felismeri a szóalakokat,
  írásváltozatokat, nyújtott betűket, rövidítéseket és cenzúrázott szavakat mind a hét nyelven.
  Tesztvideó: 14-ből 14 káromkodás kisípolva (előtte 8).
- **A sípolás pontosan a szón:** pontos szóidők egy helyi igazító modellel, minden sípolást újra
  meghallgat, és szükség esetén szélesít, renderelés után is. Részben hallható: 14-ből 1 (előtte 8-ból 4).
- **Szigorúság:** Normál, Szigorú (alapértelmezett Shorts / TikTok / Reels esetén), Paranoid. Easy
  módban egy kapcsoló: „Káromkodások szigorú ellenőrzése” (be).
- **Tanul tőled:** a kézzel kisípolt szavakat megjegyzi, a visszavontak „nem káromkodás”-nak
  számítanak (Stúdió > Szólisták).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Гораздо более строгое распознавание ругательств:** тщательная проверка заново слушает клипы
  (все голоса, даже тихие и очень короткие) моделью Whisper large-v3 в несколько проходов и
  понимает словоформы, варианты написания, растянутые буквы, сокращения и зацензуренные слова на
  всех семи языках. Тестовое видео: запикано 14 из 14 ругательств (раньше 8).
- **Запикивание точно на слове:** точное время слов с локальной моделью выравнивания, каждое
  запикивание прослушивается снова и при необходимости расширяется, в том числе после рендера.
  Частично слышно: 1 из 14 (раньше 4 из 8).
- **Строгость:** обычная, строгая (по умолчанию для Shorts / TikTok / Reels), параноидальная. В
  простом режиме один переключатель «Строго проверять ругательства» (вкл.).
- **Учится у вас:** запиканные вручную слова запоминаются, отменённые считаются «не ругательством»
  (Студия > Списки слов).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **كشف أشد صرامة للشتائم:** يستمع الفحص الدقيق إلى المقاطع من جديد (كل الأصوات، حتى الخافتة
  والقصيرة جدًا) بنموذج Whisper large-v3 على عدة مرات، ويفهم صيغ الكلمات وطرق الكتابة والحروف
  الممدودة والاختصارات والكلمات المراقَبة بكل اللغات السبع. فيديو الاختبار: صُفّرت 14 من 14 شتيمة (سابقًا 8).
- **الصفير على الكلمة تمامًا:** أوقات دقيقة للكلمات بنموذج محاذاة محلي، ويُستمع إلى كل صفير من
  جديد ويُوسَّع عند الحاجة، حتى بعد التصيير. مسموع جزئيًا: 1 من 14 (سابقًا 4 من 8).
- **الصرامة:** عادي، صارم (الافتراضي لـ Shorts وTikTok وReels)، صارم جدًا. في الوضع السهل مفتاح
  واحد: «افحص الشتائم بصرامة» (مفعّل).
- **يتعلّم منك:** تُحفظ الكلمات التي تصفّرها يدويًا، والتي تزيل صفيرها تُعدّ «ليست شتيمة» (الاستوديو > قوائم الكلمات).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **更严格的脏话识别：** 彻底检查会用 Whisper large-v3 多次重新识别片段（所有人声，包括很小声和很短的），并能理解七种语言的词形、写法变体、拉长的字母、缩写和被审查的词。测试视频：14 个脏话全部哔掉（之前 8 个）。
- **哔声精确落在词上：** 用本地对齐模型找到精确的词语时间，每个哔声都会重新试听，必要时加宽，渲染后也会检查。仍能部分听到：14 个中 1 个（之前 8 个中 4 个）。
- **严格程度：** 普通、严格（Shorts / TikTok / Reels 默认）、极严格。简易模式只有一个开关“严格检查脏话”（开）。
- **向你学习：** 你手动哔掉的词会被记住，取消哔声的词算作“不是脏话”（工作室 > 词语列表）。

</details>

## [1.2.20] - 2026-11-06

### Changed
- **Dubbed clips on TikTok and Reels say their voice is AI-made too.** The caption gets the same
  short line as on YouTube (for example "The English voice in this video is AI-generated from my
  own voice."). With automatic posting, SharkyClips also switches on the platform's own AI label
  (TikTok's "AI-generated content", Instagram's AI disclosure). With semi-automatic posting the
  line is in the copied caption and SharkyClips reminds you to switch on the AI label yourself
  before you post. Both switches are on by default and sit right above the post button.
- **Fuller credit for the voice model:** exported to ONNX by KevinAHM, packaged and quantized to
  int8 by k2-fsa/sherpa-onnx, with links to both (dubbing settings and About & licenses).

<!-- lang:tr -->
**Türkçe**

### Değişti
- **TikTok ve Reels'teki dublajlı klipler de sesin yapay zekâyla üretildiğini söyler.** Açıklamaya
  YouTube'dakiyle aynı kısa satır eklenir (örneğin "The English voice in this video is
  AI-generated from my own voice."). Otomatik paylaşımda SharkyClips platformun kendi yapay zekâ
  etiketini de açar (TikTok'ta "Yapay zekâ tarafından oluşturulan içerik", Instagram'da yapay zekâ
  bildirimi). Yarı otomatik paylaşımda satır kopyalanan açıklamada olur ve SharkyClips paylaşmadan
  önce yapay zekâ etiketini kendin açmanı hatırlatır. İki anahtar da varsayılan olarak açıktır ve
  paylaş düğmesinin hemen üstündedir.
- **Ses modelinin daha eksiksiz künyesi:** KevinAHM tarafından ONNX'e aktarıldı, k2-fsa/sherpa-onnx
  tarafından paketlenip int8'e sıkıştırıldı; ikisine de bağlantılarla (dublaj ayarları ve Hakkında
  ve lisanslar).

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Vertonte Clips auf TikTok und Reels sagen ebenfalls, dass die Stimme KI-erzeugt ist:** ein Satz
  in der Beschreibung; automatisch wird das KI-Label der Plattform gesetzt, halbautomatisch
  erinnert SharkyClips dich daran. Beides ist an und lässt sich direkt über dem Posten-Knopf
  abschalten.
- **Vollständigere Lizenzangabe:** von KevinAHM nach ONNX exportiert, von k2-fsa/sherpa-onnx gepackt
  und auf int8 quantisiert, mit Links.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **A TikTokon és Reelsen is jelzik a szinkronizált klipek, hogy a hang MI-vel készült:** egy sor
  a leírásban; automata módban a platform MI-címkéje is bekapcsol, félautomata módban a SharkyClips
  emlékeztet rá. Mindkettő be van kapcsolva, és a közzététel gomb fölött kikapcsolható.
- **Teljesebb licencadat:** ONNX-be exportálta KevinAHM, csomagolta és int8-ra kvantálta a
  k2-fsa/sherpa-onnx, linkekkel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Озвученные клипы в TikTok и Reels тоже сообщают, что голос создан ИИ:** строка в подписи; в
  автоматическом режиме включается ИИ-метка платформы, в полуавтоматическом SharkyClips напоминает
  о ней. Оба переключателя включены и находятся над кнопкой публикации.
- **Более полное указание авторства:** экспорт в ONNX — KevinAHM, упаковка и квантизация в int8 —
  k2-fsa/sherpa-onnx, со ссылками.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **المقاطع المدبلجة على TikTok وReels تذكر أيضًا أن الصوت مولَّد بالذكاء الاصطناعي:** سطر في
  الوصف؛ في النشر التلقائي تُفعَّل علامة الذكاء الاصطناعي في المنصة، وفي الوضع شبه التلقائي يذكّرك
  SharkyClips بها. كلاهما مفعَّل ويمكن إيقافه فوق زر النشر.
- **نسبة أكمل لنموذج الصوت:** صدّره KevinAHM إلى ONNX، وحزمه k2-fsa/sherpa-onnx وضغطه إلى int8، مع روابط.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **TikTok 和 Reels 上的配音片段也会说明声音由 AI 生成：** 文案中加一行说明；自动发布时会打开平台自己的 AI 标签，半自动发布时 SharkyClips 会提醒你手动打开。两者默认开启，位于发布按钮上方。
- **更完整的声音模型署名：** 由 KevinAHM 导出为 ONNX，由 k2-fsa/sherpa-onnx 打包并量化为 int8，附链接。

</details>

## [1.2.19] - 2026-11-06

### Changed
- **Dubbed clips say their voice is AI-made.** When you upload a clip dubbed in your own voice,
  SharkyClips adds a short line to the description in the clip's language (for example "The
  English voice in this video is AI-generated from my own voice.") and answers YouTube's
  "altered or synthetic content" question with yes. Both are on by default and you see them in
  the upload screen and in the Library, where you can switch each one off. Scheduled and Easy mode
  uploads do the same, and editing the description later keeps the line.
- **Credits for the AI models.** The voice model is now credited properly: Pocket TTS by Kyutai
  (CC-BY 4.0), converted to int8 ONNX by k2-fsa/sherpa-onnx, with links to the license and the
  original model. You see this in the dubbing settings and in the new **About & licenses** card
  in Settings, which also lists the cover picture models.

<!-- lang:tr -->
**Türkçe**

### Değişti
- **Dublajlı klipler sesin yapay zekâyla üretildiğini söyler.** Kendi sesinle dublajlanmış bir
  klibi yüklediğinde SharkyClips açıklamaya klibin dilinde kısa bir satır ekler (örneğin "The
  English voice in this video is AI-generated from my own voice.") ve YouTube'un "değiştirilmiş
  veya sentetik içerik" sorusunu evet olarak yanıtlar. İkisi de varsayılan olarak açıktır;
  yükleme ekranında ve Kütüphane'de görürsün ve her birini kapatabilirsin. Zamanlanmış ve Kolay
  mod yüklemeleri de aynısını yapar; açıklamayı sonradan düzenlemek satırı silmez.
- **Yapay zekâ modellerinin künyesi.** Ses modeli artık doğru şekilde anılıyor: Kyutai'nin
  Pocket TTS'i (CC-BY 4.0), k2-fsa/sherpa-onnx tarafından int8 ONNX'e dönüştürüldü; lisansa ve
  orijinal modele bağlantılarla. Bunu dublaj ayarlarında ve Ayarlar'daki yeni **Hakkında ve
  lisanslar** kartında görürsün; kart kapak resmi modellerini de listeler.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- **Vertonte Clips sagen, dass die Stimme KI-erzeugt ist:** ein Satz in der Beschreibung (in der
  Sprache des Clips) und YouTubes Markierung „veränderte oder synthetische Inhalte“. Beides ist an
  und lässt sich beim Hochladen und in der Bibliothek abschalten.
- **Lizenzhinweise:** Pocket TTS von Kyutai (CC-BY 4.0), von k2-fsa/sherpa-onnx in int8-ONNX
  umgewandelt, mit Links; in den Vertonungs-Einstellungen und in der neuen Karte **Über & Lizenzen**.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- **A szinkronizált klipek jelzik, hogy a hang MI-vel készült:** egy sor a leírásban (a klip
  nyelvén) és a YouTube „módosított vagy szintetikus tartalom” jelölése. Mindkettő be van
  kapcsolva, és a feltöltésnél és a Könyvtárban kikapcsolható.
- **Licencek:** Pocket TTS (Kyutai, CC-BY 4.0), int8 ONNX-re alakította a k2-fsa/sherpa-onnx,
  linkekkel; a szinkron beállításainál és az új **Névjegy és licencek** kártyán.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- **Озвученные клипы сообщают, что голос создан ИИ:** строка в описании (на языке клипа) и
  отметка YouTube «изменённый или синтетический контент». Оба включены и отключаются на экране
  загрузки и в Библиотеке.
- **Лицензии:** Pocket TTS от Kyutai (CC-BY 4.0), преобразована в int8 ONNX проектом
  k2-fsa/sherpa-onnx, со ссылками; в настройках озвучки и в новой карточке **О программе и лицензии**.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- **المقاطع المدبلجة تذكر أن الصوت مولَّد بالذكاء الاصطناعي:** سطر في الوصف (بلغة المقطع) وعلامة
  يوتيوب "محتوى معدَّل أو اصطناعي". كلاهما مفعَّل ويمكن إيقافه في شاشة الرفع وفي المكتبة.
- **التراخيص:** Pocket TTS من Kyutai (CC-BY 4.0)، حوّله k2-fsa/sherpa-onnx إلى int8 ONNX، مع
  روابط؛ في إعدادات الدبلجة وفي بطاقة **حول البرنامج والتراخيص** الجديدة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- **配音片段会说明声音由 AI 生成：** 描述中加一行说明（使用片段的语言），并设置 YouTube 的“经过修改或合成的内容”标记。两者默认开启，可在上传界面和媒体库中关闭。
- **许可证：** Pocket TTS（Kyutai，CC-BY 4.0），由 k2-fsa/sherpa-onnx 转换为 int8 ONNX，附链接；见配音设置和新的 **关于与许可证** 卡片。

</details>

## [1.2.18] - 2026-11-06

### Added
- **Cover studio:** the AI's cover idea becomes a real picture, made on your PC with a free
  image model (Z-Image-Turbo). One click makes 4 options in 9:16 and 16:9; pick one and the cover
  text is added in the SharkyClips style. On an 8 GB graphics card the 4 pictures of one size take
  about a minute. The model (about 6.7 GB) downloads once. On PCs that can't run it, SharkyClips says so
  and uses the facecam frame as the cover.
- **TikTok and Instagram Reels:** the upload button now has a small picker: YouTube / TikTok /
  Reels (remembered). For TikTok and Reels the clip is exported with the right settings into your
  Downloads folder, the caption with hashtags is copied, and the upload page opens: drop the file
  in and press Post. Automatic posting through the official TikTok and Instagram APIs can be set
  up in Settings with your own developer app; the app always shows which mode is active. Until
  TikTok or Meta approve your app, automatic posts are private (TikTok) or limited to your own
  account (Instagram).
- **Dub a clip in your own voice:** one switch turns a clip into English spoken in your own
  voice. Set it up once: confirm it's your own voice and record about 20 seconds (or pick a file).
  Only your lines are dubbed; friends keep their own voice and get subtitles. The timing stays,
  the game sound stays underneath, and the subtitles are translated. Everything runs on your PC.
  More languages will follow.
- **Study cards:** in study mode, key formulas, definitions and steps appear as clean animated
  cards while the teacher explains them, with properly drawn math (fractions, roots, powers).
- **Music visualizer:** in music mode a clip becomes a visualizer that moves with the beat: the
  cover in the middle, a spectrum ring around it and the lyrics as karaoke, in the SharkyClips
  colours (or your brand kit's).
- In Easy mode study cards and the visualizer are a switch each in Settings (on); Pro mode has
  off / auto in the editing panel.

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Kapak stüdyosu:** yapay zekânın kapak fikri gerçek bir resme dönüşür; ücretsiz bir resim
  modeliyle (Z-Image-Turbo) bilgisayarında yapılır. Tek tıkla 9:16 ve 16:9 boyutunda 4 seçenek;
  birini seç, kapak yazısı SharkyClips stiliyle eklenir. 8 GB'lık bir ekran kartında bir boyutun 4 resmi
  yaklaşık bir dakika sürer. Model (yaklaşık 6,7 GB) bir kez indirilir. Çalıştıramayan
  bilgisayarlarda SharkyClips bunu söyler ve kapak olarak facecam karesini kullanır.
- **TikTok ve Instagram Reels:** yükleme düğmesinde artık küçük bir seçici var: YouTube / TikTok /
  Reels (hatırlanır). TikTok ve Reels için klip doğru ayarlarla İndirilenler klasörüne aktarılır,
  hashtag'li açıklama kopyalanır ve yükleme sayfası açılır: dosyayı bırak ve Paylaş'a bas.
  Resmî TikTok ve Instagram API'leriyle otomatik paylaşım, kendi geliştirici uygulamanla
  Ayarlar'dan kurulabilir; uygulama hangi modun açık olduğunu her zaman gösterir. TikTok ya da
  Meta uygulamanı onaylayana kadar otomatik paylaşımlar gizlidir (TikTok) ya da yalnızca kendi
  hesabınla sınırlıdır (Instagram).
- **Klibi kendi sesinle dublajla:** tek bir anahtar klibi senin sesinle İngilizce konuşturur.
  Bir kez kur: bunun kendi sesin olduğunu onayla ve yaklaşık 20 saniye kaydet (ya da bir dosya
  seç). Yalnızca senin cümlelerin dublajlanır; arkadaşlar kendi seslerini korur ve altyazı alır.
  Zamanlama korunur, oyun sesi altta kalır, altyazılar çevrilir. Her şey bilgisayarında çalışır.
  Başka diller de gelecek.
- **Çalışma kartları:** çalışma modunda önemli formüller, tanımlar ve adımlar, öğretmen anlatırken
  temiz, hareketli kartlar olarak görünür; matematik düzgün çizilir (kesirler, kökler, üsler).
- **Müzik görselleştirici:** müzik modunda klip ritimle hareket eden bir görselleştiriciye
  dönüşür: ortada kapak, çevresinde bir spektrum halkası ve karaoke olarak sözler, SharkyClips
  renklerinde (ya da marka kitinin renklerinde).
- Kolay modda çalışma kartları ve görselleştirici Ayarlar'da birer anahtar (açık); Pro modda
  düzenleme panelinde kapalı / otomatik.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Neu: **Cover-Studio** – aus der Cover-Idee der KI wird ein echtes Bild, auf deinem PC
  (Z-Image-Turbo): 4 Vorschläge in 9:16 und 16:9, ein Klick zum Auswählen; schwache PCs nehmen das
  Facecam-Bild.
- **TikTok und Instagram Reels:** Plattform-Auswahl am Upload-Knopf. Halbautomatisch: passendes
  Video im Downloads-Ordner, Beschreibung kopiert, Upload-Seite offen. Automatisch über die
  offiziellen APIs mit eigener Entwickler-App (bis zur Freigabe privat / nur dein Konto).
- **Synchron mit deiner eigenen Stimme** (Englisch): nur deine Sätze, Freunde behalten ihre
  Stimme; Timing und Spielsound bleiben. Einmalige Zustimmung + kurze Stimmprobe.
- **Lernkarten** im Lernmodus (Formeln mit sauberer Mathe, Definitionen, Schritte) und ein
  **Musik-Visualizer** im Musikmodus (Beat, Cover, Karaoke-Text).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Új: **borítóstúdió** – az MI borítóötletéből valódi kép lesz a gépeden (Z-Image-Turbo):
  4 változat 9:16-ban és 16:9-ben, egy kattintással választható; gyenge gépen a facecam képkockája.
- **TikTok és Instagram Reels:** platformválasztó a feltöltés gombon. Félautomata: kész videó a
  Letöltésekben, kimásolt leírás, megnyíló feltöltő oldal. Automata a hivatalos API-kkal, saját
  fejlesztői alkalmazással (jóváhagyásig privát / csak a saját fiókod).
- **Szinkron a saját hangodon** (angolul): csak a te mondataid, a barátok hangja marad; az
  időzítés és a játék hangja megmarad. Egyszeri beleegyezés + rövid hangminta.
- **Tanulókártyák** tanuló módban (képletek szép matekkal, definíciók, lépések) és **zenei
  vizualizáció** zenei módban (ütem, borító, karaoke-szöveg).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Новое: **студия обложек** — идея обложки от ИИ становится настоящей картинкой прямо на ПК
  (Z-Image-Turbo): 4 варианта в 9:16 и 16:9, выбор одним кликом; на слабых ПК — кадр с веб-камеры.
- **TikTok и Instagram Reels:** выбор платформы на кнопке загрузки. Полуавтоматически: готовое
  видео в «Загрузках», описание скопировано, открыта страница загрузки. Автоматически — через
  официальные API со своим приложением разработчика (до одобрения — приватно / только свой аккаунт).
- **Озвучка твоим голосом** (английский): только твои фразы, друзья остаются со своим голосом;
  тайминг и звук игры сохраняются. Однократное согласие + короткий образец голоса.
- **Учебные карточки** в режиме учёбы (формулы с аккуратной математикой, определения, шаги) и
  **музыкальный визуализатор** в режиме музыки (бит, обложка, караоке).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- جديد: **استوديو الأغلفة** – تتحول فكرة الغلاف من الذكاء الاصطناعي إلى صورة حقيقية على جهازك
  (Z-Image-Turbo): ‏4 خيارات بمقاسي 9:16 و16:9 والاختيار بنقرة؛ وعلى الأجهزة الضعيفة لقطة كاميرا الوجه.
- **تيك توك وإنستغرام ريلز:** اختيار المنصة على زر الرفع. شبه تلقائي: الفيديو جاهز في التنزيلات،
  والوصف منسوخ، وصفحة الرفع مفتوحة. تلقائي عبر الواجهات الرسمية بتطبيق مطوّر خاص بك (خاص / لحسابك
  فقط حتى الموافقة).
- **دبلجة بصوتك أنت** (بالإنجليزية): جملك فقط، ويحتفظ الأصدقاء بأصواتهم؛ يبقى التوقيت وصوت اللعبة.
  موافقة لمرة واحدة + عينة صوت قصيرة.
- **بطاقات دراسة** في وضع الدراسة (صيغ برسم رياضي أنيق، تعريفات، خطوات) و**مؤثرات موسيقية**
  في وضع الموسيقى (الإيقاع، الغلاف، كلمات كاريوكي).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 新增：**封面工作室**——AI 的封面创意在你的电脑上直接变成真实图片（Z-Image-Turbo）：9:16 和 16:9
  各 4 个方案，一键选择；配置较弱的电脑改用摄像头画面。
- **TikTok 和 Instagram Reels：**上传按钮上可选平台。半自动：视频已放进“下载”、文案已复制、上传页
  已打开。也可用你自己的开发者应用通过官方 API 自动发布（审核通过前为私密 / 仅限你自己的账号）。
- **用你自己的声音配音**（英语）：只配你的台词，朋友保留原声；时间和游戏声音保持不变。一次性同意
  + 一小段声音样本。
- 学习模式下的**学习卡片**（公式排版清晰、定义、步骤），以及音乐模式下的**音乐可视化**（节拍、
  封面、卡拉 OK 歌词）。

</details>

## [1.2.17] - 2026-11-03

### Added
- **Clips by themselves after a stream:** switch on “Make clips when my stream ends” and
  SharkyClips watches the folder OBS records into (found automatically, changeable in Pro mode).
  When a recording is finished, it finds the clips, makes the best ones and writes their titles,
  only while your PC isn't busy. It never touches a file that is still being recorded, and never
  one that was already finished before you switched it on. Optional (off by default): plan or upload the
  best clips by themselves.
- **Live markers:** press **Ctrl+Alt+C** while you play (it works in games and doesn't take the
  focus; a short sound confirms it), or type **!clip** in your Twitch / YouTube chat (you or your
  moderators only). The moment becomes one of the first clips, labelled “Marked by you”, with
  what led up to it. With OBS's WebSocket server on, markers are exact even if you paused.
- **Approve from your phone:** connect your own Telegram bot in a minute (free and private).
  Each ready clip arrives with its cover, title and viral label and three buttons:
  **Upload / Plan / Skip** (and Watch). Or open the approval page on your Wi-Fi (PIN required)
  and swipe: right to upload, left to skip. It can be added to the home screen like an app;
  a short guide shows how to use it away from home with Tailscale.
- **Instant replay:** the clip's big moment (pentakill, multikill, extraction, kill, a loud
  peak, your marker) plays again in slow motion with smooth in-between frames, a gentle zoom on
  the action and a small REPLAY badge. Captions pause during the replay.
- **Chat bubbles:** real chat messages from that moment as small bubbles with colourful names,
  never more than three at once and never over the captions or the platform's buttons. Links,
  swear words, phone numbers, e-mails and @mentions are filtered out. Chat from your live
  stream is saved for this too.
- **Meme effects** (off by default; light / strong in Pro mode): on a funny moment the picture
  freezes and zooms in with a short caption the local AI writes in your language (“NASIL?!”,
  “bruh”); on a fail a quick zoom or shake. The sound effects are made on your PC: no
  copyrighted sounds.
- In Easy mode each of these is a single switch in Settings. Instant replay and chat bubbles are
  on for new videos; your older clips keep their look until you change a switch.

### Fixed
- A swear-word badge in the light theme had too little contrast.

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Yayından sonra klipler kendiliğinden:** “Yayın bitince otomatik klip çıkar”ı aç; SharkyClips
  OBS'nin kaydettiği klasörü izler (kendisi bulur, Pro modda değiştirilebilir). Kayıt bitince
  klipleri bulur, en iyilerini hazırlar ve başlıklarını yazar; bunu sadece bilgisayarın meşgul
  değilken yapar. Kaydı hâlâ süren bir dosyaya ve sen açmadan önce bitmiş olan dosyalara asla
  dokunmaz. İsteğe bağlı (varsayılan kapalı): en iyi klipleri kendiliğinden planla ya da yükle.
- **Canlı işaretler:** oynarken **Ctrl+Alt+C**'ye bas (oyunda çalışır, odağı çalmaz; kısa bir ses
  onaylar) ya da Twitch / YouTube sohbetine **!clip** yaz (sadece sen ya da moderatörlerin). O an,
  öncesiyle birlikte “Senin işaretin” etiketiyle ilk kliplerden biri olur. OBS'nin WebSocket
  sunucusu açıksa, kaydı duraklatsan bile işaretler tam doğru olur.
- **Telefondan onay:** kendi Telegram botunu bir dakikada bağla (ücretsiz ve gizli). Her hazır
  klip kapağı, başlığı ve viral etiketiyle üç düğmeyle gelir: **Yükle / Planla / Atla** (bir de
  İzle). Ya da Wi-Fi'ında onay sayfasını aç (PIN gerekir) ve kaydır: sağa yükle, sola atla.
  Uygulama gibi ana ekrana eklenebilir; evden uzakta Tailscale ile kullanmak için kısa bir
  rehber var.
- **Anlık tekrar:** klibin büyük anı (pentakill, çoklu kill, tahliye, kill, ses patlaması, senin
  işaretin) akıcı ara karelerle ağır çekimde bir daha oynar; aksiyona hafif bir yakınlaştırma ve
  küçük bir REPLAY etiketi. Tekrar sırasında altyazı durur.
- **Sohbet balonları:** o andaki gerçek sohbet mesajları renkli isimlerle küçük balonlar olarak;
  aynı anda en fazla üç tane, asla altyazının ya da platform düğmelerinin üstünde değil. Linkler,
  küfürler, telefon numaraları, e-postalar ve @etiketler süzülür. Canlı yayının sohbeti de bunun
  için kaydedilir.
- **Meme efektleri** (varsayılan kapalı; Pro modda hafif / güçlü): komik bir anda görüntü donar,
  yakınlaşır ve yerel yapay zekânın senin dilinde yazdığı kısa bir yazı çıkar (“NASIL?!”,
  “bruh”); fail anında hızlı bir yakınlaştırma ya da sarsıntı. Ses efektleri bilgisayarında
  üretilir: telifli ses yok.
- Kolay modda bunların her biri Ayarlar'da tek bir anahtar. Anlık tekrar ve sohbet balonları yeni
  videolarda açık; eski kliplerin, bir anahtarı değiştirene kadar görünümünü korur.

### Düzeltildi
- Açık temada bir küfür etiketinin kontrastı yetersizdi.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Neu: **Clips von selbst nach dem Stream** – SharkyClips beobachtet den OBS-Aufnahmeordner und
  macht aus jeder fertigen Aufnahme Clips (nur wenn der PC frei ist; laufende Aufnahmen werden
  nie angefasst). Optional: die besten automatisch planen oder hochladen.
- **Live-Marker:** Strg+Alt+C beim Spielen (ohne Fokuswechsel) oder **!clip** im Twitch-/YouTube-
  Chat (du oder deine Mods): der Moment wird einer der ersten Clips, samt Vorgeschichte.
- **Freigabe am Handy:** eigener Telegram-Bot mit Hochladen / Planen / Überspringen, oder die
  Freigabeseite im WLAN (PIN) zum Wischen.
- **Sofort-Wiederholung** des großen Moments in Zeitlupe, **Chat-Blasen** mit echten (gefilterten)
  Nachrichten und **Meme-Effekte** (Standbild + KI-Text, Wackeln bei Fails; Sounds lokal erzeugt).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Új: **klipek maguktól adás után** – a SharkyClips figyeli az OBS felvételi mappáját, és minden
  kész felvételből klipeket készít (csak ha a gép nem foglalt; futó felvételhez nem nyúl).
  Opcionális: a legjobbak automatikus ütemezése vagy feltöltése.
- **Élő jelölések:** Ctrl+Alt+C játék közben (fókuszvesztés nélkül) vagy **!clip** a Twitch /
  YouTube chatben (te vagy a moderátoraid): a pillanat az első klipek egyike lesz.
- **Jóváhagyás telefonon:** saját Telegram-bot Feltöltés / Ütemezés / Kihagy gombokkal, vagy a
  jóváhagyó oldal a Wi-Fi-n (PIN) húzogatással.
- **Azonnali visszajátszás** lassítva, **chat-buborékok** valódi (szűrt) üzenetekkel és
  **mém-effektek** (kimerevítés + MI-felirat, rázkódás failnél; a hangok helyben készülnek).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Новое: **клипы сами после стрима** — SharkyClips следит за папкой записей OBS и делает клипы из
  каждой готовой записи (только когда ПК не занят; идущую запись не трогает). По желанию:
  автоплан или автозагрузка лучших.
- **Метки во время стрима:** Ctrl+Alt+C в игре (без потери фокуса) или **!clip** в чате Twitch /
  YouTube (вы или модераторы): момент станет одним из первых клипов вместе с предысторией.
- **Одобрение с телефона:** свой бот Telegram с кнопками Загрузить / В план / Пропустить или
  страница одобрения в Wi-Fi (PIN) со свайпами.
- **Мгновенный повтор** в замедлении, **сообщения чата** пузырями (с фильтрацией) и **мем-эффекты**
  (стоп-кадр + подпись от ИИ, тряска на фейлах; звуки создаются локально).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- جديد: **مقاطع تلقائية بعد البث** – يراقب SharkyClips مجلد تسجيلات OBS ويصنع مقاطع من كل تسجيل
  مكتمل (فقط عندما لا يكون الجهاز مشغولًا، ولا يلمس تسجيلًا جاريًا). اختياري: جدولة أو رفع الأفضل تلقائيًا.
- **علامات أثناء البث:** ‎Ctrl+Alt+C أثناء اللعب (دون فقدان التركيز) أو **‎!clip** في دردشة
  Twitch / YouTube (أنت أو مشرفوك): تصبح اللحظة من أول المقاطع.
- **الموافقة من الهاتف:** بوت تيليجرام خاص بك بأزرار رفع / جدولة / تخطي، أو صفحة الموافقة على
  شبكة Wi-Fi (برمز PIN) بالسحب.
- **إعادة فورية** بالحركة البطيئة، و**فقاعات دردشة** برسائل حقيقية مُنقّاة، و**تأثيرات ميمز**
  (تجميد + تعليق من الذكاء الاصطناعي، واهتزاز عند الفشل؛ الأصوات تُصنع محليًا).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 新增：**直播后自动出片**——SharkyClips 关注 OBS 的录制文件夹，每段录完的视频都会自动做成片段
  （只在电脑空闲时运行，绝不碰正在录制的文件）。可选：自动排期或上传最好的片段。
- **直播标记：**游戏中按 Ctrl+Alt+C（不抢焦点），或在 Twitch / YouTube 聊天里发 **!clip**
  （仅你或房管）：这一刻会连同前因后果成为最靠前的片段。
- **手机审核：**你自己的 Telegram 机器人，带“上传 / 排期 / 跳过”按钮；或在 Wi-Fi 下打开审核页
  （需 PIN），左右滑动即可。
- **即时回放**慢动作重放高光，**聊天气泡**显示真实（已过滤的）弹幕，**梗图特效**（定格 + AI 字幕，
  翻车时抖动；音效在本地生成）。

</details>

## [1.2.16] - 2026-11-02

### Added
- **Easy mode** (now the start screen for everyone): drop a video or paste a link, press
  **Find clips**, and that's it. SharkyClips detects the kind of video (gaming, study or music;
  change it with the small chip), shows each step in plain words with the time left, and lets
  you close the window: a notification tells you when your clips are ready.
- **Your best clips, ready to post:** the top 6 come already made in 9:16 with good defaults
  (your remembered facecam layout, bold captions for every speaker, bleeped swears, the best AI
  title). Each one plays right on the card. "Show more" brings the next ones.
- **One click to YouTube:** "Upload to YouTube" sends the clip with its title, description,
  hashtags and cover filled in, no form. Choose **Now** or **Plan automatically** (good times,
  a few per day); your choice is remembered. Not connected yet? The button connects your Google
  account first and then keeps going. Select several clips to upload them together.
- **One click to your computer:** "Download to computer" saves the video, a text file with
  title, description and hashtags ready to paste, and the cover image to
  Downloads\SharkyClips\<video name>. "Download all" saves every clip at once.
- **Simple editing:** pick another AI title or write your own, move the start and end with two
  handles, turn captions or music on or off. Remove clips you don't want.
- A simple **Library** with three tabs: Ready, Planned and Live (with views).
- A short 3-step tour on first start. **Pro mode** (switch in the top bar, remembered) keeps
  every tool exactly as before.

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Kolay mod** (artık herkesin başlangıç ekranı): bir video bırak ya da link yapıştır,
  **Klipleri bul**'a bas, o kadar. SharkyClips videonun türünü (oyun, ders ya da müzik) kendisi
  anlar (küçük etiketten değiştirebilirsin), her adımı sade bir dille ve kalan süreyle gösterir.
  Pencereyi kapatabilirsin: klipler hazır olunca bildirim gelir.
- **Paylaşıma hazır en iyi kliplerin:** ilk 6 klip iyi varsayılanlarla 9:16 olarak hazır gelir
  (hatırlanan kamera düzenin, her konuşmacı için kalın altyazı, bip'lenmiş küfürler, en iyi yapay
  zekâ başlığı). Her biri kartın üstünde oynar. "Daha fazla göster" sonrakileri getirir.
- **Tek tıkla YouTube:** "YouTube'a yükle" klibi başlık, açıklama, hashtag ve kapakla birlikte
  gönderir, form yok. **Şimdi** ya da **Otomatik planla** (iyi saatler, günde birkaç tane) seç;
  seçimin hatırlanır. Henüz bağlı değil misin? Düğme önce Google hesabını bağlar, sonra devam eder.
  Birkaç klibi seçip birlikte yükleyebilirsin.
- **Tek tıkla bilgisayara:** "Bilgisayara indir" videoyu, başlık + açıklama + hashtag'lerin hazır
  olduğu bir metin dosyasını ve kapak görselini İndirilenler\SharkyClips\<video adı> klasörüne
  kaydeder. "Hepsini indir" tüm klipleri tek seferde kaydeder.
- **Basit düzenleme:** başka bir yapay zekâ başlığı seç ya da kendin yaz, başlangıç ve bitişi iki
  tutamakla kaydır, altyazıyı ya da müziği aç/kapat. İstemediğin klipleri çıkar.
- Üç sekmeli basit bir **Kütüphane**: Hazır, Planlandı ve Yayında (görüntülenmelerle).
- İlk açılışta 3 adımlık kısa bir tur. **Pro mod** (üst çubuktaki anahtar, hatırlanır) tüm
  araçları eskisi gibi korur.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Neu: **Einfacher Modus** als Startbildschirm: Video ablegen oder Link einfügen, „Clips finden“
  drücken. Inhaltsart wird erkannt, Fortschritt in einfachen Worten mit Restzeit; du kannst das
  Fenster schließen, eine Benachrichtigung meldet die fertigen Clips.
- Die besten 6 Clips kommen fertig in 9:16 und laufen direkt auf der Karte.
- Ein Klick auf YouTube (Titel, Beschreibung, Hashtags, Cover ausgefüllt; jetzt oder automatisch
  geplant) oder auf den Computer (Video + Textdatei + Cover in Downloads\SharkyClips).
- Einfaches Bearbeiten (Titel, Anfang/Ende, Untertitel, Musik), Bibliothek mit drei Tabs, kurze
  Tour. Der **Profi-Modus** behält alle Werkzeuge.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Új: **Egyszerű mód** kezdőképernyőként: dobd be a videót vagy a linket, és nyomd meg a „Klipek
  keresése” gombot. Felismeri a tartalom típusát, egyszerű lépésekben mutatja a haladást és a
  hátralévő időt; az ablak bezárható, értesítés jelzi, ha kész.
- A legjobb 6 klip készen jön 9:16-ban, és a kártyán lejátszható.
- Egy kattintás YouTube-ra (cím, leírás, hashtagek, borító kitöltve; most vagy automatikusan
  ütemezve) vagy a gépre (videó + szövegfájl + borító a Letöltések\SharkyClips mappába).
- Egyszerű szerkesztés (cím, eleje/vége, felirat, zene), háromlapos könyvtár, rövid bemutató. A
  **profi mód** minden eszközt megtart.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Новое: **простой режим** на стартовом экране: брось видео или вставь ссылку и нажми «Найти
  клипы». Тип контента определяется сам, шаги и оставшееся время — простыми словами; окно можно
  закрыть, уведомление сообщит, когда клипы готовы.
- Лучшие 6 клипов сразу готовы в 9:16 и проигрываются прямо в карточке.
- Один клик — на YouTube (заголовок, описание, хэштеги, обложка уже заполнены; сейчас или по
  автоплану) или на компьютер (видео + текстовый файл + обложка в «Загрузки\SharkyClips»).
- Простое редактирование (заголовок, начало/конец, субтитры, музыка), библиотека с тремя
  вкладками, короткий тур. **Режим Pro** сохраняет все инструменты.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- جديد: **الوضع السهل** كشاشة البداية: أضف فيديو أو الصق رابطًا ثم اضغط «ابحث عن المقاطع». يُكتشف
  نوع المحتوى تلقائيًا، وتظهر الخطوات والوقت المتبقي بكلمات بسيطة؛ يمكنك إغلاق النافذة وسيصلك إشعار.
- أفضل 6 مقاطع تأتي جاهزة بمقاس 9:16 وتعمل مباشرة على البطاقة.
- نقرة واحدة إلى YouTube (العنوان والوصف والوسوم والغلاف جاهزة؛ الآن أو بجدولة تلقائية) أو إلى
  الكمبيوتر (الفيديو + ملف نصي + الغلاف في التنزيلات\SharkyClips).
- تعديل بسيط (العنوان، البداية/النهاية، الترجمة، الموسيقى)، مكتبة بثلاث علامات تبويب، وجولة قصيرة.
  **الوضع الاحترافي** يحتفظ بكل الأدوات.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 新增：**简易模式**作为开始界面：放入视频或粘贴链接，点击“查找剪辑”即可。自动识别内容类型，
  用通俗的步骤和剩余时间显示进度；可以关闭窗口，完成后会通知你。
- 最好的 6 个剪辑直接做成 9:16，在卡片上就能播放。
- 一键上传 YouTube（标题、简介、话题标签、封面已填好；立即或自动安排），或一键下载到电脑
  （视频 + 文本文件 + 封面，保存在“下载\SharkyClips”）。
- 简单编辑（标题、开始/结束、字幕、音乐）、三个标签页的媒体库、简短导览。**专业模式**保留全部工具。

</details>

## [1.2.15] - 2026-11-02

### Added
- **Hear every speaker.** The new button in the project's Voices section separates the voices
  from the game sound, finds who speaks when, and transcribes your friends too, even when they're quiet on Discord. Each
  voice gets its own colour in the transcript and the captions. You can name the voices, and
  merge two that are really the same person.
- **Multi-track recordings** (OBS: mic, Discord, game): label the tracks once and every voice
  track is transcribed on its own. The labels are remembered for your next video.
- **Swear review before rendering:** every swear from every speaker, with who said it, the time,
  a play button and a bleep switch. Words that might be swears are marked "maybe" for you to
  check. Bleep anything by hand: select words in the transcript (or press B), or drag across
  the new waveform.
- Swears are found more reliably: words Whisper censored itself ("s**yim"), misheard and
  differently spelled swears, and a second listen on the separated voices.
- **Bleep sounds:** classic beep, a soft "boop", mute, or your own sound file. The bleep now
  fades in and out and matches the speaker's loudness.
- **Captions:** new Karaoke and Speaker-coloured styles, optional name tags, at most two lines
  that never split a name, a number and its word, or "sen de". The local AI can proofread the
  captions (spelling, Turkish letters, capitals, punctuation). Censored words show as "a****"
  for every speaker.

### Fixed
- **Facecam detection** picked a face inside the game (for example a portrait in the League of
  Legends HUD) instead of your webcam. It now looks for a fixed webcam rectangle with a live
  face across the whole video. When it isn't sure, it shows the options on a frame so you can
  pick one with a click. The position is remembered per channel and resolution for new projects
  ("Detect again" starts fresh).

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Herkesi duy.** Projenin Sesler bölümündeki yeni düğme sesleri oyun sesinden ayırır, kimin ne
  zaman konuştuğunu bulur ve Discord'da kısık kalan arkadaşlarının sözlerini de yazıya döker. Her ses
  transkriptte ve altyazıda kendi rengini alır. Seslere isim verebilir, aynı kişiye ait iki sesi
  birleştirebilirsin.
- **Çok kanallı kayıtlar** (OBS: mikrofon, Discord, oyun): kanalları bir kez etiketle, her ses
  kanalı ayrı yazıya dökülür. Etiketler bir sonraki videon için hatırlanır.
- **Oluşturmadan önce küfür listesi:** her konuşmacının her küfrü; kimin söylediği, zamanı,
  oynat düğmesi ve bip anahtarıyla. Küfür olabilecek kelimeler kontrol etmen için "belki"
  olarak işaretlenir. İstediğin yeri elle bip'le: transkriptte kelimeleri seç (ya da B'ye bas)
  veya yeni ses dalgası üzerinde sürükle.
- Küfürler daha güvenilir bulunuyor: Whisper'ın kendi sansürlediği kelimeler ("s**yim"), yanlış
  duyulan ya da farklı yazılan küfürler ve ayrılmış seslerde ikinci bir dinleme.
- **Bip sesleri:** klasik bip, yumuşak "bup", sessize alma ya da kendi ses dosyan. Bip artık
  yumuşakça girip çıkıyor ve konuşanın ses seviyesine uyuyor.
- **Altyazılar:** yeni Karaoke ve Konuşmacı renkli stiller, isteğe bağlı isim etiketleri; en
  fazla iki satır, isimleri, sayıyı ve kelimesini ya da "sen de"yi asla bölmüyor. Yerel yapay
  zekâ altyazıları düzeltebiliyor (yazım, Türkçe harfler, büyük harf, noktalama). Sansürlü
  kelimeler her konuşmacı için "a****" olarak görünüyor.

### Düzeltildi
- **Kamera tespiti** web kameran yerine oyunun içindeki bir yüzü (örneğin League of Legends
  arayüzündeki bir portreyi) seçiyordu. Artık tüm videoda canlı bir yüz içeren sabit bir kamera
  dikdörtgeni arıyor. Emin değilse seçenekleri bir karede gösteriyor, tek tıkla seçiyorsun. Konum
  kanal ve çözünürlük başına yeni projeler için hatırlanıyor ("Tekrar algıla" baştan başlar).

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Neu: „Alle Sprecher hören“ trennt Stimmen vom Spielton und schreibt auch deine Freunde mit,
  jede Stimme in ihrer eigenen Farbe. Mehrspur-Aufnahmen (Mikro, Discord, Spiel) werden pro Spur
  erkannt (Beschriftung wird gemerkt).
- Flüchliste vor dem Rendern mit Sprecher, Zeit, Abspielen und Piep-Schalter; manuell piepen per
  Wortauswahl oder Wellenform. Pieptöne: klassisch, sanftes „Bup“, stumm oder eigener Ton.
- Untertitel: Karaoke- und Sprecherfarben-Stil, Namensschilder, bessere Zeilenumbrüche,
  KI-Korrektur.
- Behoben: Die Facecam-Erkennung wählte ein Gesicht im Spiel statt deiner Webcam. Bei Unsicherheit
  wählst du per Klick; die Position wird pro Kanal und Auflösung gemerkt.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Új: a „Minden beszélő” leválasztja a hangokat a játékhangról, és a barátaid szavait is leírja,
  minden hang saját színnel. Többsávos felvételeknél (mikrofon, Discord, játék) sávonként dolgozik
  (a címkéket megjegyzi).
- Káromkodáslista renderelés előtt beszélővel, idővel, lejátszással és sípolás-kapcsolóval; kézi
  sípolás szókijelöléssel vagy a hullámformán. Hangok: klasszikus, lágy „bup”, némítás vagy saját.
- Feliratok: karaoke és beszélőszínes stílus, névcímkék, jobb sortörés, MI-javítás.
- Javítva: a facecam-felismerés a játékban lévő arcot választotta a webkamera helyett. Ha
  bizonytalan, egy kattintással választhatsz; a helyét csatornánként és felbontásonként megjegyzi.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Новое: «Услышать всех» отделяет голоса от звука игры и расшифровывает и твоих друзей, у каждого
  голоса свой цвет. Многодорожечные записи (микрофон, Discord, игра) обрабатываются по дорожкам
  (метки запоминаются).
- Список мата перед рендером: кто сказал, когда, кнопка воспроизведения и переключатель пика;
  пикать вручную можно выделением слов или по звуковой волне. Звуки: классический, мягкий «буп»,
  тишина или свой файл.
- Субтитры: стили «караоке» и «цвета говорящих», подписи с именами, переносы лучше, вычитка ИИ.
- Исправлено: поиск вебки выбирал лицо в игре вместо камеры. Если не уверен — выбираешь одним
  кликом; положение запоминается для канала и разрешения.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- جديد: «اسمع الجميع» يفصل الأصوات عن صوت اللعبة ويفرّغ كلام أصدقائك أيضًا، ولكل صوت لونه.
  التسجيلات متعددة المسارات (ميكروفون، ديسكورد، لعبة) تُعالج لكل مسار (وتُحفظ التسميات).
- قائمة الشتائم قبل الإنشاء مع المتحدث والوقت وزر التشغيل ومفتاح الحجب؛ حجب يدوي بتحديد الكلمات أو
  على الموجة الصوتية. أصوات: صفير كلاسيكي، «بوب» ناعم، كتم أو صوتك الخاص.
- الترجمة: نمطا كاريوكي وألوان المتحدثين، أسماء المتحدثين، تقسيم أسطر أفضل، تدقيق بالذكاء الاصطناعي.
- إصلاح: كان كشف الكاميرا يختار وجهًا داخل اللعبة بدل كاميرتك. عند الشك تختار بنقرة، ويُحفظ الموضع
  لكل قناة ودقة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 新增：“听清每个人”把人声与游戏声分开，也转录你朋友说的话，每个声音有自己的颜色。多音轨录制
  （麦克风、Discord、游戏）按音轨处理（标签会被记住）。
- 渲染前的脏话列表：谁说的、时间、播放按钮和消音开关；可选中文字或在波形上拖动手动消音。消音声音：
  经典哔声、柔和“噗”声、静音或自定义。
- 字幕：卡拉OK 与说话人配色样式、姓名标签、更好的换行、AI 校对。
- 修复：摄像头检测会选中游戏里的人脸而不是你的摄像头。不确定时一键选择；位置按频道和分辨率记住。

</details>

## [1.2.14] - 2026-11-01

### Fixed
- Project page on very short windows: if the candidate list and the render settings don't both
  fit, the side panel now scrolls instead of cutting off the bottom. Fonts that are a little wider
  (for example on Linux) no longer push the buttons out of view.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- Çok kısa pencerelerde proje sayfası: aday listesi ve oluşturma ayarları birlikte sığmazsa yan
  panel artık alt kısmı kesmek yerine kayıyor. Biraz daha geniş yazı tipleri (örneğin Linux'ta)
  düğmeleri görünümden itmiyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Projektseite in sehr niedrigen Fenstern: Passen Kandidatenliste und Render-Einstellungen nicht
  beide hinein, scrollt jetzt das Seitenpanel, statt unten etwas abzuschneiden.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Projektoldal nagyon alacsony ablakban: ha a jelöltlista és a renderelési beállítások nem férnek el
  együtt, az oldalsó panel most görgethető, ahelyett hogy levágná az alját.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Страница проекта в очень низком окне: если список кандидатов и настройки рендера не помещаются
  вместе, боковая панель теперь прокручивается, а не обрезает нижнюю часть.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- صفحة المشروع في النوافذ القصيرة جدًا: إذا لم تتسع قائمة المرشحين وإعدادات الإنشاء معًا، تمرّر
  اللوحة الجانبية الآن بدل قصّ الجزء السفلي منها.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 窗口很矮时的项目页面：如果候选列表和渲染设置无法同时放下，侧边面板现在会滚动，而不是把底部截掉。
  稍宽的字体（例如在 Linux 上）也不会再把按钮挤出视野。
- 候选列表和设置各自滚动，“渲染”和“导出”按钮始终固定在面板底部，随时可以点击。

</details>

## [1.2.13] - 2026-11-01

The project page fits laptop screens: the candidate list no longer disappears under the render
settings.

### Fixed
- **Project page on laptops** (for example a 14" screen at 125-150 % scaling): the candidate list
  was squeezed to a thin strip under the render settings, so you couldn't see your clips. Now the
  list always keeps a good height and scrolls inside its own panel, the settings scroll in their
  own area, and the **Render** and **Export** buttons stay visible at the bottom.
- The tab row (Candidates · Clips · "3 accepted") wraps instead of overlapping, so the counts are
  always visible.
- At 1024 px wide, the top bar no longer pushes the page sideways (the theme button was cut off).
- Clip cards: a long YouTube status ("YouTube · Private · 0 views") wraps instead of being cut off.
- Phones: Studio → Music with a long music folder path, and the hook test table on the Stats page,
  no longer make the page scroll sideways.

<!-- lang:tr -->
**Türkçe**

Proje sayfası artık dizüstü ekranlara sığıyor: aday listesi oluşturma ayarlarının altında
kaybolmuyor.

### Düzeltildi
- **Dizüstünde proje sayfası** (örneğin %125-150 ölçeklemeli 14" ekran): aday listesi oluşturma
  ayarlarının altında ince bir şeride sıkışıyordu, kliplerini göremiyordun. Artık liste her zaman
  iyi bir yükseklikte kalıyor ve kendi panelinde kayıyor, ayarlar kendi alanında kayıyor,
  **Oluştur** ve **Dışa aktar** düğmeleri altta hep görünüyor.
- Sekme satırı (Adaylar · Klipler · "3 kabul edildi") üst üste binmek yerine alta geçiyor; sayılar
  hep görünüyor.
- 1024 piksel genişlikte üst çubuk sayfayı yana kaydırmıyor (tema düğmesi kesiliyordu).
- Klip kartları: uzun bir YouTube durumu ("YouTube · Gizli · 0 izlenme") kesilmek yerine alt satıra
  geçiyor.
- Telefonlar: uzun müzik klasörü yolu olan Stüdyo → Müzik ve İstatistikler'deki kanca testi tablosu
  artık sayfayı yana kaydırmıyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Projektseite auf Laptops (z. B. 14" mit 125-150 % Skalierung): Die Kandidatenliste war unter den
  Render-Einstellungen zu einem schmalen Streifen zusammengedrückt. Jetzt behält sie immer eine gute
  Höhe, die Einstellungen scrollen separat, **Rendern** und **Exportieren** bleiben sichtbar.
- Tab-Zeile, obere Leiste bei 1024 px, Clip-Karten und zwei Seiten auf dem Handy überlappen oder
  scrollen nicht mehr seitlich.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Projektoldal laptopon (pl. 14" kijelző 125-150 %-os méretezéssel): a jelöltlista vékony csíkká
  nyomódott a renderelési beállítások alatt. Most mindig jó magasságú marad, a beállítások külön
  görgethetők, a **Renderelés** és **Exportálás** gomb látható marad.
- A fülsor, a felső sáv 1024 px-en, a klipkártyák és két oldal telefonon már nem fedik egymást és
  nem görgetnek oldalra.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Страница проекта на ноутбуке (например, 14" с масштабом 125-150 %): список кандидатов сжимался в
  тонкую полоску под настройками рендера. Теперь он всегда нормальной высоты, настройки
  прокручиваются отдельно, кнопки **Рендер** и **Экспорт** всегда видны.
- Строка вкладок, верхняя панель при 1024 px, карточки клипов и две страницы на телефоне больше не
  перекрываются и не прокручиваются вбок.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- صفحة المشروع على الحواسيب المحمولة (مثل شاشة 14 بوصة بتكبير 125-150٪): كانت قائمة المرشحين
  تنضغط إلى شريط رفيع تحت إعدادات الإنشاء. الآن تحتفظ دائمًا بارتفاع جيد، وتمرّر الإعدادات في
  منطقتها، ويبقى زرّا **الإنشاء** و**التصدير** ظاهرين.
- لم يعد صف التبويبات والشريط العلوي عند 1024 بكسل وبطاقات المقاطع وصفحتان على الهاتف تتداخل أو
  تمرّر الصفحة جانبيًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 笔记本上的项目页面（例如 14 英寸、125-150% 缩放）：候选列表被渲染设置挤成一条细线，看不到剪辑。
  现在列表始终保持合适高度并在自己的面板中滚动，设置单独滚动，**渲染**和**导出**按钮始终可见。
- 标签行、1024 像素宽时的顶部栏、剪辑卡片以及手机上的两个页面不再重叠或横向滚动。

</details>

## [1.2.12] - 2026-11-01

### Fixed
- Opening SharkyClips right after it crashed or was closed could wait and then show nothing.
  It now starts normally.

<!-- lang:tr -->
**Türkçe**

### Düzeltildi
- SharkyClips çöktükten ya da kapatıldıktan hemen sonra açmak bekleyip hiçbir şey göstermeyebiliyordu.
  Artık normal şekilde açılıyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Behoben: SharkyClips direkt nach einem Absturz oder Beenden zu öffnen, zeigte manchmal nichts an.
  Jetzt startet es ganz normal.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- Javítva: a SharkyClips megnyitása közvetlenül egy összeomlás vagy bezárás után néha semmit sem mutatott.
  Most normálisan elindul.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Исправлено: запуск SharkyClips сразу после сбоя или закрытия иногда ничего не открывал.
  Теперь приложение запускается как обычно.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- تم الإصلاح: فتح SharkyClips مباشرة بعد تعطّله أو إغلاقه لم يكن يُظهر شيئًا أحيانًا.
  الآن يعمل التطبيق بشكل طبيعي.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 已修复：SharkyClips 崩溃或关闭后立即打开时，有时会等待一段时间然后什么都不显示。现在它会像平常一样正常启动，并打开主界面。
- 如果 SharkyClips 已经在运行（例如更新后正在重启），再次打开只会显示正在运行的那个窗口，而不会启动第二个副本。

</details>

## [1.2.11] - 2026-11-01

SharkyClips' Google connection is now published, and scheduled uploads are safer.

### Changed
- **Settings → YouTube** shows the built-in Google connection as **published, not verified yet**:
  anyone can connect after Google's warning screen, up to 100 people until Google has verified
  SharkyClips. Google no longer signs you out every 7 days.

### Fixed
- If SharkyClips was opened a second time while it restarted after an update, two copies could
  run at once and both prepare the same scheduled clip (it could even be uploaded twice). Now
  only one copy runs; opening it again just shows the running one.
- An export could fail with "Access denied" when Windows (for example the antivirus) was still
  scanning the finished file. SharkyClips now waits a moment and tries again.

<!-- lang:tr -->
**Türkçe**

SharkyClips'in Google bağlantısı artık yayında ve zamanlanmış yüklemeler daha güvenli.

### Değişti
- **Ayarlar → YouTube**, yerleşik Google bağlantısını **yayında, henüz doğrulanmadı** olarak
  gösteriyor: Google'ın uyarı ekranından sonra herkes bağlanabilir; Google SharkyClips'i doğrulayana
  kadar en fazla 100 kişi. Google artık seni 7 günde bir oturumdan çıkarmıyor.

### Düzeltildi
- SharkyClips bir güncellemeden sonra yeniden başlarken ikinci kez açılırsa iki kopya aynı anda
  çalışabiliyor ve ikisi de aynı zamanlanmış klibi hazırlıyordu (iki kez yüklenebilirdi bile). Artık
  yalnızca bir kopya çalışıyor; tekrar açmak çalışan kopyayı gösteriyor.
- Windows (örneğin virüs tarayıcısı) bitmiş dosyayı hâlâ tararken bir dışa aktarma "Erişim engellendi"
  hatasıyla bitebiliyordu. SharkyClips artık biraz bekleyip yeniden deniyor.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Die eingebaute Google-Verbindung ist jetzt **veröffentlicht, noch nicht verifiziert**: bis zu 100
  Personen nach Googles Warnbildschirm; keine Abmeldung mehr alle 7 Tage.
- Behoben: Zwei gleichzeitig laufende SharkyClips (zweiter Start während eines Neustarts) konnten
  denselben geplanten Clip doppelt vorbereiten. Jetzt läuft immer nur eine Kopie.
- Behoben: „Zugriff verweigert“ beim Export, während Windows die Datei noch prüfte.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- A beépített Google-kapcsolat most **közzétéve, még nincs ellenőrizve**: a Google figyelmeztetése
  után legfeljebb 100 ember; nincs többé kijelentkeztetés 7 naponta.
- Javítva: két egyszerre futó SharkyClips (második indítás újraindítás közben) ugyanazt az ütemezett
  klipet kétszer készíthette elő. Most mindig csak egy példány fut.
- Javítva: „Hozzáférés megtagadva” exportáláskor, amíg a Windows még vizsgálta a fájlt.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- Встроенное подключение Google теперь **опубликовано, ещё не проверено**: до 100 человек после
  экрана предупреждения Google; больше никаких выходов из аккаунта каждые 7 дней.
- Исправлено: две одновременно запущенные копии SharkyClips (второй запуск во время перезапуска)
  могли дважды готовить один и тот же запланированный клип. Теперь работает только одна копия.
- Исправлено: «Отказано в доступе» при экспорте, пока Windows ещё проверяла файл.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- اتصال Google المدمج صار **منشورًا ولم يُتحقق منه بعد**: حتى 100 شخص بعد شاشة تحذير Google، ولا
  خروج من الحساب كل 7 أيام بعد الآن.
- تم الإصلاح: نسختان من SharkyClips تعملان معًا (تشغيل ثانٍ أثناء إعادة التشغيل) كانتا قد تجهّزان
  المقطع المجدول نفسه مرتين. الآن تعمل نسخة واحدة فقط.
- تم الإصلاح: خطأ «تم رفض الوصول» عند التصدير بينما كان Windows لا يزال يفحص الملف.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- 内置的 Google 连接现已**发布，尚未验证**：在 Google 警告页面后最多 100 人可连接；不再每 7 天退出登录。
- 已修复：更新重启期间再次打开 SharkyClips 时，两个副本可能同时运行并重复准备同一个定时剪辑。现在始终只运行一个副本。
- 已修复：Windows（例如杀毒软件）仍在扫描文件时，导出可能出现“拒绝访问”。

</details>

## [1.2.10] - 2026-11-01

SharkyClips has a website now, and the privacy policy link in the app works.

### Added
- The SharkyClips website is online: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/), with the
  [privacy policy](https://utkualsir.github.io/sharkyclips-site/privacy.html) and the
  [terms of use](https://utkualsir.github.io/sharkyclips-site/terms.html).

### Changed
- **Settings → YouTube**: the privacy policy link opens the new website.
- **Privacy policy and terms** (effective 1 November 2026): they now say clearly that SharkyClips
  only changes or deletes videos it uploaded itself, and only when you ask (editing or
  cancelling a scheduled clip). Questions go to the website's GitHub page.

<!-- lang:tr -->
**Türkçe**

SharkyClips'in artık bir web sitesi var ve uygulamadaki gizlilik politikası bağlantısı çalışıyor.

### Eklendi
- SharkyClips web sitesi yayında: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/);
  [gizlilik politikası](https://utkualsir.github.io/sharkyclips-site/privacy.html) ve
  [kullanım koşulları](https://utkualsir.github.io/sharkyclips-site/terms.html) da orada.

### Değişti
- **Ayarlar → YouTube**: gizlilik politikası bağlantısı yeni web sitesini açıyor.
- **Gizlilik politikası ve koşullar** (1 Kasım 2026'dan itibaren geçerli): SharkyClips'in yalnızca
  kendi yüklediği videoları ve yalnızca sen istediğinde (zamanlanmış bir klibi düzenlerken ya da
  iptal ederken) değiştirdiğini veya sildiğini açıkça söylüyor. Sorular web sitesinin GitHub
  sayfasına.

<details><summary>Deutsch</summary>

<!-- lang:de -->
- SharkyClips hat jetzt eine Website: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (mit
  Datenschutzerklärung und Nutzungsbedingungen); der Link in Einstellungen → YouTube funktioniert.
- Datenschutzerklärung präzisiert: SharkyClips ändert oder löscht nur selbst hochgeladene Videos,
  und nur auf deinen Wunsch.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
- A SharkyClipsnek most már van weboldala: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/)
  (adatvédelmi irányelvek és felhasználási feltételek); a Beállítások → YouTube hivatkozás működik.
- Pontosított adatvédelem: a SharkyClips csak a saját maga által feltöltött videókat módosítja
  vagy törli, és csak ha kéred.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
- У SharkyClips теперь есть сайт: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (с политикой
  конфиденциальности и условиями); ссылка в Настройки → YouTube работает.
- Уточнена политика: SharkyClips изменяет или удаляет только загруженные им видео и только по
  вашей просьбе.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
- صار لـ SharkyClips موقع ويب: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (مع سياسة الخصوصية
  وشروط الاستخدام)، ويعمل الرابط في الإعدادات ← يوتيوب.
- توضيح في سياسة الخصوصية: لا يغيّر SharkyClips ولا يحذف إلا الفيديوهات التي رفعها بنفسه، وبطلب منك فقط.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
- SharkyClips 现在有了网站：[utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/)（含隐私政策和使用条款）；
  设置 → YouTube 中的链接已可用。
- 隐私政策更明确：SharkyClips 只会在你要求时修改或删除它自己上传的视频。

</details>

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
