# Changelog

All notable changes to SharkyClips (called ClipForge before 1.2.1). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Every update bumps the patch version by 0.0.1.

Each entry starts with a one- or two-line summary in simple English, then the details grouped as
New / Improved / Fixed. Turkish follows, then the other UI languages in `<!-- lang:xx -->` blocks
(translated from the English). The app's "What's new" window and Updates page show the block of
the UI language, English where a translation is missing.

## [1.2.60] - 2026-11-21
A small fix for cover pictures: a single frame that only looks like a face no longer counts as your face.

### Fixed
- **Cover pictures.** When the app looks for the moment with your best facial expression, it now needs
  to see a face in more than one frame of the clip. A pattern that looked like a face for a moment
  could make it pick a "face" cover for a clip without a facecam.

<!-- lang:tr -->
**Türkçe**

Kapak resimleri için küçük bir düzeltme: sadece bir an yüze benzeyen tek bir kare artık senin yüzün sayılmıyor.

### Düzeltmeler
- **Kapak resimleri.** Uygulama en iyi yüz ifadeni gösteren anı ararken artık klibin birden fazla
  karesinde yüz görmesi gerekiyor. Bir an yüze benzeyen bir desen, yüz kamerası olmayan bir klip için
  "yüz" kapağı seçtirebiliyordu.

<details><summary>Español</summary>

<!-- lang:es -->
Una pequeña corrección para las portadas: un solo fotograma que solo parece una cara ya no cuenta como tu cara.

### Correcciones
- **Portadas.** Para elegir el momento con tu mejor expresión, la app ahora necesita ver una cara en más de un fotograma del clip.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Uma pequena correção nas capas: um único quadro que só parece um rosto não conta mais como o seu rosto.

### Correções
- **Capas.** Para escolher o momento com a sua melhor expressão, o app agora precisa ver um rosto em mais de um quadro do clipe.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Eine kleine Korrektur bei Titelbildern: Ein einzelnes Bild, das nur wie ein Gesicht aussieht, zählt nicht mehr als dein Gesicht.

### Behoben
- **Titelbilder.** Um den Moment mit deinem besten Gesichtsausdruck zu finden, muss die App jetzt in mehr als einem Bild des Clips ein Gesicht sehen.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Une petite correction des miniatures : une seule image qui ressemble juste à un visage ne compte plus comme ton visage.

### Corrections
- **Miniatures.** Pour choisir le moment avec ta meilleure expression, l’app doit maintenant voir un visage sur plus d’une image du clip.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Kis javítás a borítóképeknél: egyetlen képkocka, amely csak hasonlít egy arcra, már nem számít az arcodnak.

### Javítások
- **Borítóképek.** A legjobb arckifejezésed pillanatának kereséséhez az alkalmazásnak most a klip több képkockáján kell arcot látnia.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Небольшое исправление обложек: один кадр, который лишь похож на лицо, больше не считается вашим лицом.

### Исправления
- **Обложки.** Чтобы выбрать момент с вашим лучшим выражением лица, приложению теперь нужно увидеть лицо больше чем в одном кадре клипа.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
إصلاح صغير لصور الغلاف: إطار واحد يشبه الوجه فقط لم يعد يُحسب وجهك.

### إصلاحات
- **صور الغلاف.** لاختيار اللحظة التي تظهر فيها أفضل تعابير وجهك، يحتاج التطبيق الآن إلى رؤية وجه في أكثر من إطار واحد من المقطع.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
封面图片的小修复：只是看起来像脸的单独一帧不再被当作你的脸。

### 修复
- **封面图片。**在寻找你表情最好的时刻时，应用现在需要在片段的多于一帧中看到人脸。以前，一个短暂像人脸的图案可能会让没有摄像头画面的片段也选到"人脸"封面。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
カバー画像の小さな修正：顔のように見えるだけの 1 フレームは、もうあなたの顔として扱われません。

### 修正
- **カバー画像。**一番いい表情の瞬間を探すとき、クリップの複数のフレームで顔が見つかる必要があるようになりました。これまでは、一瞬だけ顔に見える模様のせいで、フェイスカメラのないクリップでも「顔」のカバーが選ばれることがありました。

</details>

## [1.2.59] - 2026-11-21
A small shark game to play while your project is processing, and animated graphics that now keep away from the game's own kill feed, score and minimap.

### New
- **Shark Snack, a mini game while you wait.** While a project is processing, a small button shows at
  the bottom of the screen. It opens a compact game: your shark eats smaller fish to grow, avoids
  bigger fish, jellyfish and spiky urchins, builds combos and picks up bubbles (magnet, double points,
  shield, extra time). Rounds are short (30 to 90 seconds) and get a little harder every second.
- **Play your way.** Mouse, finger or keyboard (arrow keys or WASD, Space to dash, P to pause). A short
  "how to play" shows the first time. Sound effects are off until you turn them on.
- **Your best score, today's best and seven shark skins** you earn by playing. No ads, nothing to buy,
  no timers or streaks, nothing online: everything stays on your computer.
- **Your clips first.** When the processing is done, a small "Your clips are ready!" message opens
  your clips with one click. The game keeps your score, so you can also keep playing.
- **Game HUD areas.** Every game profile now knows where the game draws its kill feed, score, minimap
  and other HUD parts. The animated graphics never cover them.

### Improved
- **The game never slows down your clips.** It only runs while you play, it pauses when you hide it,
  switch to another window or minimise the app, and it uses very little power (about 0.2 ms of work
  per frame in our tests). You can turn the button off in Settings, and start a game from there at
  any time.
- **Bold graphics in the split layout** now move into the free space above the action (a little
  smaller when needed) instead of sitting on the game's own text at the bottom.

### Fixed
- In Delta Force clips, the Bold style no longer covers the game's own kill text and score lines.
- Short clips with the Shorts / TikTok / Reels safe areas now show Bold graphics again where there was
  no free spot before.

<!-- lang:tr -->
**Türkçe**

Projen işlenirken oynayabileceğin küçük bir köpekbalığı oyunu ve artık oyunun kendi kill akışından, skorundan ve mini haritasından uzak duran hareketli grafikler.

### Yeni
- **Shark Snack: beklerken mini oyun.** Bir proje işlenirken ekranın altında küçük bir düğme belirir.
  Kompakt bir oyun açar: köpekbalığın küçük balıkları yiyerek büyür, büyük balıklardan, denizanalarından
  ve dikenli deniz kestanelerinden kaçar, kombo yapar ve baloncukları toplar (mıknatıs, çift puan, kalkan,
  ek süre). Turlar kısadır (30-90 saniye) ve her saniye biraz zorlaşır.
- **İstediğin gibi oyna.** Fare, parmak veya klavye (ok tuşları ya da WASD, atılmak için Boşluk,
  duraklatmak için P). İlk açılışta kısa bir "nasıl oynanır" görünür. Ses efektleri sen açana kadar
  kapalıdır.
- **En iyi skorun, bugünün en iyisi ve oynayarak kazandığın yedi köpekbalığı görünümü.** Reklam yok,
  satın alma yok, süre baskısı veya seri yok, internet yok: her şey bilgisayarında kalır.
- **Önce kliplerin.** İşlem bitince küçük bir "Kliplerin hazır!" mesajı tek tıkla kliplerini açar. Oyun
  skorunu saklar, istersen oynamaya devam edebilirsin.
- **Oyun HUD bölgeleri.** Her oyun profili artık oyunun kill akışını, skorunu, mini haritasını ve diğer
  HUD parçalarını nereye çizdiğini biliyor. Hareketli grafikler bunların üstüne asla gelmez.

### İyileştirmeler
- **Oyun kliplerini asla yavaşlatmaz.** Sadece oynarken çalışır; gizleyince, başka pencereye geçince
  veya uygulamayı küçültünce durur ve çok az güç kullanır (testlerimizde kare başına yaklaşık 0,2 ms).
  Düğmeyi Ayarlar'dan kapatabilir, oyunu oradan istediğin zaman başlatabilirsin.
- **Bölünmüş düzende Belirgin grafikler** artık alttaki oyun yazısının üstüne oturmak yerine aksiyonun
  üstündeki boş alana geçiyor (gerekirse biraz küçülerek).

### Düzeltmeler
- Delta Force kliplerinde Belirgin stil artık oyunun kendi öldürme yazısını ve puan satırlarını
  kapatmıyor.
- Shorts / TikTok / Reels güvenli alanlı kliplerde, daha önce boş yer bulunamayan Belirgin grafikler
  yeniden görünüyor.

<details><summary>Español</summary>

<!-- lang:es -->
Un pequeño juego de tiburón para jugar mientras se procesa tu proyecto, y gráficos animados que ahora se apartan del registro de bajas, el marcador y el minimapa del propio juego.

### Nuevo
- **Shark Snack, un minijuego mientras esperas:** come peces más pequeños para crecer, esquiva peces grandes, medusas y erizos, haz combos y recoge burbujas de poder. Rondas cortas (30-90 s).
- Ratón, dedo o teclado; una breve guía la primera vez; sonido apagado hasta que lo actives. Récord, mejor de hoy y siete aspectos que se ganan jugando. Sin anuncios, sin compras, nada en línea.
- Al terminar el proceso, un aviso "¡Tus clips están listos!" los abre con un clic; el juego guarda tu puntuación.
- **Zonas del HUD de cada juego:** los gráficos animados nunca cubren el registro de bajas, el marcador ni el minimapa.

### Mejoras
- El juego solo funciona mientras juegas, se pausa al ocultarlo o cambiar de ventana y gasta muy poco. Puedes desactivar el botón en Ajustes.
- Los gráficos llamativos en el diseño dividido pasan al espacio libre sobre la acción.

### Correcciones
- En Delta Force, el estilo llamativo ya no tapa el texto de bajas del juego.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Um joguinho de tubarão para jogar enquanto seu projeto é processado, e gráficos animados que agora ficam longe do feed de abates, do placar e do minimapa do próprio jogo.

### Novo
- **Shark Snack, um minijogo enquanto espera:** coma peixes menores para crescer, fuja de peixes grandes, águas-vivas e ouriços, faça combos e pegue bolhas de poder. Rodadas curtas (30-90 s).
- Mouse, dedo ou teclado; um guia rápido na primeira vez; som desligado até você ligar. Recorde, melhor de hoje e sete visuais conquistados jogando. Sem anúncios, sem compras, nada online.
- Quando o processamento termina, o aviso "Seus clipes estão prontos!" abre tudo com um clique; o jogo guarda sua pontuação.
- **Áreas do HUD de cada jogo:** os gráficos animados nunca cobrem o feed de abates, o placar ou o minimapa.

### Melhorias
- O jogo só roda enquanto você joga, pausa ao esconder ou trocar de janela e gasta muito pouco. Dá para desligar o botão nas Configurações.
- Gráficos chamativos no layout dividido vão para o espaço livre acima da ação.

### Correções
- No Delta Force, o estilo chamativo não cobre mais o texto de abates do jogo.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Ein kleines Hai-Spiel für die Wartezeit, während dein Projekt verarbeitet wird, und animierte Grafiken, die jetzt Killfeed, Punktestand und Minikarte des Spiels freilassen.

### Neu
- **Shark Snack, ein Minispiel beim Warten:** friss kleinere Fische, um zu wachsen, weiche großen Fischen, Quallen und Seeigeln aus, mach Kombos und sammle Power-up-Blasen. Kurze Runden (30-90 s).
- Maus, Finger oder Tastatur; eine kurze Anleitung beim ersten Mal; Ton aus, bis du ihn einschaltest. Bestwert, Tagesbestwert und sieben erspielbare Skins. Keine Werbung, keine Käufe, nichts online.
- Ist die Verarbeitung fertig, öffnet „Deine Clips sind fertig!“ sie mit einem Klick; das Spiel behält deinen Punktestand.
- **HUD-Bereiche je Spiel:** animierte Grafiken verdecken nie Killfeed, Punktestand oder Minikarte.

### Verbessert
- Das Spiel läuft nur, während du spielst, pausiert beim Ausblenden oder Fensterwechsel und braucht sehr wenig Leistung. Der Knopf lässt sich in den Einstellungen ausschalten.
- Auffällige Grafiken im geteilten Layout rücken in den freien Platz über der Action.

### Behoben
- In Delta Force verdeckt der auffällige Stil nicht mehr den Kill-Text des Spiels.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Un petit jeu de requin pour patienter pendant le traitement de ton projet, et des graphismes animés qui évitent maintenant le fil des kills, le score et la mini-carte du jeu.

### Nouveau
- **Shark Snack, un mini-jeu pendant l’attente :** mange les petits poissons pour grandir, évite les gros poissons, les méduses et les oursins, enchaîne les combos et attrape des bulles bonus. Manches courtes (30-90 s).
- Souris, doigt ou clavier ; un petit guide la première fois ; son coupé jusqu’à ce que tu l’actives. Record, meilleur score du jour et sept apparences à gagner en jouant. Pas de pub, rien à acheter, rien en ligne.
- Quand le traitement est fini, « Tes clips sont prêts ! » les ouvre en un clic ; le jeu garde ton score.
- **Zones du HUD de chaque jeu :** les graphismes animés ne couvrent jamais le fil des kills, le score ou la mini-carte.

### Améliorations
- Le jeu ne tourne que pendant que tu joues, se met en pause quand tu le caches ou changes de fenêtre, et consomme très peu. Tu peux masquer le bouton dans les Réglages.
- Les graphismes marqués en disposition partagée passent dans l’espace libre au-dessus de l’action.

### Corrections
- Dans Delta Force, le style marqué ne cache plus le texte des kills du jeu.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egy kis cápás játék várakozás közben, amíg a projekted készül, és animált grafikák, amelyek most elkerülik a játék saját killfeedjét, pontjait és minitérképét.

### Új
- **Shark Snack, minijáték várakozás közben:** egyél kisebb halakat, hogy nőj, kerüld a nagy halakat, medúzákat és tengeri sünöket, gyűjts kombót és erőbuborékokat. Rövid körök (30-90 mp).
- Egér, ujj vagy billentyűzet; rövid útmutató az első alkalommal; a hang ki van kapcsolva, amíg be nem kapcsolod. Rekord, mai legjobb és hét játékkal megszerezhető kinézet. Nincs reklám, nincs vásárlás, semmi sem megy az internetre.
- Ha kész a feldolgozás, a „Kész vannak a klipjeid!” üzenet egy kattintással megnyitja őket; a játék megőrzi a pontjaidat.
- **Játékonkénti HUD-területek:** az animált grafikák soha nem takarják a killfeedet, a pontokat vagy a minitérképet.

### Fejlesztések
- A játék csak játék közben fut, elrejtéskor vagy ablakváltáskor szünetel, és nagyon keveset fogyaszt. A gomb a Beállításokban kikapcsolható.
- A feltűnő grafikák osztott elrendezésben az akció feletti szabad helyre kerülnek.

### Javítások
- Delta Force-ban a feltűnő stílus már nem takarja a játék kill-szövegét.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Небольшая игра про акулу на время обработки проекта и анимированная графика, которая теперь не закрывает ленту убийств, счёт и мини-карту самой игры.

### Новое
- **Shark Snack — мини-игра во время ожидания:** ешьте рыб поменьше, чтобы расти, уворачивайтесь от больших рыб, медуз и морских ежей, делайте комбо и собирайте пузыри с бонусами. Короткие раунды (30–90 с).
- Мышь, палец или клавиатура; короткая подсказка при первом запуске; звук выключен, пока вы его не включите. Рекорд, лучший результат за день и семь обликов, которые открываются за игру. Без рекламы, без покупок, без интернета.
- Когда обработка закончится, сообщение «Ваши клипы готовы!» откроет их одним щелчком; игра сохранит ваш счёт.
- **Области интерфейса каждой игры:** анимированная графика никогда не закрывает ленту убийств, счёт и мини-карту.

### Улучшения
- Игра работает только пока вы играете, ставится на паузу, если её скрыть или переключить окно, и почти не нагружает компьютер. Кнопку можно выключить в настройках.
- Яркая графика в раздельной раскладке переходит в свободное место над действием.

### Исправления
- В Delta Force яркий стиль больше не закрывает надписи об убийствах в самой игре.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
لعبة قرش صغيرة تلعبها أثناء معالجة مشروعك، ورسومات متحركة تبتعد الآن عن سجل القتل والنتيجة والخريطة المصغّرة الخاصة باللعبة.

### جديد
- **Shark Snack، لعبة صغيرة أثناء الانتظار:** كُل الأسماك الأصغر لتكبر، وتجنّب الأسماك الكبيرة وقناديل البحر وقنافذ البحر، واصنع الكومبو واجمع فقاعات القدرات. جولات قصيرة (30-90 ثانية).
- الفأرة أو الإصبع أو لوحة المفاتيح؛ دليل قصير في المرة الأولى؛ الصوت مغلق حتى تشغّله. أفضل نتيجة، وأفضل نتيجة اليوم، وسبعة مظاهر تكسبها باللعب. بلا إعلانات ولا مشتريات ولا شيء عبر الإنترنت.
- عند انتهاء المعالجة تفتح رسالة "مقاطعك جاهزة!" مقاطعك بنقرة واحدة؛ وتحتفظ اللعبة بنتيجتك.
- **مناطق واجهة كل لعبة:** الرسومات المتحركة لا تغطي أبدًا سجل القتل أو النتيجة أو الخريطة المصغّرة.

### تحسينات
- تعمل اللعبة فقط أثناء اللعب، وتتوقف عند إخفائها أو الانتقال إلى نافذة أخرى، وتستهلك القليل جدًا. يمكنك إيقاف الزر من الإعدادات.
- الرسومات البارزة في التخطيط المقسوم تنتقل إلى المساحة الفارغة فوق الحركة.

### إصلاحات
- في Delta Force لم يعد النمط البارز يغطي نص القتل الخاص باللعبة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
项目处理期间可以玩的小鲨鱼游戏，以及现在会避开游戏自身击杀信息、比分和小地图的动态图形。

### 新功能
- **Shark Snack，等待时的小游戏：**吃掉更小的鱼长大，躲开大鱼、水母和海胆，打出连击并收集能力气泡。每局很短（30-90 秒）。
- 鼠标、手指或键盘；首次打开有简短玩法说明；声音默认关闭。最高分、今日最佳，以及七种靠玩游戏解锁的外观。没有广告，没有购买，不联网。
- 处理完成后，"你的片段已准备好！"提示一键打开片段；游戏会保留你的分数。
- **每款游戏的界面区域：**动态图形从不遮挡击杀信息、比分或小地图。

### 改进
- 游戏只在你玩的时候运行，隐藏或切换窗口时自动暂停，几乎不占资源。可以在设置中关闭按钮。
- 分屏布局中的醒目图形会移到动作上方的空白处。

### 修复
- 在 Delta Force 中，醒目样式不再遮挡游戏自身的击杀文字。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
プロジェクトの処理中に遊べる小さなサメのゲームと、ゲーム自体のキルログ・スコア・ミニマップを避けるようになったアニメーショングラフィック。

### 新機能
- **Shark Snack、待ち時間のミニゲーム：**小さな魚を食べて大きくなり、大きな魚・クラゲ・ウニをよけ、コンボを決めてパワーアップの泡を集めよう。短いラウンド（30〜90 秒）。
- マウス、指、キーボードに対応。初回は短い遊び方を表示。サウンドはオンにするまでオフ。ベスト、今日のベスト、遊んで手に入る 7 種類のスキン。広告なし、購入なし、オンライン通信なし。
- 処理が終わると「クリップの準備ができました！」から 1 クリックで開けます。スコアはそのまま残ります。
- **ゲームごとの HUD エリア：**アニメーショングラフィックがキルログ、スコア、ミニマップを隠すことはありません。

### 改善
- ゲームは遊んでいる間だけ動き、隠したりウィンドウを切り替えたりすると一時停止し、負荷はごくわずかです。ボタンは設定でオフにできます。
- 分割レイアウトの目立つグラフィックは、アクションの上の空いた場所に移ります。

### 修正
- Delta Force で、目立つスタイルがゲーム自体のキル表示を隠さなくなりました。

</details>

## [1.2.58] - 2026-11-20
Animated graphics on your gaming clips, a new Updates page with every version's notes, and English as the start language for new users.

### New
- **Animated graphics on clips.** A kill counter that counts up, banners for big moments (DOUBLE KILL,
  PENTAKILL, ACE, CLUTCH, SPIKE PLANTED and more), round wins and match results, and the big numbers
  you say ("21 KILL", "1v4") pop in for a moment with a small icon, in your brand colours.
- **Careful placement.** Only one graphic at a time, never longer than 1.5 seconds, never over your
  facecam, the captions, the title text, the middle of the game picture or the buttons of Shorts,
  TikTok and Reels. If there is no free spot, the graphic is skipped.
- **Two styles:** Minimal (the default) and Bold, or Off. In Easy mode it is one switch in Settings;
  in Pro mode you find it under the effects. Every game has its own moments, and you can add your
  own game.
- **Updates page.** A new **Updates** item in the menu lists every version, newest first: the date, a
  short summary and the details as New / Improved / Fixed, in your language. Search it, and open any
  version. A small "New" badge shows after an update until you open the page. You also find it in
  Settings > About.

### Improved
- **The preview shows the graphics exactly like the finished clip:** same moment, same place, same
  movement. With "reduce motion" on, the preview only fades them in and out.
- **Light on your PC.** The graphics are drawn by the processor, no graphics card needed. On the Light
  speed preset they use simple fades. Captions, bleeps and timing don't change.
- **Clearer release notes.** Every version now starts with a one- or two-line summary in simple
  English, and the notes no longer use technical words.
- **English first for new users.** A new install starts in English. If you already picked a language,
  it stays. The language button is on the home screen and in the top bar (also in Pro mode).

<!-- lang:tr -->
**Türkçe**

Oyun kliplerinde hareketli grafikler, her sürümün notlarını gösteren yeni Güncellemeler sayfası ve yeni kullanıcılar için başlangıç dili olarak İngilizce.

### Yeni
- **Kliplerde hareketli grafikler.** Artan bir kill sayacı, büyük anlar için bantlar (DOUBLE KILL,
  PENTAKILL, ACE, CLUTCH, SPIKE PLANTED ve dahası), kazanılan raundlar ve maç sonuçları ile
  söylediğin büyük sayılar ("21 KILL", "1v4") küçük bir simgeyle, marka renklerinde bir anlığına
  beliriyor.
- **Özenli yerleşim.** Aynı anda tek grafik, en fazla 1,5 saniye; yüz kameranın, altyazıların, başlık
  yazısının, oyun görüntüsünün ortasının ve Shorts, TikTok, Reels düğmelerinin üstüne asla gelmez.
  Boş yer yoksa grafik atlanır.
- **İki stil:** Sade (varsayılan) ve Belirgin, ya da Kapalı. Kolay modda Ayarlar'da tek bir anahtar;
  Pro modda efektlerin altında. Her oyunun kendi anları var ve kendi oyununu da ekleyebilirsin.
- **Güncellemeler sayfası.** Menüdeki yeni **Güncellemeler** öğesi tüm sürümleri en yenisi başta
  listeliyor: tarih, kısa bir özet ve Yeni / İyileştirmeler / Düzeltmeler olarak ayrıntılar, senin
  dilinde. Arama yapabilir, istediğin sürümü açabilirsin. Güncellemeden sonra sayfayı açana kadar
  küçük bir "Yeni" rozeti görünür. Ayarlar > Hakkında'da da var.

### İyileştirmeler
- **Önizleme grafikleri bitmiş klipteki gibi gösteriyor:** aynı an, aynı yer, aynı hareket. "Hareketi
  azalt" açıksa önizleme onları sadece belirip kaybolarak gösterir.
- **Bilgisayarını yormaz.** Grafikleri işlemci çiziyor, ekran kartı gerekmez. Hafif hız ayarında basit
  geçişler kullanılır. Altyazılar, bip'ler ve zamanlama değişmez.
- **Daha anlaşılır sürüm notları.** Her sürüm artık basit bir bir-iki satırlık özetle başlıyor ve
  notlarda teknik kelimeler yok.
- **Yeni kullanıcılar için önce İngilizce.** Yeni bir kurulum İngilizce açılır. Daha önce bir dil
  seçtiysen o kalır. Dil düğmesi ana ekranda ve üst çubukta (Pro modda da).

<details><summary>Español</summary>

<!-- lang:es -->
Gráficos animados en tus clips de juegos, una nueva página Novedades con las notas de cada versión e inglés como idioma inicial para usuarios nuevos.

### Nuevo
- **Gráficos animados:** un contador de bajas, rótulos para los grandes momentos (PENTAKILL, ACE, CLUTCH...), rondas ganadas y los números que dices ("21 KILL", "1v4"), con un icono y en tus colores de marca.
- Solo uno a la vez, como máximo 1,5 s, nunca encima de tu cámara, los subtítulos, el centro de la partida ni los botones de Shorts, TikTok y Reels. Estilos Mínimo (por defecto), Llamativo o No; en el modo Fácil, un interruptor.
- **Página Novedades:** todas las versiones con resumen y detalles (Nuevo / Mejoras / Correcciones), buscador y una insignia "Nuevo" tras cada actualización.

### Mejoras
- La vista previa muestra los gráficos igual que el clip final. Funcionan sin tarjeta gráfica; subtítulos y pitidos no cambian.
- Las instalaciones nuevas empiezan en inglés; tu idioma elegido se mantiene.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Gráficos animados nos seus clipes de jogos, uma nova página Atualizações com as notas de cada versão e inglês como idioma inicial para novos usuários.

### Novo
- **Gráficos animados:** um contador de abates, faixas para os grandes momentos (PENTAKILL, ACE, CLUTCH...), rodadas vencidas e os números que você fala ("21 KILL", "1v4"), com um ícone e nas cores da sua marca.
- Só um por vez, no máximo 1,5 s, nunca sobre a sua câmera, as legendas, o centro da partida ou os botões de Shorts, TikTok e Reels. Estilos Mínimo (padrão), Chamativo ou Desligado; no modo Fácil, um botão.
- **Página Atualizações:** todas as versões com resumo e detalhes (Novo / Melhorias / Correções), busca e um selo "Novo" depois de cada atualização.

### Melhorias
- A prévia mostra os gráficos igual ao clipe final. Funcionam sem placa de vídeo; legendas e bipes não mudam.
- Instalações novas começam em inglês; o idioma que você escolheu continua.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Animierte Grafiken in deinen Gaming-Clips, eine neue Seite Updates mit den Notizen jeder Version und Englisch als Startsprache für neue Nutzer.

### Neu
- **Animierte Grafiken:** ein Kill-Zähler, Banner für große Momente (PENTAKILL, ACE, CLUTCH ...), gewonnene Runden und Zahlen, die du sagst („21 KILL“, „1v4“), mit Symbol und in deinen Markenfarben.
- Immer nur eine, höchstens 1,5 s, nie über deiner Facecam, den Untertiteln, der Bildmitte oder den Buttons von Shorts, TikTok und Reels. Stile Dezent (Standard), Auffällig oder Aus; im einfachen Modus ein Schalter.
- **Seite Updates:** alle Versionen mit Zusammenfassung und Details (Neu / Verbessert / Behoben), Suche und einem „Neu“-Abzeichen nach jedem Update.

### Verbessert
- Die Vorschau zeigt die Grafiken genau wie der fertige Clip. Keine Grafikkarte nötig; Untertitel und Pieptöne bleiben gleich.
- Neue Installationen starten auf Englisch; deine gewählte Sprache bleibt.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Des graphismes animés sur tes clips de jeu, une nouvelle page Mises à jour avec les notes de chaque version, et l'anglais comme langue de départ pour les nouveaux utilisateurs.

### Nouveau
- **Graphismes animés :** un compteur de kills, des bandeaux pour les grands moments (PENTAKILL, ACE, CLUTCH...), les manches gagnées et les chiffres que tu dis (« 21 KILL », « 1v4 »), avec une icône et dans tes couleurs de marque.
- Un seul à la fois, 1,5 s au plus, jamais sur ta caméra, les sous-titres, le centre de l'image ou les boutons de Shorts, TikTok et Reels. Styles Discret (par défaut), Marqué ou Non ; en mode Facile, un interrupteur.
- **Page Mises à jour :** toutes les versions avec un résumé et les détails (Nouveau / Améliorations / Corrections), une recherche et un badge « Nouveau » après chaque mise à jour.

### Améliorations
- L'aperçu montre les graphismes exactement comme le clip final. Pas besoin de carte graphique ; sous-titres et bips inchangés.
- Les nouvelles installations démarrent en anglais ; la langue que tu as choisie reste.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Animált grafikák a játékklipjeiden, új Frissítések oldal minden verzió jegyzeteivel, és angol kezdőnyelv az új felhasználóknak.

### Új
- **Animált grafikák:** killszámláló, feliratok a nagy pillanatokhoz (PENTAKILL, ACE, CLUTCH...), megnyert körök és az általad mondott számok („21 KILL”, „1v4”), ikonnal, a márkaszíneidben.
- Egyszerre csak egy, legfeljebb 1,5 mp, soha nem takarja a kamerád, a feliratot, a kép közepét vagy a Shorts, TikTok és Reels gombjait. Stílusok: Visszafogott (alap), Feltűnő vagy Ki; Egyszerű módban egy kapcsoló.
- **Frissítések oldal:** minden verzió összefoglalóval és részletekkel (Új / Fejlesztések / Javítások), kereséssel és „Új” jelvénnyel frissítés után.

### Fejlesztések
- Az előnézet pontosan úgy mutatja a grafikákat, mint a kész klip. Nem kell videókártya; a feliratok és sípolások nem változnak.
- Az új telepítések angolul indulnak; a már kiválasztott nyelved megmarad.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Анимированная графика в игровых клипах, новая страница «Обновления» с заметками каждой версии и английский как стартовый язык для новых пользователей.

### Новое
- **Анимированная графика:** счётчик убийств, плашки для ярких моментов (PENTAKILL, ACE, CLUTCH...), выигранные раунды и сказанные вами числа («21 KILL», «1v4») — со значком и в ваших фирменных цветах.
- Только одна за раз, не дольше 1,5 с, никогда поверх камеры, субтитров, центра картинки или кнопок Shorts, TikTok и Reels. Стили: «Минимум» (по умолчанию), «Яркий» или «Выкл.»; в простом режиме — один переключатель.
- **Страница «Обновления»:** все версии с кратким итогом и подробностями (Новое / Улучшения / Исправления), поиск и значок «Новое» после обновления.

### Улучшения
- Предпросмотр показывает графику точно как в готовом клипе. Видеокарта не нужна; субтитры и запикивание не меняются.
- Новые установки запускаются на английском; выбранный вами язык сохраняется.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
رسومات متحركة في مقاطع ألعابك، وصفحة "التحديثات" الجديدة بملاحظات كل إصدار، والإنجليزية كلغة البدء للمستخدمين الجدد.

### جديد
- **رسومات متحركة:** عدّاد قتل، وشرائط للحظات الكبيرة (PENTAKILL وACE وCLUTCH...)، والجولات الرابحة، والأرقام التي تقولها ("21 KILL"، "1v4")، مع أيقونة وبألوان علامتك.
- رسم واحد فقط في كل مرة، لمدة 1.5 ثانية على الأكثر، ولا يغطي كاميرتك أو الترجمة أو وسط الصورة أو أزرار Shorts وTikTok وReels أبدًا. الأنماط: بسيط (افتراضي) أو بارز أو إيقاف؛ وفي الوضع السهل مفتاح واحد.
- **صفحة التحديثات:** كل الإصدارات مع ملخص وتفاصيل (جديد / تحسينات / إصلاحات)، وبحث، وشارة "جديد" بعد كل تحديث.

### تحسينات
- تعرض المعاينة الرسومات تمامًا كما في المقطع النهائي. لا حاجة لبطاقة رسومات؛ الترجمة والصافرات لا تتغير.
- التثبيتات الجديدة تبدأ بالإنجليزية؛ وتبقى اللغة التي اخترتها.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
游戏剪辑中的动态图形、展示每个版本说明的新“更新”页面，以及新用户默认使用英语。

### 新功能
- **动态图形：**击杀计数、精彩时刻横幅（PENTAKILL、ACE、CLUTCH 等）、赢下的回合，以及你说出的数字（“21 KILL”、“1v4”），配有小图标并使用你的品牌颜色。
- 同一时间只显示一个，最长 1.5 秒，绝不挡住你的摄像头、字幕、画面中央或 Shorts、TikTok、Reels 的按钮。样式：简约（默认）、醒目或关闭；简易模式中只有一个开关。
- **“更新”页面：**所有版本的摘要和详情（新功能 / 改进 / 修复），可搜索，更新后菜单显示“新”标记。

### 改进
- 预览中的图形与最终剪辑完全一致。无需显卡；字幕和哔声不受影响。
- 新安装默认英语；你已选择的语言保持不变。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
ゲームクリップにアニメーション表示、全バージョンのノートを見られる新しい「アップデート」ページ、新規ユーザーは英語でスタート。

### 新機能
- **アニメーション表示：**キルカウンター、見せ場のバナー（PENTAKILL・ACE・CLUTCH など）、ラウンド勝利、あなたが言った数字（「21 KILL」「1v4」）を、アイコン付き・ブランドカラーで一瞬表示します。
- 表示は一度にひとつ、最長 1.5 秒。顔カメラ・字幕・画面中央・Shorts/TikTok/Reels のボタンには重なりません。スタイルはシンプル（既定）・派手・オフ。かんたんモードではスイッチひとつ。
- **アップデートページ：**全バージョンの要約と詳細（新機能 / 改善 / 修正）、検索、更新後の「新着」バッジ。

### 改善
- プレビューのアニメーション表示は完成クリップと完全に同じです。グラフィックボード不要、字幕とピー音は変わりません。
- 新規インストールは英語で始まり、選択済みの言語はそのまま残ります。

</details>

## [1.2.57] - 2026-11-20
Connect your Kick, Twitch or YouTube channel once, and SharkyClips makes clips from every new stream by itself.

### New
- **Settings > Channels** (and "Connect my channel" on the home screen): paste your Kick, Twitch or
  YouTube channel once. When a stream ends, SharkyClips downloads its VOD and makes the clips: no OBS
  recording needed. Your PC just has to be on.
- **Only new streams.** Adding a channel never processes its old videos. Want a few anyway? "Import
  the last streams" takes them.
- **It looks often enough, never too often:** every 5 minutes while you're live and right after, every
  30 minutes otherwise. Public pages only: no login, no password. A VOD that shows up late, is still
  being prepared or was deleted is handled; subscriber-only and age-restricted VODs are skipped with a
  clear note. Was the PC off or asleep? It catches up on the missed streams, oldest first.
- **Careful with your PC:** one download at a time, continues where it stopped, checked when done.
  It waits while you play, on a metered connection (optional) and when the disk is too full (it tells
  you how much space it needs). Then the normal Easy clips run: chat replay as a hype signal, bleeps,
  titles in your style, covers, game detection.
- **"Your stream is over, 6 clips are ready."** You get it in the tray and on Telegram (if paired).
  The Library shows which channel and stream every clip came from.
- **Per channel:** content type and game (automatic by default), auto-publish (off by default; when on
  it uses your Publish / Autopilot rules and daily limits) and what happens to the downloaded video
  (by default it goes to the trash 7 days after the clips; you can keep it).
- **Other people's channels** can be watched too, clearly marked "Not mine", with auto-publish off.
  Get the streamer's permission before posting their content.

<!-- lang:tr -->
**Türkçe**

Kick, Twitch veya YouTube kanalını bir kez bağla; SharkyClips her yeni yayından klipleri kendisi çıkarır.

### Yeni
- **Ayarlar > Kanallar** (ve ana ekranda "Kanalımı bağla"): Kick, Twitch veya YouTube kanalını bir kez
  yapıştır. Yayın bitince SharkyClips VOD'u indirir ve klipleri çıkarır: OBS kaydı gerekmez.
  Bilgisayarının açık olması yeterli.
- **Sadece yeni yayınlar.** Kanal eklemek eski videoları işlemez. Yine de birkaçını istersen
  "Son yayınları içe aktar" onları alır.
- **Yeterince sık bakar, asla fazla değil:** yayındayken ve hemen sonrasında 5 dakikada bir, diğer
  zamanlarda 30 dakikada bir. Sadece herkese açık sayfalar: giriş yok, şifre yok. Geç gelen, hâlâ
  hazırlanan veya silinen VOD'lar doğru ele alınır; abonelere özel ve yaş sınırlı VOD'lar açık bir notla
  atlanır. Bilgisayar kapalı ya da uykudaydı mı? Kaçan yayınları en eskiden başlayarak yakalar.
- **Bilgisayarına özenli:** aynı anda tek indirme, kaldığı yerden devam eder, bitince kontrol edilir.
  Oyun oynarken, ölçülü bağlantıda (isteğe bağlı) ve disk çok doluyken bekler (ne kadar yer gerektiğini
  söyler). Ardından normal Kolay mod klipleri çalışır: heyecan sinyali olarak sohbet tekrarı, bipler,
  senin tarzında başlıklar, kapaklar, oyun algılama.
- **"Yayının bitti, 6 klip hazır."** Bildirimi sistem tepsisinde ve (eşleştirdiysen) Telegram'da alırsın.
  Kütüphane her klibin hangi kanal ve yayından geldiğini gösterir.
- **Kanal başına:** içerik türü ve oyun (varsayılan otomatik), otomatik yayın (varsayılan kapalı; açıkken
  Yayınla / Otopilot kurallarını ve günlük limitlerini kullanır) ve indirilen videoya ne olacağı
  (varsayılan: kliplerden 7 gün sonra çöp kutusuna gider; saklayabilirsin).
- **Başkalarının kanalları** da izlenebilir; açıkça "Benim değil" diye işaretlenir, otomatik yayın
  kapalıdır. İçeriğini paylaşmadan önce yayıncıdan izin al.

<details><summary>Español</summary>

<!-- lang:es -->
Conecta tu canal de Kick, Twitch o YouTube una vez y SharkyClips hace clips de cada nuevo directo solo.

- **Conecta tu canal** de Kick, Twitch o YouTube en Ajustes > Canales (o "Conectar mi canal" en el inicio): cuando termina un directo, SharkyClips descarga el VOD y hace los clips solo. Sin grabar con OBS.
- Solo directos nuevos (los antiguos, con "Importar los últimos directos"). Solo páginas públicas, sin iniciar sesión. Una descarga cada vez; espera mientras juegas, con conexión de uso medido y con poco disco; se pone al día si el PC estaba apagado.
- "Tu directo terminó, 6 clips están listos" en la bandeja y en Telegram. Publicación automática desactivada por defecto; canales de otras personas marcados, con permiso del streamer.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Conecte seu canal da Kick, Twitch ou YouTube uma vez e o SharkyClips faz clipes de cada nova live sozinho.

- **Conecte seu canal** da Kick, Twitch ou YouTube em Configurações > Canais (ou "Conectar meu canal" no início): quando a live acaba, o SharkyClips baixa o VOD e faz os clipes sozinho. Sem gravar no OBS.
- Só lives novas (as antigas, com "Importar as últimas lives"). Só páginas públicas, sem login. Um download por vez; espera enquanto você joga, em conexão limitada e com pouco disco; recupera o que perdeu se o PC estava desligado.
- "Sua live acabou, 6 clipes estão prontos" na bandeja e no Telegram. Publicação automática desligada por padrão; canais de outras pessoas marcados, com permissão do streamer.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Verbinde deinen Kick-, Twitch- oder YouTube-Kanal einmal, und SharkyClips macht aus jedem neuen Stream von selbst Clips.

- **Verbinde deinen Kanal** (Kick, Twitch oder YouTube) unter Einstellungen > Kanäle oder "Meinen Kanal verbinden" auf der Startseite: Wenn ein Stream endet, lädt SharkyClips das VOD und macht die Clips von selbst. Keine OBS-Aufnahme nötig.
- Nur neue Streams (alte über "Letzte Streams importieren"). Nur öffentliche Seiten, kein Login. Ein Download nach dem anderen; wartet, während du spielst, bei getakteter Verbindung und bei vollem Speicher; holt Verpasstes nach, wenn der PC aus war.
- "Dein Stream ist vorbei, 6 Clips sind fertig" im Tray und auf Telegram. Auto-Veröffentlichung standardmäßig aus; Kanäle anderer sind markiert, nur mit Erlaubnis posten.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Connecte ta chaîne Kick, Twitch ou YouTube une fois, et SharkyClips fait des clips de chaque nouveau live tout seul.

- **Connecte ta chaîne** Kick, Twitch ou YouTube dans Réglages > Chaînes (ou "Connecter ma chaîne" sur l'accueil) : à la fin d'un live, SharkyClips télécharge la VOD et fait les clips tout seul. Pas besoin d'OBS.
- Seulement les nouveaux lives (les anciens via "Importer les derniers lives"). Pages publiques uniquement, sans connexion. Un téléchargement à la fois ; attend pendant que tu joues, sur connexion limitée et quand le disque est plein ; rattrape ce qui a été manqué si le PC était éteint.
- "Ton live est terminé, 6 clips sont prêts" dans la barre des tâches et sur Telegram. Publication auto désactivée par défaut ; chaînes des autres marquées, avec l'autorisation du streamer.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Kösd össze egyszer a Kick, Twitch vagy YouTube csatornádat, és a SharkyClips minden új adásból magától klipeket készít.

- **Kösd össze a csatornádat** (Kick, Twitch vagy YouTube) a Beállítások > Csatornák alatt vagy a kezdőlapon: ha véget ér egy adás, a SharkyClips letölti a VOD-ot, és magától elkészíti a klipeket. Nem kell OBS-felvétel.
- Csak új adások (a régiek az "Utolsó adások importálása" gombbal). Csak nyilvános oldalak, bejelentkezés nélkül. Egyszerre egy letöltés; vár, amíg játszol, forgalomkorlátos kapcsolaton és ha kevés a hely; pótolja, ha a gép ki volt kapcsolva.
- "Véget ért az adásod, 6 klip kész" a tálcán és a Telegramon. Az automatikus közzététel alapból ki van kapcsolva; mások csatornái jelölve, csak engedéllyel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Подключите канал Kick, Twitch или YouTube один раз — SharkyClips сам сделает клипы из каждого нового стрима.

- **Подключите свой канал** Kick, Twitch или YouTube в Настройки > Каналы (или «Подключить мой канал» на главной): когда стрим заканчивается, SharkyClips скачивает запись и сам делает клипы. Запись в OBS не нужна.
- Только новые стримы (старые — кнопкой «Импортировать последние стримы»). Только публичные страницы, без входа. Одна загрузка за раз; ждёт, пока вы играете, при лимитном подключении и нехватке места; догоняет пропущенное, если ПК был выключен.
- «Стрим закончился, готово 6 клипов» в трее и в Telegram. Автопубликация по умолчанию выключена; чужие каналы помечены, публикуйте только с разрешения стримера.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
اربط قناتك على Kick أو Twitch أو YouTube مرة واحدة، وسيصنع SharkyClips مقاطع من كل بث جديد بنفسه.

- **اربط قناتك** على Kick أو Twitch أو YouTube من الإعدادات > القنوات (أو "اربط قناتي" في الصفحة الرئيسية): عند انتهاء البث ينزّل SharkyClips التسجيل ويصنع المقاطع بنفسه. لا حاجة لتسجيل OBS.
- البثوث الجديدة فقط (القديمة عبر "استيراد آخر البثوث"). صفحات عامة فقط بلا تسجيل دخول. تنزيل واحد في كل مرة؛ ينتظر أثناء لعبك ومع الاتصال المحدود وعند امتلاء القرص؛ يلحق بما فاته إذا كان الجهاز مطفأً.
- "انتهى بثك، 6 مقاطع جاهزة" في شريط النظام وعلى Telegram. النشر التلقائي مُعطّل افتراضيًا؛ قنوات الآخرين مُعلَّمة، وانشر فقط بإذن صاحب البث.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
只需连接一次 Kick、Twitch 或 YouTube 频道，SharkyClips 会自动为每场新直播制作剪辑。

- **连接你的频道**（Kick、Twitch 或 YouTube）：在 设置 > 频道（或首页的"连接我的频道"）。直播结束后，SharkyClips 会下载回放并自动剪辑，无需 OBS 录制。
- 只处理新直播（旧直播可用"导入最近的直播"）。只访问公开页面，无需登录。一次只下载一个；你玩游戏时、按流量计费时和磁盘不足时会等待；电脑关机后会补上错过的直播。
- 托盘和 Telegram 会提示"直播结束了，6 个剪辑已就绪"。自动发布默认关闭；他人频道会标明，发布前请征得主播许可。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
Kick・Twitch・YouTube のチャンネルを一度つなぐだけで、新しい配信ごとに SharkyClips が自動でクリップを作ります。

- **チャンネルをつなぐ**（Kick・Twitch・YouTube）：設定 > チャンネル（またはホームの「自分のチャンネルをつなぐ」）。配信が終わると SharkyClips がアーカイブをダウンロードし、自動でクリップを作ります。OBS 録画は不要です。
- 対象はこれからの配信だけ（過去の配信は「直近の配信を取り込む」で）。公開ページのみ、ログイン不要。ダウンロードは 1 件ずつ。ゲーム中・従量制課金接続・空き容量不足のときは待ち、PC がオフだった間の配信も後から処理します。
- 「配信が終わりました。クリップが 6 本できています」をトレイと Telegram でお知らせ。自動投稿は初期設定でオフ。他人のチャンネルは明示され、投稿には配信者の許可が必要です。

</details>

## [1.2.56] - 2026-11-20
SharkyClips now has a real Windows installer: double-click, Next, done. It downloads the AI parts your PC needs on the first start.

### New
- **Install SharkyClips like any app:** download the SharkyClips installer, double-click, Next, done.
  No Python, no console windows, no admin rights. It brings everything it needs, adds a Start
  menu entry (and a desktop shortcut if you want) and shows up in Apps & features.
- **First start: the AI parts for your PC.** A new "Downloads" step picks what your PC needs (the
  speech-to-text model, the GPU libraries on an NVIDIA PC, the local AI for titles; the Light setup on
  slower PCs), shows the size, then downloads it with a progress bar and the time left. Stopped
  downloads continue where they stopped, every file is checked, and afterwards it all works offline.
  You find the same list later in **Settings > Downloads**.
- **Updates for the installed app** come only from the official GitHub release: the new installer is
  checked and installed in the background as soon as no job is running, then SharkyClips
  opens again by itself. It never goes back to an older version.
- **If SharkyClips can't start,** a clear error window shows what happened, with "Copy diagnostic
  info" for a bug report (no passwords or keys in it).
- **Uninstalling** removes the app and asks before deleting your projects, settings or AI models
  (the default keeps them).
- **Used the old install script before?** Just run the installer: your settings are used and your
  projects stay where they are. Nothing is moved or deleted.

<!-- lang:tr -->
**Türkçe**

SharkyClips'in artık gerçek bir Windows kurulum dosyası var: çift tıkla, İleri, bitti. İlk açılışta bilgisayarının ihtiyaç duyduğu yapay zekâ parçalarını indirir.

### Yeni
- **SharkyClips'i her uygulama gibi kurun:** `SharkyClips-Setup.exe`'yi indirin, çift tıklayın,
  İleri, bitti. Python yok, konsol penceresi yok, yönetici izni yok. Kendi Python'unu ve FFmpeg'ini
  getirir, Başlat menüsüne (isterseniz masaüstüne) kısayol ekler ve Uygulamalar listesinde görünür.
- **İlk açılış: bilgisayarınıza uygun yapay zekâ parçaları.** Yeni "İndirmeler" adımı bilgisayarınızın
  neye ihtiyacı olduğunu seçer (konuşmayı yazıya çevirme modeli, NVIDIA kartta GPU kütüphaneleri,
  başlıklar için yerel yapay zekâ; yavaş bilgisayarlarda Hafif kurulum), boyutunu gösterir ve ilerleme
  çubuğu ile kalan süreyle indirir. Yarıda kalan indirme kaldığı yerden devam eder, her dosya kontrol
  edilir; sonrasında her şey internetsiz çalışır. Aynı liste **Ayarlar > İndirmeler**'de de var.
- **Kurulu uygulamanın güncellemeleri** yalnızca resmî GitHub sürümünden gelir: yeni kurulum dosyası
  kontrol edilir (SHA-256), çalışan bir iş kalmayınca arka planda kurulur ve SharkyClips kendiliğinden
  yeniden açılır. Asla eski bir sürüme dönmez.
- **SharkyClips açılamazsa** ne olduğunu gösteren net bir hata penceresi çıkar; hata kaydı için
  "Tanılama bilgisini kopyala" düğmesi vardır (şifre veya anahtar içermez).
- **Kaldırırken** uygulama silinir; projeleriniz, ayarlarınız ve yapay zekâ modelleri için önce sorulur
  (varsayılan: saklanır).
- **install.bat / git kurulumundan mı geliyorsunuz?** Kurulum dosyasını çalıştırmanız yeterli:
  ayarlarınız kullanılır, projeleriniz olduğu yerde kalır. Hiçbir şey taşınmaz veya silinmez.

<details><summary>Español</summary>

<!-- lang:es -->
SharkyClips ya tiene un instalador real para Windows: doble clic, Siguiente y listo. En el primer inicio descarga las partes de IA que necesita tu PC.

- **Instalador real para Windows:** descarga `SharkyClips-Setup.exe`, doble clic, Siguiente y listo. Sin Python, sin ventanas de consola, sin permisos de administrador.
- **Primer inicio:** un nuevo paso "Descargas" elige las partes de IA para tu PC y las descarga con barra de progreso y tiempo restante; las descargas continúan donde se quedaron y después todo funciona sin internet.
- **Actualizaciones** solo desde la versión oficial de GitHub, comprobadas (SHA-256) e instaladas cuando no hay tareas. Al desinstalar se pregunta antes de borrar tus proyectos (por defecto se conservan).

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O SharkyClips agora tem um instalador de verdade para Windows: clique duas vezes, Avançar e pronto. Na primeira vez ele baixa as partes de IA que seu PC precisa.

- **Instalador de verdade para Windows:** baixe `SharkyClips-Setup.exe`, clique duas vezes, Avançar e pronto. Sem Python, sem janelas de console, sem permissão de administrador.
- **Primeira abertura:** a nova etapa "Downloads" escolhe as partes de IA para o seu PC e baixa com barra de progresso e tempo restante; downloads interrompidos continuam de onde pararam e depois tudo funciona offline.
- **Atualizações** só da versão oficial do GitHub, verificadas (SHA-256) e instaladas quando nenhuma tarefa está rodando. Ao desinstalar, ele pergunta antes de apagar seus projetos (o padrão é manter).

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
SharkyClips hat jetzt einen echten Windows-Installer: Doppelklick, Weiter, fertig. Beim ersten Start lädt er die KI-Teile, die dein PC braucht.

- **Echtes Windows-Setup:** `SharkyClips-Setup.exe` herunterladen, doppelklicken, Weiter, fertig. Kein Python, keine Konsolenfenster, keine Adminrechte.
- **Erster Start:** Der neue Schritt „Downloads“ wählt die KI-Teile für deinen PC und lädt sie mit Fortschrittsbalken und Restzeit; abgebrochene Downloads machen weiter, danach läuft alles offline.
- **Updates** nur vom offiziellen GitHub-Release, geprüft (SHA-256) und installiert, wenn kein Auftrag läuft. Beim Deinstallieren wird vor dem Löschen deiner Projekte gefragt (Standard: behalten).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
SharkyClips a maintenant un vrai installateur Windows : double-clic, Suivant, terminé. Au premier lancement, il télécharge les parties d'IA dont ton PC a besoin.

- **Un vrai installateur Windows :** télécharge `SharkyClips-Setup.exe`, double-clic, Suivant, c'est fini. Pas de Python, pas de fenêtre de console, pas de droits administrateur.
- **Premier lancement :** la nouvelle étape « Téléchargements » choisit les éléments d'IA pour ton PC et les télécharge avec une barre de progression et le temps restant ; un téléchargement interrompu reprend, ensuite tout fonctionne hors ligne.
- **Mises à jour** uniquement depuis la version officielle GitHub, vérifiées (SHA-256) et installées quand aucune tâche ne tourne. La désinstallation demande avant de supprimer tes projets (par défaut ils sont gardés).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A SharkyClipsnek most már igazi Windows-telepítője van: dupla kattintás, Tovább, kész. Az első indításkor letölti a géped számára szükséges MI-részeket.

- **Valódi Windows-telepítő:** töltsd le a `SharkyClips-Setup.exe` fájlt, dupla kattintás, Tovább, kész. Nem kell Python, nincs konzolablak, nem kell rendszergazdai jog.
- **Első indítás:** az új „Letöltések” lépés kiválasztja a gépedhez illő MI-részeket, és folyamatjelzővel, hátralévő idővel tölti le őket; a megszakadt letöltés folytatódik, utána minden internet nélkül működik.
- **Frissítések** csak a hivatalos GitHub-kiadásból, ellenőrizve (SHA-256), és akkor települnek, amikor nem fut feladat. Eltávolításkor a projektek törlése előtt rákérdez (alapból megmaradnak).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
У SharkyClips появился настоящий установщик для Windows: двойной щелчок, «Далее», готово. При первом запуске он скачает нужные вашему ПК части ИИ.

- **Настоящий установщик для Windows:** скачайте `SharkyClips-Setup.exe`, дважды щёлкните, «Далее» — готово. Без Python, без окон консоли, без прав администратора.
- **Первый запуск:** новый шаг «Загрузки» выбирает части ИИ для вашего ПК и скачивает их с индикатором и оставшимся временем; прерванная загрузка продолжается, потом всё работает без интернета.
- **Обновления** только из официального релиза на GitHub, с проверкой (SHA-256), ставятся, когда нет задач. При удалении спрашивает, прежде чем удалить проекты (по умолчанию они сохраняются).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح لـ SharkyClips مثبّت حقيقي لنظام Windows: انقر مرتين، التالي، وانتهى. وفي أول تشغيل ينزّل أجزاء الذكاء الاصطناعي التي يحتاجها جهازك.

- **مثبّت حقيقي لويندوز:** نزّل `SharkyClips-Setup.exe` وانقر نقرًا مزدوجًا ثم التالي وانتهى. دون Python ودون نوافذ أوامر ودون صلاحيات مسؤول.
- **أول تشغيل:** خطوة "التنزيلات" الجديدة تختار أجزاء الذكاء الاصطناعي المناسبة لجهازك وتنزّلها مع شريط تقدم والوقت المتبقي؛ التنزيل المتوقف يكمل، وبعدها يعمل كل شيء دون إنترنت.
- **التحديثات** من إصدار GitHub الرسمي فقط، مع التحقق (SHA-256)، وتُثبَّت عندما لا تعمل أي مهمة. عند الإزالة يسأل قبل حذف مشاريعك (الافتراضي الإبقاء عليها).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
SharkyClips 现在有了真正的 Windows 安装程序：双击、下一步、完成。首次启动时会下载你的电脑需要的 AI 组件。

- **真正的 Windows 安装程序：**下载 `SharkyClips-Setup.exe`，双击，下一步，完成。无需 Python，没有控制台窗口，也不需要管理员权限。
- **首次启动：**新的“下载”步骤会为你的电脑挑选 AI 组件，并显示进度条和剩余时间进行下载；中断的下载会继续，之后一切都可以离线使用。
- **更新**只来自官方 GitHub 发布，经过校验（SHA-256），在没有任务运行时安装。卸载时会先询问是否删除你的项目（默认保留）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
SharkyClips に本格的な Windows インストーラーが登場。ダブルクリックして「次へ」で完了。初回起動時に PC に必要な AI 部品をダウンロードします。

- **本格的な Windows インストーラー：**`SharkyClips-Setup.exe` をダウンロードしてダブルクリック、次へで完了。Python もコンソール画面も管理者権限も不要です。
- **初回起動：**新しい「ダウンロード」ステップが PC に合った AI パーツを選び、進捗バーと残り時間を表示してダウンロードします。中断しても続きから再開し、その後はすべてオフラインで動きます。
- **アップデート**は公式 GitHub リリースからのみ。SHA-256 で確認し、ジョブが動いていないときにインストールします。アンインストール時はプロジェクトを削除する前に確認します（既定は保持）。

</details>

## [1.2.55] - 2026-11-19
Marvel Rivals: ACE and KO streaks now become clip moments, and short banner words with "!" are read correctly in every game.

### Improved
- **Marvel Rivals: ACE and KO streaks are found.** Tested on real gameplay videos: SharkyClips now
  reads the "ACE!" banner and "5 / 10 / 15 PLAYER KO STREAK!" and puts those moments in your clips.
- **Short banner words with "!" are read correctly** in every game ("ACE!" was missed before).
- EA Sports FC and ARC Raiders stay **beta**: the test videos had no goal banner or extraction screen.
  A video with one helps (the guide on GitHub shows how to send it).

<!-- lang:tr -->
**Türkçe**

Marvel Rivals: ACE ve KO serileri artık klip anı oluyor; "!" içeren kısa ekran yazıları her oyunda doğru okunuyor.

### İyileştirmeler
- **Marvel Rivals: ACE ve KO serileri bulunuyor.** Gerçek oyun videolarında denendi: SharkyClips
  artık "ACE!" yazısını ve "5 / 10 / 15 PLAYER KO STREAK!" serilerini okuyor ve bu anları kliplerine
  koyuyor.
- **Sonunda "!" olan kısa ekran yazıları** artık her oyunda doğru okunuyor (önce "ACE!" kaçıyordu).
- EA Sports FC ve ARC Raiders **beta** olarak kalıyor: deneme videolarında gol yazısı ya da tahliye
  ekranı yoktu. Böyle bir klip çok yardımcı olur (bkz. docs/ADDING_A_GAME.md).

<details><summary>Español</summary>

<!-- lang:es -->
Marvel Rivals: los ACE y las rachas de KO ya son momentos de clip, y las palabras cortas con "!" se leen bien en todos los juegos.

- **Marvel Rivals: ahora se detectan ACE y las rachas de KO** ("ACE!", "5 / 10 / 15 PLAYER KO STREAK!"), probado con videos reales.
- **Las palabras cortas con "!" en pantalla ahora se leen bien en todos los juegos** (antes se perdía "ACE!").

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Marvel Rivals: ACE e sequências de KO agora viram momentos de clipe, e palavras curtas com "!" são lidas certo em todos os jogos.

- **Marvel Rivals: ACE e sequências de KO agora são detectados** ("ACE!", "5 / 10 / 15 PLAYER KO STREAK!"), testado em vídeos reais.
- **Palavras curtas com "!" na tela agora são lidas em todos os jogos** (antes "ACE!" passava despercebido).

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Marvel Rivals: ACE und KO-Serien werden jetzt zu Clip-Momenten, und kurze Banner-Wörter mit „!“ werden in jedem Spiel richtig gelesen.

- **Marvel Rivals: ACE und KO-Serien werden erkannt** („ACE!“, „5 / 10 / 15 PLAYER KO STREAK!“), an echten Videos getestet.
- **Kurze Banner-Wörter mit „!“ werden jetzt in allen Spielen erkannt** (vorher wurde „ACE!“ übersehen).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Marvel Rivals : les ACE et les séries de KO deviennent des moments de clip, et les mots courts avec « ! » sont bien lus dans tous les jeux.

- **Marvel Rivals : les ACE et les séries de KO sont détectés** (« ACE! », « 5 / 10 / 15 PLAYER KO STREAK! »), testé sur de vraies vidéos.
- **Les mots courts avec « ! » à l'écran sont maintenant lus dans tous les jeux** (avant, « ACE! » était raté).

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Marvel Rivals: az ACE és a KO-sorozatok mostantól klip-pillanatok, és a rövid, „!”-es feliratokat minden játékban jól olvassa.

- **Marvel Rivals: az ACE és a KO-sorozatok felismerése** („ACE!”, „5 / 10 / 15 PLAYER KO STREAK!”), valódi videókon tesztelve.
- **A rövid, „!”-lel végződő képernyőszavakat most minden játékban felismeri** (korábban az „ACE!” kimaradt).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Marvel Rivals: ACE и серии KO теперь становятся моментами для клипов, а короткие надписи с «!» читаются верно во всех играх.

- **Marvel Rivals: теперь находятся ACE и серии KO** («ACE!», «5 / 10 / 15 PLAYER KO STREAK!»), проверено на настоящих видео.
- **Короткие слова с «!» на экране теперь распознаются во всех играх** (раньше «ACE!» пропускалось).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
Marvel Rivals: أصبحت لحظات ACE وسلاسل KO مقاطع، وتُقرأ الكلمات القصيرة مع "!" بشكل صحيح في كل الألعاب.

- **Marvel Rivals: يتم الآن اكتشاف ACE وسلاسل KO** ("ACE!" و"5 / 10 / 15 PLAYER KO STREAK!")، تم الاختبار على فيديوهات حقيقية.
- **الكلمات القصيرة التي تنتهي بـ "!" على الشاشة تُقرأ الآن في كل الألعاب** (كانت "ACE!" تُفوَّت من قبل).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
Marvel Rivals：ACE 和 KO 连杀现在会成为剪辑时刻，所有游戏中带“!”的短横幅文字都能正确识别。

- **Marvel Rivals：现在能识别 ACE 和 KO 连杀**（“ACE!”、“5 / 10 / 15 PLAYER KO STREAK!”），已在真实视频上测试。
- **所有游戏中带“!”的屏幕短词现在都能正确识别**（以前会漏掉“ACE!”）。EA Sports FC 和 ARC Raiders 仍为 beta：测试视频中没有进球或撤离画面。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
Marvel Rivals：ACE と KO ストリークがクリップの見どころになり、「!」付きの短いバナー文字もすべてのゲームで正しく読めます。

- **Marvel Rivals：ACE と KO ストリークを検出**（「ACE!」「5 / 10 / 15 PLAYER KO STREAK!」）。実際の動画でテスト済み。
- **「!」付きの短い画面の文字を全ゲームで正しく読み取ります**（以前は「ACE!」を見逃していました）。EA Sports FC と ARC Raiders はベータのままです。

</details>

## [1.2.54] - 2026-11-19
The new game profiles were tested on real gameplay, so SharkyClips finds the right moments in more games and makes fewer mistakes.

### Improved
- **New game profiles were tested on real gameplay videos.** SharkyClips now reliably reads ACE,
  CLUTCH, SPIKE PLANTED and round wins in VALORANT, Victory Royale and eliminations in Fortnite,
  kills and knocks in PUBG, WASTED in GTA V, deaths in Minecraft hardcore, the kill leader in Apex,
  double kills in Warzone, eliminations and VICTORY in Overwatch, RAMPAGE in Dota 2 and round
  results in CS2. Hover over the **beta** badge to see which moments were checked.
- **Fewer wrong moments.** In Overwatch, "You were eliminated" no longer counts as your kill. A half-read
  word on screen no longer turns into a different event (GTA "WASTED" was sometimes read as
  "BUSTED"). The same PUBG kill message is counted once.
- **Better French and Spanish.** French now always uses "tu", like other gaming apps. Spanish uses
  "PC", which people in Latin America and in Spain both say.

<!-- lang:tr -->
**Türkçe**

Yeni oyun profilleri gerçek oyun videolarında denendi; SharkyClips daha çok oyunda doğru anları buluyor ve daha az hata yapıyor.

### İyileştirmeler
- **Yeni oyun profilleri gerçek oyun videolarında test edildi.** SharkyClips artık VALORANT'ta ACE,
  CLUTCH, SPIKE PLANTED ve raund galibiyetlerini, Fortnite'ta Victory Royale ve elemeleri, PUBG'de
  kill ve yere sermeleri, GTA V'te WASTED'i, Minecraft hardcore'da ölümleri, Apex'te kill liderini,
  Warzone'da double kill'i, Overwatch'ta elemeleri ve VICTORY'yi, Dota 2'de RAMPAGE'ı ve CS2'de raund
  sonuçlarını güvenilir şekilde okuyor. Hangi anların denendiğini görmek için **beta** rozetinin
  üzerine gel.
- **Daha az yanlış an.** Overwatch'ta "You were eliminated" artık senin kill'in sayılmıyor. Ekranda
  yarım okunan bir kelime artık başka bir olaya dönüşmüyor (GTA'daki "WASTED" bazen "BUSTED"
  okunuyordu). Aynı PUBG kill mesajı bir kez sayılıyor.
- **Daha iyi Fransızca ve İspanyolca.** Fransızca artık oyun uygulamaları gibi hep "tu" kullanıyor.
  İspanyolca, hem Latin Amerika'da hem İspanya'da söylenen "PC" kelimesini kullanıyor.

<details><summary>Español</summary>

<!-- lang:es -->
Los nuevos perfiles de juego se probaron con partidas reales: SharkyClips encuentra los momentos correctos en más juegos y se equivoca menos.

- **Los nuevos perfiles de juego se probaron con videos reales:** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 y CS2. Pasa el ratón sobre la etiqueta **beta** para ver qué momentos se comprobaron.
- **Menos momentos falsos:** en Overwatch, "You were eliminated" ya no cuenta como tu kill, y una palabra leída a medias ya no se convierte en otro evento.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Os novos perfis de jogo foram testados em partidas reais: o SharkyClips acha os momentos certos em mais jogos e erra menos.

- **Os novos perfis de jogo foram testados em vídeos reais:** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 e CS2. Passe o mouse sobre o selo **beta** para ver quais momentos foram verificados.
- **Menos momentos errados:** no Overwatch, "You were eliminated" não conta mais como seu abate, e uma palavra lida pela metade não vira outro evento.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die neuen Spielprofile wurden mit echtem Gameplay getestet: SharkyClips findet in mehr Spielen die richtigen Momente und irrt sich seltener.

- **Die neuen Spielprofile wurden an echten Videos getestet:** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 und CS2. Fahre über das **Beta**-Abzeichen, um zu sehen, welche Momente geprüft sind.
- **Weniger falsche Momente:** In Overwatch zählt „You were eliminated“ nicht mehr als dein Kill, und ein halb gelesenes Wort wird kein anderes Ereignis mehr.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Les nouveaux profils de jeu ont été testés sur de vraies parties : SharkyClips trouve les bons moments dans plus de jeux et se trompe moins.

- **Les nouveaux profils de jeu ont été testés sur de vraies vidéos :** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 et CS2. Survole le badge **bêta** pour voir quels moments sont vérifiés.
- **Moins de faux moments :** dans Overwatch, « You were eliminated » ne compte plus comme ton kill. L'appli te tutoie maintenant partout.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az új játékprofilokat valódi játékmeneten teszteltük: a SharkyClips több játékban találja meg a jó pillanatokat, és kevesebbet téved.

- **Az új játékprofilokat valódi videókon teszteltük:** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 és CS2. Vidd az egeret a **béta** jelzésre, és látod, mely pillanatok ellenőrzöttek.
- **Kevesebb hibás pillanat:** az Overwatchban a „You were eliminated” már nem számít a te ölésednek.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Новые профили игр проверены на реальных записях: SharkyClips находит нужные моменты в большем числе игр и реже ошибается.

- **Новые профили игр проверены на настоящих видео:** VALORANT, Fortnite, PUBG, GTA V, Minecraft, Apex, Warzone, Overwatch, Dota 2 и CS2. Наведите на значок **бета**, чтобы увидеть, какие моменты проверены.
- **Меньше ложных моментов:** в Overwatch «You were eliminated» больше не считается вашим убийством.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
اختُبرت ملفات الألعاب الجديدة على لعب حقيقي، فأصبح SharkyClips يجد اللحظات الصحيحة في ألعاب أكثر ويخطئ أقل.

- **تم اختبار ملفات الألعاب الجديدة على فيديوهات حقيقية:** VALORANT وFortnite وPUBG وGTA V وMinecraft وApex وWarzone وOverwatch وDota 2 وCS2. مرّر المؤشر فوق شارة **تجريبي** لترى اللحظات التي تم التحقق منها.
- **لحظات خاطئة أقل:** في Overwatch لم تعد عبارة "You were eliminated" تُحسب كقتل لك.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
新的游戏配置已在真实游戏视频上测试：SharkyClips 能在更多游戏中找到正确时刻，错误也更少。

- **新的游戏配置已在真实视频上测试：** VALORANT、Fortnite、PUBG、GTA V、Minecraft、Apex、Warzone、Overwatch、Dota 2 和 CS2。把鼠标移到 **beta** 标记上即可查看已验证的时刻。
- **误判更少：** 在 Overwatch 中，“You were eliminated” 不再算作你的击杀。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
新しいゲームプロファイルを実際のプレイ動画でテストしました。より多くのゲームで正しい場面を見つけ、ミスも減りました。

- **新しいゲームプロファイルを実際の動画でテストしました：** VALORANT、Fortnite、PUBG、GTA V、Minecraft、Apex、Warzone、Overwatch、Dota 2、CS2。**ベータ**の印にマウスを乗せると、確認済みの場面が表示されます。
- **誤検出が減りました：** Overwatch の「You were eliminated」は自分のキルとして数えなくなりました。

</details>

## [1.2.53] - 2026-11-18
Much faster on slow PCs, 11 app languages with English as the default, one setting for the language of your titles, and 15 games.

### New
- **Typing in the clip's edit window works again.** Backspace and Delete in the title field
  did nothing, and the window jumped back to the top while you scrolled. Both are fixed, in
  every browser (Chrome, Edge, Opera GX, Firefox). Keyboard shortcuts never run while you type.
- **One "Content language".** Settings > Content language sets the language of AI titles,
  descriptions, hashtags, captions and the YouTube language fields. It is separate from the app
  language. Changing it really changes the next titles (they no longer stay Turkish).
- **Much faster on slow PCs.** New in Settings > Performance: **Processing device** (Auto / CPU
  only / GPU) and a **Light** speed preset. Auto never uses a weak built-in graphics chip for the
  AI. On a slow PC (little RAM, few CPU cores) SharkyClips picks Light by itself: smaller AI
  models, no slow voice separation, fewer screen checks, one job at a time. Before a big job you
  see about how long it will take on your PC.
- **11 languages.** New: Español (Latin America and Spain), Português (Brasil), Français and
  日本語. English is the default for new users. Pick your language with the flag button on the
  home screen or in the top bar. Swear bleeping knows all 11 languages.
- **15 games.** SharkyClips now reads the screen of CS2, VALORANT, Warzone / MW4, Fortnite, Apex,
  PUBG, GTA V / Online / RP, GTA 6, Minecraft, League of Legends, Dota 2, Overwatch, Marvel
  Rivals, EA Sports FC 27 and ARC Raiders, with game hashtags per language. New games show a
  **beta** badge until they are checked on real videos. Pick the game with one tap in Easy mode.
- **Better clip picks.** The AI reads more of the story before and after a moment. A loud noise
  with no reason counts less, and menus, loading screens and AFK parts are pushed down.

<!-- lang:tr -->
**Türkçe**

Yavaş bilgisayarlarda çok daha hızlı, varsayılanı İngilizce olan 11 uygulama dili, başlıkların dili için tek ayar ve 15 oyun.

### Yeni
- **Klip düzenleme penceresinde yazmak yine çalışıyor.** Başlık kutusunda Backspace ve Delete
  hiçbir şey yapmıyordu, kaydırırken pencere en üste zıplıyordu. İkisi de düzeldi, her
  tarayıcıda (Chrome, Edge, Opera GX, Firefox). Yazarken klavye kısayolları artık hiç çalışmaz.
- **Tek bir "İçerik dili".** Ayarlar > İçerik dili; yapay zekâ başlıklarının, açıklamaların,
  hashtag'lerin, altyazıların ve YouTube dil alanlarının dilini belirler. Uygulama dilinden
  ayrıdır. Değiştirince sonraki başlıklar gerçekten değişir (artık Türkçe kalmıyor).
- **Yavaş bilgisayarlarda çok daha hızlı.** Ayarlar > Performans'ta yeni: **İşlem cihazı**
  (Otomatik / Sadece CPU / GPU) ve **Hafif** hız ayarı. Otomatik, yapay zekâ için zayıf dahili
  grafik çipini asla kullanmaz. Yavaş bir bilgisayarda (az RAM, az çekirdek) SharkyClips Hafif'i
  kendisi seçer: daha küçük yapay zekâ modelleri, yavaş ses ayırma yok, daha az ekran kontrolü,
  aynı anda tek iş. Büyük bir işten önce bilgisayarında yaklaşık ne kadar süreceğini görürsün.
- **11 dil.** Yeni: Español (Latin Amerika ve İspanya), Português (Brasil), Français ve 日本語.
  Yeni kullanıcılar için varsayılan dil İngilizce. Dilini ana ekrandaki ya da üst çubuktaki
  bayraklı düğmeden seç. Küfür bipleme 11 dilin hepsini biliyor.
- **15 oyun.** SharkyClips artık CS2, VALORANT, Warzone / MW4, Fortnite, Apex, PUBG, GTA V /
  Online / RP, GTA 6, Minecraft, League of Legends, Dota 2, Overwatch, Marvel Rivals, EA Sports
  FC 27 ve ARC Raiders ekranını okuyor; her dil için oyun hashtag'leriyle. Yeni oyunlar gerçek
  videolarda denenene kadar **beta** rozetiyle görünür. Kolay modda oyunu tek dokunuşla seç.
- **Daha iyi klip seçimi.** Yapay zekâ bir anın öncesini ve sonrasını daha çok okuyor. Sebepsiz
  bir gürültü daha az sayılıyor; menüler, yükleme ekranları ve AFK kısımları geri itiliyor.

<details><summary>Español</summary>

<!-- lang:es -->
Mucho más rápido en PCs lentos, 11 idiomas con inglés por defecto, un solo ajuste para el idioma de tus títulos y 15 juegos.

- **Ya puedes escribir en la ventana de edición del clip:** Retroceso y Suprimir funcionan y la ventana ya no salta arriba al desplazarte, en todos los navegadores.
- **Un solo "Idioma del contenido"** para títulos, descripciones, hashtags, subtítulos y los campos de idioma de YouTube (estilo Latinoamérica o España).
- **Mucho más rápido en PCs lentos:** Ajustes > Rendimiento > Dispositivo (Auto / Solo CPU / GPU) y el modo **Ligero**. Ves cuánto tardará antes de empezar.
- **11 idiomas** (nuevos: español, portugués de Brasil, francés y japonés) y **15 juegos**, los nuevos con la etiqueta **beta**.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Muito mais rápido em PCs lentos, 11 idiomas com inglês como padrão, um só ajuste para o idioma dos títulos e 15 jogos.

- **Dá para digitar de novo na janela de edição do clipe:** Backspace e Delete funcionam e a janela não pula mais para o topo, em todos os navegadores.
- **Um só "Idioma do conteúdo"** para títulos, descrições, hashtags, legendas e os campos de idioma do YouTube.
- **Muito mais rápido em PCs fracos:** Configurações > Desempenho > Dispositivo (Auto / Só CPU / GPU) e o modo **Leve**. Você vê quanto tempo vai levar antes de começar.
- **11 idiomas** (novos: espanhol, português do Brasil, francês e japonês) e **15 jogos**, os novos com o selo **beta**.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Viel schneller auf langsamen PCs, 11 Sprachen mit Englisch als Standard, eine Einstellung für die Sprache deiner Titel und 15 Spiele.

- **Tippen im Bearbeitungsfenster geht wieder:** Rücktaste und Entf funktionieren, und das Fenster springt beim Scrollen nicht mehr nach oben – in allen Browsern.
- **Eine „Inhaltssprache“** für KI-Titel, Beschreibungen, Hashtags, Untertitel und die YouTube-Sprachfelder, getrennt von der App-Sprache.
- **Viel schneller auf langsamen PCs:** Einstellungen > Leistung > Rechengerät (Auto / Nur CPU / GPU) und die Voreinstellung **Leicht**. Vor großen Aufgaben siehst du die ungefähre Dauer.
- **11 Sprachen** (neu: Spanisch, Portugiesisch (Brasilien), Französisch, Japanisch) und **15 Spiele**, neue mit **Beta**-Hinweis.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Bien plus rapide sur les PC lents, 11 langues avec l'anglais par défaut, un seul réglage pour la langue de tes titres et 15 jeux.

- **On peut de nouveau écrire dans la fenêtre d'édition du clip :** Retour arrière et Suppr marchent, et la fenêtre ne remonte plus quand tu fais défiler, dans tous les navigateurs.
- **Une seule « Langue du contenu »** pour les titres, descriptions, hashtags, sous-titres et les champs de langue YouTube.
- **Bien plus rapide sur les PC lents :** Paramètres > Performances > Appareil (Auto / CPU seul / GPU) et le mode **Léger**. Tu vois la durée prévue avant de commencer.
- **11 langues** (nouvelles : espagnol, portugais du Brésil, français, japonais) et **15 jeux**, les nouveaux avec un badge **bêta**.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Sokkal gyorsabb lassú gépeken, 11 nyelv (alapból angol), egy beállítás a címek nyelvéhez és 15 játék.

- **Újra lehet gépelni a klip szerkesztőablakában:** a Backspace és a Delete működik, és görgetéskor az ablak már nem ugrik a tetejére, minden böngészőben.
- **Egyetlen „Tartalom nyelve”** az MI-címekhez, leírásokhoz, hashtagekhez, feliratokhoz és a YouTube nyelvi mezőihez.
- **Sokkal gyorsabb lassú gépeken:** Beállítások > Teljesítmény > Feldolgozó eszköz (Auto / Csak CPU / GPU) és a **Könnyű** mód. Nagy feladat előtt látod, kb. mennyi ideig tart.
- **11 nyelv** (új: spanyol, brazil portugál, francia, japán) és **15 játék**, az újak **béta** jelzéssel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Гораздо быстрее на слабых ПК, 11 языков (по умолчанию английский), одна настройка языка заголовков и 15 игр.

- **В окне редактирования клипа снова можно печатать:** Backspace и Delete работают, а окно больше не прыгает вверх при прокрутке — во всех браузерах.
- **Один «Язык контента»** для заголовков ИИ, описаний, хештегов, субтитров и языковых полей YouTube, отдельно от языка приложения.
- **Намного быстрее на слабых ПК:** Настройки > Производительность > Устройство (Авто / Только CPU / GPU) и режим **Лёгкий**. Перед большой задачей видно, сколько она займёт.
- **11 языков** (новые: испанский, португальский (Бразилия), французский, японский) и **15 игр**, новые с отметкой **бета**.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أسرع بكثير على الأجهزة البطيئة، و11 لغة مع الإنجليزية افتراضيًا، وإعداد واحد للغة العناوين، و15 لعبة.

- **عادت الكتابة في نافذة تعديل المقطع:** يعمل مفتاحا Backspace وDelete، ولم تعد النافذة تقفز إلى الأعلى أثناء التمرير، في كل المتصفحات.
- **«لغة المحتوى» واحدة** للعناوين والأوصاف والوسوم والترجمة وحقول اللغة في YouTube، منفصلة عن لغة التطبيق.
- **أسرع بكثير على الأجهزة البطيئة:** الإعدادات > الأداء > جهاز المعالجة (تلقائي / المعالج فقط / GPU) ووضع **خفيف**. ترى المدة التقريبية قبل البدء.
- **11 لغة** (الجديدة: الإسبانية والبرتغالية البرازيلية والفرنسية واليابانية) و**15 لعبة**، الجديدة منها بعلامة **تجريبي**.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
在慢电脑上快得多，11 种界面语言（默认英语），标题语言只需一个设置，支持 15 款游戏。

- **剪辑编辑窗口又能正常输入了：** 退格键和删除键可用，滚动时窗口不再跳回顶部，所有浏览器都一样。
- **统一的“内容语言”**，用于 AI 标题、简介、话题标签、字幕和 YouTube 语言字段，与界面语言分开。
- **慢电脑上快很多：** 设置 > 性能 > 处理设备（自动 / 仅 CPU / GPU）和**轻量**模式。大任务开始前会显示大约要多久。
- **11 种语言**（新增西班牙语、巴西葡萄牙语、法语、日语）和 **15 款游戏**，新游戏带 **beta** 标记。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
遅い PC でも大幅に高速化、英語が既定の 11 言語、タイトルの言語はひとつの設定で、15 ゲームに対応。

- **クリップ編集画面でまた入力できます:** BackspaceとDeleteが効き、スクロールしても上に戻りません。どのブラウザでも同じです。
- **「コンテンツの言語」を一つに:** AIのタイトル、説明、ハッシュタグ、字幕、YouTubeの言語欄に使われます。
- **遅いPCでもずっと速く:** 設定 > パフォーマンス > 処理デバイス(自動 / CPUのみ / GPU)と**ライト**モード。大きな作業の前に目安の時間が出ます。
- **11言語**(新: スペイン語、ブラジルポルトガル語、フランス語、日本語)と**15のゲーム**。新しいゲームには**ベータ**の印が付きます。

</details>

## [1.2.52] - 2026-11-18
A security update: other websites can no longer control SharkyClips, devices on your network need a PIN, and your keys stay hidden.

### Improved
- **Other websites can't use SharkyClips any more.** Until now, a web page open in your browser
  could secretly send commands to SharkyClips on your computer (publish, delete, change settings,
  disconnect accounts). Now SharkyClips only obeys its own window: every action carries a secret
  key that only the SharkyClips page knows, requests from other sites and other address names are
  refused, and other sites can't show or read your clips.
- **YouTube: connect your own Google project.** SharkyClips no longer comes with a shared Google
  connection. Settings > YouTube > **Connect your own Google project** walks you through it in
  about 5 minutes (once): your uploads then run on your own free quota. If you already set up a
  Google client file, **Reload Google client** reads it again.
- **The YouTube quota is guarded.** Settings > YouTube shows today's use. New uploads stop a bit
  before the limit, and an upload that doesn't fit today waits and starts by itself after
  Google's daily reset.
- **Phone / other devices (network mode) need a PIN.** Without an access PIN no other device can
  use SharkyClips. Set one in Settings > Other devices.
- **Safer links and updates.** "Paste a link" only accepts public internet addresses (never your
  own computer or home network). Updates come only from the official SharkyClips page and only
  as finished releases; downloaded models are checked before use.
- **Your keys stay private.** Account sign-ins stay encrypted on your computer and are now also
  hidden in every log and error message.

<!-- lang:tr -->
**Türkçe**

Güvenlik güncellemesi: başka web siteleri artık SharkyClips'i kontrol edemiyor, ağındaki cihazlar PIN istiyor ve anahtarların gizli kalıyor.

### İyileştirmeler
- **Başka web siteleri artık SharkyClips'i kullanamaz.** Şimdiye kadar tarayıcında açık bir web
  sayfası bilgisayarındaki SharkyClips'e gizlice komut gönderebiliyordu (yayınla, sil, ayarları
  değiştir, hesap bağlantısını kes). Artık SharkyClips sadece kendi penceresini dinliyor: her
  işlem yalnızca SharkyClips sayfasının bildiği gizli bir anahtar taşıyor, başka sitelerden ve
  başka adres adlarından gelen istekler reddediliyor, başka siteler kliplerini gösteremiyor ya da
  okuyamıyor.
- **YouTube: kendi Google projeni bağla.** SharkyClips artık ortak bir Google bağlantısıyla
  gelmiyor. Ayarlar > YouTube > **Kendi Google projeni bağla** seni yaklaşık 5 dakikada (bir kez)
  adım adım götürür: yüklemelerin kendi ücretsiz kotanla çalışır. Zaten bir Google istemci
  dosyası kurduysan **Google istemcisini yeniden yükle** onu tekrar okur.
- **YouTube kotası korunuyor.** Ayarlar > YouTube bugünkü kullanımı gösterir. Yeni yüklemeler
  sınırdan biraz önce durur; bugüne sığmayan bir yükleme bekler ve Google'ın günlük
  sıfırlamasından sonra kendiliğinden başlar.
- **Telefon / diğer cihazlar (ağ modu) PIN ister.** Erişim PIN'i olmadan başka hiçbir cihaz
  SharkyClips'i kullanamaz. Ayarlar > Diğer cihazlar'dan bir PIN belirle.
- **Daha güvenli bağlantılar ve güncellemeler.** "Link yapıştır" sadece herkese açık internet
  adreslerini kabul eder (asla kendi bilgisayarını ya da ev ağını değil). Güncellemeler sadece
  resmi SharkyClips sayfasından ve sadece tamamlanmış sürümler olarak gelir; indirilen modeller
  kullanılmadan önce kontrol edilir.
- **Anahtarların gizli kalır.** Hesap girişleri bilgisayarında şifreli kalır ve artık her kayıt
  dosyasında ve hata mesajında da gizlenir.

<details><summary>Español</summary>

<!-- lang:es -->
Actualización de seguridad: otras webs ya no pueden controlar SharkyClips, los dispositivos de tu red necesitan un PIN y tus claves quedan ocultas.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Atualização de segurança: outros sites não conseguem mais controlar o SharkyClips, aparelhos da sua rede precisam de PIN e suas chaves ficam ocultas.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Sicherheitsupdate: Andere Websites können SharkyClips nicht mehr steuern, Geräte im Netzwerk brauchen eine PIN, und deine Schlüssel bleiben verborgen.

- **Sicherheitsupdate:** Andere Websites in deinem Browser können SharkyClips keine Befehle mehr schicken (Veröffentlichen, Löschen, Einstellungen). Jede Aktion trägt einen geheimen Schlüssel, den nur die SharkyClips-Seite kennt.
- **YouTube mit deinem eigenen Google-Projekt:** Einstellungen > YouTube > „Eigenes Google-Projekt verbinden“ führt dich in etwa 5 Minuten durch; „Google-Client neu laden“ liest eine Client-Datei erneut ein.
- **YouTube-Kontingent geschützt:** Uploads stoppen kurz vor dem Limit, was heute nicht passt, startet nach dem täglichen Reset von selbst.
- Andere Geräte brauchen eine PIN, eingefügte Links nur öffentliche Adressen, Updates nur offizielle Releases, und Anmeldedaten tauchen in keinem Log auf.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Mise à jour de sécurité : les autres sites ne peuvent plus contrôler SharkyClips, les appareils du réseau ont besoin d'un code PIN et tes clés restent cachées.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Biztonsági frissítés: más weboldalak már nem irányíthatják a SharkyClipset, a hálózati eszközöknek PIN kell, és a kulcsaid rejtve maradnak.

- **Biztonsági frissítés:** a böngésződben megnyitott más weboldalak már nem küldhetnek parancsot a SharkyClipsnek (közzététel, törlés, beállítások). Minden művelet egy titkos kulcsot visz, amelyet csak a SharkyClips oldala ismer.
- **YouTube a saját Google-projekteddel:** Beállítások > YouTube > „Saját Google-projekt csatlakoztatása” kb. 5 perc alatt végigvezet; a „Google-kliens újratöltése” újraolvassa a kliensfájlt.
- **Védett YouTube-kvóta:** a feltöltések a határ előtt megállnak, ami ma nem fér bele, a napi visszaállítás után magától indul.
- Más eszközökhöz PIN kell, a beillesztett linkek csak nyilvános címek lehetnek, frissítés csak hivatalos kiadásból, a belépési adatok semmilyen naplóban nem jelennek meg.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Обновление безопасности: другие сайты больше не могут управлять SharkyClips, устройствам в сети нужен PIN, а ваши ключи скрыты.

- **Обновление безопасности:** другие сайты в вашем браузере больше не могут отправлять SharkyClips команды (публикация, удаление, настройки). Каждое действие несёт секретный ключ, который знает только страница SharkyClips.
- **YouTube через ваш собственный проект Google:** Настройки > YouTube > «Подключить свой проект Google» проведёт вас по шагам примерно за 5 минут; «Перезагрузить клиент Google» заново читает файл клиента.
- **Квота YouTube под защитой:** загрузки останавливаются чуть раньше лимита, а то, что не помещается сегодня, начнётся само после ежедневного сброса.
- Другим устройствам нужен PIN-код, вставленные ссылки — только публичные адреса, обновления — только официальные релизы, данные входа не попадают ни в один журнал.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تحديث أمني: لم تعد المواقع الأخرى قادرة على التحكم في SharkyClips، وتحتاج أجهزة شبكتك إلى رمز PIN، وتبقى مفاتيحك مخفية.

- **تحديث أمني:** لم يعد بإمكان المواقع الأخرى المفتوحة في متصفحك إرسال أوامر إلى SharkyClips (النشر، الحذف، الإعدادات). كل إجراء يحمل مفتاحًا سريًا لا تعرفه إلا صفحة SharkyClips.
- **YouTube عبر مشروع Google الخاص بك:** الإعدادات > YouTube > «اربط مشروع Google الخاص بك» يرشدك خلال نحو 5 دقائق؛ و«إعادة تحميل عميل Google» يعيد قراءة ملف العميل.
- **حماية حصة YouTube:** تتوقف عمليات الرفع قبل الحد بقليل، وما لا يتسع اليوم يبدأ تلقائيًا بعد إعادة التعيين اليومية.
- تحتاج الأجهزة الأخرى إلى رمز PIN، والروابط الملصقة إلى عناوين عامة فقط، والتحديثات إلى إصدارات رسمية فقط، ولا تظهر بيانات الدخول في أي سجل.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
安全更新：其他网站不能再控制 SharkyClips，局域网设备需要 PIN，你的密钥保持隐藏。

- **安全更新：** 浏览器中打开的其他网站再也无法向 SharkyClips 发送命令（发布、删除、更改设置）。每个操作都带有只有 SharkyClips 页面知道的密钥。
- **用你自己的 Google 项目连接 YouTube：** 设置 > YouTube >“连接你自己的 Google 项目”约 5 分钟一步步完成；“重新加载 Google 客户端”会重新读取客户端文件。
- **保护 YouTube 配额：** 上传会在达到上限前停下，今天放不下的上传会在每日重置后自动开始。
- 其他设备需要 PIN，粘贴的链接只能是公开地址，更新只来自官方正式版本，登录信息不会出现在任何日志中。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
セキュリティ更新：ほかのサイトから SharkyClips を操作できなくなり、ネットワーク上の機器には PIN が必要に。キーも隠されます。

</details>

## [1.2.51] - 2026-11-16
The wrong "updated to an older version" bar is gone. New: Channel style learns how you write, and the whole stream can go to YouTube.

### New
**Channel style**
- Studio > Brand kit > **Channel style**: SharkyClips reads your own YouTube videos and Shorts
  (read only: nothing on your channel changes) and learns how you write: title length, CAPITALS,
  emojis, "?!", your words and tone, the (BRACKET) endings, description layout, the fixed parts
  (Kick / Instagram links, sign-off), hashtags and tags, separately for gaming, study videos and
  AI songs, and for Shorts and long videos.
- It compares your best 20% and weakest 20% videos by views and shows what works. Every title,
  description, hashtag and cover text the app writes follows your style (Shorts, TikTok, Reels and
  full videos) and doesn't repeat the same opening clip after clip. #utkualsirr is always there.
- Your last 3 videos: your real titles next to what SharkyClips would write. Edit the profile
  (extra rules, words to avoid, notes, capitals), or press "Analyse again"; it updates by itself
  once a week.

**The full video on YouTube**
- When you import a video, SharkyClips can also upload the **whole video** to YouTube (the
  "Upload the full video to YouTube" switch, on by default). It is written in your channel's
  style: title, description with chapters (00:00 Giriş ...) and your fixed parts, tags with
  #utkualsirr, the Gaming category, "not made for kids" and a 16:9 thumbnail suggestion.
- Nothing goes out before you check it: the confirm screen lets you change the title,
  description, tags and the time, then "Upload". It is always **scheduled** (default: the next
  free evening at 20:00, Settings), never published at once.
- At most one full video a day, one automatic retry, a progress bar, and a cut upload continues
  where it stopped. When it goes public, the Shorts of that stream get "Tam video: <link>".

### Fixed
**The "updated to an older version" bar**
- SharkyClips said "updated to 1.2.49, but the old version 1.2.50 is still running" (and before
  that 1.2.47 vs 1.2.49), and "Restart now" never made it go away. The version check now only
  counts a **higher** version: the same or an older one never shows an update or the bar, and
  SharkyClips can never go back to an older version. "Restart now" really starts the new
  version; if it doesn't come back within 45 seconds, the bar closes and you keep working (the
  × hides it too). Left-over files of an interrupted update are cleaned up.

<!-- lang:tr -->
**Türkçe**

Hatalı "eski sürüme güncellendi" uyarısı gitti. Yeni: Kanal Stili nasıl yazdığını öğreniyor ve yayının tamamı YouTube'a gidebiliyor.

### Yeni
**Kanal Stili**
- Stüdyo > Marka kiti > **Kanal Stili**: SharkyClips kendi YouTube videolarını ve Shorts'larını
  okur (sadece okuma: kanalında hiçbir şey değişmez) ve nasıl yazdığını öğrenir: başlık uzunluğu,
  BÜYÜK HARF, emoji, "?!", kelimelerin ve tonun, (PARANTEZ) sonları, açıklama düzeni, sabit
  kısımlar (Kick / Instagram linkleri, kapanış), hashtag ve etiketler; oyun, ders videoları ve AI
  şarkılar için, Shorts ve uzun videolar için ayrı ayrı.
- İzlenmeye göre en iyi %20 ile en zayıf %20'yi karşılaştırıp neyin işe yaradığını gösterir.
  Uygulamanın yazdığı her başlık, açıklama, hashtag ve kapak yazısı senin tarzına uyar (Shorts,
  TikTok, Reels ve tam videolar), klipten klibe aynı kalıpla başlamaz. #utkualsirr her zaman var.
- Son 3 videon: gerçek başlıkların ve SharkyClips'in yazacakları yan yana. Profili düzenle (ek
  kurallar, kullanılmayacak kelimeler, notlar, büyük harf) ya da "Yeniden analiz et"e bas;
  haftada bir kendiliğinden güncellenir.

**Tam video YouTube'a**
- Bir video içe aktardığında SharkyClips **videonun tamamını** da YouTube'a yükleyebilir ("Tam
  videoyu YouTube'a yükle" anahtarı, varsayılan açık). Kanalının tarzında hazırlanır: başlık,
  bölümlü açıklama (00:00 Giriş ...) ve sabit kısımların, #utkualsirr'li etiketler, Oyun
  kategorisi, "çocuklara özel değil" ve 16:9 küçük resim önerisi.
- Sen kontrol etmeden hiçbir şey gitmez: onay ekranında başlık, açıklama, etiket ve saati
  değiştirip "Yükle"ye basarsın. Video her zaman **zamanlanır** (varsayılan: bir sonraki boş akşam
  20:00, Ayarlar), asla anında yayınlanmaz.
- Günde en fazla 1 tam video, 1 otomatik tekrar deneme, ilerleme çubuğu; kesilen yükleme kaldığı
  yerden devam eder. Herkese açık olunca o yayının Shorts'larına "Tam video: <link>" eklenir.

### Düzeltmeler
**"eski sürüme güncellendi" uyarısı**
- SharkyClips "1.2.49 sürümüne güncellendi ama eski 1.2.50 sürümü hâlâ çalışıyor" diyordu (daha
  önce de 1.2.47 / 1.2.49 için), "Yeniden başlat" da uyarıyı hiç kaldırmıyordu. Sürüm kontrolü
  artık sadece **daha yüksek** sürümü sayıyor: aynı ya da daha eski sürüm asla güncelleme ya da
  uyarı göstermez ve SharkyClips asla eski sürüme dönemez. "Yeniden başlat" gerçekten yeni sürümü
  açar; 45 saniye içinde gelmezse uyarı kapanır ve çalışmaya devam edersin (× ile de
  gizleyebilirsin). Yarım kalmış güncellemelerin kalıntı dosyaları temizlenir.

<details><summary>Español</summary>

<!-- lang:es -->
Se acabó la barra errónea de "actualizado a una versión anterior". Nuevo: Estilo del canal aprende cómo escribes y el directo completo puede ir a YouTube.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A barra errada de "atualizado para uma versão antiga" sumiu. Novo: Estilo do canal aprende como você escreve e a live inteira pode ir para o YouTube.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die falsche Leiste „auf eine ältere Version aktualisiert“ ist weg. Neu: Kanalstil lernt, wie du schreibst, und der ganze Stream kann zu YouTube.

- **Behoben:** Die Leiste „auf eine ältere Version aktualisiert“ erscheint nicht mehr. Nur eine höhere Version zählt als Update, zurück zu einer älteren geht es nie, und „Jetzt neu starten“ startet wirklich die neue Version (sonst schließt sich die Leiste nach 45 s).
- **Neu: Kanalstil.** SharkyClips liest deine YouTube-Videos und Shorts (nur Lesen) und lernt deinen Stil: Titel, Beschreibungen, Hashtags, Tags, was am besten läuft. Alle Texte der App folgen ihm; deine letzten 3 Titel stehen zum Vergleich daneben.
- **Neu: das ganze Video auf YouTube.** Beim Import kann auch das ganze Video hochgeladen werden, im Stil deines Kanals, mit Kapiteln und Thumbnail-Vorschlag, immer geplant (nächster freier Abend 20:00) und erst nach deiner Bestätigung.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La fausse barre « mis à jour vers une version plus ancienne » a disparu. Nouveau : Style de chaîne apprend ta façon d'écrire, et le live entier peut aller sur YouTube.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Eltűnt a hibás „régebbi verzióra frissült” sáv. Új: a Csatornastílus megtanulja, hogyan írsz, és a teljes adás feltölthető a YouTube-ra.

- **Javítva:** nem jelenik meg többé a „régebbi verzióra frissült” sáv. Csak a magasabb verzió számít frissítésnek, régebbire visszalépni soha nem lehet, és az „Újraindítás most” tényleg az új verziót indítja (különben a sáv 45 mp után bezárul).
- **Új: Csatornastílus.** A SharkyClips elolvassa a YouTube-videóidat és Shortsaidat (csak olvasás), és megtanulja a stílusodat: címek, leírások, hashtagek, címkék, mi működik a legjobban. Az app minden szövege ezt követi; az utolsó 3 címed összehasonlításként mellette áll.
- **Új: a teljes videó a YouTube-ra.** Importáláskor a teljes videó is feltölthető, a csatornád stílusában, fejezetekkel és bélyegkép-javaslattal, mindig ütemezve (következő szabad este 20:00) és csak a jóváhagyásod után.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Ошибочная полоса «обновлено до старой версии» исчезла. Новое: «Стиль канала» учится вашей манере, а весь стрим можно загрузить на YouTube.

- **Исправлено:** больше нет панели «обновлено до более старой версии». Обновлением считается только более высокая версия, откат на старую невозможен, а «Перезапустить» действительно запускает новую версию (иначе панель закроется через 45 с).
- **Новое: стиль канала.** SharkyClips читает ваши видео и Shorts на YouTube (только чтение) и изучает ваш стиль: названия, описания, хештеги, теги и то, что работает лучше всего. Все тексты приложения следуют ему; ваши последние 3 названия показаны рядом для сравнения.
- **Новое: полное видео на YouTube.** При импорте можно загрузить и всё видео целиком, в стиле канала, с главами и предложенной обложкой, всегда по расписанию (ближайший свободный вечер в 20:00) и только после вашего подтверждения.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
اختفى شريط "تم التحديث إلى إصدار أقدم" الخاطئ. جديد: نمط القناة يتعلم طريقة كتابتك، ويمكن رفع البث كاملًا إلى YouTube.

- **إصلاح:** لم يعد يظهر شريط «تم التحديث إلى إصدار أقدم». الإصدار الأعلى فقط يُعدّ تحديثًا، ولا يمكن الرجوع إلى إصدار أقدم أبدًا، و«أعد التشغيل الآن» يشغّل الإصدار الجديد فعلًا (وإلا يُغلق الشريط بعد 45 ثانية).
- **جديد: أسلوب القناة.** يقرأ SharkyClips فيديوهاتك ومقاطع Shorts على YouTube (قراءة فقط) ويتعلّم أسلوبك: العناوين والأوصاف والوسوم والكلمات المفتاحية وما ينجح أكثر. كل نصوص التطبيق تتبعه، وتظهر عناوينك الثلاثة الأخيرة بجانبها للمقارنة.
- **جديد: الفيديو الكامل على YouTube.** عند الاستيراد يمكن رفع الفيديو كله أيضًا، بأسلوب قناتك، مع فصول وصورة مصغّرة مقترحة، مجدولًا دائمًا (أقرب مساء فارغ 20:00) وبعد تأكيدك فقط.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
错误的“已更新到旧版本”提示条已修复。新功能：频道风格会学习你的写法，整场直播也能上传到 YouTube。

- **修复：** 不再出现“已更新到更旧的版本”的提示条。只有更高的版本才算更新，永远不会回退到旧版本，“立即重启”会真正启动新版本（否则提示条会在 45 秒后关闭）。
- **新功能：频道风格。** SharkyClips 读取你在 YouTube 上的视频和 Shorts（只读），学习你的风格：标题、简介、话题标签、标签以及最有效的写法。应用写的所有文字都遵循它，你最近 3 个视频的真实标题会并排显示以便对比。
- **新功能：完整视频上传到 YouTube。** 导入时也可以上传整个视频，按你频道的风格撰写，带章节和缩略图建议，始终定时发布（下一个空闲晚上 20:00），并且只在你确认后上传。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
誤った「古いバージョンに更新されました」バーを修正。新機能：チャンネルスタイルがあなたの書き方を学び、配信全体を YouTube に上げられます。

</details>

## [1.2.50] - 2026-11-16
To keep your Instagram accounts safe, Instagram is now posted by hand with a reminder and a step-by-step guide.

### Improved
- Meta restricted a connected business account for automation. To keep your Instagram accounts
  safe, SharkyClips no longer talks to Instagram / Meta by itself: no automatic posting, no
  automatic checks, no browser automation (the Claude in Chrome briefs skip Instagram and Meta
  Business Suite too).
- **Manual mode** is now how Instagram works: at the planned time SharkyClips reminds you (a
  Windows notification and a bar on every screen). The guide opens the folder with the video
  (send it to your phone) and copies the title, the description and the hashtags with one click
  each. You post from the Instagram app, then tap "I shared it".
- Instagram posts that were planned to go out automatically are **paused**: nothing was deleted
  and nothing is sent. The bar lists them with their times; "Prepare by hand" turns one (or all)
  into a Manual-mode reminder.
- Extra care on TikTok and YouTube: at most 3 automatic posts a day per platform, and a failed
  automatic post is tried again by itself only once.

<!-- lang:tr -->
**Türkçe**

Instagram hesaplarını korumak için Instagram artık bir hatırlatma ve adım adım rehberle elle paylaşılıyor.

### İyileştirmeler
- Meta, bağlı bir işletme hesabını otomasyon gerekçesiyle kısıtladı. Instagram hesaplarını riske
  atmamak için SharkyClips artık Instagram'a / Meta'ya kendi başına bağlanmıyor: otomatik
  paylaşım yok, otomatik kontrol yok, tarayıcı otomasyonu yok (Claude in Chrome yönergeleri de
  Instagram'ı ve Meta Business Suite'i atlıyor).
- Instagram artık **Manuel mod** ile çalışıyor: planlanan saatte SharkyClips sana hatırlatır
  (Windows bildirimi ve her ekranda bir çubuk). Rehber videonun olduğu klasörü açar (telefona
  gönder), başlığı, açıklamayı ve hashtag'leri tek tıkla ayrı ayrı kopyalar. Paylaşımı Instagram
  uygulamasından sen yaparsın, sonra "Paylaştım"a dokunursun.
- Otomatik gönderilmek üzere planlanmış Instagram gönderileri **duraklatıldı**: hiçbiri silinmedi,
  hiçbiri gönderilmiyor. Çubuk onları saatleriyle listeler; "Elle hazırla" birini (ya da hepsini)
  Manuel mod hatırlatmasına çevirir.
- TikTok ve YouTube için ek önlem: platform başına günde en fazla 3 otomatik paylaşım ve hata
  olunca kendiliğinden yalnızca 1 kez yeniden deneme.

<details><summary>Español</summary>

<!-- lang:es -->
Para proteger tus cuentas de Instagram, ahora Instagram se publica a mano, con un aviso y una guía paso a paso.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Para proteger suas contas do Instagram, agora o Instagram é postado à mão, com um lembrete e um guia passo a passo.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Damit deine Instagram-Konten sicher bleiben, wird Instagram jetzt von Hand gepostet, mit Erinnerung und Schritt-für-Schritt-Hilfe.

- **Geändert:** Instagram wird jetzt von Hand gepostet (manueller Modus). Meta hat ein Konto wegen Automatisierung eingeschränkt, daher spricht SharkyClips nicht mehr selbst mit Instagram / Meta. Zur geplanten Zeit kommt eine Erinnerung (Windows-Benachrichtigung + Leiste), Titel, Beschreibung und Hashtags lassen sich mit einem Klick kopieren, der Ordner öffnet sich. Geplante automatische Instagram-Posts sind pausiert (nichts gelöscht). TikTok / YouTube: höchstens 3 automatische Posts pro Tag, nur ein automatischer neuer Versuch.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Pour protéger tes comptes Instagram, Instagram se publie maintenant à la main, avec un rappel et un guide pas à pas.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az Instagram-fiókjaid védelmében az Instagramra most kézzel posztolsz, emlékeztetővel és lépésenkénti útmutatóval.

- **Változás:** az Instagramra most kézzel posztolsz (kézi mód). A Meta automatizálás miatt korlátozott egy fiókot, ezért a SharkyClips már nem kapcsolódik magától az Instagramhoz / Metához. A tervezett időpontban emlékeztet (Windows-értesítés + sáv), a cím, a leírás és a hashtagek egy kattintással másolhatók, a mappa megnyílik. A tervezett automatikus Instagram-posztok szüneteltetve (semmi sem törlődött). TikTok / YouTube: naponta legfeljebb 3 automatikus poszt, csak egy automatikus újrapróbálás.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Чтобы защитить ваши аккаунты Instagram, публикация в Instagram теперь ручная — с напоминанием и пошаговой подсказкой.

- **Изменено:** в Instagram теперь публикуете вы (ручной режим). Meta ограничила аккаунт за автоматизацию, поэтому SharkyClips больше не обращается к Instagram / Meta сам. В назначенное время приходит напоминание (уведомление Windows + панель), заголовок, описание и хештеги копируются одним щелчком, папка открывается. Запланированные автопубликации Instagram приостановлены (ничего не удалено). TikTok / YouTube: не более 3 автопубликаций в день и только одна автоматическая повторная попытка.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
لحماية حسابات Instagram، أصبح النشر على Instagram يدويًا مع تذكير ودليل خطوة بخطوة.

- **تغيير:** النشر على Instagram يدوي الآن (الوضع اليدوي). قيّدت Meta حسابًا بسبب الأتمتة، لذا لم يعد SharkyClips يتصل بـ Instagram / Meta تلقائيًا. في الموعد المخطط يصلك تذكير (إشعار Windows وشريط)، ويُنسخ العنوان والوصف والوسوم بنقرة، ويُفتح المجلد. المنشورات التلقائية المخططة متوقفة مؤقتًا (لم يُحذف شيء). TikTok / YouTube: 3 منشورات تلقائية يوميًا كحد أقصى ومحاولة تلقائية واحدة فقط عند الخطأ.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
为保护你的 Instagram 账号，Instagram 现在改为手动发布，并有提醒和分步指南。

- **变更：** Instagram 现在改为手动发布（手动模式）。Meta 因自动化限制了一个账号，所以 SharkyClips 不再自行连接 Instagram / Meta。到计划时间会提醒你（Windows 通知 + 每个页面顶部的提示条），标题、描述和话题标签都能一键分别复制，并会打开视频所在文件夹。原计划自动发布的 Instagram 帖子已暂停（没有删除任何内容）。TikTok / YouTube：每个平台每天最多自动发布 3 条，出错后只自动重试 1 次。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
Instagram アカウントを守るため、Instagram はリマインダーと手順ガイド付きの手動投稿になりました。

</details>

## [1.2.49] - 2026-11-15
Fixed: after an update SharkyClips could get stuck and not open again. It now closes and starts cleanly every time.

### Fixed
- With the speech-to-text model on the graphics card, SharkyClips could get stuck
  while restarting after an update. It then didn't open any more ("Another SharkyClips is still
  starting or not responding") until the computer was restarted.
- Now it closes quickly and cleanly every time: running video / audio tools are ended first, and
  if it is still stuck after 15 seconds it is ended from outside.
- Opening SharkyClips now cleans up after a stuck or crashed one by itself: a SharkyClips that no
  longer answers, and left-over background processes, are ended, and the app starts normally.
- The job queue is saved reliably again when several jobs finish at the same moment.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: güncellemeden sonra SharkyClips takılıp tekrar açılmayabiliyordu. Artık her seferinde temiz kapanıp açılıyor.

### Düzeltmeler
- Ekran kartında bir konuşma tanıma (Whisper) modeli yüklüyken SharkyClips, güncellemeden sonra
  yeniden başlarken takılı kalabiliyordu. Sonra bilgisayar yeniden başlatılana kadar açılmıyordu
  ("Another SharkyClips is still starting or not responding").
- Artık her seferinde hızlı ve temiz kapanıyor: çalışan video / ses araçları önce kapatılıyor, 15
  saniye sonra hâlâ takılıysa dışarıdan sonlandırılıyor.
- SharkyClips açılırken takılmış ya da çökmüş bir öncekinin arkasını kendisi topluyor: artık yanıt
  vermeyen bir SharkyClips ve geride kalan arka plan işlemleri kapatılıyor, uygulama normal açılıyor.
- Birkaç iş aynı anda bittiğinde iş kuyruğu yeniden sorunsuz kaydediliyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: tras una actualización SharkyClips podía quedarse colgado y no volver a abrir. Ahora se cierra y arranca bien siempre.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: depois de uma atualização o SharkyClips podia travar e não abrir mais. Agora ele fecha e abre direito sempre.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Nach einem Update konnte SharkyClips hängen bleiben und nicht mehr öffnen. Jetzt schließt und startet es jedes Mal sauber.

- **Behoben:** Mit einem Whisper-Modell auf der Grafikkarte konnte SharkyClips beim Neustart nach einem Update hängen bleiben und öffnete sich danach nicht mehr. Jetzt schließt es immer schnell (nach 15 Sekunden notfalls von außen), und beim Öffnen werden hängende Reste automatisch beendet.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : après une mise à jour, SharkyClips pouvait se bloquer et ne plus s'ouvrir. Il se ferme et redémarre proprement à chaque fois.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: frissítés után a SharkyClips megakadhatott, és nem nyílt meg újra. Most mindig rendben bezár és elindul.

- **Javítva:** ha Whisper-modell volt a videokártyán, a SharkyClips frissítés utáni újraindításkor elakadhatott, és utána nem nyílt meg. Most mindig gyorsan bezárul (szükség esetén 15 másodperc után kívülről), megnyitáskor pedig magától leállítja a beragadt maradványokat.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: после обновления SharkyClips мог зависнуть и больше не открываться. Теперь он всегда корректно закрывается и запускается.

- **Исправлено:** с моделью Whisper на видеокарте SharkyClips мог зависнуть при перезапуске после обновления и потом не открывался. Теперь он всегда закрывается быстро (при необходимости через 15 секунд принудительно), а при открытии сам завершает зависшие остатки.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: بعد التحديث قد يتعلّق SharkyClips ولا يفتح مجددًا. أصبح الآن يُغلق ويعمل بشكل سليم في كل مرة.

- **إصلاح:** مع نموذج Whisper على بطاقة الرسومات كان SharkyClips قد يتعلق أثناء إعادة التشغيل بعد التحديث ثم لا يفتح. الآن يُغلق دائمًا بسرعة (وعند الحاجة يُنهى من الخارج بعد 15 ثانية)، وعند الفتح يُنهي البقايا العالقة تلقائيًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：更新后 SharkyClips 可能卡住无法再次打开。现在每次都能正常关闭和启动。

- **已修复：** 当 Whisper 语音识别模型加载在显卡上时，SharkyClips 在更新后重启可能会卡住，之后就再也打不开了。现在它每次都能快速关闭（必要时在 15 秒后被强制结束），打开时也会自动清理卡住的旧进程，正常启动。
- 多个任务同时完成时，任务队列也能可靠保存了。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：更新後に SharkyClips が固まって開かなくなることがありました。今は毎回きれいに終了・起動します。

</details>

## [1.2.48] - 2026-11-15
Fixed: deleting a project no longer stops with "is in use" when Windows keeps its folder open.

### Fixed
- Sometimes Windows keeps a project's folder itself open (the search indexer or the virus scanner,
  for example) while nothing inside it is in use. Deleting the project then stopped with "is in
  use", even with no video player open. Now its files go to the trash one by one and only an empty
  folder stays behind. That folder is no project any more, and Restore fills it again.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: Windows klasörü açık tuttuğunda proje silme artık "kullanımda" hatasıyla durmuyor.

### Düzeltmeler
- Windows bazen bir projenin klasörünün kendisini açık tutuyor (örneğin arama dizinleyicisi ya da
  virüs tarayıcısı), içindeki hiçbir dosya kullanımda olmasa bile. Proje silme o zaman, açık bir
  video oynatıcı olmasa da "kullanımda" diyerek duruyordu. Artık dosyaları tek tek çöp kutusuna
  gidiyor, geride yalnızca boş bir klasör kalıyor. O klasör artık proje sayılmıyor; Geri yükle onu
  yeniden dolduruyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: borrar un proyecto ya no se detiene con "está en uso" cuando Windows deja su carpeta abierta.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: apagar um projeto não para mais com "está em uso" quando o Windows deixa a pasta aberta.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Das Löschen eines Projekts bricht nicht mehr mit „wird verwendet“ ab, wenn Windows den Ordner offen hält.

- **Behoben:** Hält Windows den Projektordner selbst offen (z. B. Suchindex oder Virenscanner), brach das Löschen mit „wird verwendet“ ab. Jetzt wandern die Dateien einzeln in den Papierkorb; nur ein leerer Ordner bleibt, und Wiederherstellen füllt ihn wieder.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : supprimer un projet ne s'arrête plus sur « est utilisé » quand Windows garde son dossier ouvert.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a projekt törlése már nem áll le „használatban van” hibával, ha a Windows nyitva tartja a mappát.

- **Javítva:** ha a Windows magát a projektmappát tartja nyitva (pl. keresési indexelő vagy víruskereső), a törlés „használatban van” hibával leállt. Most a fájlok egyenként kerülnek a lomtárba, csak egy üres mappa marad, és a visszaállítás újra feltölti.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: удаление проекта больше не прерывается ошибкой «используется», если Windows держит папку открытой.

- **Исправлено:** если Windows держит открытой саму папку проекта (например, индексатор поиска или антивирус), удаление останавливалось с ошибкой «используется». Теперь файлы переносятся в корзину по одному, остаётся лишь пустая папка, а восстановление снова её заполняет.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: لم يعد حذف مشروع يتوقف برسالة "قيد الاستخدام" عندما يُبقي Windows مجلده مفتوحًا.

- **إصلاح:** إذا أبقى Windows مجلد المشروع نفسه مفتوحًا (مثل مفهرس البحث أو مكافح الفيروسات)، كان الحذف يتوقف برسالة «قيد الاستخدام». الآن تنتقل الملفات إلى السلة واحدًا تلو الآخر ويبقى مجلد فارغ فقط، والاستعادة تملؤه من جديد.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：当 Windows 占用文件夹时，删除项目不再因“正在使用”而中断。

- **已修复：** 如果 Windows 占用了项目文件夹本身（例如搜索索引器或杀毒软件），删除会因"正在使用"而中止。现在文件会逐个移入回收站，只留下一个空文件夹，恢复时会重新填回。
- 即使没有打开视频播放器，删除项目也不会再卡在"正在使用"上；那个空文件夹不再算作项目。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：Windows がフォルダーを開いたままでも、プロジェクト削除が「使用中」で止まらなくなりました。

</details>

## [1.2.47] - 2026-11-15
Deleting a project now keeps its planned posts going out, and a new Trash card in Settings shows the space it takes.

### New
**Trash settings**
- Settings has a new **Trash** card: how much space the trash takes, an **Empty trash** button,
  and how many days deleted things are kept (30 by default). **0** deletes for good at once, with
  no undo.

### Improved
**Deleting a project no longer drops its planned posts**
- When you delete a project that still has planned posts, SharkyClips now checks where they wait.
  Posts already on the platform (planned on YouTube, or in TikTok Studio's own schedule) aren't
  touched: the project is just deleted, and they go out by themselves.
- Instagram can't plan posts made by other apps, so SharkyClips uploads those Reels at their time from
  the project's files. For these, the delete window now warns you ("This project has 3 planned
  posts that aren't on the platform yet") and asks:
  - **Keep the posts** (recommended): only the videos of those posts stay. The project leaves your
    list, the stream video and everything else are deleted, and after the last post the rest goes
    by itself. If a post has no up-to-date video yet, it is made first.
  - **Cancel the posts**: they come off the plan, as before.
- Earlier, deleting a project also took posts planned in TikTok Studio off the Library, although
  they still went out.

<!-- lang:tr -->
**Türkçe**

Proje silmek artık planlı gönderilerin çıkmasını engellemiyor; Ayarlar'daki yeni Çöp kutusu kartı kapladığı alanı gösteriyor.

### Yeni
**Çöp kutusu ayarları**
- Ayarlar'da yeni bir **Çöp kutusu** kartı var: çöpün ne kadar yer kapladığı, **Çöpü boşalt**
  butonu ve silinenlerin kaç gün saklanacağı (varsayılan 30). **0** hemen kalıcı olarak siler,
  geri alınamaz.

### İyileştirmeler
**Proje silmek artık planlı gönderileri düşürmüyor**
- Hâlâ planlı gönderisi olan bir projeyi sildiğinde SharkyClips önce onların nerede beklediğine
  bakıyor. Platforma zaten yüklenmiş olanlara (YouTube'da planlı ya da TikTok Studio'nun kendi
  takviminde) dokunulmuyor: proje doğrudan siliniyor, gönderiler saatinde kendiliğinden çıkıyor.
- Instagram API'si zamanlama yapamıyor; bu yüzden SharkyClips o Reels'leri saatinde projenin
  dosyalarından yüklüyor. Bunlar için silme penceresi artık seni uyarıyor ("Bu projenin henüz
  platforma yüklenmemiş 3 planlı gönderisi var") ve soruyor:
  - **Gönderileri koru** (önerilen): yalnızca o gönderilerin videoları kalır. Proje listenden
    kalkar, yayın videosu ve geri kalan her şey silinir, son gönderiden sonra kalanı da
    kendiliğinden gider. Bir gönderinin güncel videosu yoksa önce o hazırlanır.
  - **Gönderileri iptal et**: eskisi gibi plandan çıkarılırlar.
- Önceden proje silmek, TikTok Studio'da planlı gönderileri de Kütüphane'den düşürüyordu; oysa
  onlar yine de yayınlanıyordu.

<details><summary>Español</summary>

<!-- lang:es -->
Borrar un proyecto ya no cancela sus publicaciones planificadas, y una nueva tarjeta Papelera en Ajustes muestra cuánto espacio ocupa.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Apagar um projeto não cancela mais suas postagens planejadas, e um novo cartão Lixeira nas Configurações mostra o espaço que ocupa.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Das Löschen eines Projekts stoppt seine geplanten Posts nicht mehr, und eine neue Papierkorb-Karte in den Einstellungen zeigt den belegten Platz.

- **Neu:** Beim Löschen eines Projekts mit geplanten Beiträgen prüft SharkyClips, wo sie warten. Beiträge, die schon auf der Plattform sind (YouTube, TikTok Studio), bleiben unberührt. Für Instagram-Reels, die SharkyClips selbst hochlädt, warnt das Fenster und fragt: Beiträge behalten (nur ihre Videos bleiben, der Rest wird gelöscht und geht nach dem letzten Beitrag von selbst) oder abbrechen.
- **Neu:** Karte „Papierkorb“ in den Einstellungen mit belegtem Platz, „Papierkorb leeren“ und der Aufbewahrungsdauer (Standard 30 Tage, 0 = sofort endgültig löschen).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Supprimer un projet n'empêche plus ses publications planifiées de sortir, et une nouvelle carte Corbeille dans les réglages montre la place prise.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A projekt törlése már nem állítja le a tervezett posztjait, és a Beállítások új Kuka kártyája mutatja, mennyi helyet foglal.

- **Új:** ha tervezett bejegyzésekkel rendelkező projektet törölsz, a SharkyClips megnézi, hol várnak. A már platformon lévőket (YouTube, TikTok Studio) nem érinti. Az Instagram Reelsekre, amelyeket a SharkyClips maga tölt fel, figyelmeztet és megkérdezi: megtartod a bejegyzéseket (csak a videóik maradnak, a többi törlődik, az utolsó bejegyzés után a maradék is megy) vagy lemondod őket.
- **Új:** „Lomtár” kártya a Beállításokban: foglalt hely, „Lomtár ürítése” és a megőrzési idő (alapból 30 nap, 0 = azonnali végleges törlés).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Удаление проекта больше не отменяет запланированные публикации, а новая карточка «Корзина» в настройках показывает, сколько места она занимает.

- **Новое:** при удалении проекта с запланированными публикациями SharkyClips проверяет, где они ждут. Уже загруженные на платформу (YouTube, TikTok Studio) не затрагиваются. Для Reels в Instagram, которые SharkyClips загружает сам, окно предупреждает и спрашивает: сохранить публикации (останутся только их видео, остальное удалится, а после последней публикации уйдёт и остаток) или отменить их.
- **Новое:** карточка «Корзина» в настройках: занятое место, «Очистить корзину» и срок хранения (по умолчанию 30 дней, 0 = удалять навсегда сразу).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
حذف مشروع لم يعد يلغي منشوراته المجدولة، وبطاقة سلة المهملات الجديدة في الإعدادات تعرض المساحة التي تشغلها.

- **جديد:** عند حذف مشروع له منشورات مجدولة، يتحقق SharkyClips من مكان انتظارها. المنشورات الموجودة على المنصة (YouTube وTikTok Studio) لا تُمس. أما مقاطع Reels على Instagram التي يرفعها SharkyClips بنفسه، فتنبهك النافذة وتسألك: إبقاء المنشورات (تبقى فيديوهاتها فقط ويُحذف الباقي، ثم يُحذف ما تبقى بعد آخر منشور) أو إلغاؤها.
- **جديد:** بطاقة «سلة المحذوفات» في الإعدادات: المساحة المستخدمة وزر «إفراغ السلة» ومدة الاحتفاظ (30 يومًا افتراضيًا، 0 = حذف نهائي فوري).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
删除项目后，已计划的帖子仍会照常发布；设置中新的回收站卡片会显示占用空间。

- **新增：** 删除带有计划帖子的项目时，SharkyClips 会先检查它们在哪里等待。已在平台上的帖子（YouTube、TikTok Studio）不受影响。对于 SharkyClips 自己上传的 Instagram Reels，窗口会提醒并询问：保留帖子（只保留它们的视频，其余删除，最后一条发布后剩余部分自动删除）或取消。
- **新增：** 设置中的"回收站"卡片：占用空间、"清空回收站"按钮和保留天数（默认 30 天，0 = 立即永久删除）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
プロジェクトを削除しても予約投稿はそのまま公開されます。設定の新しい「ゴミ箱」カードで使用容量がわかります。

</details>

## [1.2.46] - 2026-11-15
Fixed: Instagram posts that failed with "Request processing failed" are now uploaded again by themselves.

### Fixed
- Instagram sometimes refuses a video while it receives it ("ProcessingFailedError"), and takes
  the very same file a minute later. SharkyClips used to give up on the first refusal, so a
  planned Reel didn't go out. Now it starts a fresh upload right away. If Instagram refuses again,
  the post is tried again by itself a little later, each time with a fresh upload.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: "Request processing failed" hatasıyla düşen Instagram paylaşımları artık kendiliğinden yeniden yükleniyor.

### Düzeltmeler
- Instagram bazen bir videoyu alırken reddediyor ("ProcessingFailedError"), aynı dosyayı bir
  dakika sonra kabul ediyor. SharkyClips ilk retta vazgeçiyordu, bu yüzden planlı bir Reel
  çıkmıyordu. Artık hemen sıfırdan yeni bir yükleme başlatıyor. Instagram yine reddederse paylaşım
  biraz sonra kendiliğinden tekrar deneniyor, her seferinde yeni bir yüklemeyle.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: las publicaciones de Instagram que fallaban con "Request processing failed" ahora se vuelven a subir solas.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: posts do Instagram que falhavam com "Request processing failed" agora são enviados de novo sozinhos.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Instagram-Posts, die mit „Request processing failed“ scheiterten, werden jetzt von selbst neu hochgeladen.

- **Behoben:** Instagram lehnt ein Video manchmal beim Empfang ab („ProcessingFailedError“) und nimmt dieselbe Datei kurz danach an. SharkyClips gab beim ersten Mal auf, sodass ein geplantes Reel nicht erschien. Jetzt startet sofort ein neuer Upload, und bei erneuter Ablehnung wird der Post später automatisch noch einmal versucht, jedes Mal mit einem neuen Upload.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : les publications Instagram qui échouaient avec « Request processing failed » sont maintenant renvoyées toutes seules.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a „Request processing failed” hibával elakadt Instagram-posztokat most magától újra feltölti.

- **Javítva:** az Instagram néha visszautasít egy videót fogadás közben („ProcessingFailedError”), majd ugyanazt a fájlt kicsit később elfogadja. A SharkyClips az első elutasításnál feladta, így egy ütemezett Reel nem jelent meg. Most azonnal új feltöltés indul, újabb elutasításnál pedig a poszt később magától újra próbálkozik, mindig új feltöltéssel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: посты Instagram с ошибкой «Request processing failed» теперь сами загружаются заново.

- **Исправлено:** Instagram иногда отклоняет видео при приёме («ProcessingFailedError») и через минуту принимает тот же файл. SharkyClips сдавался после первого отказа, и запланированный Reel не выходил. Теперь сразу начинается новая загрузка, а при повторном отказе публикация автоматически повторяется позже, каждый раз с новой загрузкой.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: منشورات Instagram التي فشلت برسالة "Request processing failed" تُرفع الآن من جديد تلقائيًا.

- **إصلاح:** يرفض Instagram أحيانًا الفيديو أثناء استلامه («ProcessingFailedError») ثم يقبل الملف نفسه بعد دقيقة. كان SharkyClips يتوقف عند أول رفض فلا يُنشر الـReel المجدول. الآن يبدأ رفعًا جديدًا فورًا، وإذا رُفض مرة أخرى يُعاد المحاولة تلقائيًا بعد قليل، وفي كل مرة برفع جديد.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：因“Request processing failed”失败的 Instagram 帖子现在会自动重新上传。

- **已修复：** Instagram 有时会在接收视频时拒绝（"ProcessingFailedError"），一分钟后又接受同一个文件。以前 SharkyClips 第一次被拒就放弃，导致排期的 Reel 没有发出。现在会立即重新上传；如果再次被拒，稍后会自动重试，每次都重新上传。
- 这样排期的 Reels 不会因为 Instagram 的一次临时错误而错过。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：「Request processing failed」で失敗した Instagram 投稿が自動で再アップロードされるようになりました。

</details>

## [1.2.45] - 2026-11-15
The preview now bleeps exactly like the exported file, a new Final preview plays the real file, and you can edit bleeps on the timeline.

### New
**The preview bleeps exactly like the file that goes out**
- **You hear the bleeps in the preview.** On the project page the 9:16 preview now bleeps (or
  mutes) the swears whenever the video plays, also with the player's own play button, not only
  with "Play clip". The bleeps come from the same plan the render uses, so they sit at exactly
  the same moments as in the exported file, with the same soft 12 ms edges. We measured it: on
  a test clip the bleep edges differ by less than 0.2 ms, and on 37 bleeps of your own rendered
  clips they line up to the sample.
- **Captions show what the file shows.** A censored word appears in the preview exactly as it is
  burned in ("****" or "s*****"), with the same setting.
- **Final preview.** The new **Final preview** button renders the file the platforms get (small,
  540×960) through the same steps as the export, bleep check included, and plays it.
- **Edit the bleeps on the timeline.** In the Swears panel every bleep is a red mark with its
  word, showing the range the render really bleeps. Click a mark to play it, turn it off,
  delete it (your own bleeps) or go back to the automatic range. Drag its edges to move the start
  or end. Drag across the wave to add a bleep anywhere.
- **Bleep sound per clip:** classic bleep, silence or a sound effect. The "show censored words as
  *** in the captions" switch is right there too.
- **Platform view.** Tabs above the preview lay the YouTube Shorts, TikTok or Instagram Reels
  screen over it, half see-through: the top bar, the buttons and the title area. You can see at a
  glance whether a caption or the hook ends up under them. The areas are the ones the export
  presets keep the text out of.

### Fixed
- **Bleep changes in the Swears panel were lost.** Switching a swear off, or bleeping a part by
  hand, wasn't saved unless the clip also had a trim or a cut, and even then it never reached the
  render. Both are fixed: your choices now go into the preview, the render, the export and the
  posts. A clip you change is rendered again.
- A clip that was rendered before you changed its bleeps or cuts is never posted as the old
  file: the post makes a fresh export of the edited clip instead.

<!-- lang:tr -->
**Türkçe**

Önizleme artık dışa aktarılan dosyayla birebir aynı bip'liyor, yeni Son önizleme gerçek dosyayı oynatıyor ve bip'leri zaman çizelgesinde düzenleyebiliyorsun.

### Yeni
**Önizleme, platformlara giden dosyayla birebir aynı bip'liyor**
- **Bipleri önizlemede duyuyorsun.** Proje sayfasındaki 9:16 önizleme, video her oynadığında
  küfürleri bip'liyor (ya da susturuyor). Sadece "Klibi oynat" ile değil, oynatıcının kendi
  oynat düğmesiyle de. Bipler render'ın kullandığı planın aynısından geliyor, bu yüzden export
  edilen dosyadakiyle tam aynı anlarda ve aynı yumuşak 12 ms geçişlerle çalıyor. Ölçtük: test
  klibinde bip kenarları arasındaki fark 0,2 ms'nin altında, senin render edilmiş kliplerindeki
  37 bipte örnek düzeyinde birebir.
- **Altyazı, dosyadaki gibi.** Sansürlenen kelime önizlemede de dosyaya basıldığı gibi görünüyor
  ("****" ya da "s*****"), aynı ayarla.
- **Final önizleme.** Yeni **Final önizleme** düğmesi, platformlara gidecek dosyayı export ile
  aynı adımlardan (bip kontrolü dahil) küçük boyutta (540×960) render edip oynatıyor.
- **Bipleri zaman çizelgesinde düzenle.** Küfürler panelinde her bip, kelimesiyle birlikte
  kırmızı bir işaret. İşaret render'ın gerçekten bip'lediği aralığı gösteriyor. İşarete tıklayıp
  oynatabilir, kapatabilir, (kendi eklediğin bipleri) silebilir ya da otomatik aralığa dönebilirsin.
  Başlangıcı veya bitişi değiştirmek için kenarlarını sürükle. Bip eklemek için dalganın üzerinde
  sürükle.
- **Klip başına bip sesi:** klasik bip, sessizlik ya da ses efekti. "Sansürlenen kelimeleri
  altyazıda *** olarak göster" anahtarı da hemen yanında.
- **Platform görünümü.** Önizlemenin üstündeki sekmeler YouTube Shorts, TikTok ya da Instagram
  Reels ekranını yarı saydam olarak üstüne koyar: üst çubuk, düğmeler ve başlık alanı. Bir
  altyazının ya da hook yazısının bunların altında kalıp kalmadığını tek bakışta görürsün. Alanlar,
  export ön ayarlarının yazıları dışında tuttuğu alanların aynısı.

### Düzeltmeler
- **Küfürler panelindeki bip değişiklikleri kayboluyordu.** Bir küfrü kapatmak ya da bir kısmı elle
  bip'lemek, klipte ayrıca bir kırpma veya kesim yoksa kaydedilmiyordu; olsa bile render'a hiç
  ulaşmıyordu. İkisi de düzeldi: seçimlerin artık önizlemeye, render'a, export'a ve paylaşımlara
  gidiyor. Değiştirdiğin klip yeniden render edilir.
- Bip'leri veya kesimleri değiştirilmeden önce render edilmiş bir klip asla eski dosya olarak
  paylaşılmaz: paylaşım, düzenlenmiş klipten taze bir export yapar.

<details><summary>Español</summary>

<!-- lang:es -->
La vista previa ahora pita igual que el archivo exportado, la nueva Vista previa final reproduce el archivo real y puedes editar los pitidos en la línea de tiempo.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A prévia agora bipa igual ao arquivo exportado, a nova Prévia final toca o arquivo real e você edita os bipes na linha do tempo.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die Vorschau piept jetzt genau wie die exportierte Datei, die neue Endvorschau spielt die echte Datei, und Pieptöne lassen sich auf der Zeitleiste bearbeiten.

- **Die Vorschau piept jetzt genau wie die Datei, die hochgeladen wird:** auch mit dem Play-Knopf des Players, an denselben Stellen und mit denselben weichen 12-ms-Kanten wie im Export (gemessen: unter 0,2 ms Unterschied).
- Zensierte Wörter erscheinen in der Vorschau wie in der Datei. Neu: **Finale Vorschau** rendert die Datei für die Plattformen klein (540×960) und spielt sie ab.
- **Pieps auf der Zeitleiste bearbeiten:** rote Markierungen mit dem Wort, Ränder ziehen, an/aus, löschen, über die Welle ziehen zum Hinzufügen. Piepton pro Clip: klassisch, Stille oder Soundeffekt.
- **Plattformansicht:** Shorts-, TikTok- oder Reels-Oberfläche halbtransparent über der Vorschau.
- **Behoben:** Piep-Änderungen im Schimpfwort-Panel gingen verloren und kamen nie im Render an. Ein veralteter Clip wird nie als alte Datei gepostet.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
L'aperçu bipe maintenant exactement comme le fichier exporté, le nouvel Aperçu final lit le vrai fichier, et tu peux modifier les bips sur la timeline.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az előnézet most pontosan úgy sípol, mint az exportált fájl, az új Végső előnézet a valódi fájlt játssza, és a sípolásokat az idővonalon szerkesztheted.

- **Az előnézet pontosan úgy sípol, mint a feltöltött fájl:** a lejátszó saját gombjával is, ugyanott és ugyanolyan lágy, 12 ms-os szélekkel, mint az exportban (mérve: 0,2 ms alatti eltérés).
- A cenzúrázott szavak az előnézetben is úgy jelennek meg, mint a fájlban. Új: a **Végső előnézet** kicsiben (540×960) rendereli és lejátssza a platformokra kerülő fájlt.
- **Sípolások szerkesztése az idővonalon:** piros jelölések a szóval, húzható szélek, be/ki, törlés, új sípolás a hullámon húzva. Sípolás hangja klipenként: klasszikus, csend vagy hangeffekt.
- **Platform nézet:** a Shorts, TikTok vagy Reels felülete félig átlátszóan az előnézet felett.
- **Javítva:** a káromkodás panel sípolásmódosításai elvesztek, és sosem kerültek a renderbe. Egy elavult klip sosem megy ki régi fájlként.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Предпросмотр теперь запикивает точно как итоговый файл, новый «Финальный предпросмотр» играет настоящий файл, а запикивания можно править на таймлайне.

- **Превью запикивает так же, как файл, который уходит на платформы:** и при нажатии кнопки самого плеера, в тех же местах и с теми же мягкими краями 12 мс, что и в экспорте (измерено: разница меньше 0,2 мс).
- Запиканные слова в превью выглядят как в файле. Новое: **Финальное превью** рендерит файл для платформ в малом размере (540×960) и проигрывает его.
- **Правка пиков на таймлайне:** красные отметки со словом, перетаскивание краёв, вкл/выкл, удаление, добавление проведением по волне. Звук пика для каждого клипа: классический, тишина или звуковой эффект.
- **Вид платформы:** интерфейс Shorts, TikTok или Reels полупрозрачно поверх превью.
- **Исправлено:** изменения пиков в панели мата терялись и не попадали в рендер. Устаревший клип никогда не публикуется старым файлом.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
المعاينة تضع الصافرة الآن تمامًا مثل الملف المُصدَّر، و"المعاينة النهائية" الجديدة تشغّل الملف الحقيقي، ويمكنك تعديل الصافرات على الخط الزمني.

- **المعاينة تصفّر تمامًا مثل الملف الذي يُنشر:** حتى مع زر التشغيل في المشغّل نفسه، في نفس اللحظات وبنفس الحواف الناعمة 12 مللي ثانية كما في التصدير (بالقياس: فرق أقل من 0.2 مللي ثانية).
- تظهر الكلمات المحجوبة في المعاينة كما في الملف. جديد: **المعاينة النهائية** تصيّر الملف الذي يذهب إلى المنصات بحجم صغير (540×960) وتشغّله.
- **تحرير الصفير على الخط الزمني:** علامات حمراء مع الكلمة، اسحب الحواف، تشغيل/إيقاف، حذف، واسحب على الموجة للإضافة. صوت الصفير لكل مقطع: كلاسيكي أو صمت أو مؤثر صوتي.
- **عرض المنصة:** واجهة Shorts أو TikTok أو Reels شبه شفافة فوق المعاينة.
- **إصلاح:** كانت تغييرات الصفير في لوحة الشتائم تضيع ولا تصل إلى التصيير. ولا يُنشر مقطع قديم أبدًا بملفه القديم.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
预览现在的哔声与导出文件完全一致，新的“最终预览”播放真实文件，还可以在时间线上编辑哔声。

- **预览的消音与发往平台的文件完全一致：** 使用播放器自带的播放按钮也会消音，位置和 12 毫秒柔和边缘都与导出相同（实测差异小于 0.2 毫秒）。
- 预览中被消音的词与文件中显示的一样。新功能：**最终预览**以小尺寸（540×960）渲染发往平台的文件并播放。
- **在时间线上编辑消音：** 带词语的红色标记，可拖动两端、开/关、删除，在波形上拖动即可添加。每个片段可选消音声音：经典哔声、静音或音效。
- **平台视图：** 在预览上半透明叠加 Shorts、TikTok 或 Reels 界面。
- **已修复：** 脏话面板中的消音修改会丢失，且从未进入渲染。过期的片段绝不会以旧文件发布。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
プレビューのピー音が書き出しファイルと完全に一致。新しい「最終プレビュー」で実際のファイルを再生でき、ピー音はタイムラインで編集できます。

</details>

## [1.2.44] - 2026-11-15
Automatic TikTok passed its first real test in TikTok Studio, and bigger Instagram uploads work again.

### Fixed
- **Automatic TikTok passed its first real test.** A post planned two days ahead showed up in
  TikTok Studio at the right date and time, visible to everyone, and five clips have gone out
  that way since. Three things on the real page needed care:
  - TikTok's one-time hints ("Turn on automatic content checks?" and the "New editing features"
    tour) covered the page after the upload. SharkyClips now closes them: the content checks
    dialog with its X, so your TikTok settings stay as they are.
  - A video left half-finished by an earlier attempt ("continue editing?") is discarded first. The
    TikTok profile belongs to SharkyClips, so that draft is always one of its own.
  - Planned posts are now recognised in TikTok Studio's list by their alarm label, in any
    language. Before, a planned post could be read as already published. The planned time is
    kept with the post, and the links point to tiktok.com.
- **A stuck step stops cleanly.** If anything on the page doesn't respond, the post stops with a
  screenshot (plus the dialogs that were open), and the clip is ready for you to post by hand,
  just like after a CAPTCHA.
- **Instagram uploads work again.** Since 14 November Instagram refused bigger videos sent in one
  piece ("refused the upload: 400"). SharkyClips now sends them in 4 MB parts, and a part that
  fails is sent again. Error messages now include Instagram's own reason.

<!-- lang:tr -->
**Türkçe**

Otomatik TikTok, TikTok Studio'daki ilk gerçek testini geçti; büyük Instagram yüklemeleri yeniden çalışıyor.

### Düzeltmeler
- **Otomatik TikTok ilk gerçek testi geçti.** İki gün sonrasına planlanan bir gönderi TikTok
  Studio'da doğru gün ve saatte, herkese açık olarak göründü. O günden beri beş klip bu yolla
  çıktı. Gerçek sayfada üç şeye dikkat etmek gerekiyordu:
  - TikTok'un bir kerelik ipuçları ("Otomatik içerik kontrolleri açılsın mı?" ve "Yeni düzenleme
    özellikleri" turu) yüklemeden sonra sayfayı kapatıyordu. SharkyClips artık bunları kapatır:
    içerik kontrolü penceresini X ile kapatır, yani TikTok ayarların olduğu gibi kalır.
  - Önceki bir denemeden yarım kalan video ("düzenlemeye devam edilsin mi?") önce silinir. TikTok
    profili SharkyClips'e ait olduğu için o taslak her zaman onun kendi taslağıdır.
  - Planlı gönderiler TikTok Studio listesinde alarm etiketinden tanınır, dil fark etmez. Önceden
    planlı bir gönderi yayınlanmış sanılabiliyordu. Planlanan saat gönderiyle birlikte saklanır,
    linkler tiktok.com'u gösterir.
- **Takılan bir adım düzgün durur.** Sayfada bir şey yanıt vermezse gönderi ekran görüntüsüyle
  (açık pencerelerle birlikte) durur ve klip elle paylaşman için hazır olur, tıpkı bir
  CAPTCHA'dan sonraki gibi.
- **Instagram yüklemeleri yeniden çalışıyor.** 14 Kasım'dan beri Instagram büyük videoları tek
  parça halinde almıyordu ("yüklemeyi reddetti: 400"). SharkyClips artık 4 MB'lık parçalar halinde
  gönderir, başarısız bir parçayı yeniden yollar. Hata mesajlarında Instagram'ın kendi açıklaması
  da yazar.

<details><summary>Español</summary>

<!-- lang:es -->
TikTok automático pasó su primera prueba real en TikTok Studio, y las subidas grandes a Instagram vuelven a funcionar.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O TikTok automático passou no primeiro teste real no TikTok Studio, e uploads grandes no Instagram voltaram a funcionar.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Automatisches TikTok hat den ersten echten Test in TikTok Studio bestanden, und größere Instagram-Uploads klappen wieder.

- **Automatisches TikTok hat den ersten echten Test bestanden:** Ein zwei Tage im Voraus geplanter Post stand mit richtigem Datum und richtiger Uhrzeit in TikTok Studio.
- TikToks einmalige Hinweise („Automatische Inhaltsprüfungen aktivieren?“, Tour „Neue Bearbeitungsfunktionen“) werden geschlossen, deine TikTok-Einstellungen bleiben unverändert. Ein halb fertiger Entwurf eines früheren Versuchs wird zuerst verworfen.
- Geplante Posts werden in der Liste an ihrem Wecker-Symbol erkannt, in jeder Sprache. Hängt ein Schritt, stoppt der Post mit Screenshot und der Clip liegt zum Posten von Hand bereit.
- **Instagram-Uploads funktionieren wieder:** Größere Videos gehen jetzt in 4-MB-Teilen hoch (seit dem 14. November lehnte Instagram sie am Stück mit „400“ ab).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
TikTok automatique a réussi son premier vrai test dans TikTok Studio, et les gros envois Instagram refonctionnent.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az automatikus TikTok átment az első valódi teszten a TikTok Studióban, és a nagyobb Instagram-feltöltések is újra működnek.

- **Az automatikus TikTok átment az első valódi teszten:** egy két nappal előre ütemezett poszt a megfelelő napon és időpontban jelent meg a TikTok Studióban.
- A TikTok egyszeri tippjei („Bekapcsolod az automatikus tartalomellenőrzést?”, „Új szerkesztési funkciók” bemutató) bezáródnak, a TikTok-beállításaid nem változnak. Egy korábbi próbálkozásból félbemaradt piszkozat előbb törlődik.
- Az ütemezett posztokat a listában az ébresztő ikonjuk alapján ismeri fel, bármilyen nyelven. Ha egy lépés elakad, a poszt képernyőképpel leáll, és a klip kézi posztolásra kész.
- **Az Instagram-feltöltések újra működnek:** a nagyobb videók most 4 MB-os részekben mennek fel (november 14. óta az Instagram egyben „400”-zal elutasította őket).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Автоматический TikTok прошёл первую реальную проверку в TikTok Studio, а большие загрузки в Instagram снова работают.

- **Автоматический TikTok прошёл первую настоящую проверку:** пост, запланированный на два дня вперёд, появился в TikTok Studio с правильными датой и временем.
- Одноразовые подсказки TikTok («Включить автоматическую проверку контента?», тур «Новые функции редактирования») закрываются, настройки TikTok не меняются. Недоделанный черновик прошлой попытки сначала удаляется.
- Запланированные посты распознаются в списке по значку будильника на любом языке. Если шаг завис, публикация останавливается со скриншотом, а клип готов к ручной публикации.
- **Загрузка в Instagram снова работает:** большие видео теперь отправляются частями по 4 МБ (с 14 ноября Instagram отклонял их целиком с ошибкой «400»).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
اجتاز TikTok التلقائي أول اختبار حقيقي في TikTok Studio، وعادت عمليات الرفع الكبيرة إلى Instagram للعمل.

- **اجتاز TikTok التلقائي أول اختبار حقيقي:** ظهر منشور مجدول قبل يومين في TikTok Studio بالتاريخ والوقت الصحيحين.
- تُغلق تلميحات TikTok التي تظهر مرة واحدة («تشغيل فحوصات المحتوى التلقائية؟» وجولة «ميزات تحرير جديدة») وتبقى إعدادات TikTok كما هي. وتُحذف أولًا مسودة غير مكتملة من محاولة سابقة.
- تُعرف المنشورات المجدولة في القائمة من رمز المنبّه بأي لغة. وإذا تعطلت خطوة يتوقف النشر مع لقطة شاشة ويصبح المقطع جاهزًا للنشر يدويًا.
- **عاد رفع المقاطع إلى Instagram للعمل:** تُرسل المقاطع الكبيرة الآن على أجزاء بحجم 4 ميغابايت (منذ 14 نوفمبر كان Instagram يرفضها دفعة واحدة برمز «400»).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
自动 TikTok 在 TikTok Studio 中通过了首次真实测试，较大的 Instagram 上传也恢复正常。

- **自动 TikTok 通过了第一次真实测试:** 提前两天排期的帖子以正确的日期和时间出现在 TikTok Studio 中，此后已有五个片段通过这种方式发布。
- TikTok 的一次性提示（"开启自动内容检查？"和"新编辑功能"导览）会被关闭，你的 TikTok 设置保持不变。之前尝试遗留的未完成草稿会先被删除。
- 列表中的排期帖子按闹钟标记识别，任何语言都可以。如果某一步卡住，发布会停止并保存截图，片段可以手动发布。
- **Instagram 上传恢复正常:** 较大的视频现在按 4 MB 分段上传（自 11 月 14 日起，Instagram 拒绝整体上传，提示"400"），失败的分段会自动重发。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
自動 TikTok が TikTok Studio で初の実地テストに合格。大きな Instagram アップロードも再び動作します。

</details>

## [1.2.43] - 2026-11-14
Fixed: the TikTok login said "too many attempts" every time. It now opens your own Chrome and you log in as usual.

### Fixed
- **The login now opens your own Google Chrome.** Settings → Accounts → TikTok → **Log in to
  TikTok** starts your installed Chrome as a normal window on the TikTok login page. It uses
  SharkyClips' separate TikTok profile, not your everyday Chrome profile, and nothing else is
  attached to it. TikTok had recognised the old login window as automated and refused every
  attempt, the QR code too. Log in the way you always do: your password manager, the QR code or
  your phone.
- **Close the window when you're in.** The card says "I'll continue once you close the login
  window". When you close it, SharkyClips checks the login and shows the account it found. If you
  closed it before logging in, it tells you so.
- **A clean start.** The old TikTok browser folder from 1.2.42 had never been logged in, so it is
  replaced with a fresh one. Leftover lock files from a crashed browser are removed before each
  start, and a broken folder is rebuilt by itself.
- **Automatic posts use the same Chrome.** They now open the same installed Chrome with that
  profile and without the "controlled by automated test software" switch. Pacing, the daily
  limit and the hard stop on any CAPTCHA or verification stay exactly as before: SharkyClips never
  tries to solve one.
- The login window is no longer tied to SharkyClips. It keeps normal speed while SharkyClips is
  in a quiet mode, and an app restart doesn't close it.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: TikTok girişi her seferinde "çok fazla deneme" diyordu. Artık kendi Chrome'un açılıyor ve her zamanki gibi giriş yapıyorsun.

### Düzeltmeler
- **Giriş artık kendi Google Chrome'unu açıyor.** Ayarlar → Hesaplar → TikTok → **TikTok'a giriş
  yap**, yüklü Chrome'unu TikTok giriş sayfasında normal bir pencere olarak başlatır. SharkyClips'in
  ayrı TikTok profilini kullanır (her gün kullandığın Chrome profilini değil) ve pencereye başka
  hiçbir şey bağlanmaz. TikTok eski giriş penceresini otomatik bir pencere olarak tanıyıp her
  denemeyi (QR kodu dahil) reddediyordu. Her zamanki gibi giriş yap: şifre yöneticin, QR kodu ya da
  telefonunla.
- **Girince pencereyi kapat.** Kartta "Giriş penceresini kapattığında devam edeceğim" yazar.
  Pencereyi kapatınca SharkyClips girişi kontrol eder ve bulduğu hesabı gösterir. Giriş yapmadan
  kapattıysan bunu da söyler.
- **Temiz başlangıç.** 1.2.42'den kalan TikTok tarayıcı klasöründe hiç giriş yapılmamıştı, yerine
  yenisi açılır. Çöken bir tarayıcıdan kalan kilit dosyaları her açılıştan önce silinir, bozuk bir
  klasör kendiliğinden yeniden kurulur.
- **Otomatik gönderiler aynı Chrome'u kullanır.** Aynı yüklü Chrome'u bu profille ve "otomatik test
  yazılımı tarafından kontrol ediliyor" anahtarı olmadan açarlar. Aralar, günlük sınır ve her
  CAPTCHA ya da doğrulamada hemen durma kuralı aynen kalır: SharkyClips asla çözmeye çalışmaz.
- Giriş penceresi artık SharkyClips'e bağlı değil. SharkyClips sessiz moddayken de normal hızda
  çalışır, uygulama yeniden başlayınca kapanmaz.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: el inicio de sesión de TikTok decía "demasiados intentos" cada vez. Ahora se abre tu propio Chrome e inicias sesión como siempre.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: o login do TikTok dizia "tentativas demais" toda vez. Agora abre o seu próprio Chrome e você entra como sempre.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Der TikTok-Login meldete jedes Mal „zu viele Versuche“. Jetzt öffnet sich dein eigenes Chrome und du meldest dich wie gewohnt an.

- **Behoben: Die TikTok-Anmeldung meldete jedes Mal „zu viele Versuche“.** „Bei TikTok anmelden“ startet jetzt dein installiertes Google Chrome als normales Fenster. Es nutzt das eigene TikTok-Profil von SharkyClips und hat nichts angehängt (TikTok hatte das alte Fenster als automatisiert erkannt, auch beim QR-Code).
- Melde dich wie gewohnt an (Passwortmanager oder QR-Code) und schließe das Fenster. „Ich mache weiter, sobald du das Anmeldefenster schließt“: danach prüft SharkyClips die Anmeldung und zeigt das Konto.
- Der alte, nie angemeldete TikTok-Browserordner aus 1.2.42 wird durch einen neuen ersetzt. Alte Sperrdateien werden entfernt, ein defekter Ordner wird neu angelegt.
- Automatische Posts nutzen dasselbe Chrome ohne den Schalter „von automatisierter Software gesteuert“. Pausen, Tageslimit und der sofortige Stopp bei CAPTCHA oder Bestätigung bleiben unverändert.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : la connexion TikTok disait « trop de tentatives » à chaque fois. Ton propre Chrome s'ouvre maintenant et tu te connectes comme d'habitude.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a TikTok-bejelentkezés minden alkalommal „túl sok próbálkozást” írt. Most a saját Chrome-od nyílik meg, és a szokott módon lépsz be.

- **Javítva: a TikTok-bejelentkezés minden alkalommal „túl sok próbálkozást” írt.** A „Bejelentkezés a TikTokra” most a telepített Google Chrome-ot indítja normál ablakként. A SharkyClips külön TikTok-profilját használja, és semmi nincs hozzá csatolva (a TikTok a régi ablakot automatizáltnak ismerte fel, QR-kóddal is).
- Jelentkezz be a szokott módon (jelszókezelő vagy QR-kód), majd zárd be az ablakot. „Amint bezárod a bejelentkezési ablakot, folytatom”: ezután a SharkyClips ellenőrzi a bejelentkezést, és megmutatja a fiókot.
- Az 1.2.42-es, soha be nem jelentkezett TikTok-böngészőmappa helyére új kerül. A régi zárolófájlok törlődnek, egy sérült mappa magától újraépül.
- Az automatikus posztok ugyanezt a Chrome-ot használják, az „automatizált szoftver vezérli” kapcsoló nélkül. A szünetek, a napi korlát és a CAPTCHA vagy ellenőrzés esetén azonnali leállás változatlan.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: вход в TikTok каждый раз писал «слишком много попыток». Теперь открывается ваш Chrome, и вы входите как обычно.

- **Исправлено: вход в TikTok каждый раз писал «слишком много попыток».** «Войти в TikTok» теперь запускает ваш установленный Google Chrome обычным окном. Он работает с отдельным профилем TikTok в SharkyClips, и к нему ничего не подключено (TikTok распознавал старое окно как автоматическое, даже с QR-кодом).
- Войдите как обычно (менеджер паролей или QR-код) и закройте окно. «Я продолжу, когда вы закроете окно входа»: после этого SharkyClips проверит вход и покажет аккаунт.
- Старая папка браузера TikTok из 1.2.42, в которой ни разу не было входа, заменяется новой. Старые файлы блокировки удаляются, повреждённая папка пересоздаётся сама.
- Автоматические публикации используют тот же Chrome без переключателя «управляется автоматизированным ПО». Паузы, дневной лимит и немедленная остановка при CAPTCHA или проверке остаются прежними.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: كان تسجيل الدخول إلى TikTok يقول "محاولات كثيرة جدًا" في كل مرة. الآن يفتح متصفح Chrome الخاص بك وتسجّل الدخول كالمعتاد.

- **تم الإصلاح: كان تسجيل الدخول إلى TikTok يقول «محاولات كثيرة جدًا» في كل مرة.** يفتح «تسجيل الدخول إلى TikTok» الآن متصفح Google Chrome المثبت لديك كنافذة عادية. يستخدم ملف TikTok المنفصل في SharkyClips ولا يرتبط به أي شيء آخر (كان TikTok يتعرف على النافذة القديمة كنافذة آلية، حتى مع رمز QR).
- سجّل الدخول كالمعتاد (مدير كلمات المرور أو رمز QR) ثم أغلق النافذة. «سأتابع عندما تغلق نافذة تسجيل الدخول»: بعدها يتحقق SharkyClips من الدخول ويعرض الحساب.
- يُستبدل مجلد متصفح TikTok القديم من 1.2.42، الذي لم يُسجَّل الدخول فيه قط، بمجلد جديد. تُحذف ملفات القفل القديمة، ويُعاد بناء المجلد التالف تلقائيًا.
- تستخدم المنشورات التلقائية Chrome نفسه دون مفتاح «يتحكم به برنامج آلي». تبقى فترات التوقف والحد اليومي والتوقف الفوري عند CAPTCHA أو التحقق كما هي.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：TikTok 登录每次都提示“尝试次数过多”。现在会打开你自己的 Chrome，像平常一样登录即可。

- **已修复：TikTok 登录每次都提示“尝试次数过多”。**“登录 TikTok”现在会以普通窗口启动你电脑上安装的 Google Chrome，使用 SharkyClips 单独的 TikTok 配置文件，不附加任何自动化（TikTok 之前把旧登录窗口识别为自动化窗口，连二维码登录也被拒绝）。
- 像平时一样登录（密码管理器或二维码），然后关闭窗口。卡片会显示“你关闭登录窗口后我会继续”，关闭后 SharkyClips 会检查登录并显示账号；如果你没登录就关了窗口，它也会告诉你。
- 1.2.42 留下的、从未登录过的 TikTok 浏览器文件夹会换成全新的；每次启动前清除残留的锁文件，损坏的文件夹会自动重建。
- 自动发布使用同一个 Chrome，并去掉“受自动测试软件控制”开关；节奏、每日上限以及遇到验证码或验证立即停止的规则保持不变，绝不尝试破解。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：TikTok ログインが毎回「試行回数が多すぎます」になっていました。今はご自身の Chrome が開き、いつもどおりログインできます。

</details>

## [1.2.42] - 2026-11-14
One Publish button now posts to YouTube, Instagram and TikTok side by side, and TikTok can post by itself.

### New
**One Publish, three platforms, TikTok automatic too**
- **TikTok posts by itself now.** Settings → Accounts → TikTok → **Log in to TikTok** opens a
  window of SharkyClips' own browser (not your Chrome profile). You log in yourself, once.
  SharkyClips keeps only that browser profile on this PC, never your password. The card shows the
  account it's logged in as and a status light.
- **Publish posts everywhere.** With TikTok on **Automatic**, the one **Publish** button (Easy and
  Pro) sends the clip to YouTube Shorts, Instagram Reels and TikTok side by side, each with its own
  status. If one platform fails, **Retry** redoes only that one. A clip is never posted twice.
- **Planned times go into TikTok's own planner.** A time 20 minutes to 10 days ahead is planned
  in TikTok Studio, so your PC doesn't have to be on then. Later times are planned when they come
  into reach. When the time has passed, the Library shows the post as live with its link.
- **Careful by design.** It works in a real window off the screen, with pauses like a person's
  and never two uploads at once. At most 3 automatic TikTok posts a day (you can change this). A
  full day moves the next post to the day after.
- **It never fights TikTok.** If TikTok shows a CAPTCHA, a verification, a login page or a screen
  SharkyClips doesn't know, it stops at once and never tries to solve it. It saves a screenshot and
  tells you (tray notice, plus Telegram if your phone is paired). That clip is then ready for you
  to post by hand. Automatic TikTok pauses for a few hours, and **Check** brings it back.
- **Automatic or Semi-automatic per platform.** Instagram and TikTok each have the switch in their
  account card. The swear check, the AI-voice label for dubbed clips, the daily limits and the best
  times all work as before.

### Improved
**Publish queue**
- **Check on TikTok + Instagram.** Overdue posts ("time passed, no report") can now be looked up
  for you: Instagram through its connection, TikTok in TikTok Studio. A post that's there becomes
  "published" (with its link) or "scheduled". One that isn't becomes "failed (never posted)", so
  you can plan it again without posting it twice. This check also runs by itself right after your
  first TikTok login.
- Posts made with the Publish button also update the calendar, and the Publish button skips clips
  the queue has already posted.

<!-- lang:tr -->
**Türkçe**

Tek Yayınla düğmesi artık YouTube, Instagram ve TikTok'a yan yana paylaşıyor; TikTok kendi kendine de paylaşabiliyor.

### Yeni
**Tek Yayınla, üç platform, TikTok da otomatik**
- **TikTok artık kendiliğinden paylaşıyor.** Ayarlar → Hesaplar → TikTok → **TikTok'a giriş yap**
  SharkyClips'in kendi tarayıcısında bir pencere açar (Chrome profilin değil). Girişi bir kez sen
  yaparsın. SharkyClips bu bilgisayarda yalnızca o tarayıcı profilini saklar, şifreni asla. Kartta
  giriş yapılan hesap ve bir durum ışığı görünür.
- **Yayınla her yere gönderir.** TikTok **Otomatik**'teyken tek **Yayınla** düğmesi (Kolay ve Pro)
  klibi YouTube Shorts, Instagram Reels ve TikTok'a yan yana gönderir, her birinin kendi durumu
  vardır. Bir platform başarısız olursa **Tekrar dene** yalnızca onu yeniden yapar. Bir klip asla
  iki kez paylaşılmaz.
- **Planlı saatler TikTok'un kendi planlayıcısına girer.** 20 dakika ile 10 gün ilerideki bir saat
  TikTok Studio'da planlanır, o saatte bilgisayarın açık olması gerekmez. Daha ileri saatler
  yaklaştıkça planlanır. Saat geçince Kitaplık gönderiyi linkiyle yayında gösterir.
- **Dikkatli çalışır.** Ekranın dışında gerçek bir pencerede, insan gibi aralar vererek çalışır ve
  asla aynı anda iki yükleme yapmaz. Günde en fazla 3 otomatik TikTok gönderisi (değiştirebilirsin).
  Dolu bir gün sıradaki gönderiyi ertesi güne kaydırır.
- **TikTok'la asla uğraşmaz.** TikTok CAPTCHA, doğrulama, giriş sayfası ya da SharkyClips'in
  tanımadığı bir ekran gösterirse hemen durur ve asla çözmeye çalışmaz. Ekran görüntüsü alır ve
  sana haber verir (sistem bildirimi, telefonun eşliyse Telegram). O klip elle paylaşman için
  hazır olur. Otomatik TikTok birkaç saat durur, **Kontrol et** geri açar.
- **Platform başına Otomatik ya da Yarı otomatik.** Instagram ve TikTok'un hesap kartında bu anahtar
  var. Küfür kontrolü, dublajlı kliplerde yapay zeka ses etiketi, günlük sınırlar ve en iyi saatler
  eskisi gibi çalışır.

### İyileştirmeler
**Yayın kuyruğu**
- **TikTok + Instagram'da kontrol et.** Zamanı geçmiş gönderiler ("zamanı geçti, rapor yok") artık
  senin yerine kontrol edilebilir: Instagram bağlantısı üzerinden, TikTok ise TikTok Studio'da.
  Orada olan gönderi linkiyle "yayında" ya da "planlandı" olur. Olmayan "başarısız (hiç
  paylaşılmamış)" olur, böylece iki kez paylaşmadan yeniden planlayabilirsin. Bu kontrol ilk TikTok
  girişinden hemen sonra kendiliğinden de çalışır.
- Yayınla ile yapılan gönderiler takvimi de günceller, Yayınla da kuyruğun zaten paylaştığı
  klipleri atlar.

<details><summary>Español</summary>

<!-- lang:es -->
Un solo botón Publicar sube a YouTube, Instagram y TikTok a la vez, y TikTok puede publicar solo.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Um só botão Publicar posta no YouTube, Instagram e TikTok lado a lado, e o TikTok pode postar sozinho.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Ein Veröffentlichen-Button postet jetzt parallel auf YouTube, Instagram und TikTok, und TikTok kann von selbst posten.

- **Neu: TikTok postet automatisch.** Einstellungen → Konten → TikTok → „Bei TikTok anmelden“ öffnet ein Fenster in SharkyClips' eigenem Browser. Du meldest dich einmal selbst an; gespeichert wird nur dieses Browserprofil, nie dein Passwort.
- Ein „Veröffentlichen“ schickt den Clip parallel zu YouTube Shorts, Instagram Reels und TikTok, mit eigenem Status pro Plattform, „Erneut versuchen“ nur für die fehlgeschlagene und nie doppelt. Geplante Zeiten (20 Minuten bis 10 Tage voraus) landen in TikToks eigenem Planer.
- Höchstens 3 automatische TikTok-Posts pro Tag (einstellbar), nie zwei Uploads gleichzeitig. Bei CAPTCHA, Bestätigung, Anmeldeseite oder unbekanntem Bildschirm hält es sofort an, löst nichts, meldet sich (Benachrichtigung + Telegram) und der Clip liegt zum Posten von Hand bereit.
- Veröffentlichungs-Warteschlange: „Auf TikTok + Instagram prüfen“ klärt überfällige Posts (veröffentlicht mit Link, geplant oder nie gepostet).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Un seul bouton Publier envoie sur YouTube, Instagram et TikTok en même temps, et TikTok peut publier tout seul.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egyetlen Közzététel gomb most egyszerre posztol a YouTube-ra, az Instagramra és a TikTokra, és a TikTok magától is tud posztolni.

- **Új: a TikTok magától posztol.** Beállítások → Fiókok → TikTok → „Bejelentkezés a TikTokra” megnyit egy ablakot a SharkyClips saját böngészőjében. Egyszer te jelentkezel be; csak ez a böngészőprofil marad meg, a jelszavad soha.
- Egy „Közzététel” egyszerre küldi a klipet a YouTube Shortsra, az Instagram Reelsre és a TikTokra, platformonként saját állapottal; az „Újra” csak a sikertelent ismétli, és soha nem posztol kétszer. A 20 perc és 10 nap közötti időpontok a TikTok saját ütemezőjébe kerülnek.
- Naponta legfeljebb 3 automatikus TikTok-poszt (állítható), soha két feltöltés egyszerre. CAPTCHA, ellenőrzés, bejelentkezési oldal vagy ismeretlen képernyő esetén azonnal leáll, semmit nem old meg, szól (értesítés + Telegram), a klip pedig kézi posztolásra kész.
- Közzétételi sor: az „Ellenőrzés a TikTokon + Instagramon” rendbe teszi a lejárt bejegyzéseket (közzétéve linkkel, ütemezve vagy soha nem posztolva).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Одна кнопка «Опубликовать» отправляет клип в YouTube, Instagram и TikTok сразу, а TikTok может публиковать сам.

- **Новое: TikTok публикует сам.** Настройки → Аккаунты → TikTok → «Войти в TikTok» открывает окно собственного браузера SharkyClips. Вы входите сами один раз; хранится только этот профиль браузера, пароль — никогда.
- Одна кнопка «Опубликовать» отправляет клип в YouTube Shorts, Instagram Reels и TikTok параллельно, у каждой платформы свой статус; «Повторить» — только для неудавшейся, дважды — никогда. Время от 20 минут до 10 дней вперёд попадает в собственный планировщик TikTok.
- Не больше 3 автоматических публикаций TikTok в день (настраивается), никогда две загрузки сразу. При CAPTCHA, проверке, странице входа или незнакомом экране — сразу стоп, ничего не решает, сообщает (уведомление + Telegram), а клип готов к ручной публикации.
- Очередь публикаций: «Проверить в TikTok + Instagram» разбирает просроченные посты (опубликован со ссылкой, запланирован или не публиковался).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
زر نشر واحد ينشر الآن على YouTube وInstagram وTikTok معًا، ويمكن لـ TikTok النشر تلقائيًا.

- **جديد: TikTok ينشر تلقائيًا.** الإعدادات ← الحسابات ← TikTok ← «تسجيل الدخول إلى TikTok» يفتح نافذة في متصفح SharkyClips الخاص. تسجّل الدخول بنفسك مرة واحدة؛ يُحفظ ملف المتصفح فقط ولا تُحفظ كلمة المرور أبدًا.
- زر «نشر» واحد يرسل المقطع إلى YouTube Shorts وInstagram Reels وTikTok معًا، ولكل منصة حالتها؛ «إعادة المحاولة» للمنصة الفاشلة فقط، ولا نشر مكرر أبدًا. الأوقات من 20 دقيقة إلى 10 أيام تدخل مخطِّط TikTok نفسه.
- 3 منشورات TikTok تلقائية يوميًا كحد أقصى (قابل للتغيير)، ولا رفعين في وقت واحد. عند CAPTCHA أو تحقق أو صفحة دخول أو شاشة غير معروفة يتوقف فورًا ولا يحل شيئًا ويُبلغك (إشعار + Telegram)، ويصبح المقطع جاهزًا للنشر اليدوي.
- قائمة النشر: «تحقق على TikTok + Instagram» يحسم المنشورات المتأخرة (منشور مع الرابط أو مجدول أو لم يُنشر قط).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
一个“发布”按钮即可同时发布到 YouTube、Instagram 和 TikTok，TikTok 也能自动发布。

- **新功能：TikTok 也能自动发布。** 设置 → 账号 → TikTok →“登录 TikTok”会在 SharkyClips 自己的浏览器中打开一个窗口。你只需亲自登录一次；本机只保存该浏览器配置文件，从不保存密码。
- 一个“发布”按钮即可把剪辑同时发到 YouTube Shorts、Instagram Reels 和 TikTok，每个平台各有状态；“重试”只重做失败的平台，绝不重复发布。20 分钟到 10 天之后的计划时间会进入 TikTok 自己的定时发布。
- 每天最多 3 条自动 TikTok（可调整），绝不同时上传两条。遇到验证码、验证、登录页或未知页面会立即停止，绝不尝试破解，并通知你（系统通知 + Telegram），该剪辑随即准备好供你手动发布。
- 发布队列：“在 TikTok + Instagram 上检查”会核实过期的帖子（已发布并附链接、已排期，或从未发布）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
ひとつの「公開」ボタンで YouTube・Instagram・TikTok に同時投稿。TikTok は自動投稿もできます。

</details>

## [1.2.41] - 2026-11-13
Delete clips and projects safely: everything goes to a 30-day trash first, and your original video and online posts stay unless you choose otherwise.

### New
**Delete clips and projects, with a 30-day trash**
- **Delete what you don't need.** A clip has **Delete clip** (Pro: the bin next to it, or
  **Select clips** to delete several at once; Easy: in its **…** menu). A whole project has a bin
  on its card and **Delete project** at the top of the project page.
- **Nothing is gone at once.** Deleted clips and projects go to the new **Trash** for 30 days. Right
  after a delete, **Undo** in the message brings it back; later, **Restore** in the Trash does.
  **Empty trash** deletes everything for good after one clear question (how many items, how much
  disk space). After 30 days, items leave the trash by themselves.
- **Your original video is safe.** Deleting a project never touches the video you made it from,
  unless you tick **Delete the original video too** (it then goes to the trash as well, and Restore
  puts it back where it was).
- **Your posts stay online.** YouTube, Instagram and TikTok posts are only deleted if you tick that
  separate box (that can't be undone). TikTok doesn't let apps delete posts: you get the links
  to delete them yourself.
- **Stops what's running.** Renders and uploads of deleted clips are cancelled, and their planned
  posts are taken off the plan (they come back with Restore if their time is still ahead).
- **Disk space and clean-up.** The Trash page (also in Settings and next to your projects) shows how
  much space each project takes, and a **Clean up** button for rendered files of rejected clips, old
  previews and caches. The project list shows each project's size.

### Improved
**Publish queue**
- **Posts nobody reported on.** A planned post whose time has passed without a status shows
  **time passed, no report**. Copy a check for Claude in Chrome (it looks them up in TikTok Studio,
  Meta Business Suite and YouTube Studio and answers in the import format), set the status yourself
  in the calendar, or **Plan them again** in one tap.
- **Browser posts count.** YouTube, TikTok and Instagram posts made through the publish queue now
  show in the Library with their platform badges, YouTube's views come back for them, the weekly
  digest counts them, and SharkyClips never posts them a second time.
- **Your accounts are settings.** The Instagram accounts, the hashtag on every post and the time zone
  are now set in the queue settings. New users start with none of them and their computer's time
  zone; yours were kept.

### Fixed
- At 1024 px wide in Turkish, the top bar pushed the page sideways by a few pixels. Fixed.
- Speaker colours in the transcript are easier to read in the light theme.

<!-- lang:tr -->
**Türkçe**

Klipleri ve projeleri güvenle sil: her şey önce 30 günlük çöp kutusuna gider; aksini seçmedikçe orijinal videon ve çevrimiçi gönderilerin kalır.

### Yeni
**Klip ve proje silme, 30 günlük çöp kutusu**
- **İstemediğini sil.** Her klipte **Klibi sil** var (Pro: yanındaki çöp kutusu simgesi ya da
  birkaçını birden silmek için **Klip seç**; Kolay: **…** menüsünde). Her projenin kartında bir
  çöp kutusu simgesi, proje sayfasının üstünde de **Projeyi sil** var.
- **Hiçbir şey hemen yok olmaz.** Silinen klipler ve projeler 30 gün yeni **Çöp kutusu**nda
  durur. Sildikten hemen sonra mesajdaki **Geri al** geri getirir; sonra da çöp kutusundaki
  **Geri yükle**. **Çöpü boşalt** tek bir net sorudan sonra (kaç öğe, ne kadar disk alanı) her
  şeyi kalıcı olarak siler. 30 gün dolan öğeler kendiliğinden gider.
- **Orijinal videon güvende.** Proje silmek, projeyi yaptığın videoya asla dokunmaz; ancak
  **Orijinal videoyu da sil**'i işaretlersen o da çöp kutusuna gider (geri yükleme eski yerine koyar).
- **Gönderilerin yayında kalır.** YouTube, Instagram ve TikTok gönderileri sadece o ayrı kutuyu
  işaretlersen silinir (bu geri alınamaz). TikTok'un API'si gönderi silemiyor: kendin silmen için
  linkleri gösterilir.
- **Çalışanı durdurur.** Silinen kliplerin render ve yüklemeleri iptal edilir, planlı gönderileri
  plandan çıkar (geri yüklersen, saati hâlâ ilerideyse geri gelir).
- **Disk alanı ve temizlik.** Çöp kutusu sayfası (Ayarlar'da ve projelerinin yanında da var) her
  projenin ne kadar yer kapladığını gösterir; reddedilen kliplerin dosyaları, eski önizlemeler ve
  önbellek için bir **Temizle** düğmesi var. Proje listesi her projenin boyutunu gösterir.

### İyileştirmeler
**Yayın Kuyruğu**
- **Raporu gelmeyen gönderiler.** Zamanı geçtiği halde durumu bilinmeyen planlı bir gönderi
  **zamanı geçti, rapor yok** olarak görünür. Claude in Chrome için bir kontrol metni kopyala
  (TikTok Studio, Meta Business Suite ve YouTube Studio'da bakıp içe aktarma biçiminde cevap
  verir), durumu takvimde kendin seç ya da tek dokunuşla **Yeniden planla**.
- **Tarayıcıdan yapılan gönderiler sayılır.** Yayın Kuyruğu ile yapılan YouTube, TikTok ve
  Instagram gönderileri artık platform rozetleriyle Kütüphane'de görünür, YouTube izlenmeleri
  gelir, haftalık özet onları sayar ve SharkyClips onları ikinci kez paylaşmaz.
- **Hesapların artık ayar.** Instagram hesapları, her gönderideki hashtag ve saat dilimi artık
  kuyruk ayarlarında. Yeni kullanıcılar bunların hiçbiriyle ve kendi bilgisayarının saat
  dilimiyle başlar; seninkiler korundu.

### Düzeltmeler
- 1024 px genişlikte Türkçede üst bar sayfayı birkaç piksel yana kaydırıyordu. Düzeltildi.
- Açık temada metin dökümündeki konuşmacı renkleri daha kolay okunuyor.

<details><summary>Español</summary>

<!-- lang:es -->
Borra clips y proyectos con seguridad: todo va primero a una papelera de 30 días, y tu vídeo original y tus publicaciones se quedan salvo que elijas lo contrario.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Apague clipes e projetos com segurança: tudo vai primeiro para uma lixeira de 30 dias, e seu vídeo original e seus posts ficam, a menos que você escolha outra coisa.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Clips und Projekte sicher löschen: Alles kommt erst 30 Tage in den Papierkorb, und dein Originalvideo und deine Posts bleiben, außer du willst es anders.

- **Neu: Clips und Projekte löschen, mit 30-Tage-Papierkorb.** Einzeln, mehrere auf einmal oder ein ganzes Projekt; „Rückgängig“ direkt danach, „Wiederherstellen“ im Papierkorb, „Papierkorb leeren“ nach einer klaren Rückfrage (Anzahl + Speicherplatz).
- Das Originalvideo und deine Posts auf YouTube / Instagram / TikTok bleiben, außer du hakst es ausdrücklich an. Laufende Renders gelöschter Clips werden abgebrochen.
- Speicherplatz pro Projekt und „Aufräumen“ (abgelehnte Clips, alte Vorschauen, Caches).
- Veröffentlichungs-Warteschlange: Posts ohne Meldung werden markiert (prüfen lassen, Status setzen, neu planen); Browser-Posts erscheinen in der Bibliothek und im Wochenrückblick; Konten, Hashtag und Zeitzone sind jetzt Einstellungen.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Supprime clips et projets en toute sécurité : tout passe d'abord 30 jours dans la corbeille, et ta vidéo d'origine et tes publications restent sauf si tu choisis autrement.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Törölj biztonságosan klipeket és projekteket: minden előbb 30 napra a kukába kerül, az eredeti videód és a posztjaid pedig maradnak, hacsak mást nem választasz.

- **Új: klipek és projektek törlése 30 napos lomtárral.** Egyenként, többet egyszerre vagy egész projektet; közvetlenül utána „Visszavonás”, később „Visszaállítás” a lomtárban, az „Ürítés” egy egyértelmű kérdés után (darabszám + lemezterület).
- Az eredeti videó és a YouTube / Instagram / TikTok bejegyzéseid maradnak, hacsak külön be nem jelölöd. A törölt klipek futó renderelése leáll.
- Projektenkénti lemezhasználat és „Takarítás” (elutasított klipek, régi előnézetek, gyorsítótár).
- Közzétételi sor: a jelentés nélküli bejegyzések megjelölve (ellenőrzés, állapot beállítása, újratervezés); a böngészős bejegyzések megjelennek a Könyvtárban és a heti összefoglalóban; a fiókok, a hashtag és az időzóna mostantól beállítások.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Удаляйте клипы и проекты безопасно: всё сначала попадает в корзину на 30 дней, а исходное видео и публикации остаются, если вы не решите иначе.

- **Новое: удаление клипов и проектов с корзиной на 30 дней.** По одному, несколько сразу или весь проект; «Отменить» сразу после, «Восстановить» в корзине, «Очистить корзину» после одного понятного вопроса (сколько и сколько места).
- Исходное видео и посты на YouTube / в Instagram / TikTok остаются, если вы явно не отметите иное. Рендеры удалённых клипов отменяются.
- Место на диске по проектам и «Очистка» (отклонённые клипы, старые превью, кэш).
- Очередь публикаций: посты без отчёта отмечаются (проверить, указать статус, запланировать заново); посты из браузера видны в Библиотеке и в недельной сводке; аккаунты, хэштег и часовой пояс теперь в настройках.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
احذف المقاطع والمشاريع بأمان: يذهب كل شيء أولًا إلى سلة مهملات لمدة 30 يومًا، ويبقى الفيديو الأصلي ومنشوراتك ما لم تختر غير ذلك.

- **جديد: حذف المقاطع والمشاريع مع سلة محذوفات لمدة 30 يومًا.** مقطع واحد أو عدة مقاطع أو مشروع كامل؛ «تراجع» مباشرة بعد الحذف، و«استعادة» من السلة، و«إفراغ السلة» بعد سؤال واضح واحد (العدد والمساحة).
- يبقى الفيديو الأصلي ومنشوراتك على YouTube وInstagram وTikTok ما لم تحدد ذلك صراحة. تُلغى عمليات تصيير المقاطع المحذوفة.
- مساحة القرص لكل مشروع و«تنظيف» (المقاطع المرفوضة والمعاينات القديمة والذاكرة المؤقتة).
- قائمة النشر: تُعلَّم المنشورات بلا تقرير (تحقق أو تعيين الحالة أو إعادة الجدولة)؛ تظهر منشورات المتصفح في المكتبة والملخص الأسبوعي؛ والحسابات والوسم والمنطقة الزمنية أصبحت إعدادات.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
安全删除剪辑和项目：所有内容先进入保留 30 天的回收站，除非你另选，原视频和线上帖子都会保留。

- **新功能：删除片段和项目，并有保留 30 天的回收站。** 可以删除单个片段、一次删除多个或删除整个项目；删除后立即可“撤销”，之后可在回收站“恢复”；“清空回收站”前会明确询问一次（数量和磁盘空间）。
- 原始视频以及你在 YouTube、Instagram、TikTok 上的帖子都会保留，除非你明确勾选。被删除片段正在进行的渲染会被取消。
- 每个项目的磁盘占用和“清理”（已拒绝的片段、旧预览、缓存）。
- 发布队列：没有回报的帖子会被标出（核查、设置状态或重新安排）；浏览器发布的帖子会出现在资料库和每周总结中；账号、话题标签和时区现在都在设置里。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
クリップやプロジェクトを安全に削除。まず 30 日間のゴミ箱に入り、選ばない限り元の動画や公開済み投稿は残ります。

</details>

## [1.2.40] - 2026-11-11
A new Publish queue page prepares your approved clips, texts and times so Claude in Chrome can post them for you.

### New
- **New "Publish queue" page.** It lists your approved clips (accepted, or rendered and not
  thrown away) with the AI's title, description, tags and hashtags already filled in. Change any
  of them, switch platforms on or off per clip, or pick your own time.
- **"Prepare for Chrome"** makes a 9:16 MP4 **under 10 MB** of every picked clip (H.264 + AAC,
  quality worked out from the clip's length), writes the list of posts and a short brief next to the
  files in a dated folder in SharkyClips' publish queue folder, plans the times and opens the folder.
- **Times that make sense.** Set posts per day and the times for each platform (for example
  12:00, 18:00, 21:00). At most 8 a day on YouTube, 10 on Instagram, and your own TikTok limit
  (10 by default). Nothing is planned sooner than an hour from now, and a full day moves on to
  the next one. All times are Budapest time.
- **One calendar.** A calendar file keeps every planned post, and a second file shows it
  as an easy-to-read table. A clip that's already scheduled on a platform isn't queued there
  again.
- **Instagram account per clip.** Gaming clips go to @utkualsirr48 by default, others to
  @utkualsirr; change it in the settings or per clip. #utkualsirr is on every post.
- **"Copy for Claude in Chrome"** copies the brief with the whole queue, and **"Import status"**
  reads back Claude's answer: the calendar and the queue show what got scheduled,
  with links, and what failed.

<!-- lang:tr -->
**Türkçe**

Yeni Yayın Kuyruğu sayfası onaylı kliplerini, metinlerini ve saatlerini hazırlıyor; Claude in Chrome onları senin için paylaşabiliyor.

### Yeni
- **Yeni "Yayın Kuyruğu" sayfası.** Onaylanan kliplerini (kabul ettiklerin ya da render edilip
  atılmayanlar) AI'ın başlık, açıklama, etiket ve hashtag önerileriyle dolu olarak listeler.
  İstediğini değiştir, her klipte platformları aç/kapat ya da kendi saatini seç.
- **"Chrome için hazırla"** seçtiğin her klibin **10 MB altında** 9:16 MP4'ünü yapar (H.264 +
  AAC, kalite klibin süresine göre hesaplanır), dosyaların yanına `queue.json` ve kısa bir talimat
  yazar (`SharkyClips/publish_queue/<tarih>_batch`), saatleri planlar ve klasörü açar.
- **Mantıklı saatler.** Her platform için günlük gönderi sayısını ve saatleri ayarla (örneğin
  12:00, 18:00, 21:00). YouTube'da günde en fazla 8, Instagram'da 10, TikTok'ta kendi sınırın
  (varsayılan 10). Hiçbir gönderi şimdiden bir saat sonradan önceye planlanmaz, dolan gün ertesi
  güne kayar. Tüm saatler Budapeşte saatidir.
- **Tek takvim.** `SharkyClips/takvim.json` planlanan her gönderiyi tutar, `takvim.md` de kolay
  okunur bir tablo olarak gösterir. Bir platformda zaten planlanmış bir klip oraya tekrar
  kuyruğa alınmaz.
- **Klip başına Instagram hesabı.** Oyun klipleri varsayılan olarak @utkualsirr48'e, diğerleri
  @utkualsirr'a gider; ayarlardan ya da klip başına değiştir. #utkualsirr her gönderide var.
- **"Claude in Chrome için kopyala"** talimatı tüm kuyrukla birlikte kopyalar, **"Durumu içe
  aktar"** da Claude'un verdiği JSON'u okur: takvimde ve kuyrukta neyin planlandığı (linkleriyle)
  ve neyin başarısız olduğu görünür.

<details><summary>Español</summary>

<!-- lang:es -->
La nueva página Cola de publicación prepara tus clips aprobados, textos y horarios para que Claude in Chrome los publique por ti.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A nova página Fila de publicação prepara seus clipes aprovados, textos e horários para o Claude in Chrome postar por você.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die neue Seite Veröffentlichungswarteschlange bereitet deine freigegebenen Clips, Texte und Zeiten vor, damit Claude in Chrome sie für dich postet.

- **Neue Seite „Veröffentlichungs-Warteschlange“:** freigegebene Clips mit den KI-Texten (änderbar), „Für Chrome vorbereiten“ macht 9:16-MP4s unter 10 MB, schreibt queue.json und eine Anleitung für Claude in Chrome und plant die Zeiten (Budapest, pro Tag und Plattform mit Obergrenzen, frühestens in 1 Stunde).
- Ein Kalender (takvim.json + takvim.md) verhindert doppelte Planung; „Status importieren“ liest Claudes Antwort zurück.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La nouvelle page File de publication prépare tes clips validés, textes et horaires pour que Claude in Chrome les publie pour toi.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az új Közzétételi sor oldal előkészíti a jóváhagyott klipjeidet, szövegeiket és időpontjaikat, hogy a Claude in Chrome posztolja őket helyetted.

- **Új „Közzétételi sor” oldal:** jóváhagyott klipek az MI szövegeivel (szerkeszthetők); az „Előkészítés Chrome-hoz” 10 MB alatti 9:16-os MP4-eket készít, megírja a queue.json-t és a Claude in Chrome utasítását, és ütemez (budapesti idő, napi korlátokkal, legkorábban 1 óra múlva).
- Egy naptár (takvim.json + takvim.md) megakadályozza a dupla ütemezést; az „Állapot importálása” visszaolvassa Claude válaszát.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Новая страница «Очередь публикаций» готовит одобренные клипы, тексты и время, чтобы Claude in Chrome опубликовал их за вас.

- **Новая страница «Очередь публикаций»:** одобренные клипы с текстами ИИ (можно править); «Подготовить для Chrome» делает MP4 9:16 до 10 МБ, пишет queue.json и инструкцию для Claude in Chrome и расставляет время (Будапешт, лимиты в день, не раньше чем через час).
- Один календарь (takvim.json + takvim.md) не даёт запланировать дважды; «Импорт статуса» читает ответ Claude.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
صفحة "قائمة النشر" الجديدة تجهّز مقاطعك المعتمدة ونصوصها وأوقاتها لينشرها Claude in Chrome نيابةً عنك.

- **صفحة جديدة «قائمة النشر»:** المقاطع المعتمدة مع نصوص الذكاء الاصطناعي (قابلة للتعديل)؛ «جهّز لـ Chrome» يصنع ملفات MP4 بنسبة 9:16 أقل من 10 ميغابايت، ويكتب queue.json وتعليمات Claude in Chrome، ويجدول الأوقات (بتوقيت بودابست، بحدود يومية، وليس قبل ساعة).
- تقويم واحد (takvim.json وtakvim.md) يمنع الجدولة المكررة؛ و«استيراد الحالة» يقرأ رد Claude.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
新的“发布队列”页面会准备好已批准的剪辑、文案和时间，让 Claude in Chrome 替你发布。

- **新的“发布队列”页面：** 列出已通过的片段并预填 AI 文案（可修改）；“为 Chrome 准备”生成 10 MB 以下的 9:16 MP4，写好 queue.json 和给 Claude in Chrome 的说明，并按布达佩斯时间排期（每日上限，最早一小时后）。
- 一个日历（takvim.json + takvim.md）防止重复排期；“导入状态”读回 Claude 的结果。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
新しい「公開キュー」ページが承認済みクリップ・テキスト・時刻を準備し、Claude in Chrome が代わりに投稿できます。

</details>

## [1.2.39] - 2026-11-11
Publish now works for Instagram and TikTok without an account connection: a small guide helps you post each one by hand.

### New
- **Publish just works for Instagram and TikTok, no account needed.** YouTube still posts by
  itself. For Instagram and TikTok, SharkyClips makes the right file for each platform and saves
  it in Downloads/SharkyClips with the caption next to it.
- **One platform after the other.** A small guide opens: press **Copy & open Instagram**. The
  caption and hashtags go to the clipboard, the file shows up in its folder and Instagram's
  upload page opens. Then **Copied, paste and share**: drop the file in, paste the caption and
  press Share. Tap **I shared it** and the guide moves on to TikTok.
- **Come back any time.** Closed the guide too early? The clip shows "Ready to post", with a
  button that opens the guide again. Shared posts count as published in your Library.
- **Automatic posting is still there.** If you connected Instagram or TikTok with a working
  key, switch on "Post automatically" on its account card. If the key stops
  working, SharkyClips goes back to the step-by-step way by itself.

<!-- lang:tr -->
**Türkçe**

Yayınla artık hesap bağlamadan Instagram ve TikTok için de çalışıyor: küçük bir rehber her birini elle paylaşmana yardım ediyor.

### Yeni
- **Instagram ve TikTok için Yayınla hesap bağlamadan çalışıyor.** YouTube yine kendiliğinden
  yükleniyor. Instagram ve TikTok için SharkyClips her platforma uygun dosyayı hazırlıyor ve
  açıklamasıyla birlikte İndirilenler/SharkyClips klasörüne kaydediyor.
- **Platformlar sırayla.** Küçük bir rehber açılıyor: **Kopyala ve Instagram sayfasını aç**'a
  bas. Açıklama ve etiketler panoya kopyalanıyor, dosya klasöründe gösteriliyor ve Instagram'ın
  yükleme sayfası açılıyor. Sonra **Kopyalandı, yapıştır ve paylaş**: dosyayı bırak, açıklamayı
  yapıştır ve Paylaş'a bas. **Paylaştım**'a dokununca rehber TikTok'a geçiyor.
- **İstediğin zaman dönebilirsin.** Rehberi erken mi kapattın? Klipte "Paylaşmaya hazır" ve
  rehberi yeniden açan bir düğme görünüyor. Paylaştıkların Kitaplık'ta yayınlanmış sayılıyor.
- **Otomatik paylaşım duruyor.** Instagram'ı ya da TikTok'u çalışan bir token'la bağladıysan
  hesap kartında "API ile otomatik paylaş"ı aç. Token çalışmayı bırakırsa SharkyClips
  kendiliğinden adım adım yönteme dönüyor.

<details><summary>Español</summary>

<!-- lang:es -->
Publicar ya funciona en Instagram y TikTok sin conectar cuentas: una pequeña guía te ayuda a publicar cada uno a mano.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Publicar agora funciona no Instagram e no TikTok sem conectar conta: um pequeno guia ajuda você a postar cada um à mão.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Veröffentlichen klappt jetzt für Instagram und TikTok ohne Kontoverbindung: Eine kleine Anleitung hilft dir, von Hand zu posten.

- **Instagram und TikTok ohne Konto:** Beim Veröffentlichen postet YouTube von allein; für Instagram und TikTok erstellt SharkyClips die passende Datei (Downloads/SharkyClips) und ein Assistent führt dich durch: „Kopieren & öffnen“ kopiert Beschreibung und Hashtags und öffnet die Upload-Seite, dann „Kopiert – einfügen und teilen“, „Geteilt“ geht weiter zu TikTok.
- Automatisches Posten per API bleibt: auf der Kontokarte einschalten (mit funktionierendem Token).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Publier marche maintenant pour Instagram et TikTok sans connecter de compte : un petit guide t'aide à publier chacun à la main.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A Közzététel most fiókösszekötés nélkül is működik az Instagramon és a TikTokon: egy kis útmutató segít kézzel posztolni.

- **Instagram és TikTok fiók nélkül:** közzétételkor a YouTube magától töltődik fel; Instagramhoz és TikTokhoz a SharkyClips elkészíti a megfelelő fájlt (Letöltések/SharkyClips), és egy útmutató végigvezet: a „Másolás és megnyitás” kimásolja a leírást és a hashtageket, megnyitja a feltöltő oldalt, aztán „Kimásolva – illeszd be és oszd meg”, a „Megosztottam” pedig a TikTokra lép.
- Az automatikus API-s közzététel megmarad: a fiókkártyán kapcsolható be (működő tokennel).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
«Опубликовать» теперь работает для Instagram и TikTok без подключения аккаунта: небольшая подсказка поможет выложить вручную.

- **Instagram и TikTok без аккаунта:** при публикации YouTube загружается сам; для Instagram и TikTok SharkyClips готовит нужный файл (Загрузки/SharkyClips), а помощник ведёт по шагам: «Скопировать и открыть» копирует подпись и хештеги и открывает страницу загрузки, затем «Скопировано — вставьте и опубликуйте», «Опубликовал» переходит к TikTok.
- Автопубликация через API осталась: включается на карточке аккаунта (с рабочим токеном).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح النشر يعمل على Instagram وTikTok دون ربط حساب: دليل صغير يساعدك على النشر يدويًا خطوة بخطوة.

- **Instagram وTikTok دون حساب:** عند النشر يُرفع YouTube تلقائيًا؛ أما Instagram وTikTok فيجهّز SharkyClips الملف المناسب (التنزيلات/SharkyClips) ويرشدك مساعد خطوة بخطوة: «انسخ وافتح» ينسخ الوصف والوسوم ويفتح صفحة الرفع، ثم «تم النسخ، الصق وانشر»، و«نشرته» ينتقل إلى TikTok.
- النشر التلقائي عبر API باقٍ: فعّله من بطاقة الحساب (برمز يعمل).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
无需连接账号，“发布”现在也能用于 Instagram 和 TikTok：小向导会帮你逐个手动发布。

- **Instagram 和 TikTok 无需连接账号：** 发布时 YouTube 自动上传；Instagram 和 TikTok 由 SharkyClips 生成合适的文件（下载/SharkyClips），向导一步步带你完成：“复制并打开”复制文案和话题标签并打开上传页面，然后“已复制，粘贴并发布”，点“已发布”进入 TikTok。
- 通过 API 自动发布仍然可用：在账号卡片上开启（需要有效令牌）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
アカウント連携なしで Instagram と TikTok にも「公開」が使えます。小さなガイドが手動投稿を手伝います。

</details>

## [1.2.38] - 2026-11-10
Paste Kick VODs and clips like Twitch links (with chat replay), and your YouTube numbers are kept only as long as needed.

### New
**Kick VODs and clips**
- **Paste a Kick link.** VOD links (from a channel's videos page or a short video link)
  and clip links import like Twitch and YouTube links.
  A channel link tells you where to find a VOD instead of failing.
- **Kick chat replay.** The chat of a Kick VOD or clip is downloaded by itself and counts as a
  hype signal, emotes included (KEKW spam counts).
- **Knows the game.** The stream's Kick category helps SharkyClips recognise the game.
- If Kick changes its site and the downloader can't read a link, SharkyClips asks Kick directly.
  Subscriber-only VODs can't be downloaded (SharkyClips never logs in to sites).

### Improved
**Your YouTube data is kept only as long as needed**
- **Disconnect deletes it.** Disconnecting YouTube now also deletes the views, likes and
  retention numbers SharkyClips read from YouTube (it asks first). Numbers you typed in yourself
  stay.
- **Nothing old lingers.** Numbers that weren't refreshed for 30 days are deleted by themselves,
  and if Google signs you out and you don't reconnect within 7 days, they're deleted too.

**TikTok**
- **Disconnect ends the access at TikTok too**, not only on your computer.
- The post screen always loads your account's current TikTok settings when it opens, and the
  disclosure notes use TikTok's own wording.

### Fixed
**Steadier**
- On Windows, a clip you had just posted could briefly show as "not posted" while another
  platform's upload was being saved. Fixed.

<!-- lang:tr -->
**Türkçe**

Kick yayınlarını ve kliplerini Twitch linkleri gibi yapıştır (sohbet tekrarıyla); YouTube sayıların yalnızca gerektiği kadar saklanıyor.

### Yeni
**Kick yayınları ve klipleri**
- **Kick linkini yapıştır.** Yayın kayıtları (`kick.com/<kanal>/videos/…` ve kısa
  `kick.com/video/…`) ile klipler (`kick.com/<kanal>/clips/…` ya da `?clip=…`) Twitch ve YouTube
  linkleri gibi içe aktarılıyor. Kanal linki verirsen hata yerine yayın kaydını nerede bulacağın
  söyleniyor.
- **Kick sohbet tekrarı.** Kick yayınının ya da klibinin sohbeti kendiliğinden indiriliyor ve
  heyecan sinyali olarak sayılıyor; emojiler de dahil (KEKW yağmuru sayılır).
- **Oyunu tanıyor.** Yayının Kick kategorisi, SharkyClips'in oyunu tanımasına yardım ediyor.
- Kick sitesini değiştirir ve indirici bir linki okuyamazsa SharkyClips doğrudan Kick'e soruyor.
  Yalnızca abonelere açık yayınlar indirilemiyor (SharkyClips sitelere hiç giriş yapmaz).

### İyileştirmeler
**YouTube verilerin yalnızca gerektiği kadar saklanıyor**
- **Bağlantıyı kesince siliniyor.** YouTube bağlantısını kesmek artık SharkyClips'in YouTube'dan
  okuduğu izlenme, beğeni ve izlenme süresi sayılarını da siliyor (önce soruyor). Kendi girdiğin
  sayılar kalıyor.
- **Eski veri kalmıyor.** 30 gün yenilenmeyen sayılar kendiliğinden siliniyor; Google oturumunu
  kapatır ve 7 gün içinde yeniden bağlanmazsan onlar da siliniyor.

**TikTok**
- **Bağlantıyı kesmek erişimi TikTok tarafında da bitiriyor**, yalnızca bilgisayarında değil.
- Paylaşım ekranı her açılışta hesabının güncel TikTok ayarlarını yüklüyor; açıklama notları
  TikTok'un kendi ifadelerini kullanıyor.

### Düzeltmeler
**Daha sağlam**
- Windows'ta az önce paylaştığın bir klip, başka bir platformun yüklemesi kaydedilirken kısa
  bir an "paylaşılmadı" görünebiliyordu. Düzeltildi.

<details><summary>Español</summary>

<!-- lang:es -->
Pega VODs y clips de Kick como los enlaces de Twitch (con el chat), y tus datos de YouTube solo se guardan el tiempo necesario.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Cole VODs e clipes da Kick como links da Twitch (com o chat), e seus números do YouTube ficam guardados só o tempo necessário.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Füge Kick-VODs und -Clips wie Twitch-Links ein (mit Chat-Wiedergabe), und deine YouTube-Zahlen werden nur so lange wie nötig gespeichert.

- **Kick:** VODs (auch kurze `kick.com/video/…`-Links) und Clips importieren wie Twitch und YouTube, der Chat-Replay zählt als Hype-Signal (Emotes inklusive), die Kick-Kategorie hilft beim Erkennen des Spiels. Ein Kanal-Link erklärt, wo du ein VOD findest; Abonnenten-VODs gehen nicht (kein Login).
- **YouTube-Daten:** Beim Trennen werden auch die von YouTube gelesenen Aufrufe, Likes und Zuschauerbindung gelöscht (mit Nachfrage); Zahlen, die 30 Tage nicht aktualisiert wurden, verschwinden von selbst.
- **TikTok:** Trennen beendet den Zugriff auch bei TikTok. **Windows:** ein gerade geposteter Clip wirkt nicht mehr kurz „nicht gepostet“.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Colle des VOD et clips Kick comme des liens Twitch (avec le chat), et tes chiffres YouTube ne sont gardés que le temps nécessaire.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Kick-felvételeket és klipeket is beilleszthetsz, mint a Twitch-linkeket (chat-visszajátszással), a YouTube-adataidat pedig csak a szükséges ideig tárolja.

- **Kick:** a VOD-ok (a rövid `kick.com/video/…` linkek is) és a klipek úgy importálhatók, mint a Twitch és a YouTube linkek; a chat-visszajátszás hype-jelként számít (az emote-ok is), a Kick-kategória segít felismerni a játékot. Csatornalinknél megmondja, hol találsz VOD-ot; az előfizetői VOD-ok nem tölthetők le (nincs bejelentkezés).
- **YouTube-adatok:** leválasztáskor a YouTube-ról beolvasott megtekintések, kedvelések és nézettség is törlődnek (előtte rákérdez); a 30 napig nem frissített számok maguktól törlődnek.
- **TikTok:** a leválasztás a TikTok oldalán is megszünteti a hozzáférést. **Windows:** az épp közzétett klip már nem látszik egy pillanatra „nem közzétettnek”.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Вставляйте записи и клипы Kick, как ссылки Twitch (с повтором чата), а данные YouTube хранятся только столько, сколько нужно.

- **Kick:** VOD (и короткие ссылки `kick.com/video/…`) и клипы импортируются как ссылки Twitch и YouTube, повтор чата считается сигналом хайпа (вместе с эмоутами), категория Kick помогает узнать игру. Для ссылки на канал подскажет, где найти VOD; VOD только для подписчиков скачать нельзя (без входа).
- **Данные YouTube:** при отключении удаляются и полученные от YouTube просмотры, лайки и удержание (сначала спросит); числа, не обновлявшиеся 30 дней, удаляются сами.
- **TikTok:** отключение закрывает доступ и на стороне TikTok. **Windows:** только что опубликованный клип больше не мелькает как «не опубликован».

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
الصق تسجيلات Kick ومقاطعه مثل روابط Twitch (مع إعادة الدردشة)، وتُحفظ أرقام YouTube فقط للمدة اللازمة.

- **Kick:** تُستورد البثوث المسجلة (ومنها الروابط القصيرة `kick.com/video/…`) والمقاطع مثل روابط Twitch وYouTube، وتُحسب إعادة الدردشة إشارةً للحماس (مع الرموز التعبيرية)، وتساعد فئة Kick على معرفة اللعبة. رابط القناة يدلّك على مكان البث المسجل؛ وبثوث المشتركين فقط لا تُنزَّل (بلا تسجيل دخول).
- **بيانات YouTube:** عند قطع الاتصال تُحذف أيضًا المشاهدات والإعجابات ونسب المشاهدة المقروءة من YouTube (بعد السؤال)، والأرقام التي لم تُحدَّث 30 يومًا تُحذف تلقائيًا.
- **TikTok:** قطع الاتصال يُنهي الوصول لدى TikTok أيضًا. **ويندوز:** المقطع المنشور للتو لم يعد يظهر لحظةً «غير منشور».

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
像 Twitch 链接一样粘贴 Kick 回放和剪辑（含聊天回放），你的 YouTube 数据只保留必要的时间。

- **Kick：** 直播回放（包括 `kick.com/video/…` 短链接）和剪辑可以像 Twitch、YouTube 链接一样导入；聊天回放会作为热度信号（表情也算），Kick 分类帮助识别游戏。粘贴频道链接时会告诉你去哪里找回放；仅限订阅者的回放无法下载（不登录任何网站）。
- **YouTube 数据：** 断开连接时会一并删除从 YouTube 读取的观看量、点赞数和留存数据（会先询问）；30 天未更新的数据会自动删除。
- **TikTok：** 断开连接也会在 TikTok 端撤销访问。**Windows：** 刚发布的剪辑不会再短暂显示为“未发布”。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
Kick のアーカイブやクリップを Twitch リンクと同じように貼り付け可能（チャットリプレイ付き）。YouTube の数値は必要な期間だけ保存します。

</details>

## [1.2.37] - 2026-11-10
Both kinds of Instagram token now work, and captions, bleeps and covers work on the Mac again.

### Improved
**Instagram: tokens from a business portfolio work too**
- **Both kinds of Instagram token.** Meta's newer setup (login through Facebook) gives a
  token that starts with **EAA** (for example a business portfolio's system user). SharkyClips
  used to refuse it with "Cannot parse access token". Now it recognises the token by itself:
  **IGAA…** tokens work as before, **EAA…** tokens connect through Facebook.
  Posting Reels, views, the daily limit and deleting a post work with both.
- **Finds your account.** With an EAA token, SharkyClips looks up the Instagram account behind
  your Pages or your business portfolio. The new optional **Instagram account** field
  (@username or user id) picks one when the token reaches several, or when none can be found.
- **Clear messages.** If the token belongs to a different account, can't post, or was copied
  badly, you're told what's wrong and what to do, in your language. Spaces and line breaks
  pasted with the token are removed.
- **No expiry worries.** System-user tokens don't expire, so nothing is renewed. If you revoke
  one, the Instagram card turns red (signed out) instead of failing quietly.

### Fixed
**Mac: captions, bleeps and covers work again**
- The standard video tool from Homebrew no longer draws subtitles or text. The Mac installer
  now sets up the full version, SharkyClips uses it by itself, and the health check warns you
  when yours is missing these features.

<!-- lang:tr -->
**Türkçe**

Her iki tür Instagram token'ı artık çalışıyor; Mac'te altyazılar, bip sesleri ve kapaklar yeniden çalışıyor.

### İyileştirmeler
**Instagram: işletme portföyünden alınan token'lar da çalışıyor**
- **İki tür Instagram token'ı.** Meta'nın yeni kurulumu ("Unified login ile API kurulumu")
  **EAA** ile başlayan bir token veriyor (örneğin işletme portföyünün sistem kullanıcısı).
  SharkyClips bunu "Cannot parse access token" diyerek reddediyordu. Artık token'ı kendisi
  tanıyor: **IGAA…** token'ları eskisi gibi, **EAA…** token'ları API'nin Facebook tarafından
  bağlanıyor. Reels paylaşma, görüntülenmeler, günlük sınır ve gönderi silme ikisinde de çalışıyor.
- **Hesabını kendisi buluyor.** EAA token'ında SharkyClips, sayfalarının ya da işletme
  portföyünün arkasındaki Instagram hesabını buluyor. Yeni, isteğe bağlı **Instagram hesabı**
  alanı (@kullanıcıadı veya kullanıcı kimliği), token birden fazla hesaba erişiyorsa ya da hiç
  hesap bulunamıyorsa hangisinin kullanılacağını seçiyor.
- **Açık mesajlar.** Token başka bir hesaba aitse, paylaşım izni yoksa ya da eksik kopyalandıysa
  neyin yanlış olduğu ve ne yapman gerektiği kendi dilinde söyleniyor. Token'la birlikte
  yapıştırılan boşluklar ve satır sonları siliniyor.
- **Süre derdi yok.** Sistem kullanıcısı token'ları sona ermiyor, yenilenecek bir şey yok.
  Token'ı iptal edersen Instagram kartı sessizce hata vermek yerine kırmızıya (oturum kapandı)
  dönüyor.

### Düzeltmeler
**Mac: altyazılar, bip sesleri ve kapaklar yeniden çalışıyor**
- Homebrew'un standart FFmpeg'i artık altyazı ve yazı çizme içermiyor. Mac kurulumu artık
  **ffmpeg-full** kuruyor, SharkyClips onu kendiliğinden kullanıyor ve `doctor`, FFmpeg'inde bu
  özellikler eksikse uyarıyor (`brew install ffmpeg-full` düzeltir).

<details><summary>Español</summary>

<!-- lang:es -->
Ya funcionan los dos tipos de token de Instagram, y los subtítulos, pitidos y portadas vuelven a funcionar en Mac.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Os dois tipos de token do Instagram funcionam agora, e legendas, bipes e capas voltaram a funcionar no Mac.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Beide Arten von Instagram-Token funktionieren jetzt, und Untertitel, Pieptöne und Cover klappen auf dem Mac wieder.

- **Instagram mit Business-Portfolio-Token:** Tokens mit **EAA** (z. B. Systemnutzer aus „API setup with unified login“) werden jetzt erkannt und über Facebooks Seite der API verbunden; **IGAA…** funktioniert wie bisher. Das Konto wird automatisch gefunden (optional: Feld „Instagram-Konto“), Fehler wie ein falsches Konto werden klar in deiner Sprache erklärt, Systemnutzer-Tokens laufen nicht ab, ein widerrufener Token zeigt „abgemeldet“.
- **Mac:** Untertitel, Pieptöne und Cover funktionieren wieder (der Installer richtet **ffmpeg-full** ein).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Les deux types de jeton Instagram marchent maintenant, et sous-titres, bips et miniatures refonctionnent sur Mac.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Mindkét fajta Instagram-token működik, és Macen újra mennek a feliratok, a sípolások és a borítók.

- **Instagram vállalati portfólió tokennel:** az **EAA** kezdetű tokeneket (pl. rendszerfelhasználó az „API setup with unified login” részből) a SharkyClips most felismeri, és a Facebook-oldali API-n keresztül csatlakoztatja; az **IGAA…** ugyanúgy működik. A fiókot magától megtalálja (nem kötelező: „Instagram-fiók” mező), a hibákat (pl. rossz fiók) érthetően, a saját nyelveden magyarázza el, a rendszerfelhasználói token nem jár le, a visszavont token „kijelentkezve” állapotot mutat.
- **Mac:** a feliratok, a sípolások és a borítók újra működnek (a telepítő **ffmpeg-full**-t tesz fel).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Теперь работают оба вида токенов Instagram, а на Mac снова работают субтитры, запикивание и обложки.

- **Instagram с токеном бизнес-портфолио:** токены, начинающиеся с **EAA** (например, системный пользователь из «API setup with unified login»), теперь распознаются и подключаются через API на стороне Facebook; **IGAA…** работает как раньше. Аккаунт находится сам (необязательное поле «Аккаунт Instagram»), ошибки вроде чужого аккаунта объясняются понятно на вашем языке, токены системного пользователя не истекают, отозванный токен показывает «выход выполнен».
- **Mac:** субтитры, запикивание и обложки снова работают (установщик ставит **ffmpeg-full**).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
يعمل الآن نوعا رموز Instagram، وعادت الترجمات والصافرات والأغلفة للعمل على Mac.

- **إنستغرام برمز من حافظة الأعمال:** الرموز التي تبدأ بـ **EAA** (مثل مستخدم النظام من «API setup with unified login») صارت تُعرف تلقائيًا وتتصل عبر واجهة فيسبوك؛ ورموز **IGAA…** تعمل كما كانت. يُعثر على الحساب تلقائيًا (حقل «حساب Instagram» اختياري)، وتُشرح الأخطاء مثل الحساب الخطأ بوضوح وبلغتك، ورموز مستخدم النظام لا تنتهي، والرمز الملغى يظهر «تم تسجيل الخروج».
- **ماك:** عادت الترجمات والصفير والأغلفة للعمل (المثبّت يُعدّ **ffmpeg-full**).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
两种 Instagram 令牌现在都能用，Mac 上的字幕、哔声和封面也恢复正常。

- **用商务资产组合令牌连接 Instagram：** 以 **EAA** 开头的令牌（例如“API setup with unified login”中的系统用户）现在会被自动识别，并通过 Facebook 侧的 API 连接；**IGAA…** 令牌照常使用。会自动找到账号（可选“Instagram 账号”栏），账号不对等错误会用你的语言清楚说明；系统用户令牌不会过期，被撤销的令牌会显示“已退出登录”。
- **Mac：** 字幕、哔声和封面恢复正常（安装程序会安装 **ffmpeg-full**）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
2 種類の Instagram トークンが両方使えるように。Mac で字幕・ピー音・カバーが再び動作します。

</details>

## [1.2.36] - 2026-11-09
One Publish button for YouTube, Instagram and TikTok, with an Accounts section and a phone-style preview for each platform.

### New
- **Accounts.** Settings has a new **Accounts** section with three cards: YouTube, Instagram and
  TikTok. Each shows who is connected (picture and name), a status (green connected, amber needs
  attention, red signed out), Connect / Reconnect / Disconnect, and how much you can still post
  today. Sign-ins are saved encrypted on this PC and renew themselves.
- **Step-by-step setup** for your own Meta app (Instagram) and TikTok developer app, with direct
  links: creating the app, adding yourself as an Instagram tester and accepting the invite,
  TikTok's sandbox, the exact redirect address to copy.
- **Publish everywhere.** The clip card has one **Publish** button with three switches
  (YouTube · Instagram · TikTok, all on by default and remembered). Nothing to fix? One tap posts
  everywhere. Something to fix? The preview opens: a phone-frame preview per platform with the
  title or caption, hashtags, cover frame and length check, the platform limits, and one-tap
  fixes (shorten, keep 30 hashtags, skip a platform, connect).
- **Same clip, adapted texts.** YouTube gets title + description + tags; Instagram and TikTok get
  a caption made from the title, a short description, your hashtags (your channel tag first) and
  your socials where they fit. Swears are censored and the AI-voice line is added everywhere, and
  a clip with an unbleeped swear can't go out anywhere.
- **TikTok's own post screen**, as TikTok requires: who is posting, who can see it (you choose),
  comments / Duet / Stitch, the branded-content disclosure and the Music Usage Confirmation.
  Until TikTok reviews your app, posts are "Only me": after posting, **Make it public on TikTok**
  takes you there.
- **Now or planned.** Post now or pick a time: YouTube schedules it, Instagram and TikTok are
  posted by SharkyClips at that time (the PC has to be on; if it was off, they go out as soon as
  it starts).
- **Reliable posting.** The three platforms upload side by side, each with its own progress.
  If one fails, the others are not touched and **Try again** redoes only that one. Nothing is
  ever posted twice, even after a crash or a restart: SharkyClips picks up where it stopped.
  Rate limits are waited out by themselves.
- **Library:** each clip shows small badges per platform (status and views, linked to the post),
  a total, a "Posted everywhere" mark, and filters per platform. Views and likes from every
  platform also teach the viral score.

<!-- lang:tr -->
**Türkçe**

YouTube, Instagram ve TikTok için tek Yayınla düğmesi; Hesaplar bölümü ve her platform için telefon görünümlü önizleme.

### Yeni
- **Hesaplar.** Ayarlar'da yeni bir **Hesaplar** bölümü var: YouTube, Instagram ve TikTok için üç
  kart. Her biri kimin bağlı olduğunu (resim ve ad), bir durum (yeşil bağlı, sarı dikkat
  gerekiyor, kırmızı oturum kapandı), Bağla / Yeniden bağla / Bağlantıyı kes düğmelerini ve
  bugün daha ne kadar paylaşabileceğini gösteriyor. Oturumlar bu bilgisayarda şifreli saklanıyor
  ve kendiliğinden yenileniyor.
- Kendi Meta uygulaman (Instagram) ve TikTok geliştirici uygulaman için **adım adım kurulum**,
  doğrudan bağlantılarla: uygulamayı oluşturma, kendini Instagram test kullanıcısı olarak ekleyip
  daveti kabul etme, TikTok sandbox'ı, kopyalanacak tam yönlendirme adresi.
- **Her yerde yayınla.** Klip kartında üç anahtarlı tek bir **Yayınla** düğmesi var (YouTube ·
  Instagram · TikTok; üçü de varsayılan açık ve hatırlanıyor). Düzeltilecek bir şey yoksa tek
  dokunuş her yere paylaşır. Varsa önizleme açılır: her platform için telefon çerçevesinde başlık
  ya da metin, hashtag'ler, kapak karesi ve süre kontrolü, platform sınırları ve tek dokunuşla
  düzeltmeler (kısalt, 30 hashtag bırak, platformu atla, bağla).
- **Aynı klip, uyarlanmış metinler.** YouTube başlık + açıklama + etiket alır; Instagram ve
  TikTok başlıktan, kısa açıklamadan, hashtag'lerinden (önce kanal etiketin) ve sığdığı yerde
  sosyal medya satırlarından oluşan bir metin alır. Küfürler her yerde sansürleniyor, yapay zekâ
  ses satırı her yere ekleniyor ve bip'lenmemiş küfür içeren bir klip hiçbir yere gidemiyor.
- **TikTok'un kendi paylaşım ekranı**, TikTok'un istediği gibi: kim paylaşıyor, kimler görebilir
  (sen seçersin), yorum / Düet / Stitch, markalı içerik beyanı ve Müzik Kullanım Onayı. TikTok
  uygulamanı inceleyene kadar paylaşımlar "Sadece ben" olur: paylaştıktan sonra **TikTok'ta
  herkese aç** seni oraya götürür.
- **Şimdi ya da planlı.** Şimdi paylaş ya da bir saat seç: YouTube planlar, Instagram ve TikTok'u
  SharkyClips o saatte paylaşır (bilgisayar açık olmalı; kapalıysa açılır açılmaz gönderilir).
- **Güvenilir paylaşım.** Üç platform yan yana yüklenir, her birinin kendi ilerlemesi var. Biri
  başarısız olursa diğerlerine dokunulmaz, **Yeniden dene** yalnızca onu tekrarlar. Çökme ya da
  yeniden başlatmadan sonra bile hiçbir şey iki kez paylaşılmaz: SharkyClips kaldığı yerden devam
  eder. Hız sınırları kendiliğinden beklenir.
- **Kitaplık:** her klipte platform başına küçük rozetler (durum ve izlenme, paylaşıma bağlantılı),
  toplam, "Her yerde yayında" işareti ve platform filtreleri var. Tüm platformlardan gelen
  izlenme ve beğeniler viral puanı da eğitiyor.

<details><summary>Español</summary>

<!-- lang:es -->
Un botón Publicar para YouTube, Instagram y TikTok, con una sección Cuentas y una vista previa tipo móvil para cada plataforma.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Um botão Publicar para YouTube, Instagram e TikTok, com uma seção Contas e uma prévia estilo celular para cada plataforma.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Ein Veröffentlichen-Button für YouTube, Instagram und TikTok, mit einem Bereich Konten und einer Handy-Vorschau für jede Plattform.

- **Ein Veröffentlichen-Knopf für YouTube, Instagram und TikTok:** neuer Bereich „Konten“ mit drei Karten (verbunden / Achtung / abgemeldet, Kontingent, verschlüsselte Anmeldung) und Schritt-für-Schritt-Einrichtung deiner eigenen Meta- und TikTok-App. Ein Tipp postet überall, oder die Vorschau zeigt pro Plattform Text, Grenzen und Ein-Tipp-Korrekturen. TikToks eigene Post-Einstellungen sind dabei („Nur ich“, bis TikTok deine App prüft). Jetzt oder geplant; die Plattformen laden parallel hoch, ein Fehler betrifft nur seine Plattform, nichts wird doppelt gepostet. Die Mediathek zeigt Status und Aufrufe pro Plattform.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Un bouton Publier pour YouTube, Instagram et TikTok, avec une section Comptes et un aperçu façon téléphone pour chaque plateforme.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egy Közzététel gomb a YouTube-hoz, Instagramhoz és TikTokhoz, Fiókok résszel és telefonos előnézettel minden platformra.

- **Egy Közzététel gomb a YouTube-hoz, az Instagramhoz és a TikTokhoz:** új „Fiókok” rész három kártyával (csatlakoztatva / figyelem / kijelentkezve, keret, titkosított bejelentkezés) és lépésenkénti beállítás a saját Meta- és TikTok-alkalmazásodhoz. Egy koppintás mindenhová posztol, vagy az előnézet platformonként mutatja a szöveget, a korlátokat és az egykoppintásos javításokat. A TikTok saját poszt-beállításai is benne vannak („Csak én”, amíg a TikTok nem ellenőrzi az alkalmazásodat). Most vagy ütemezve; a platformok párhuzamosan töltenek fel, egy hiba csak a saját platformját érinti, semmi sem megy ki kétszer. A könyvtár platformonként mutatja az állapotot és a megtekintéseket.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Одна кнопка «Опубликовать» для YouTube, Instagram и TikTok, раздел «Аккаунты» и предпросмотр как на телефоне для каждой платформы.

- **Одна кнопка «Опубликовать» для YouTube, Instagram и TikTok:** новый раздел «Аккаунты» с тремя карточками (подключено / требует внимания / выход выполнен, лимиты, зашифрованный вход) и пошаговая настройка своих приложений Meta и TikTok. Одно касание публикует везде, или предпросмотр показывает текст, ограничения и исправления в одно касание для каждой платформы. Есть собственные настройки публикации TikTok («Только я», пока TikTok не проверит приложение). Сейчас или по расписанию; платформы загружаются параллельно, ошибка затрагивает только свою платформу, ничего не публикуется дважды. В библиотеке видны статус и просмотры по платформам.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
زر نشر واحد لـ YouTube وInstagram وTikTok، مع قسم للحسابات ومعاينة بشكل الهاتف لكل منصة.

- **زر نشر واحد لـيوتيوب وإنستغرام وتيك توك:** قسم «الحسابات» الجديد بثلاث بطاقات (متصل / يحتاج انتباهًا / تم تسجيل الخروج، الحصة، تسجيل دخول مشفّر) وإعداد خطوة بخطوة لتطبيقَي Meta وتيك توك الخاصّين بك. نقرة واحدة تنشر في كل مكان، أو تعرض المعاينة النص والحدود والإصلاحات بنقرة واحدة لكل منصة. تتضمن إعدادات النشر الخاصة بتيك توك («لي فقط» حتى يدقّق تيك توك تطبيقك). الآن أو بجدولة؛ ترفع المنصات بالتوازي، والخطأ يخص منصته فقط، ولا يُنشر شيء مرتين. تعرض المكتبة الحالة والمشاهدات لكل منصة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
YouTube、Instagram 和 TikTok 共用一个“发布”按钮，新增“账号”部分，并为每个平台提供手机样式预览。

- **YouTube、Instagram 和 TikTok 一键发布：** 新增“账号”区域，三张卡片显示连接状态（已连接 / 需要处理 / 已退出登录）、剩余额度和加密保存的登录，并提供自建 Meta 应用和 TikTok 开发者应用的分步设置。
- 没有问题时一键发到所有平台；有问题时预览会按平台显示文案、限制和一键修正。包含 TikTok 要求的发布设置（在 TikTok 审核你的应用之前仅自己可见）。
- 可以立即发布或定时发布；三个平台并行上传，一个出错不影响其他平台，任何情况下都不会重复发布。资料库按平台显示状态和观看次数。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
YouTube・Instagram・TikTok 共通の「公開」ボタン。アカウント欄と、各プラットフォームのスマホ風プレビュー付き。

</details>

## [1.2.35] - 2026-11-09
Clip length now follows what gets the most views on your own channel, once there is enough data.

### Improved
- **Your channel decides the length.** SharkyClips now looks at the real views of your published
  shorts and finds the length that works best for you (under 20 s, 20-30 s, 30-45 s or over
  45 s). New Easy clips aim for that length, and clips that are too short get a little more setup
  before the moment and more payoff after it (always at sentence boundaries, never into the next
  clip). It only learns once there is enough data: at least 8 published clips with views, 3 of
  them in the winning length, each at least 2 days old, and one viral clip alone can't decide.
  It keeps updating as new views come in.
- Until then, a target can be set by hand in the settings file. Without one, the usual targets per content type stay.
- Clips that aren't uploaded yet are re-cut when the target changes; your own trims and uploaded
  clips are never touched.
- The weekly digest in the Library shows the current target length, and the length tip no longer
  points to the "short version" button when longer clips are the ones doing well.

<!-- lang:tr -->
**Türkçe**

Klip uzunluğu, yeterli veri olunca artık kendi kanalında en çok izlenen uzunluğa göre ayarlanıyor.

### İyileştirmeler
- **Uzunluğa kanalın karar veriyor.** SharkyClips artık yayınladığın Shorts'ların gerçek
  izlenmelerine bakıp sana en iyi gelen uzunluğu buluyor (20 sn altı, 20-30 sn, 30-45 sn ya da
  45 sn üstü). Yeni Kolay mod klipleri bu uzunluğu hedefliyor; fazla kısa kliplere andan önce biraz
  daha giriş, sonrasına biraz daha sonuç ekleniyor (her zaman cümle sınırında, asla bir sonraki
  klibe taşmadan). Yeterli veri olunca öğreniyor: izlenmesi gelmiş en az 8 yayınlanmış klip,
  bunların 3'ü kazanan uzunlukta, her biri en az 2 günlük; tek bir viral klip tek başına karar
  veremez. Yeni izlenmeler geldikçe kendini güncelliyor.
- O zamana kadar, kanalının rakamlarına göre bir hedef ayar dosyasından (`length_targets`)
  belirlenebiliyor. Yoksa içerik türüne göre olağan hedefler geçerli.
- Hedef değişince henüz yüklenmemiş klipler yeniden kesiliyor; senin kendi kesimlerine ve
  yüklenmiş kliplere asla dokunulmuyor.
- Kitaplıktaki haftalık özet geçerli hedef uzunluğu gösteriyor; uzun klipler daha iyi gidiyorsa
  uzunluk ipucu artık "kısa versiyon" butonunu önermiyor.

<details><summary>Español</summary>

<!-- lang:es -->
La duración de los clips ahora sigue lo que más vistas consigue en tu propio canal, cuando hay datos suficientes.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A duração dos clipes agora segue o que dá mais views no seu canal, quando há dados suficientes.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die Cliplänge richtet sich jetzt danach, was auf deinem Kanal die meisten Aufrufe bekommt, sobald genug Daten da sind.

- **Die Cliplänge folgt den Aufrufen deines Kanals:** SharkyClips lernt aus den echten Aufrufen deiner Shorts, welche Länge am besten läuft (ab 8 Clips mit Aufrufen), neue Clips zielen darauf und zu kurze bekommen etwas mehr Aufbau und Pointe. Eigene Schnitte und hochgeladene Clips bleiben unverändert; der Wochenrückblick zeigt die Ziellänge.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La durée des clips suit maintenant ce qui marche le mieux sur ta chaîne, dès qu'il y a assez de données.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A klipek hossza mostantól ahhoz igazodik, ami a saját csatornádon a legtöbb nézést hozza, ha már van elég adat.

- **A kliphossz a csatornád megtekintéseit követi:** a SharkyClips a Shortsaid valós megtekintéseiből tanulja meg, melyik hossz működik a legjobban (legalább 8 megtekintéssel rendelkező kliptől), az új klipek erre törekszenek, a túl rövidek kicsit több felvezetést és csattanót kapnak. A saját vágásaid és a feltöltött klipek nem változnak; a heti összefoglaló mutatja a célhosszt.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Длина клипов теперь подстраивается под то, что набирает больше всего просмотров на вашем канале, когда данных достаточно.

- **Длина клипа следует за просмотрами канала:** SharkyClips учится по реальным просмотрам твоих Shorts, какая длина работает лучше (от 8 клипов с просмотрами), новые клипы стремятся к ней, а слишком короткие получают чуть больше завязки и развязки. Твои обрезки и загруженные клипы не меняются; недельная сводка показывает целевую длину.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح طول المقطع يتبع ما يحصد أكثر المشاهدات على قناتك، عندما تتوفر بيانات كافية.

- **طول المقطع يتبع مشاهدات قناتك:** يتعلم SharkyClips من المشاهدات الحقيقية لمقاطع Shorts الطول الأنسب لك (بدءًا من 8 مقاطع لها مشاهدات)، وتستهدفه المقاطع الجديدة، وتحصل المقاطع القصيرة جدًا على تمهيد ونهاية أطول قليلًا. لا تتغير قصّاتك ولا المقاطع المرفوعة؛ ويعرض الملخص الأسبوعي الطول المستهدف.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
有足够数据后，剪辑时长会按你自己频道里播放量最高的长度来定。

- **片段时长跟随你频道的观看量：** SharkyClips 会根据你 Shorts 的真实观看量学习哪个时长效果最好（至少 8 个有观看量的片段），新片段以此为目标，太短的片段会多保留一点铺垫和结尾。你自己的剪辑和已上传的片段不会改动；每周摘要会显示目标时长。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
十分なデータがたまると、クリップの長さはあなたのチャンネルで最も再生される長さに合わせます。

</details>

## [1.2.34] - 2026-11-08
Easy mode 2.0: clips keep their setup and punchline, a strong first 3 seconds, the right length, Autopilot and a weekly digest.

### New
- **Clips keep their setup and their punchline.** Every clip now starts at the beginning of the
  sentence, keeps the build-up before the big moment and waits until the laugh or the reaction
  calms down before it ends. The AI's "needs more setup" judgement counts too. Each card says in
  plain words what was fixed, and has one-tap buttons: **Start earlier**, **End later** (3 s),
  **Short version**, **Long version** and back to the **Smart cut**.
- **The right length.** Every clip has a target for its kind (funny gaming 18-28 s, clutch /
  action 20-35 s, study 30-45 s, music 15-30 s) and the card warns in plain words when a clip is
  longer. Dead air is tightened by itself, and you can switch on **Speed up slow parts (1.2×)**:
  walking and looting with nobody talking play a little faster, never speech or the big moment.
- **A strong first 3 seconds.** Each clip gets a hook score (motion, loudness, your face, text).
  When the opening is weak, SharkyClips tries a later start and the "best moment first" flash and
  keeps the stronger one. A **headline banner** (on by default) shows a short punchy line from
  your title on top, in capitals with your emojis and your brand colours.
- **Why this clip?** Cards show 1-3 plain reasons ("Pentakill", "Laughter", "Chat exploded",
  "7 bleeps"). Once a clip is live, its real views replace the prediction.
- **Learn my taste.** 👍 / 👎 on whole clips: after 3 votes, new picks follow what you like and
  what really performs on your channel.
- **Autopilot.** One switch: new recording → clips → bleeps → titles in your style → covers →
  planned at your daily limit. Every morning one line: "4 clips ready, 3 planned". A failed or
  blocked upload is always announced, never skipped quietly.
- **YouTube connection at a glance.** A green / amber / red pill on every Easy screen with a
  one-tap fix (reconnect, open the Library). The sign-in is checked every 30 minutes, so a
  sign-out shows up before an upload fails.
- **See it like on a phone.** The phone button on a clip draws the Shorts buttons, title area
  and progress bar over it. Captions and the banner now always stay clear of them.
- **Action tracking.** Gaming clips without a facecam fill the whole phone screen and the picture
  follows the action smoothly, instead of a small picture with a blurred background.
- **Fix a caption word in one tap.** In the Edit sheet, tap a wrong word and type it right. The
  clip is made again and the same mistake is fixed in every later clip; new names go into your
  glossary.
- **Weekly digest** at the top of the Library: shorts published, views, the best one, what worked
  (length, hook, game) and one suggestion.

Older projects keep their look: open one and tap **Turn on** under "New: smart cuts".

<!-- lang:tr -->
**Türkçe**

Kolay mod 2.0: klipler girişini ve esprisini koruyor, güçlü ilk 3 saniye, doğru uzunluk, Otopilot ve haftalık özet.

### Yeni
- **Klipler girişini ve esprisini koruyor.** Her klip artık cümlenin başından başlıyor, büyük
  andan önceki hazırlığı tutuyor ve kahkaha ya da tepki sakinleşmeden bitmiyor. Yapay zekânın
  "girişe ihtiyacı var" yorumu da hesaba katılıyor. Her kart neyin düzeltildiğini sade bir dille
  söylüyor ve tek dokunuşluk butonları var: **Daha erken başlat**, **Daha geç bitir** (3 sn),
  **Kısa versiyon**, **Uzun versiyon** ve **Akıllı kesim**e geri dönüş.
- **Doğru uzunluk.** Her türün bir hedefi var (komik oyun 18-28 sn, clutch / aksiyon 20-35 sn,
  ders 30-45 sn, müzik 15-30 sn); klip daha uzunsa kart sade bir dille uyarıyor. Boşluklar
  kendiliğinden kısalıyor; istersen **Yavaş kısımları hızlandır (1.2×)** seçeneğini aç: kimsenin
  konuşmadığı yürüme ve loot kısımları biraz hızlı oynar, konuşma ve asıl an asla.
- **Güçlü ilk 3 saniye.** Her klibin bir kanca puanı var (hareket, ses, yüzün, yazı). Açılış
  zayıfsa SharkyClips daha geç bir başlangıcı ve "en iyi an önce" flaşını deniyor, güçlü olanı
  seçiyor. **Başlık bandı** (varsayılan açık) başlığından kısa ve vurucu bir satırı büyük harfle,
  emojilerinle ve marka renklerinle üstte gösteriyor.
- **Neden bu klip?** Kartlarda 1-3 sade sebep var ("Pentakill", "Kahkaha", "Sohbet patladı",
  "7 bip"). Klip yayına girince tahminin yerini gerçek izlenmeler alıyor.
- **Zevkimi öğren.** Klibin tamamına 👍 / 👎: 3 oydan sonra yeni seçimler senin sevdiklerine ve
  kanalında gerçekten iyi gidenlere göre yapılıyor.
- **Otopilot.** Tek anahtar: yeni kayıt → klipler → bipler → senin tarzında başlıklar → kapaklar
  → günlük limitine göre planlama. Her sabah tek satır: "4 klip hazır, 3 tanesi planlandı".
  Başarısız ya da bekleyen bir yükleme her zaman bildiriliyor, sessizce atlanmıyor.
- **YouTube bağlantısı bir bakışta.** Her Kolay ekranda yeşil / sarı / kırmızı bir gösterge ve
  tek dokunuşla çözüm (yeniden bağlan, Kütüphaneyi aç). Oturum her 30 dakikada kontrol ediliyor;
  oturum kapanırsa yükleme başarısız olmadan önce görüyorsun.
- **Telefondaki gibi gör.** Klipteki telefon butonu Shorts butonlarını, başlık alanını ve
  ilerleme çubuğunu üstüne çiziyor. Altyazılar ve bant artık hep bunların dışında kalıyor.
- **Aksiyon takibi.** Facecam'siz oyun klipleri telefon ekranını tamamen dolduruyor ve görüntü
  aksiyonu yumuşakça takip ediyor; bulanık arka planlı küçük görüntü yok.
- **Altyazı kelimesini tek dokunuşla düzelt.** Düzenle penceresinde yanlış kelimeye dokun ve
  doğrusunu yaz. Klip yeniden hazırlanıyor, aynı hata sonraki tüm kliplerde düzeliyor; yeni
  isimler sözlüğüne giriyor.
- **Haftalık özet** Kütüphanenin en üstünde: yayınlanan short'lar, izlenmeler, en iyisi, işe
  yarayanlar (uzunluk, kanca, oyun) ve bir öneri.

Eski projeler görünüşlerini koruyor: birini aç ve "Yeni: akıllı kesimler" altındaki **Aç**'a dokun.

<details><summary>Español</summary>

<!-- lang:es -->
Modo Fácil 2.0: los clips conservan la preparación y el remate, unos primeros 3 segundos fuertes, la duración correcta, Piloto automático y un resumen semanal.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Modo Fácil 2.0: os clipes mantêm a preparação e o desfecho, 3 primeiros segundos fortes, a duração certa, Piloto automático e um resumo semanal.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Einfacher Modus 2.0: Clips behalten Aufbau und Pointe, starke erste 3 Sekunden, die richtige Länge, Autopilot und ein Wochenrückblick.

- **Einfacher Modus 2.0:** Clips behalten Aufbau und Pointe (Satzanfang, Aufbau vor dem Moment, Ende erst wenn das Lachen abklingt) mit Tasten für früher / später / kurz / lang; Ziellängen je Inhalt und optionales 1,2× für langsame Stellen; Hook-Bewertung mit Test einer späteren Startstelle und Titelbanner im eigenen Stil.
- Klare Gründe auf jeder Karte und echte Aufrufe statt Prognose; 👍 / 👎 lernt deinen Geschmack; Autopilot von der Aufnahme bis zum geplanten Short mit Morgen-Zusammenfassung; YouTube-Status in Grün / Gelb / Rot mit Lösung per Tipp.
- Handy-Vorschau mit Shorts-Buttons, Action-Tracking ohne Facecam, Untertitelwort per Tipp korrigieren (wird gelernt) und ein Wochenrückblick in der Bibliothek.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Mode Facile 2.0 : les clips gardent la mise en place et la chute, 3 premières secondes fortes, la bonne durée, le Pilote auto et un résumé de la semaine.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egyszerű mód 2.0: a klipek megtartják a felvezetést és a csattanót, erős első 3 másodperc, jó hossz, Robotpilóta és heti összefoglaló.

- **Egyszerű mód 2.0:** a klipek megtartják a felvezetést és a csattanót (mondat eleje, felvezetés a pillanat előtt, vége csak ha a nevetés lecsengett), korábban / később / rövid / hosszú gombokkal; tartalomtól függő célhossz és opcionális 1,2× a lassú részekre; horog-pontszám későbbi kezdés tesztjével, címsáv a saját stílusodban.
- Érthető okok minden kártyán, élesítés után valós megtekintések; a 👍 / 👎 megtanulja az ízlésed; Robotpilóta a felvételtől az ütemezett Shortsig reggeli összefoglalóval; YouTube-állapot zöld / sárga / piros jelzéssel és egy koppintásos javítással.
- Telefonos előnézet a Shorts gombjaival, akciókövetés facecam nélkül, feliratszó javítása egy koppintással (megtanulja) és heti összefoglaló a Könyvtárban.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Простой режим 2.0: в клипах сохраняются завязка и развязка, сильные первые 3 секунды, нужная длина, автопилот и недельная сводка.

- **Простой режим 2.0:** клипы сохраняют завязку и развязку (начало фразы, подводка к моменту, конец только когда смех утих), кнопки «раньше / позже / короче / длиннее»; целевая длина по типу контента и опциональное ускорение 1,2× скучных моментов; оценка хука с проверкой более позднего старта и заголовок-баннер в твоём стиле.
- Понятные причины на каждой карточке и реальные просмотры вместо прогноза; 👍 / 👎 учат твоему вкусу; автопилот от записи до запланированного Shorts с утренней сводкой; статус YouTube зелёный / жёлтый / красный с исправлением в одно касание.
- Предпросмотр как на телефоне с кнопками Shorts, слежение за экшеном без вебки, исправление слова в субтитрах одним касанием (запоминается) и недельная сводка в Библиотеке.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
الوضع السهل 2.0: تحافظ المقاطع على التمهيد والنهاية، وثلاث ثوانٍ أولى قوية، والطول المناسب، والطيار الآلي، وملخص أسبوعي.

- **الوضع السهل 2.0:** تحتفظ المقاطع بالتمهيد والنهاية (بداية الجملة، التمهيد قبل اللحظة، والنهاية بعد أن تهدأ الضحكة) مع أزرار أبكر / لاحقًا / قصير / طويل؛ طول مستهدف حسب نوع المحتوى وتسريع اختياري 1.2× للأجزاء البطيئة؛ تقييم للجذب مع تجربة بداية لاحقة وشريط عنوان بأسلوبك.
- أسباب واضحة على كل بطاقة ومشاهدات حقيقية بدل التوقع؛ 👍 / 👎 تتعلم ذوقك؛ طيار آلي من التسجيل إلى Short مجدول مع ملخص صباحي؛ حالة YouTube بالأخضر / الأصفر / الأحمر مع حل بلمسة.
- معاينة كما على الهاتف مع أزرار Shorts، وتتبع الحدث بدون كاميرا الوجه، وتصحيح كلمة الترجمة بلمسة (يُتعلَّم)، وملخص أسبوعي في المكتبة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
简易模式 2.0：剪辑保留铺垫和笑点，开头 3 秒更抓人，时长合适，新增自动驾驶和每周摘要。

- **简易模式 2.0：** 片段会保留铺垫和笑点（从句子开头开始、保留高光前的铺垫、等笑声和反应平息后才结束），并提供“提前开始 / 延后结束 / 短版 / 长版”一键按钮；按内容类型设定目标时长，可选把平淡片段加速到 1.2 倍；开头吸引力评分会试验更晚的开头，并在顶部加上你风格的标题横幅。
- 每张卡片用大白话说明入选原因，发布后显示真实观看量；👍 / 👎 学习你的偏好；自动驾驶从录像一路到排期好的 Shorts，每天早上发一句摘要；YouTube 连接状态用绿 / 黄 / 红显示，一键修复。
- 手机效果预览（带 Shorts 按钮），没有摄像头画面的游戏片段会平滑跟随动作，点按字幕中的词即可改正并记住，资料库顶部还有每周摘要。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
かんたんモード 2.0：前振りとオチを残すクリップ、強い最初の 3 秒、ちょうどいい長さ、オートパイロット、週間まとめ。

</details>

## [1.2.33] - 2026-11-08
Fixed: clips with every swear bleeped were sometimes marked "could not be bleeped" by mistake.

### Fixed
- **No more false "could not be bleeped" warnings.** When SharkyClips listens to a finished clip,
  it also gives the listener the swear words as a hint. On a bleep, the listener sometimes just
  read that hint list back, so fully bleeped clips were marked "1 swear could not be bleeped" and
  waited for you before upload. A read-back hint no longer counts, and a word under a full bleep
  only counts when it is heard without the hint (or at the edge of the bleep).

<!-- lang:tr -->
**Türkçe**

Düzeltildi: tüm küfürleri bip'lenmiş klipler bazen yanlışlıkla "bip'lenemedi" diye işaretleniyordu.

### Düzeltmeler
- **Artık yanlış "biplenemedi" uyarısı yok.** SharkyClips bitmiş klibi dinlerken dinleyiciye
  küfür kelimelerini ipucu olarak da veriyor. Bir bip üzerinde dinleyici bazen bu ipucu listesini
  aynen geri okuyordu; tamamen bip'lenmiş klipler "1 küfür biplenemedi" diye işaretlenip yükleme
  için seni bekliyordu. Geri okunan ipucu artık sayılmıyor; tam bip altındaki bir kelime ancak
  ipucu olmadan duyulursa (ya da bip'in kenarında) sayılıyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: a veces se marcaban por error como "no se pudo pitar" clips con todas las palabrotas pitadas.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: clipes com todos os palavrões bipados às vezes eram marcados por engano como "não deu para bipar".

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Clips, in denen jedes Schimpfwort überpiept war, wurden manchmal fälschlich als „konnte nicht überpiept werden“ markiert.

- Keine falschen Warnungen „nicht überpiept“ mehr: Beim Nachhören las die Erkennung manchmal nur die Liste der Hinweiswörter vor. Vollständig überpiepte Clips warten nicht mehr auf dich.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : des clips où tous les gros mots étaient bipés étaient parfois marqués à tort « n'a pas pu être bipé ».

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: azokat a klipeket, ahol minden káromkodás ki volt sípolva, néha tévesen „nem sikerült kisípolni” jelzéssel látta el.

- Nincs több téves „nincs kisípolva” figyelmeztetés: az újrahallgatás néha csak visszaolvasta a súgószavak listáját. A teljesen kisípolt klipek már nem várnak rád a feltöltés előtt.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: клипы, где запикан каждый мат, иногда ошибочно помечались «не удалось запикать».

- Больше нет ложных предупреждений «не запикано»: при повторном прослушивании распознавание иногда просто зачитывало список слов-подсказок. Полностью запиканные клипы больше не ждут вас перед загрузкой.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: كانت مقاطع جميع شتائمها مغطاة بالصافرة تُعلَّم أحيانًا خطأً بأنها "تعذّر تغطيتها".

- لا مزيد من التحذيرات الخاطئة "لم يُغطَّ عليها": عند إعادة الاستماع كان التعرّف أحيانًا يكرر قائمة الكلمات المساعدة فقط. المقاطع المغطاة بالصفير بالكامل لم تعد تنتظرك قبل الرفع.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：所有脏话都已哔掉的剪辑有时会被误标为“无法哔掉”。

- 完全消音的片段不再误报"未消音"：复听时识别有时只是把提示词列表念了一遍，导致片段被误标并等待你确认。现在提示词的回读不再计入，只有不带提示也能听到的脏话（或消音边缘漏出的部分）才算，完全消音的片段上传前不会再卡住等你。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：すべての汚い言葉にピー音が入ったクリップが、誤って「ピー音を入れられませんでした」と表示されることがありました。

</details>

## [1.2.32] - 2026-11-08
Fixed: a clip that looks like one of your examples in My style now still gets a description.

### Fixed
- **A clip that looks like one of your examples still gets a description.** When a clip shows the
  same moment as one of the examples in My style, the AI kept writing almost the same sentences,
  every try was rejected and the clip ended up with no description. Now that example is left out
  of the next tries, and if only one sentence is copied, the rest of the description is kept.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: Tarzım'daki örneklerinden birine benzeyen bir klip artık yine de açıklama alıyor.

### Düzeltmeler
- **Örneklerinden birine benzeyen klip de açıklama alıyor.** Bir klip, Benim tarzımdaki
  örneklerden biriyle aynı anı gösterince yapay zekâ neredeyse aynı cümleleri yazıyor, her deneme
  reddediliyor ve klip açıklamasız kalıyordu. Artık o örnek sonraki denemelerde gösterilmiyor;
  sadece bir cümle kopyaysa açıklamanın geri kalanı korunuyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: un clip parecido a uno de tus ejemplos de Mi estilo ahora también recibe descripción.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: um clipe parecido com um dos seus exemplos em Meu estilo agora também ganha descrição.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Ein Clip, der einem deiner Beispiele in Mein Stil ähnelt, bekommt jetzt trotzdem eine Beschreibung.

- Ein Clip, der einem deiner Beispiele gleicht, bekommt trotzdem eine Beschreibung.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : un clip qui ressemble à l'un de tes exemples de Mon style reçoit quand même une description.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: az a klip is kap leírást, amely hasonlít a Saját stílus egyik példádra.

- Az egyik példádhoz hasonló klip is kap leírást.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: клип, похожий на один из ваших примеров в «Мой стиль», теперь тоже получает описание.

- Клип, похожий на один из ваших примеров, тоже получает описание.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: المقطع الذي يشبه أحد أمثلتك في "أسلوبي" يحصل الآن على وصف أيضًا.

- المقطع الذي يشبه أحد أمثلتك يحصل على وصف أيضًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：与“我的风格”中某个示例相似的剪辑现在也能得到描述。

- 与你的某个示例相似的片段也会有简介。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：「マイスタイル」の例に似たクリップにも説明文が付くようになりました。

</details>

## [1.2.31] - 2026-11-08
Every swear gets its bleep: missed swears are found, every clip is checked after it is made, and you see a bleep report.

### New
- **Bleep report.** Each clip shows how many swears it bleeped ("7 bleeps ✅"). In Pro you get the
  list with a play button for each swear.
- **Checked after every clip.** SharkyClips listens to the finished clip. If a swear can still be
  heard, the bleep gets wider and the clip is made again (at most twice). If one is still left,
  the clip says "2 swears could not be bleeped", and one-click and automatic uploads wait until
  you listen and press "I listened, it's OK".

### Improved
- **More bleeps by default.** Strict is the default for every format, and "Check swears strictly"
  is on in Easy mode. Likely swears are bleeped from a lower score, for every speaker. A few more
  false bleeps are possible, but missed swears are much rarer.

### Fixed
- **Every swear gets its bleep.** Often only one swear of a clip was bleeped and the others
  could be heard. Four reasons, all fixed:
  - Swears the way the transcript writes them fast ("Amanakoyim", "iskiyim", "Skiyim", "pıç",
    "aman akayım", "Deepfuck") were missed. They are found now, and two-word swears get both
    words bleeped.
  - Clips made with an older version were kept as they were. A clip is now made again whenever
    anything about its bleeps changes, so your existing clips get the new bleeps.
  - The hook flash at the start, the slow-motion replay and best-of videos played the original
    sound, swears included. They are bleeped the same way now.
  - The check after making a clip only ran in some places. It runs after every clip now: Easy,
    Pro, the queue, exports, A/B hooks, stories and loops.
- **Swears in titles, descriptions and captions are always censored** ("S*KTİR") before an upload.

<!-- lang:tr -->
**Türkçe**

Her küfür bip'ini alıyor: kaçan küfürler bulunuyor, her klip yapıldıktan sonra kontrol ediliyor ve bir bip raporu görüyorsun.

### Yeni
- **Bip raporu.** Her klip kaç küfrü bip'lediğini gösteriyor ("7 bip ✅"). Pro'da her küfür için
  bir dinle düğmesiyle liste var.
- **Her klipten sonra kontrol.** SharkyClips bitmiş klibi dinliyor. Bir küfür hâlâ duyuluyorsa
  bip genişliyor ve klip yeniden yapılıyor (en fazla iki kez). Yine de kalan olursa klipte
  "2 küfür biplenemedi" yazıyor; tek tıkla ve otomatik yükleme, sen dinleyip "Dinledim, sorun yok"
  diyene kadar bekliyor.

### İyileştirmeler
- **Varsayılan olarak daha çok bip.** Her formatta varsayılan Sıkı; Kolay modda "Küfürleri sıkı
  denetle" açık. Büyük ihtimalle küfür olan kelimeler, her konuşanda, daha düşük bir puandan
  itibaren bip'leniyor. Arada fazladan bir bip olabilir ama kaçan küfür çok daha nadir.

### Düzeltmeler
- **Her küfür bip'leniyor.** Bir klipte çoğu zaman tek küfür bip'leniyor, diğerleri duyuluyordu.
  Dört sebebi vardı, hepsi düzeltildi:
  - Hızlı söylenip yazıya öyle geçen küfürler ("Amanakoyim", "iskiyim", "Skiyim", "pıç",
    "aman akayım", "Deepfuck") kaçıyordu. Artık yakalanıyor; iki kelimelik küfürlerde iki kelime
    de bip'leniyor.
  - Eski sürümle yapılmış klipler olduğu gibi kalıyordu. Artık bip'leriyle ilgili herhangi bir şey
    değişince klip yeniden yapılıyor, yani mevcut kliplerin de yeni bip'leri alıyor.
  - Baştaki açılış flaşı, ağır çekim tekrar ve en iyiler videoları orijinal sesi, küfürleriyle
    birlikte çalıyordu. Artık onlar da aynı şekilde bip'leniyor.
  - Klip yapıldıktan sonraki kontrol sadece bazı yerlerde çalışıyordu. Artık her klipten sonra
    çalışıyor: Kolay mod, Pro, kuyruk, dışa aktarmalar, A/B kancaları, hikâyeler ve döngüler.
- **Başlık, açıklama ve altyazı metinlerindeki küfürler** yüklemeden önce her zaman sansürleniyor
  ("S*KTİR").

<details><summary>Español</summary>

<!-- lang:es -->
Cada palabrota recibe su pitido: se encuentran las que se escapaban, cada clip se revisa al terminar y ves un informe de pitidos.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Todo palavrão ganha seu bipe: os que escapavam são achados, cada clipe é conferido no final e você vê um relatório de bipes.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Jedes Schimpfwort bekommt seinen Piepton: Übersehene werden gefunden, jeder Clip wird danach geprüft, und du siehst einen Piep-Bericht.

- Jedes Schimpfwort wird überpiept: auch schnell gesprochene Formen, die Hook-Flash, die Zeitlupen-Wiederholung und Best-of-Videos.
- Ältere Clips werden neu gemacht, sobald sich etwas an ihren Pieps ändert.
- Neu: Piep-Bericht pro Clip („7 Pieps ✅“). Nach jedem Clip wird nachgehört; bleibt etwas hörbar, wartet der Upload auf dich.
- Strenge Prüfung ist überall Standard; Schimpfwörter in Titeln und Beschreibungen werden immer zensiert.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Chaque gros mot a son bip : ceux qui passaient sont trouvés, chaque clip est vérifié après sa création et tu vois un rapport des bips.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Minden káromkodás megkapja a sípolást: a kimaradtakat is megtalálja, minden klipet ellenőriz utána, és sípolási jelentést látsz.

- Minden káromkodás kisípolva: a gyorsan kimondott alakok, a nyitó villanás, a lassított visszajátszás és a legjobb pillanatok videók is.
- A régebbi klipek újrakészülnek, ha bármi változik a sípolásaikon.
- Új: sípolás-jelentés klipenként („7 sípolás ✅”). Minden klip után újrahallgatás; ha valami hallható marad, a feltöltés rád vár.
- A szigorú ellenőrzés mindenhol alapértelmezett; a címekben és leírásokban a káromkodás mindig cenzúrázva.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Каждый мат запикан: пропущенные слова находятся, каждый клип проверяется после создания, и вы видите отчёт о запикивании.

- Запикивается каждый мат: и быстро сказанные формы, и вспышка-хук, и замедленный повтор, и видео с лучшими моментами.
- Старые клипы делаются заново, как только меняется что-то в их запикивании.
- Новое: отчёт о запикивании для каждого клипа («7 запикиваний ✅»). После каждого клипа он прослушивается; если что-то слышно, загрузка ждёт вас.
- Строгая проверка по умолчанию везде; мат в названиях и описаниях всегда скрывается.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
كل شتيمة تحصل على صافرتها: تُكتشف الشتائم الفائتة، ويُفحص كل مقطع بعد صنعه، وترى تقرير الصافرات.

- يُغطّى على كل شتيمة بالصفير: حتى الصيغ السريعة، ووميض البداية، والإعادة البطيئة، وفيديوهات أفضل اللحظات.
- تُصنع المقاطع القديمة من جديد عندما يتغير أي شيء في صفيرها.
- جديد: تقرير صفير لكل مقطع ("7 صفير ✅"). يُستمع لكل مقطع بعد صنعه؛ إن بقي شيء مسموعًا ينتظر الرفع موافقتك.
- الفحص الصارم افتراضي في كل مكان، والشتائم في العناوين والأوصاف تُخفى دائمًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
每个脏话都会被哔掉：漏掉的会被找到，每个剪辑完成后都会检查，并显示哔声报告。

- 每一处脏话都会消音：包括说得很快的写法、开头闪回、慢动作回放和精彩合集视频。
- 只要消音相关的内容有变化，旧片段就会重新制作。
- 新增：每个片段的消音报告（"7 处消音 ✅"）。每个片段做完后都会再听一遍；若仍能听到，上传会等你确认。
- 所有格式默认严格检查；标题和简介中的脏话始终打码。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
すべての汚い言葉にピー音を。見逃しを検出し、作成後に全クリップを確認、ピー音レポートも表示します。

</details>

## [1.2.30] - 2026-11-08
Fixed: many more new titles survive, descriptions no longer copy your examples, and every clip gets a description.

### Fixed
- **Many more new titles survive.** In My style almost every title ends with the same bracket,
  like "(DELTA FORCE)". That alone made new titles look like repeats of other clips' titles, so
  many clips kept their old titles and got no new description. Titles are now compared without
  the bracket and the emojis.
- **Descriptions never copy your examples.** A description that repeats sentences from your own
  example descriptions is written again. Only your fixed lines (the like / subscribe line and
  "İyi seyirler!") may repeat.
- **Every clip gets a description**, even when it keeps older titles.
- **Cleaner tags.** Search phrases with broken or invented words ("leof legends") are left out.
- **Names are written the same way** in capitals every time (DARİUS, not DARIUS), and "nihai
  yetenekle" and "dubl kill" become "ultiyle" and "double kill".

<!-- lang:tr -->
**Türkçe**

Düzeltildi: çok daha fazla yeni başlık korunuyor, açıklamalar artık örneklerini kopyalamıyor ve her klip açıklama alıyor.

### Düzeltmeler
- **Çok daha fazla yeni başlık kalıyor.** Benim tarzımda neredeyse her başlık "(DELTA FORCE)" gibi
  aynı parantezle bitiyor. Sırf bu yüzden yeni başlıklar başka kliplerin başlıklarının tekrarı
  sanılıyor, birçok klip eski başlıklarında kalıp yeni açıklama alamıyordu. Başlıklar artık
  parantez ve emojiler olmadan karşılaştırılıyor.
- **Açıklamalar örneklerini asla kopyalamıyor.** Kendi örnek açıklamalarındaki cümleleri tekrar
  eden bir açıklama yeniden yazılıyor. Sadece sabit satırların (beğen / abone ol satırı ve
  "İyi seyirler!") tekrar edebilir.
- **Her klip bir açıklama alıyor**, eski başlıklarını korusa bile.
- **Daha temiz etiketler.** Bozuk ya da uydurma kelimeli arama ifadeleri ("leof legends") çıkarılıyor.
- **İsimler büyük harfle hep aynı yazılıyor** (DARIUS değil DARİUS); "nihai yetenekle" ve "dubl kill"
  artık "ultiyle" ve "double kill" oluyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: sobreviven muchos más títulos nuevos, las descripciones ya no copian tus ejemplos y cada clip recibe descripción.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: muito mais títulos novos sobrevivem, as descrições não copiam mais seus exemplos e todo clipe ganha descrição.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Viel mehr neue Titel bleiben erhalten, Beschreibungen kopieren deine Beispiele nicht mehr, und jeder Clip bekommt eine Beschreibung.

- Viel mehr neue Titel bleiben: die gleiche Klammer wie „(DELTA FORCE)“ am Ende zählt nicht mehr als Wiederholung.
- Beschreibungen kopieren deine Beispiele nie; jeder Clip bekommt eine Beschreibung.
- Sauberere Tags ohne kaputte Wörter; Namen in Großbuchstaben immer gleich geschrieben.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : bien plus de nouveaux titres sont gardés, les descriptions ne copient plus tes exemples et chaque clip a une description.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: sokkal több új cím marad meg, a leírások már nem másolják a példáidat, és minden klip kap leírást.

- Sokkal több új cím marad meg: az azonos zárójel a végén, mint „(DELTA FORCE)”, már nem számít ismétlésnek.
- A leírások soha nem másolják a példáidat; minden klip kap leírást.
- Tisztább címkék hibás szavak nélkül; a nevek nagybetűvel mindig egyformán íródnak.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: сохраняется гораздо больше новых заголовков, описания больше не копируют ваши примеры, и у каждого клипа есть описание.

- Сохраняется гораздо больше новых названий: одинаковая скобка в конце вроде «(DELTA FORCE)» больше не считается повтором.
- Описания никогда не копируют ваши примеры; у каждого клипа есть описание.
- Более чистые теги без сломанных слов; имена заглавными всегда пишутся одинаково.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: تبقى عناوين جديدة أكثر بكثير، ولم تعد الأوصاف تنسخ أمثلتك، ويحصل كل مقطع على وصف.

- تبقى عناوين جديدة أكثر بكثير: القوس نفسه في النهاية مثل "(DELTA FORCE)" لم يعد يُعد تكرارًا.
- الأوصاف لا تنسخ أمثلتك أبدًا، ويحصل كل مقطع على وصف.
- علامات أنظف دون كلمات مكسورة، وتُكتب الأسماء بالأحرف الكبيرة بالطريقة نفسها دائمًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：保留下来的新标题多了很多，描述不再照抄你的示例，每个剪辑都有描述。

- 保留下来的新标题多得多：标题结尾相同的括号（如"(DELTA FORCE)"）不再被当作与其他片段重复，很多片段不会再停留在旧标题上。
- 简介绝不照抄你的示例；即使保留旧标题，每个片段也都会有简介。
- 标签更干净，不再有拼错或编造的词；名字大写时总是写成同一种形式。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：新しいタイトルが残りやすくなり、説明文が例をコピーしなくなり、すべてのクリップに説明文が付きます。

</details>

## [1.2.29] - 2026-11-08
Fixed: full-video texts always get titles, labels no longer slip into titles, and a title with a swear never comes first.

### Fixed
- **Full video texts always get titles.** Titles for the whole match were thrown out for naming
  the same champions as the clips' titles, so a project could end up with none. Now they only
  have to differ from each other.
- **No "[LONG VIDEO]" in titles.** The AI sometimes copied a label from its instructions to the
  front of a title. It is now removed.
- **A title with a swear never comes first.** The first title is the one that gets uploaded, so
  titles with a censored swear now always go to the end of the list.
- **English gaming words in capitals** are read correctly ("FULL CLIP", "REVIVE"), so good
  titles are no longer rejected as misspelled.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: tam video metinleri her zaman başlık alıyor, etiketler artık başlıklara karışmıyor ve küfürlü bir başlık asla ilk sırada olmuyor.

### Düzeltmeler
- **Tam video metinleri her zaman başlık alıyor.** Maçın tamamı için yazılan başlıklar, kliplerin
  başlıklarıyla aynı şampiyonları andığı için eleniyor, proje başlıksız kalabiliyordu. Artık
  sadece birbirinden farklı olmaları gerekiyor.
- **Başlıklarda "[LONG VİDEO]" yok.** Yapay zekâ bazen talimatlarındaki bir etiketi başlığın
  başına kopyalıyordu. Artık siliniyor.
- **Küfürlü başlık asla ilk sırada değil.** Yüklenen başlık ilk başlık olduğu için sansürlü küfür
  içeren başlıklar artık hep listenin sonuna gidiyor.
- **Büyük harfle yazılmış İngilizce oyun kelimeleri** ("FULL CLIP", "REVIVE") doğru okunuyor;
  iyi başlıklar artık yanlış yazılmış sanılıp elenmiyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: los textos del vídeo completo siempre tienen títulos, ya no se cuelan etiquetas en los títulos y un título con palabrota nunca va primero.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: textos do vídeo completo sempre ganham títulos, rótulos não entram mais nos títulos e um título com palavrão nunca vem primeiro.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Texte für das ganze Video bekommen immer Titel, Markierungen rutschen nicht mehr in Titel, und ein Titel mit Schimpfwort steht nie zuerst.

- Texte fürs ganze Video bekommen immer Titel: sie werden nicht mehr verworfen, nur weil sie
  dieselben Champions nennen wie die Clips.
- Kein „[LONG VIDEO]“ mehr am Titelanfang; ein Titel mit (zensiertem) Fluch steht nie an erster Stelle.
- Englische Gaming-Wörter in Großbuchstaben werden richtig erkannt.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : les textes de la vidéo complète ont toujours des titres, les étiquettes ne se glissent plus dans les titres et un titre avec un gros mot n'est jamais en premier.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a teljes videó szövegei mindig kapnak címet, címkék már nem csúsznak a címekbe, és káromkodást tartalmazó cím sosem kerül előre.

- A teljes videó szövegei mindig kapnak címet: már nem dobja el őket, csak mert ugyanazokat a
  hősöket említik, mint a klipek.
- Nincs több „[LONG VIDEO]” a cím elején; káromkodást tartalmazó cím soha nem kerül az első helyre.
- A nagybetűs angol játékos szavakat helyesen ismeri fel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: тексты для полного видео всегда получают заголовки, служебные метки не попадают в заголовки, а заголовок с матом никогда не идёт первым.

- Тексты для всего видео всегда получают названия: их больше не отбрасывают за то, что они
  называют тех же чемпионов, что и клипы.
- Больше никакого «[LONG VIDEO]» в начале названия; название с (скрытым) матом никогда не идёт первым.
- Английские игровые слова заглавными буквами распознаются правильно.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: نصوص الفيديو الكامل تحصل دائمًا على عناوين، ولم تعد التسميات تتسلل إلى العناوين، ولا يأتي عنوان فيه شتيمة أولًا أبدًا.

- تحصل نصوص الفيديو الكامل دائمًا على عناوين: لم تعد تُستبعد لأنها تذكر نفس الأبطال المذكورين
  في عناوين المقاطع.
- لا مزيد من "[LONG VIDEO]" في بداية العنوان؛ والعنوان الذي فيه شتيمة مخفية لا يأتي أولًا أبدًا.
- تُقرأ كلمات الألعاب الإنجليزية المكتوبة بأحرف كبيرة بشكل صحيح.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：完整视频文案总会有标题，标签不再混进标题，含脏话的标题绝不会排在第一。

- 完整视频文案总能得到标题：不会再因为和片段标题提到同样的英雄而被全部淘汰，导致没有标题。
- 标题开头不再出现"[LONG VIDEO]"；带有（已打码）脏话的标题永远不会排在第一个，因为第一个标题就是上传用的标题。
- 大写的英文游戏词（如 FULL CLIP、REVIVE）现在能被正确识别，好标题不再被误判为拼写错误。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：フル動画のテキストに必ずタイトルが付き、ラベルがタイトルに混ざらず、汚い言葉入りのタイトルが先頭に来ることはありません。

</details>

## [1.2.28] - 2026-11-08
My style: titles, descriptions, hashtags and tags are now written in your own style, with gamer Turkish and better quality when the PC is free.

### New
- **My style.** Studio > Brand kit > My style holds your own titles, descriptions, hashtags and
  tags that got views (Shorts and long videos, per game). Gaming texts are now written exactly in
  that style: ALL CAPS titles with "!" or "?!", two fitting emojis and a short (CONTEXT) at the
  end, real details from the clip (names, scores like 55 KILL, 1v9). Your examples are used for
  the same game and format first and are never copied. Titles you like (👍) are added by
  themselves. Your style stays on your PC only.
- **Shorts that hook in the first words.** Shorts titles often open with a real line from the
  clip in quotes ("NASIL ÖLDÜM LAN?!"), checked against what was really said. The hook always
  comes first, because YouTube shows only about 40 characters. Swears are always censored
  (S*KTİR), never written out, and only one title per clip may contain one.
- **Descriptions in your layout.** Shorts: 2-3 short lines with emojis and a comment question
  ending with 👇, no socials block (you can turn it on). Long videos: a hook opener, one story
  paragraph about the match, "İyi seyirler!", a like / subscribe / comment line, your socials,
  then the hashtags.
- **Hashtags and tags like yours.** 10-12 hashtags (game, game TR, champions or operators, mood,
  format, your channel tag, #GamingTR) and 10-15 natural search phrases with your name. Never
  another game.
- **Full video texts.** A new button on the project page writes the title, description, hashtags
  and tags for uploading the whole stream as a long 16:9 video. Best-of videos use your
  long-video style too.
- **Every result is checked.** Caps, emoji count, censored swears, the right game, real quotes and
  length are checked, and anything that fails is written again.

### Improved
- **Gamer Turkish.** Gaming words stay the way streamers write them (kill, revive, ulti, gank,
  tilt, clutch...): no more "iki katil" or "revize". Spelling and vowel harmony are fixed
  ("kurtarırdın", "Delta Force'ta"). Words you correct in a title or description are remembered
  and fixed from then on.
- **Better quality when the PC is free.** While you're away or in Turbo mode, titles and
  descriptions use the bigger AI model and more drafts.

### Fixed
- The word "şikayet" (complaint) is no longer treated as a swear and bleeped.

<!-- lang:tr -->
**Türkçe**

Tarzım: başlıklar, açıklamalar, hashtag'ler ve etiketler artık senin tarzında yazılıyor; oyuncu Türkçesi ve bilgisayar boşken daha iyi kalite.

### Yeni
- **Benim tarzım.** Stüdyo > Marka kiti > Benim tarzım bölümünde izlenme getiren kendi
  başlıkların, açıklamaların, hashtag'lerin ve etiketlerin duruyor (Shorts ve uzun videolar, oyun
  oyun). Oyun metinleri artık tam bu tarzda yazılıyor: "!" ya da "?!" ile biten TAMAMI BÜYÜK
  HARF başlıklar, iki uygun emoji, sonda kısa bir (BAĞLAM), klipten gerçek detaylar (isimler,
  55 KILL gibi skorlar, 1v9). Örneklerin önce aynı oyun ve format için kullanılıyor, asla
  kopyalanmıyor. Beğendiğin (👍) başlıklar kendiliğinden ekleniyor. Tarzın sadece senin
  bilgisayarında duruyor.
- **İlk kelimelerde yakalayan Shorts.** Shorts başlıkları çoğu zaman klipten tırnak içinde gerçek
  bir sözle açılıyor ("NASIL ÖLDÜM LAN?!"); sözün gerçekten söylendiği kontrol ediliyor. YouTube
  yalnızca 40 karakter kadar gösterdiği için kanca her zaman başta. Küfürler her zaman sansürlü
  (S*KTİR), asla açık yazılmıyor ve bir klipte en fazla bir başlıkta geçebiliyor.
- **Senin düzeninde açıklamalar.** Shorts: emojili 2-3 kısa satır ve 👇 ile biten bir yorum
  sorusu, sosyal medya bloğu yok (istersen açabilirsin). Uzun videolar: kanca cümlesi, maçı
  anlatan tek paragraf, "İyi seyirler!", beğen / abone ol / yorum satırı, sosyal medya hesapların,
  sonra hashtag'ler.
- **Seninki gibi hashtag ve etiketler.** 10-12 hashtag (oyun, oyun TR, şampiyonlar ya da
  operatörler, mod, format, kanal hashtag'in, #GamingTR) ve adınla birlikte 10-15 doğal arama
  ifadesi. Asla başka bir oyun yok.
- **Tam video metinleri.** Proje sayfasındaki yeni düğme, yayının tamamını uzun 16:9 video olarak
  yüklemek için başlık, açıklama, hashtag ve etiketleri yazıyor. Best-of videolar da uzun video
  tarzını kullanıyor.
- **Her sonuç kontrol ediliyor.** Büyük harf, emoji sayısı, sansürlü küfür, doğru oyun, gerçek
  alıntı ve uzunluk kontrol ediliyor; uymayan her şey yeniden yazılıyor.

### İyileştirmeler
**İyileştirildi**
- **Oyuncu Türkçesi.** Oyun kelimeleri yayıncıların yazdığı gibi kalıyor (kill, revive, ulti,
  gank, tilt, clutch...): artık "iki katil" ya da "revize" yok. Yazım ve ünlü uyumu düzeltiliyor
  ("kurtarırdın", "Delta Force'ta"). Bir başlıkta ya da açıklamada düzelttiğin kelimeler
  hatırlanıyor ve bundan sonra hep düzeltiliyor.
- **Bilgisayar boştayken daha iyi kalite.** Sen yokken ya da Turbo modunda başlık ve açıklamalar
  daha büyük yapay zekâ modeliyle ve daha çok taslakla yazılıyor.

### Düzeltmeler
- "Şikayet" kelimesi artık küfür sanılıp bipleme yapılmıyor.

<details><summary>Español</summary>

<!-- lang:es -->
Mi estilo: títulos, descripciones, hashtags y etiquetas ahora se escriben en tu propio estilo, con mejor calidad cuando el PC está libre.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Meu estilo: títulos, descrições, hashtags e tags agora são escritos no seu estilo, com qualidade melhor quando o PC está livre.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Mein Stil: Titel, Beschreibungen, Hashtags und Tags werden jetzt in deinem eigenen Stil geschrieben, mit besserer Qualität, wenn der PC frei ist.

- Neu: **Mein Stil** (Studio > Brand-Kit). Deine eigenen erfolgreichen Titel, Beschreibungen,
  Hashtags und Tags; Gaming-Texte werden genau in diesem Stil geschrieben und geprüft, nie kopiert.
- Shorts-Titel beginnen oft mit einem echten Zitat aus dem Clip, der Hook steht immer vorn,
  Flüche sind immer zensiert.
- Neu: **Texte fürs ganze Video** (16:9) auf der Projektseite; Best-of-Videos nutzen deinen Stil.
- Gaming-Wörter werden nie übersetzt, Korrekturen werden gelernt; mehr Qualität, wenn der PC frei ist.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Mon style : titres, descriptions, hashtags et tags sont maintenant écrits dans ton style, avec une meilleure qualité quand le PC est libre.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Saját stílus: a címek, leírások, hashtagek és címkék most a te stílusodban készülnek, és jobb minőségben, amikor a gép szabad.

- Új: **Saját stílusom** (Stúdió > Márkakészlet). A saját bevált címeid, leírásaid, hashtagjeid és
  címkéid; a játékos szövegek pontosan ebben a stílusban készülnek és ellenőrzöttek, soha nem másolva.
- A Shorts címek gyakran valódi idézettel indulnak a klipből, a horog mindig elöl van, a
  káromkodás mindig cenzúrázott.
- Új: **Teljes videó szövegei** (16:9) a projektoldalon; a best-of videók is a stílusodat követik.
- A játékos szavakat soha nem fordítja le, a javításaidat megtanulja; jobb minőség, ha a gép szabad.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
«Мой стиль»: заголовки, описания, хэштеги и теги теперь пишутся в вашем стиле, а когда ПК свободен — ещё качественнее.

- Новое: **Мой стиль** (Студия > Бренд-кит). Ваши удачные названия, описания, хештеги и теги;
  игровые тексты пишутся точно в этом стиле и проверяются, без копирования.
- Названия Shorts часто начинаются с настоящей цитаты из клипа, зацепка всегда в начале, мат
  всегда скрыт звёздочками.
- Новое: **Тексты для всего видео** (16:9) на странице проекта; best-of тоже в вашем стиле.
- Игровые слова не переводятся, ваши исправления запоминаются; выше качество, когда ПК свободен.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
"أسلوبي": تُكتب العناوين والأوصاف والوسوم والكلمات المفتاحية الآن بأسلوبك، وبجودة أعلى عندما يكون الجهاز متفرغًا.

- جديد: **أسلوبي** (الاستوديو > عُدة العلامة). عناوينك وأوصافك ووسومك الناجحة؛ تُكتب نصوص الألعاب
  بهذا الأسلوب تمامًا وتُفحص، دون نسخ أبدًا.
- تبدأ عناوين Shorts غالبًا باقتباس حقيقي من المقطع، والجذب دائمًا في البداية، والشتائم مخفية دائمًا.
- جديد: **نصوص الفيديو الكامل** (16:9) في صفحة المشروع؛ وفيديوهات best-of بأسلوبك أيضًا.
- كلمات الألعاب لا تُترجم، وتُحفظ تصحيحاتك؛ جودة أعلى عندما يكون الجهاز متفرغًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
我的风格：标题、描述、话题标签和标签现在都按你的风格来写，电脑空闲时质量更高。

- 新增：**我的风格**（工作室 > 品牌套件）。保存你自己带来播放量的标题、简介、话题标签和标签；游戏文案完全按这个风格写并逐条检查，绝不照抄。
- Shorts 标题常以片段里的真实原话开头，钩子总在最前，脏话一律打码。
- 新增：项目页的**完整视频文案**（16:9）；best-of 视频也用你的风格。
- 游戏词不再被翻译，你的修改会被记住；电脑空闲时质量更高。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
マイスタイル：タイトル・説明文・ハッシュタグ・タグをあなたのスタイルで作成。PC が空いているときはさらに高品質に。

</details>

## [1.2.27] - 2026-11-08
Fixed: every clip gets a description, clips keep enough titles after rewrites, and Cancel works correctly on Linux.

### Fixed
- **Every clip gets a description.** When the AI's notes about a clip named a player whose name
  has a swear word in it, every description it wrote was rejected and the clip ended up with
  none. Such names are now left out before the description is written.
- **Enough titles, even after several rewrites.** SharkyClips now remembers a clip's original
  titles. If a later rewrite throws out most of the new ideas, the clip falls back on those
  instead of keeping only one or two titles.
- **Cancel on Linux.** A process stopped by Cancel could be reported as finished successfully on
  Linux. It is now always reported as stopped.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: her klip açıklama alıyor, klipler yeniden yazmalardan sonra yeterli başlığı koruyor ve İptal Linux'ta doğru çalışıyor.

### Düzeltmeler
- **Her klibin bir açıklaması var.** Yapay zekânın klip notlarında adında küfür geçen bir oyuncu
  olduğunda yazdığı her açıklama reddediliyor, klip açıklamasız kalıyordu. Artık bu isimler
  açıklama yazılmadan önce çıkarılıyor.
- **Birkaç kez yeniden yazılsa da yeterli başlık.** SharkyClips artık bir klibin ilk başlıklarını
  hatırlıyor. Sonraki bir yeniden yazımda yeni fikirlerin çoğu elenirse klip bir iki başlıkla
  kalmıyor, bu başlıklara geri dönüyor.
- **Linux'ta İptal.** İptal ile durdurulan bir işlem Linux'ta başarıyla bitmiş gibi
  görünebiliyordu. Artık her zaman durduruldu olarak gösteriliyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: cada clip recibe descripción, los clips conservan títulos suficientes tras reescribir y Cancelar funciona bien en Linux.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: todo clipe ganha descrição, os clipes mantêm títulos suficientes depois de reescrever e Cancelar funciona certo no Linux.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Jeder Clip bekommt eine Beschreibung, Clips behalten nach Neuschreiben genug Titel, und Abbrechen funktioniert unter Linux richtig.

- Jeder Clip bekommt wieder eine Beschreibung, auch wenn ein Spielername ein Schimpfwort enthält.
- Clips behalten auch nach mehrmaligem Neuschreiben genug Titel: SharkyClips merkt sich die
  ursprünglichen Titel.
- Linux: Ein mit „Abbrechen“ gestoppter Prozess wird nicht mehr als erfolgreich gemeldet.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : chaque clip a une description, les clips gardent assez de titres après réécriture, et Annuler marche bien sous Linux.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: minden klip kap leírást, újraírás után is marad elég cím, és a Mégse Linuxon is jól működik.

- Minden klip újra kap leírást, akkor is, ha egy játékos nevében káromkodás van.
- A klipeknek többszöri újraírás után is marad elég címük: a SharkyClips megjegyzi az eredeti
  címeket.
- Linux: a Mégse gombbal leállított folyamat már nem jelenik meg sikeresen befejezettként.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: у каждого клипа есть описание, после переписывания остаётся достаточно заголовков, а «Отмена» корректно работает в Linux.

- У каждого клипа снова есть описание, даже если в имени игрока есть ругательство.
- После нескольких переписываний у клипа остаётся достаточно названий: SharkyClips запоминает
  исходные названия.
- Linux: процесс, остановленный кнопкой «Отмена», больше не считается успешно завершённым.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: يحصل كل مقطع على وصف، وتحتفظ المقاطع بعناوين كافية بعد إعادة الكتابة، ويعمل الإلغاء بشكل صحيح على Linux.

- يحصل كل مقطع على وصف من جديد، حتى عندما يحتوي اسم أحد اللاعبين على كلمة نابية.
- يحتفظ كل مقطع بعناوين كافية حتى بعد إعادة الكتابة عدة مرات، إذ يتذكر SharkyClips العناوين
  الأصلية.
- لينكس: العملية التي توقفت بزر الإلغاء لم تعد تظهر كأنها انتهت بنجاح.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：每个剪辑都有描述，重写后仍保留足够标题，Linux 上“取消”也能正确工作。

- 每个片段都会重新获得简介，即使某位玩家的名字里含有脏话也不例外，不会再出现没有简介的片段。
- 多次重新撰写之后，片段仍然保留足够的标题：SharkyClips 会记住最初的标题，新标题被淘汰太多时会用它们补足。
- Linux：用"取消"停止的进程不再被错误地显示为成功完成，现在始终显示为已停止。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：すべてのクリップに説明文が付き、書き直し後もタイトルが十分残り、Linux でキャンセルが正しく動きます。

</details>

## [1.2.26] - 2026-11-07
Fixed: no swear words hidden in player names, no clip timings in titles, and always enough titles.

### Fixed
- **No swear words hidden inside names.** A player name with a swear word inside it could end up
  in a title or description. Such names are now caught too.
- **No clip timings in titles or descriptions.** Titles sometimes said things like "in the last
  5.7 seconds" or "+7 seconds", taken from SharkyClips' own notes, not from the video. Those are
  now rejected.
- **Always enough titles.** When rewriting an existing project's texts, a clip whose new ideas
  were almost all rejected now keeps its best old titles instead of ending up with just one.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: oyuncu adlarında gizli küfür yok, başlıklarda klip süreleri yok ve her zaman yeterli başlık var.

### Düzeltmeler
- **İsimlerin içine gizlenmiş küfür yok.** İçinde küfür geçen bir oyuncu adı başlığa ya da
  açıklamaya girebiliyordu. Artık bunlar da yakalanıyor.
- **Başlık ve açıklamalarda klip zamanı yok.** Başlıklar bazen "son 5.7 saniyede" ya da
  "+7 saniyede" gibi ifadeler kullanıyordu; bunlar videodan değil SharkyClips'in kendi
  notlarından geliyordu. Artık reddediliyor.
- **Her zaman yeterli başlık.** Mevcut bir projenin metinleri yeniden yazılırken yeni fikirlerinin
  neredeyse hepsi elenen bir klip artık tek başlıkla kalmıyor, en iyi eski başlıklarını koruyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: no hay palabrotas escondidas en nombres de jugadores, ni tiempos del clip en los títulos, y siempre hay títulos suficientes.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: nada de palavrões escondidos em nomes de jogadores, nada de tempos do clipe nos títulos, e sempre títulos suficientes.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Keine Schimpfwörter in Spielernamen, keine Clip-Zeiten in Titeln, und immer genug Titel.

- Keine in Namen versteckten Schimpfwörter und keine internen Clip-Zeiten („+7 Sekunden“) mehr in
  Titeln und Beschreibungen; Clips behalten beim Neuschreiben immer genug Titel.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : plus de gros mots cachés dans les pseudos, plus de durées du clip dans les titres, et toujours assez de titres.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: nincs több játékosnévbe rejtett káromkodás, nincsenek klipidők a címekben, és mindig van elég cím.

- Nincs több nevekbe rejtett káromkodás és belső klipidő („+7 másodperc”) a címekben és
  leírásokban; újraíráskor a klipeknek mindig marad elég címe.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: никакого мата в никах игроков, никаких таймингов клипа в заголовках, и заголовков всегда достаточно.

- Больше никаких ругательств, спрятанных в именах, и внутренних отметок времени («+7 секунд») в
  названиях и описаниях; при переписывании у клипа всегда остаётся достаточно названий.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: لا شتائم مخفية في أسماء اللاعبين، ولا توقيتات المقطع في العناوين، ودائمًا عناوين كافية.

- لا شتائم مخفية داخل الأسماء ولا أوقات المقطع الداخلية ("+7 ثوان") في العناوين والأوصاف بعد الآن؛
  ويحتفظ كل مقطع دائما بعناوين كافية عند إعادة الكتابة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：玩家名里不再藏脏话，标题里不再出现剪辑时间，标题数量始终够用。

- 标题和简介中不再出现藏在名字里的脏话和内部片段时间（"+7 秒"）；重新撰写时每个片段都会保留足够的标题。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：プレイヤー名に隠れた汚い言葉や、タイトル内のクリップ時間がなくなり、タイトル数も常に十分です。

</details>

## [1.2.25] - 2026-11-07
No more hashtags from other games: the game is decided once per video. Plus better hashtags, real YouTube tags and livelier descriptions.

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

### Fixed
- **No more hashtags from other games.** A League of Legends clip could get hashtags like
  #Warzone or #CallofDuty. The AI guessed the game again for every single clip, and on a stream
  without a clear title it sometimes guessed wrong (Valorant, Call of Duty, Overwatch...). Now the
  game is decided once for the whole video (the game you picked, the game screen, the title and
  what you say) and every title, description, hashtag and tag is about that game only. Anything
  that names a different game is thrown out. When the game is unknown, only general gaming
  hashtags are used, never a guess.

<!-- lang:tr -->
**Türkçe**

Artık başka oyunların hashtag'leri yok: oyun her video için bir kez belirleniyor. Ayrıca daha iyi hashtag'ler, gerçek YouTube etiketleri ve daha canlı açıklamalar.

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

### Düzeltmeler
- **Artık başka oyunların hashtag'leri yok.** Bir League of Legends klibine #Warzone ya da
  #CallofDuty gibi hashtag'ler gelebiliyordu. Yapay zeka oyunu her klip için yeniden tahmin
  ediyordu ve başlığı belli olmayan bir yayında bazen yanlış tahmin ediyordu (Valorant, Call of
  Duty, Overwatch...). Artık oyun tüm video için bir kez belirleniyor (senin seçtiğin oyun, oyun
  ekranı, başlık ve söylediklerin) ve her başlık, açıklama, hashtag ve etiket sadece o oyunla
  ilgili. Başka bir oyunun adını geçiren her şey atılıyor. Oyun bilinmiyorsa sadece genel oyun
  hashtag'leri kullanılıyor, asla tahmin yok.

<details><summary>Español</summary>

<!-- lang:es -->
Se acabaron los hashtags de otros juegos: el juego se decide una vez por vídeo. Además, mejores hashtags, etiquetas reales de YouTube y descripciones más vivas.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Chega de hashtags de outros jogos: o jogo é decidido uma vez por vídeo. E ainda hashtags melhores, tags reais do YouTube e descrições mais vivas.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Keine Hashtags anderer Spiele mehr: Das Spiel wird einmal pro Video bestimmt. Dazu bessere Hashtags, echte YouTube-Tags und lebendigere Beschreibungen.

- **Keine Hashtags anderer Spiele mehr:** das Spiel wird einmal für das ganze Video bestimmt;
  Titel, Beschreibungen, Hashtags und Tags handeln nur von diesem Spiel (unbekanntes Spiel: nur
  allgemeine Gaming-Hashtags).
- **Neu:** Hashtags in fester Reihenfolge (Kanal, #shorts, Spiel, 2-4 zum Clip), 10-20 echte
  YouTube-Tags, lebendigere Beschreibungen mit einer Frage am Ende, Social-Media-Block aus dem
  Brand-Kit, stärkere Titel mit 1-2 Schlüsselwörtern in GROSSBUCHSTABEN, Studio > Spiele.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Fini les hashtags d'autres jeux : le jeu est choisi une fois par vidéo. Et aussi de meilleurs hashtags, de vrais tags YouTube et des descriptions plus vivantes.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Nincs több más játékhoz tartozó hashtag: a játékot videónként egyszer dönti el. Emellett jobb hashtagek, valódi YouTube-címkék és élénkebb leírások.

- **Nincs több más játékból származó hashtag:** a játékot egyszer, az egész videóra határozzuk
  meg; a címek, leírások, hashtagek és címkék csak erről a játékról szólnak (ismeretlen játéknál
  csak általános gamer hashtagek).
- **Új:** hashtagek fix sorrendben (csatorna, #shorts, játék, 2-4 a klipről), 10-20 valódi
  YouTube-címke, élénkebb leírások kérdéssel a végén, közösségi blokk a Márkacsomagból, erősebb
  címek 1-2 NAGYBETŰS kulcsszóval, Stúdió > Játékok.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Больше никаких хэштегов чужих игр: игра определяется один раз на видео. А ещё лучшие хэштеги, настоящие теги YouTube и живые описания.

- **Больше никаких хештегов других игр:** игра определяется один раз для всего видео; названия,
  описания, хештеги и теги — только про эту игру (если игра неизвестна — только общие игровые
  хештеги).
- **Новое:** хештеги в чётком порядке (канал, #shorts, игра, 2-4 про клип), 10-20 настоящих тегов
  YouTube, живые описания с вопросом в конце, блок соцсетей из «Брендинга», сильные названия с
  1-2 КЛЮЧЕВЫМИ словами капсом, Студия > Игры.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
لا وسوم من ألعاب أخرى بعد الآن: تُحدَّد اللعبة مرة واحدة لكل فيديو. إضافةً إلى وسوم أفضل وكلمات YouTube حقيقية وأوصاف أكثر حيوية.

- **لا وسوم من ألعاب أخرى بعد الآن:** تُحدَّد اللعبة مرة واحدة للفيديو كله، والعناوين والأوصاف
  والوسوم والعلامات كلها عن هذه اللعبة فقط (لعبة غير معروفة: وسوم ألعاب عامة فقط).
- **جديد:** وسوم بترتيب ثابت (القناة، #shorts، اللعبة، 2-4 عن المقطع)، 10-20 علامة يوتيوب حقيقية،
  أوصاف أكثر حيوية تنتهي بسؤال، كتلة التواصل من الهوية البصرية، عناوين أقوى بكلمة أو كلمتين
  مفتاحيتين بالأحرف الكبيرة، الاستوديو > الألعاب.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
不再出现其他游戏的话题标签：每个视频只判定一次游戏。另外话题标签更好、YouTube 标签更真实、描述更生动。

- **不再出现其他游戏的话题标签：** 整个视频只确定一次游戏；标题、简介、话题标签和标签都只围绕
  这个游戏（游戏未知时只用通用游戏标签）。
- **新增：** 固定顺序的话题标签（频道、#shorts、游戏、2-4 个关于片段的）、10-20 个真实的 YouTube
  标签、结尾带问题的更生动简介、来自品牌套件的社交媒体区块、带 1-2 个大写关键词的更有力标题、
  工作室 > 游戏。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
ほかのゲームのハッシュタグが付かなくなりました（ゲームは動画ごとに一度だけ判定）。ハッシュタグ・YouTube タグ・説明文も改善。

</details>

## [1.2.24] - 2026-11-07
Cancel is final: a cancelled job never starts again by itself, and the queue can be paused.

### New
- **Pause queue:** nothing new starts while the queue is paused (a job that is already running
  finishes). It stays paused after a restart until you press **Resume queue**.
- **Cancel all** now asks once before it cancels everything in the queue.

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

<!-- lang:tr -->
**Türkçe**

İptal kesin: iptal edilen bir iş asla kendiliğinden yeniden başlamıyor ve kuyruk duraklatılabiliyor.

### Yeni
- **Kuyruğu duraklat:** kuyruk duraklatılmışken yeni iş başlamaz (çalışmakta olan iş biter).
  Uygulama yeniden başlasa da **Kuyruğu sürdür**'e basana kadar duraklatılmış kalır.
- **Hepsini iptal et** artık her şeyi iptal etmeden önce bir kez sorar.

### Düzeltmeler
- **İptal kesindir.** Kuyruk ekranında bir render'ı iptal etmek işe yaramış gibi görünüp birkaç
  saniye sonra klibin yeniden render edilmeye başlamasına yol açabiliyordu: Kolay projelerde
  otomatik "en iyi klipleri render et" adımı klibin render edilmediğini görüp onu tekrar kuyruğa
  ekliyordu. Artık iptal edilen iş iptal edilmiş olarak kalır: hiçbir otomatik adım onu geri
  getirmez (Kolay mod, zamanlanmış yayın ya da uygulamanın yeniden başlaması). Yalnızca sen
  **Tekrar dene** ile (ya da klibi düzenleyerek / Tekrar dene'ye basarak) yeniden başlatabilirsin.
- **İptal işi hemen durdurur.** İptal edilen işin video kodlayıcısı anında durdurulur (SharkyClips
  bir oyun yüzünden duraklamışken bile), artık ikinci bir (CPU) denemesine geçmez ve yarım kalan
  dosyalar silinir.

<details><summary>Español</summary>

<!-- lang:es -->
Cancelar es definitivo: un trabajo cancelado nunca vuelve a empezar solo, y la cola se puede pausar.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Cancelar é definitivo: uma tarefa cancelada nunca recomeça sozinha, e a fila pode ser pausada.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Abbrechen ist endgültig: Ein abgebrochener Auftrag startet nie wieder von selbst, und die Warteschlange lässt sich pausieren.

- **Abbrechen ist endgültig:** ein abgebrochener Render startet nicht mehr von selbst neu (auch
  nicht im Einfach-Modus, beim geplanten Veröffentlichen oder nach einem Neustart). Nur **Erneut
  versuchen** startet ihn wieder. Der Encoder stoppt sofort, halbe Dateien werden gelöscht.
- **Neu:** „Warteschlange pausieren“ (bleibt nach einem Neustart pausiert) und „Alle abbrechen“
  mit Rückfrage.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Annuler est définitif : une tâche annulée ne redémarre jamais toute seule, et la file peut être mise en pause.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A Mégse végleges: a megszakított feladat soha nem indul el újra magától, és a sor szüneteltethető.

- **A megszakítás végleges:** a megszakított renderelés magától már nem indul újra (Egyszerű
  módban, ütemezett közzétételnél és újraindítás után sem). Csak az **Újra** indítja el. A kódoló
  azonnal leáll, a félkész fájlok törlődnek.
- **Új:** „Sor szüneteltetése” (újraindítás után is szünetel) és „Összes megszakítása” megerősítéssel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Отмена окончательна: отменённая задача никогда не запустится сама, а очередь можно поставить на паузу.

- **Отмена окончательна:** отменённый рендер больше не запускается сам (ни в простом режиме, ни
  при запланированной публикации, ни после перезапуска). Запустить снова можно только кнопкой
  **Повторить**. Кодировщик останавливается сразу, недописанные файлы удаляются.
- **Новое:** «Приостановить очередь» (пауза сохраняется после перезапуска) и «Отменить всё» с
  подтверждением.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
الإلغاء نهائي: لا تبدأ المهمة الملغاة من جديد من تلقاء نفسها، ويمكن إيقاف قائمة الانتظار مؤقتًا.

- **الإلغاء نهائي:** لم يعد العرض الملغى يبدأ من جديد تلقائيًا (لا في الوضع السهل ولا في النشر
  المجدول ولا بعد إعادة التشغيل). وحده زر **إعادة المحاولة** يشغّله مجددًا. يتوقف المُرمِّز فورًا
  وتُحذف الملفات غير المكتملة.
- **جديد:** "إيقاف قائمة الانتظار مؤقتًا" (يبقى بعد إعادة التشغيل) و"إلغاء الكل" مع تأكيد.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
取消即最终：已取消的任务不会再自动开始，队列也可以暂停。

- **取消即最终：** 已取消的渲染不会再自行重新开始（简易模式、定时发布、重启应用后都不会）。
  只有 **重试** 才能再次开始。编码器立即停止，未写完的文件会被删除。
- **新增：** "暂停队列"（重启后仍保持暂停）和带确认的"全部取消"。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
キャンセルは確定：キャンセルしたジョブが勝手に再開することはなく、キューも一時停止できます。

</details>

## [1.2.23] - 2026-11-07
Fixed: the 9:16 preview no longer zooms in and shifts, and it now shows exactly what the clip will look like.

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

Düzeltildi: 9:16 önizleme artık yakınlaşıp kaymıyor ve klibin tam olarak nasıl görüneceğini gösteriyor.

### Düzeltmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: la vista previa 9:16 ya no hace zoom ni se desplaza, y muestra exactamente cómo quedará el clip.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: a prévia 9:16 não dá mais zoom nem se desloca, e mostra exatamente como o clipe vai ficar.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: Die 9:16-Vorschau zoomt und verschiebt sich nicht mehr und zeigt genau, wie der Clip aussehen wird.

- **Die 9:16-Vorschau zoomt und verrutscht nicht mehr:** schuld war ein endloses „Wort“ der
  Spracherkennung („Zzzzzz…“), das die Seite gedehnt hat. Solche Wörter werden jetzt gekürzt oder
  entfernt, auch in bestehenden Projekten.
- **Die Vorschau zeigt genau den fertigen Clip:** gleicher Ausschnitt, gleicher Zoom (max. 1,25×).

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : l'aperçu 9:16 ne zoome plus et ne se décale plus, et montre exactement à quoi ressemblera le clip.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a 9:16-os előnézet már nem nagyít be és nem csúszik el, és pontosan mutatja, milyen lesz a klip.

- **A 9:16-os előnézet már nem nagyít és csúszik el:** a beszédfelismerés egy végtelen „szava”
  („Zzzzzz…”) nyújtotta meg az oldalt. Az ilyen szavakat most lerövidítjük vagy töröljük, a
  meglévő projektekben is.
- **Az előnézet pontosan a kész klipet mutatja:** ugyanaz a kivágás és zoom (legfeljebb 1,25×).

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: предпросмотр 9:16 больше не увеличивается и не сдвигается и показывает клип ровно таким, каким он будет.

- **Превью 9:16 больше не увеличивается и не съезжает:** виновато было бесконечное «слово»
  распознавания речи («Zzzzzz…»), растягивавшее страницу. Такие слова теперь сокращаются или
  удаляются, и в старых проектах тоже.
- **Превью показывает ровно готовый клип:** та же обрезка и тот же зум (максимум 1,25×).

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: لم تعد معاينة 9:16 تُكبّر وتنزاح، وأصبحت تعرض المقطع تمامًا كما سيبدو.

- **معاينة 9:16 لم تعد تتكبّر وتنزاح:** السبب "كلمة" لا نهائية من التعرّف على الكلام
  ("Zzzzzz…") كانت تمدّ الصفحة. تُختصر هذه الكلمات أو تُحذف الآن، في المشاريع القديمة أيضًا.
- **المعاينة تعرض المقطع النهائي تمامًا:** نفس القصّ ونفس التكبير (حتى 1.25×).

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：9:16 预览不再放大和偏移，现在会准确显示剪辑的最终样子。

- **9:16 预览不再放大和偏移：** 原因是语音识别写出的一个无限长的"词"（"Zzzzzz…"）把页面撑宽了。
  这类词现在会被缩短或删除，旧项目也一样。
- **预览与成片完全一致：** 相同的裁剪和缩放（最多 1.25×）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：9:16 プレビューが勝手に拡大・移動しなくなり、仕上がりどおりに表示されます。

</details>

## [1.2.22] - 2026-11-07
Captions say exactly what you said again, zoom can't run away, and bleeps are on for every clip with a clear visual cue.

### Improved
- **Bleeps are on for every clip by default, at Strict**, in Easy and Pro, vertical and 16:9.
- **A more professional bleep:** one level for the whole clip, just under your voice, quick
  fades with no clicks; classic beep, soft "boop" or mute.
- **A visual cue:** a bleeped word shows as "****" in red with a short pop, and a small "#@!"
  badge pops up next to the facecam while the bleep plays (both on by default, switchable next
  to the swear settings).
- **Every bleep is checked after the render:** it must really be in the sound, and no swear may
  still be heard; otherwise the clip is rendered again.

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

<!-- lang:tr -->
**Türkçe**

Altyazılar yine tam olarak söylediğini yazıyor, zoom kontrolden çıkamıyor ve bip'ler her klipte açık, belirgin bir görsel işaretle.

### İyileştirmeler
- **Bip'ler varsayılan olarak her klipte açık, Sıkı seviyede**; Kolay ve Pro modda, dikey ve 16:9.
- **Daha profesyonel bip:** tüm klip için tek seviye, sesinin biraz altında, tıkırtısız hızlı
  geçişler; klasik bip, yumuşak "boop" ya da sessiz.
- **Görsel ipucu:** bip'lenen kelime altyazıda kırmızı "****" olarak kısa bir zıplamayla görünür,
  bip çalarken kameranın yanında küçük bir "#@!" rozeti belirir (ikisi de varsayılan açık, küfür
  ayarlarının yanından kapatılabilir).
- **Her bip render'dan sonra kontrol edilir:** sesin içinde gerçekten olmalı ve hiçbir küfür hâlâ
  duyulmamalı; yoksa klip yeniden render edilir.

### Düzeltmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
Los subtítulos vuelven a decir exactamente lo que dijiste, el zoom ya no se descontrola y los pitidos están activos en cada clip con una señal visual clara.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
As legendas voltam a dizer exatamente o que você falou, o zoom não sai do controle e os bipes ficam ligados em todo clipe com um sinal visual claro.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Untertitel zeigen wieder genau, was du gesagt hast, der Zoom läuft nicht mehr davon, und Pieptöne sind in jedem Clip an, mit klarem Bildhinweis.

- **Untertitel stimmen wieder genau:** die Schimpfwort-Prüfung fügt nur Pieptöne hinzu und ändert
  nie den Untertiteltext; nur echte Schimpfwörter erscheinen als „****“.
- **Nie versehentlich null Pieptöne:** bei einem Problem greift die einfache Erkennung aus 1.2.20,
  mit Hinweis.
- **Zoom bleibt im Rahmen:** alle Zooms zusammen höchstens 1,25×, Ausschnitt aus der echten
  Bildgröße, Facecam immer im Bild.
- **Pieptöne standardmäßig in jedem Clip (Streng)**, gleichmäßiger Pegel knapp unter der Stimme,
  rotes „****“ mit kleinem Pop und „#@!“-Abzeichen neben der Facecam; nach dem Rendern geprüft.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Les sous-titres redisent exactement ce que tu as dit, le zoom ne s'emballe plus et les bips sont actifs sur chaque clip avec un repère visuel clair.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A feliratok újra pontosan azt írják, amit mondtál, a zoom nem szalad el, és minden klipben be van kapcsolva a sípolás, jól látható jelzéssel.

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
Субтитры снова точно повторяют сказанное, зум больше не уходит вразнос, а запикивание включено в каждом клипе с понятной визуальной меткой.

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
تعود الترجمات لتكتب ما قلته بالضبط، ولم يعد التكبير يخرج عن السيطرة، والصافرات مفعّلة في كل مقطع مع إشارة مرئية واضحة.

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
字幕重新准确显示你说的话，缩放不会失控，每个剪辑默认开启哔声并带有清晰的视觉提示。

- **字幕重新准确：** 脏话检查只增加哔声，绝不修改字幕文字；只有真正的脏话才显示为“****”。
- **不会意外地一个哔声都没有：** 出现问题时改用 1.2.20 的基础检测器，并显示提示。
- **缩放不会超出画面：** 所有缩放合计最多 1.25 倍，按视频真实画面尺寸裁剪，摄像头始终在画面内。
- **默认每个片段都加哔声（严格）**，音量统一、略低于人声，红色“****”带弹出效果，摄像头旁显示“#@!”徽章；渲染后自动检查。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
字幕が再び話したとおりに。ズームが暴走しなくなり、すべてのクリップでピー音がオン、わかりやすい表示付き。

</details>

## [1.2.21] - 2026-11-07
Much stricter swear detection: a deep check listens to every voice again, bleeps sit exactly on the word, and it learns from you.

### New
- **Much stricter swear detection: almost no swear gets through any more.** A new deep check
  listens to your clips again: every voice (also quiet friends and short "aq!" bursts the
  transcript skipped), with quiet voices turned up, in several passes with the biggest speech-to-text
  model. It also understands Turkish word forms (siktir, sikerler, amına, götünü...),
  spellings with ı instead of i, stretched letters ("siiiiktir"), short forms (amk, aq) and words
  the transcript wrote censored ("s**"), in all seven app languages. Real words that look similar
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

### Improved
- The deep check downloads a big speech-to-text model (3.1 GB) and a word-timing model (290 MB)
  once. On computers without a strong graphics card it uses the normal model instead.

<!-- lang:tr -->
**Türkçe**

Çok daha sıkı küfür algılama: derin kontrol her sesi yeniden dinliyor, bip'ler tam kelimenin üstüne oturuyor ve senden öğreniyor.

### Yeni
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

### İyileştirmeler
- Derin kontrol Whisper large-v3 modelini (3,1 GB) ve hizalama modelini (290 MB) bir kez indirir.
  Güçlü ekran kartı olmayan bilgisayarlarda normal modeli kullanır.

<details><summary>Español</summary>

<!-- lang:es -->
Detección de palabrotas mucho más estricta: una revisión a fondo escucha de nuevo cada voz, los pitidos caen justo en la palabra y aprende de ti.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Detecção de palavrões muito mais rígida: uma checagem profunda escuta cada voz de novo, os bipes caem exatamente na palavra e ela aprende com você.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Viel strengere Schimpfwort-Erkennung: Eine gründliche Prüfung hört jede Stimme noch einmal, Pieptöne sitzen genau auf dem Wort, und sie lernt von dir.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Détection des gros mots bien plus stricte : une vérification approfondie réécoute chaque voix, les bips tombent pile sur le mot et elle apprend de toi.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Sokkal szigorúbb káromkodásfelismerés: egy alapos ellenőrzés minden hangot újra meghallgat, a sípolás pontosan a szóra kerül, és tanul tőled.

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
Гораздо более строгий поиск мата: глубокая проверка заново слушает каждый голос, запикивание точно ложится на слово и учится у вас.

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
كشف أكثر صرامة بكثير للشتائم: فحص عميق يستمع من جديد لكل صوت، والصافرات تقع على الكلمة تمامًا، ويتعلم منك.

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
更严格的脏话检测：深度检查会重新听每一个声音，哔声准确盖住单词，还会向你学习。

- **更严格的脏话识别：** 彻底检查会用 Whisper large-v3 多次重新识别片段（所有人声，包括很小声和很短的），并能理解七种语言的词形、写法变体、拉长的字母、缩写和被审查的词。测试视频：14 个脏话全部哔掉（之前 8 个）。
- **哔声精确落在词上：** 用本地对齐模型找到精确的词语时间，每个哔声都会重新试听，必要时加宽，渲染后也会检查。仍能部分听到：14 个中 1 个（之前 8 个中 4 个）。
- **严格程度：** 普通、严格（Shorts / TikTok / Reels 默认）、极严格。简易模式只有一个开关“严格检查脏话”（开）。
- **向你学习：** 你手动哔掉的词会被记住，取消哔声的词算作“不是脏话”（工作室 > 词语列表）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
汚い言葉の検出が大幅に厳しく。全員の声を聞き直す精密チェック、単語ぴったりのピー音、あなたからの学習機能。

</details>

## [1.2.20] - 2026-11-06
Dubbed clips on TikTok and Reels now say their voice is AI-made, and the voice model gets fuller credit.

### Improved
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

TikTok ve Reels'teki seslendirilmiş klipler artık seslerinin yapay zekâyla yapıldığını belirtiyor; ses modeline daha eksiksiz atıf yapılıyor.

### İyileştirmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
Los clips doblados en TikTok y Reels ahora indican que su voz está hecha con IA, y el modelo de voz recibe un crédito más completo.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Clipes dublados no TikTok e no Reels agora avisam que a voz foi feita por IA, e o modelo de voz ganha crédito mais completo.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Synchronisierte Clips auf TikTok und Reels sagen jetzt, dass ihre Stimme KI-generiert ist, und das Stimmmodell wird vollständiger genannt.

- **Vertonte Clips auf TikTok und Reels sagen ebenfalls, dass die Stimme KI-erzeugt ist:** ein Satz
  in der Beschreibung; automatisch wird das KI-Label der Plattform gesetzt, halbautomatisch
  erinnert SharkyClips dich daran. Beides ist an und lässt sich direkt über dem Posten-Knopf
  abschalten.
- **Vollständigere Lizenzangabe:** von KevinAHM nach ONNX exportiert, von k2-fsa/sherpa-onnx gepackt
  und auf int8 quantisiert, mit Links.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Les clips doublés sur TikTok et Reels indiquent maintenant que leur voix est faite par IA, et le modèle de voix est mieux crédité.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A szinkronizált klipek a TikTokon és a Reelsen most jelzik, hogy a hangjuk MI-vel készült, és a hangmodell teljesebb említést kap.

- **A TikTokon és Reelsen is jelzik a szinkronizált klipek, hogy a hang MI-vel készült:** egy sor
  a leírásban; automata módban a platform MI-címkéje is bekapcsol, félautomata módban a SharkyClips
  emlékeztet rá. Mindkettő be van kapcsolva, és a közzététel gomb fölött kikapcsolható.
- **Teljesebb licencadat:** ONNX-be exportálta KevinAHM, csomagolta és int8-ra kvantálta a
  k2-fsa/sherpa-onnx, linkekkel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Озвученные клипы в TikTok и Reels теперь сообщают, что голос создан ИИ, а у голосовой модели более полные указания авторства.

- **Озвученные клипы в TikTok и Reels тоже сообщают, что голос создан ИИ:** строка в подписи; в
  автоматическом режиме включается ИИ-метка платформы, в полуавтоматическом SharkyClips напоминает
  о ней. Оба переключателя включены и находятся над кнопкой публикации.
- **Более полное указание авторства:** экспорт в ONNX — KevinAHM, упаковка и квантизация в int8 —
  k2-fsa/sherpa-onnx, со ссылками.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
المقاطع المدبلجة على TikTok وReels تذكر الآن أن صوتها مصنوع بالذكاء الاصطناعي، مع نسب أوضح لنموذج الصوت.

- **المقاطع المدبلجة على TikTok وReels تذكر أيضًا أن الصوت مولَّد بالذكاء الاصطناعي:** سطر في
  الوصف؛ في النشر التلقائي تُفعَّل علامة الذكاء الاصطناعي في المنصة، وفي الوضع شبه التلقائي يذكّرك
  SharkyClips بها. كلاهما مفعَّل ويمكن إيقافه فوق زر النشر.
- **نسبة أكمل لنموذج الصوت:** صدّره KevinAHM إلى ONNX، وحزمه k2-fsa/sherpa-onnx وضغطه إلى int8، مع روابط.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
TikTok 和 Reels 上的配音剪辑现在会注明声音由 AI 生成，语音模型的署名也更完整。

- **TikTok 和 Reels 上的配音片段也会说明声音由 AI 生成：** 文案中加一行说明；自动发布时会打开平台自己的 AI 标签，半自动发布时 SharkyClips 会提醒你手动打开。两者默认开启，位于发布按钮上方。
- **更完整的声音模型署名：** 由 KevinAHM 导出为 ONNX，由 k2-fsa/sherpa-onnx 打包并量化为 int8，附链接。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
TikTok と Reels の吹き替えクリップに AI 音声である旨を表示。音声モデルのクレジットもより詳しくなりました。

</details>

## [1.2.19] - 2026-11-06
Clips dubbed in your own voice now say on YouTube that the voice is AI-made, and a new About & licenses card credits the AI models.

### Improved
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

Kendi sesinle seslendirilen klipler artık YouTube'da sesin yapay zekâyla yapıldığını belirtiyor; yeni Hakkında ve lisanslar kartı yapay zekâ modellerine atıf yapıyor.

### İyileştirmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
Los clips doblados con tu propia voz ahora indican en YouTube que la voz es de IA, y una nueva tarjeta Acerca de y licencias acredita los modelos de IA.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Clipes dublados com a sua voz agora avisam no YouTube que a voz é de IA, e um novo cartão Sobre e licenças dá crédito aos modelos de IA.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Mit deiner eigenen Stimme synchronisierte Clips sagen auf YouTube jetzt, dass die Stimme KI-generiert ist, und eine neue Karte Über & Lizenzen nennt die KI-Modelle.

- **Vertonte Clips sagen, dass die Stimme KI-erzeugt ist:** ein Satz in der Beschreibung (in der
  Sprache des Clips) und YouTubes Markierung „veränderte oder synthetische Inhalte“. Beides ist an
  und lässt sich beim Hochladen und in der Bibliothek abschalten.
- **Lizenzhinweise:** Pocket TTS von Kyutai (CC-BY 4.0), von k2-fsa/sherpa-onnx in int8-ONNX
  umgewandelt, mit Links; in den Vertonungs-Einstellungen und in der neuen Karte **Über & Lizenzen**.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Les clips doublés avec ta propre voix indiquent maintenant sur YouTube que la voix est faite par IA, et une nouvelle carte À propos et licences crédite les modèles d'IA.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A saját hangoddal szinkronizált klipek a YouTube-on jelzik, hogy a hang MI-vel készült, és az új Névjegy és licencek kártya feltünteti az MI-modelleket.

- **A szinkronizált klipek jelzik, hogy a hang MI-vel készült:** egy sor a leírásban (a klip
  nyelvén) és a YouTube „módosított vagy szintetikus tartalom” jelölése. Mindkettő be van
  kapcsolva, és a feltöltésnél és a Könyvtárban kikapcsolható.
- **Licencek:** Pocket TTS (Kyutai, CC-BY 4.0), int8 ONNX-re alakította a k2-fsa/sherpa-onnx,
  linkekkel; a szinkron beállításainál és az új **Névjegy és licencek** kártyán.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Клипы, озвученные вашим голосом, теперь сообщают на YouTube, что голос создан ИИ, а новая карточка «О программе и лицензии» указывает авторов моделей.

- **Озвученные клипы сообщают, что голос создан ИИ:** строка в описании (на языке клипа) и
  отметка YouTube «изменённый или синтетический контент». Оба включены и отключаются на экране
  загрузки и в Библиотеке.
- **Лицензии:** Pocket TTS от Kyutai (CC-BY 4.0), преобразована в int8 ONNX проектом
  k2-fsa/sherpa-onnx, со ссылками; в настройках озвучки и в новой карточке **О программе и лицензии**.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
المقاطع المدبلجة بصوتك تذكر الآن على YouTube أن الصوت مصنوع بالذكاء الاصطناعي، وبطاقة "حول وتراخيص" الجديدة تنسب نماذج الذكاء الاصطناعي.

- **المقاطع المدبلجة تذكر أن الصوت مولَّد بالذكاء الاصطناعي:** سطر في الوصف (بلغة المقطع) وعلامة
  يوتيوب "محتوى معدَّل أو اصطناعي". كلاهما مفعَّل ويمكن إيقافه في شاشة الرفع وفي المكتبة.
- **التراخيص:** Pocket TTS من Kyutai (CC-BY 4.0)، حوّله k2-fsa/sherpa-onnx إلى int8 ONNX، مع
  روابط؛ في إعدادات الدبلجة وفي بطاقة **حول البرنامج والتراخيص** الجديدة.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
用你自己声音配音的剪辑现在会在 YouTube 上注明声音由 AI 生成，新的“关于与许可”卡片列出了 AI 模型的署名。

- **配音片段会说明声音由 AI 生成：** 描述中加一行说明（使用片段的语言），并设置 YouTube 的“经过修改或合成的内容”标记。两者默认开启，可在上传界面和媒体库中关闭。
- **许可证：** Pocket TTS（Kyutai，CC-BY 4.0），由 k2-fsa/sherpa-onnx 转换为 int8 ONNX，附链接；见配音设置和新的 **关于与许可证** 卡片。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
あなたの声で吹き替えたクリップは YouTube で AI 音声と表示。新しい「情報とライセンス」カードで AI モデルのクレジットを表示します。

</details>

## [1.2.18] - 2026-11-06
AI covers made on your PC, TikTok and Reels exports, dubbing in your own voice, study cards and a music visualizer.

### New
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

Bilgisayarında yapılan yapay zekâ kapakları, TikTok ve Reels dışa aktarımı, kendi sesinle seslendirme, ders kartları ve müzik görselleştirici.

### Yeni
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

<details><summary>Español</summary>

<!-- lang:es -->
Portadas con IA hechas en tu PC, exportación para TikTok y Reels, doblaje con tu propia voz, tarjetas de estudio y un visualizador de música.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Capas com IA feitas no seu PC, exportação para TikTok e Reels, dublagem com a sua voz, cartões de estudo e um visualizador de música.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
KI-Cover direkt auf deinem PC, Export für TikTok und Reels, Synchronisation mit deiner eigenen Stimme, Lernkarten und ein Musik-Visualizer.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Miniatures IA faites sur ton PC, export pour TikTok et Reels, doublage avec ta propre voix, cartes d'étude et un visualiseur de musique.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
MI-borítók a saját gépeden, TikTok- és Reels-export, szinkron a saját hangodon, tanulókártyák és zenei vizualizáció.

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
Обложки ИИ прямо на вашем ПК, экспорт для TikTok и Reels, озвучка вашим голосом, учебные карточки и музыкальный визуализатор.

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
أغلفة بالذكاء الاصطناعي تُصنع على جهازك، وتصدير لـ TikTok وReels، ودبلجة بصوتك، وبطاقات دراسة، ومؤثر بصري للموسيقى.

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
在你的电脑上生成 AI 封面，导出 TikTok 和 Reels，用你自己的声音配音，学习卡片和音乐可视化。

- 新增：**封面工作室**——AI 的封面创意在你的电脑上直接变成真实图片（Z-Image-Turbo）：9:16 和 16:9
  各 4 个方案，一键选择；配置较弱的电脑改用摄像头画面。
- **TikTok 和 Instagram Reels：**上传按钮上可选平台。半自动：视频已放进“下载”、文案已复制、上传页
  已打开。也可用你自己的开发者应用通过官方 API 自动发布（审核通过前为私密 / 仅限你自己的账号）。
- **用你自己的声音配音**（英语）：只配你的台词，朋友保留原声；时间和游戏声音保持不变。一次性同意
  + 一小段声音样本。
- 学习模式下的**学习卡片**（公式排版清晰、定义、步骤），以及音乐模式下的**音乐可视化**（节拍、
  封面、卡拉 OK 歌词）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
PC 上で作る AI カバー、TikTok・Reels 用書き出し、自分の声での吹き替え、学習カード、音楽ビジュアライザー。

</details>

## [1.2.17] - 2026-11-03
Clips by themselves after a stream, live markers, approve from your phone, instant replay, chat bubbles and meme effects.

### New
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

Yayından sonra kendiliğinden klipler, canlı işaretler, telefondan onay, anlık tekrar, sohbet baloncukları ve meme efektleri.

### Yeni
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

### Düzeltmeler
- Açık temada bir küfür etiketinin kontrastı yetersizdi.

<details><summary>Español</summary>

<!-- lang:es -->
Clips solos al terminar el directo, marcadores en vivo, aprobar desde el móvil, repetición instantánea, burbujas de chat y efectos meme.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Clipes sozinhos depois da live, marcadores ao vivo, aprovar pelo celular, replay instantâneo, balões de chat e efeitos de meme.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Clips von selbst nach dem Stream, Live-Marker, Freigabe vom Handy, Sofortwiederholung, Chat-Blasen und Meme-Effekte.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Des clips tout seuls après le live, des marqueurs en direct, la validation depuis ton téléphone, le replay instantané, des bulles de chat et des effets mèmes.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Klipek maguktól adás után, élő jelölők, jóváhagyás telefonról, azonnali visszajátszás, chatbuborékok és mémeffektek.

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
Клипы сами после стрима, живые метки, одобрение с телефона, мгновенный повтор, пузыри чата и мем-эффекты.

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
مقاطع تلقائية بعد البث، وعلامات مباشرة، وموافقة من هاتفك، وإعادة فورية، وفقاعات دردشة، ومؤثرات ميم.

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
直播结束后自动出剪辑、直播标记、手机审批、即时回放、聊天气泡和表情包特效。

- 新增：**直播后自动出片**——SharkyClips 关注 OBS 的录制文件夹，每段录完的视频都会自动做成片段
  （只在电脑空闲时运行，绝不碰正在录制的文件）。可选：自动排期或上传最好的片段。
- **直播标记：**游戏中按 Ctrl+Alt+C（不抢焦点），或在 Twitch / YouTube 聊天里发 **!clip**
  （仅你或房管）：这一刻会连同前因后果成为最靠前的片段。
- **手机审核：**你自己的 Telegram 机器人，带“上传 / 排期 / 跳过”按钮；或在 Wi-Fi 下打开审核页
  （需 PIN），左右滑动即可。
- **即时回放**慢动作重放高光，**聊天气泡**显示真实（已过滤的）弹幕，**梗图特效**（定格 + AI 字幕，
  翻车时抖动；音效在本地生成）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
配信後に自動でクリップ、ライブマーカー、スマホで承認、インスタントリプレイ、チャット吹き出し、ミーム効果。

</details>

## [1.2.16] - 2026-11-02
Easy mode is the new start screen: drop a video, press Find clips, and get your best clips ready to post or download.

### New
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

Kolay mod yeni başlangıç ekranı: bir video bırak, Klip bul'a bas ve en iyi kliplerin paylaşmaya ya da indirmeye hazır olsun.

### Yeni
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

<details><summary>Español</summary>

<!-- lang:es -->
El modo Fácil es la nueva pantalla de inicio: suelta un vídeo, pulsa Buscar clips y tendrás tus mejores clips listos para publicar o descargar.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O modo Fácil é a nova tela inicial: solte um vídeo, aperte Encontrar clipes e seus melhores clipes ficam prontos para postar ou baixar.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Der einfache Modus ist der neue Startbildschirm: Video hineinziehen, Clips finden drücken, und deine besten Clips sind bereit zum Posten oder Herunterladen.

- Neu: **Einfacher Modus** als Startbildschirm: Video ablegen oder Link einfügen, „Clips finden“
  drücken. Inhaltsart wird erkannt, Fortschritt in einfachen Worten mit Restzeit; du kannst das
  Fenster schließen, eine Benachrichtigung meldet die fertigen Clips.
- Die besten 6 Clips kommen fertig in 9:16 und laufen direkt auf der Karte.
- Ein Klick auf YouTube (Titel, Beschreibung, Hashtags, Cover ausgefüllt; jetzt oder automatisch
  geplant) oder auf den Computer (Video + Textdatei + Cover in Downloads\SharkyClips).
- Einfaches Bearbeiten (Titel, Anfang/Ende, Untertitel, Musik), Bibliothek mit drei Tabs, kurze
  Tour. Der **Profi-Modus** behält alle Werkzeuge.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Le mode Facile est le nouvel écran d'accueil : dépose une vidéo, appuie sur Trouver des clips, et tes meilleurs clips sont prêts à publier ou télécharger.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az Egyszerű mód az új kezdőképernyő: dobj be egy videót, nyomd meg a Klipek keresése gombot, és a legjobb klipjeid készen állnak posztolásra vagy letöltésre.

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
Простой режим — новый стартовый экран: перетащите видео, нажмите «Найти клипы» и получите лучшие клипы, готовые к публикации или загрузке.

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
الوضع السهل هو شاشة البداية الجديدة: أسقط فيديو، واضغط "ابحث عن مقاطع"، فتجهز أفضل مقاطعك للنشر أو التنزيل.

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
简易模式成为新的开始界面：拖入视频，点“查找剪辑”，最佳剪辑即可发布或下载。

- 新增：**简易模式**作为开始界面：放入视频或粘贴链接，点击“查找剪辑”即可。自动识别内容类型，
  用通俗的步骤和剩余时间显示进度；可以关闭窗口，完成后会通知你。
- 最好的 6 个剪辑直接做成 9:16，在卡片上就能播放。
- 一键上传 YouTube（标题、简介、话题标签、封面已填好；立即或自动安排），或一键下载到电脑
  （视频 + 文本文件 + 封面，保存在“下载\SharkyClips”）。
- 简单编辑（标题、开始/结束、字幕、音乐）、三个标签页的媒体库、简短导览。**专业模式**保留全部工具。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
かんたんモードが新しいスタート画面に。動画をドロップして「クリップを探す」を押せば、ベストクリップがすぐ投稿・保存できます。

</details>

## [1.2.15] - 2026-11-02
Hear every speaker: voices are separated and transcribed, swears are reviewed before rendering, and captions get new styles.

### New
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
- Swears are found more reliably: words the transcript censored itself ("s**yim"), misheard and
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

Her konuşanı duy: sesler ayrılıp yazıya dökülüyor, küfürler işlemeden önce gözden geçiriliyor ve altyazılara yeni stiller geliyor.

### Yeni
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

### Düzeltmeler
- **Kamera tespiti** web kameran yerine oyunun içindeki bir yüzü (örneğin League of Legends
  arayüzündeki bir portreyi) seçiyordu. Artık tüm videoda canlı bir yüz içeren sabit bir kamera
  dikdörtgeni arıyor. Emin değilse seçenekleri bir karede gösteriyor, tek tıkla seçiyorsun. Konum
  kanal ve çözünürlük başına yeni projeler için hatırlanıyor ("Tekrar algıla" baştan başlar).

<details><summary>Español</summary>

<!-- lang:es -->
Oye a cada persona: las voces se separan y transcriben, las palabrotas se revisan antes de renderizar y los subtítulos tienen estilos nuevos.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Ouça cada pessoa: as vozes são separadas e transcritas, os palavrões são revisados antes de renderizar e as legendas ganham estilos novos.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Jede Stimme hören: Stimmen werden getrennt und transkribiert, Schimpfwörter vor dem Rendern geprüft, und Untertitel bekommen neue Stile.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Entends chaque voix : les voix sont séparées et transcrites, les gros mots vérifiés avant le rendu, et les sous-titres ont de nouveaux styles.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Minden beszélőt hallasz: a hangokat szétválasztja és leírja, a káromkodásokat renderelés előtt átnézheted, és a feliratok új stílusokat kapnak.

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
Слышно каждого: голоса разделяются и расшифровываются, мат проверяется до рендера, а у субтитров новые стили.

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
اسمع كل متحدث: تُفصل الأصوات وتُفرَّغ نصيًا، وتُراجَع الشتائم قبل الإخراج، وتحصل الترجمات على أنماط جديدة.

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
听清每个说话人：分离并转写各个声音，渲染前检查脏话，字幕也有新样式。

- 新增：“听清每个人”把人声与游戏声分开，也转录你朋友说的话，每个声音有自己的颜色。多音轨录制
  （麦克风、Discord、游戏）按音轨处理（标签会被记住）。
- 渲染前的脏话列表：谁说的、时间、播放按钮和消音开关；可选中文字或在波形上拖动手动消音。消音声音：
  经典哔声、柔和“噗”声、静音或自定义。
- 字幕：卡拉OK 与说话人配色样式、姓名标签、更好的换行、AI 校对。
- 修复：摄像头检测会选中游戏里的人脸而不是你的摄像头。不确定时一键选择；位置按频道和分辨率记住。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
全員の声を聞き分け：声を分離して文字起こし、書き出し前に汚い言葉を確認、字幕に新スタイル。

</details>

## [1.2.14] - 2026-11-01
Fixed: on very short windows the project page side panel now scrolls instead of cutting off the bottom.

### Fixed
- Project page on very short windows: if the candidate list and the render settings don't both
  fit, the side panel now scrolls instead of cutting off the bottom. Fonts that are a little wider
  (for example on Linux) no longer push the buttons out of view.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: çok kısa pencerelerde proje sayfasının yan paneli artık alt kısmı kesmek yerine kayıyor.

### Düzeltmeler
- Çok kısa pencerelerde proje sayfası: aday listesi ve oluşturma ayarları birlikte sığmazsa yan
  panel artık alt kısmı kesmek yerine kayıyor. Biraz daha geniş yazı tipleri (örneğin Linux'ta)
  düğmeleri görünümden itmiyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: en ventanas muy bajas el panel lateral de la página del proyecto ahora se desplaza en vez de cortar la parte de abajo.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: em janelas muito baixas o painel lateral da página do projeto agora rola em vez de cortar a parte de baixo.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: In sehr niedrigen Fenstern scrollt die Seitenleiste der Projektseite jetzt, statt unten abgeschnitten zu werden.

- Projektseite in sehr niedrigen Fenstern: Passen Kandidatenliste und Render-Einstellungen nicht
  beide hinein, scrollt jetzt das Seitenpanel, statt unten etwas abzuschneiden.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : dans les fenêtres très basses, le panneau latéral de la page du projet défile au lieu d'être coupé en bas.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: nagyon alacsony ablakokban a projektoldal oldalpanelje most görgethető, és nem vágja le az alját.

- Projektoldal nagyon alacsony ablakban: ha a jelöltlista és a renderelési beállítások nem férnek el
  együtt, az oldalsó panel most görgethető, ahelyett hogy levágná az alját.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: в очень низких окнах боковая панель страницы проекта теперь прокручивается, а не обрезается снизу.

- Страница проекта в очень низком окне: если список кандидатов и настройки рендера не помещаются
  вместе, боковая панель теперь прокручивается, а не обрезает нижнюю часть.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: في النوافذ القصيرة جدًا أصبحت اللوحة الجانبية لصفحة المشروع تُمرَّر بدلًا من قطع الجزء السفلي.

- صفحة المشروع في النوافذ القصيرة جدًا: إذا لم تتسع قائمة المرشحين وإعدادات الإنشاء معًا، تمرّر
  اللوحة الجانبية الآن بدل قصّ الجزء السفلي منها.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：窗口很矮时，项目页侧边栏现在会滚动，而不是截掉底部。

- 窗口很矮时的项目页面：如果候选列表和渲染设置无法同时放下，侧边面板现在会滚动，而不是把底部截掉。
  稍宽的字体（例如在 Linux 上）也不会再把按钮挤出视野。
- 候选列表和设置各自滚动，“渲染”和“导出”按钮始终固定在面板底部，随时可以点击。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：とても低いウィンドウでも、プロジェクトページのサイドパネルが下を切らずにスクロールします。

</details>

## [1.2.13] - 2026-11-01
The project page now fits laptop screens: the clip list no longer disappears under the render settings.

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

Proje sayfası artık dizüstü ekranlara sığıyor: aday listesi oluşturma ayarlarının altında kaybolmuyor.

### Düzeltmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
La página del proyecto ya cabe en pantallas de portátil: la lista de clips ya no desaparece bajo los ajustes de render.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A página do projeto agora cabe em telas de notebook: a lista de clipes não some mais debaixo das configurações.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die Projektseite passt jetzt auf Laptop-Bildschirme: Die Clipliste verschwindet nicht mehr unter den Render-Einstellungen.

- Projektseite auf Laptops (z. B. 14" mit 125-150 % Skalierung): Die Kandidatenliste war unter den
  Render-Einstellungen zu einem schmalen Streifen zusammengedrückt. Jetzt behält sie immer eine gute
  Höhe, die Einstellungen scrollen separat, **Rendern** und **Exportieren** bleiben sichtbar.
- Tab-Zeile, obere Leiste bei 1024 px, Clip-Karten und zwei Seiten auf dem Handy überlappen oder
  scrollen nicht mehr seitlich.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La page du projet tient maintenant sur les écrans de portable : la liste des clips ne disparaît plus sous les réglages de rendu.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A projektoldal most elfér laptopok képernyőjén: a kliplista már nem tűnik el a renderbeállítások alatt.

- Projektoldal laptopon (pl. 14" kijelző 125-150 %-os méretezéssel): a jelöltlista vékony csíkká
  nyomódott a renderelési beállítások alatt. Most mindig jó magasságú marad, a beállítások külön
  görgethetők, a **Renderelés** és **Exportálás** gomb látható marad.
- A fülsor, a felső sáv 1024 px-en, a klipkártyák és két oldal telefonon már nem fedik egymást és
  nem görgetnek oldalra.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Страница проекта теперь помещается на экраны ноутбуков: список клипов больше не исчезает под настройками рендера.

- Страница проекта на ноутбуке (например, 14" с масштабом 125-150 %): список кандидатов сжимался в
  тонкую полоску под настройками рендера. Теперь он всегда нормальной высоты, настройки
  прокручиваются отдельно, кнопки **Рендер** и **Экспорт** всегда видны.
- Строка вкладок, верхняя панель при 1024 px, карточки клипов и две страницы на телефоне больше не
  перекрываются и не прокручиваются вбок.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبحت صفحة المشروع تناسب شاشات الحواسيب المحمولة: لم تعد قائمة المقاطع تختفي تحت إعدادات الإخراج.

- صفحة المشروع على الحواسيب المحمولة (مثل شاشة 14 بوصة بتكبير 125-150٪): كانت قائمة المرشحين
  تنضغط إلى شريط رفيع تحت إعدادات الإنشاء. الآن تحتفظ دائمًا بارتفاع جيد، وتمرّر الإعدادات في
  منطقتها، ويبقى زرّا **الإنشاء** و**التصدير** ظاهرين.
- لم يعد صف التبويبات والشريط العلوي عند 1024 بكسل وبطاقات المقاطع وصفحتان على الهاتف تتداخل أو
  تمرّر الصفحة جانبيًا.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
项目页现在适配笔记本屏幕：剪辑列表不再被渲染设置挡住。

- 笔记本上的项目页面（例如 14 英寸、125-150% 缩放）：候选列表被渲染设置挤成一条细线，看不到剪辑。
  现在列表始终保持合适高度并在自己的面板中滚动，设置单独滚动，**渲染**和**导出**按钮始终可见。
- 标签行、1024 像素宽时的顶部栏、剪辑卡片以及手机上的两个页面不再重叠或横向滚动。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
プロジェクトページがノート PC の画面に収まるように。クリップ一覧が書き出し設定の下に隠れなくなりました。

</details>

## [1.2.12] - 2026-11-01
Fixed: opening SharkyClips right after it crashed or was closed now starts normally.

### Fixed
- Opening SharkyClips right after it crashed or was closed could wait and then show nothing.
  It now starts normally.

<!-- lang:tr -->
**Türkçe**

Düzeltildi: SharkyClips çöktükten ya da kapatıldıktan hemen sonra açmak artık normal başlatıyor.

### Düzeltmeler
- SharkyClips çöktükten ya da kapatıldıktan hemen sonra açmak bekleyip hiçbir şey göstermeyebiliyordu.
  Artık normal şekilde açılıyor.

<details><summary>Español</summary>

<!-- lang:es -->
Corregido: abrir SharkyClips justo después de que se cerrara o fallara ahora arranca con normalidad.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Corrigido: abrir o SharkyClips logo depois de fechar ou travar agora inicia normalmente.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Behoben: SharkyClips direkt nach einem Absturz oder dem Schließen zu öffnen, startet jetzt normal.

- Behoben: SharkyClips direkt nach einem Absturz oder Beenden zu öffnen, zeigte manchmal nichts an.
  Jetzt startet es ganz normal.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Corrigé : ouvrir SharkyClips juste après un plantage ou une fermeture démarre maintenant normalement.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Javítva: a SharkyClips összeomlás vagy bezárás utáni azonnali megnyitása most rendben elindul.

- Javítva: a SharkyClips megnyitása közvetlenül egy összeomlás vagy bezárás után néha semmit sem mutatott.
  Most normálisan elindul.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Исправлено: запуск SharkyClips сразу после сбоя или закрытия теперь проходит нормально.

- Исправлено: запуск SharkyClips сразу после сбоя или закрытия иногда ничего не открывал.
  Теперь приложение запускается как обычно.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
تم الإصلاح: فتح SharkyClips مباشرة بعد تعطّله أو إغلاقه يعمل الآن بشكل طبيعي.

- تم الإصلاح: فتح SharkyClips مباشرة بعد تعطّله أو إغلاقه لم يكن يُظهر شيئًا أحيانًا.
  الآن يعمل التطبيق بشكل طبيعي.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
已修复：在 SharkyClips 崩溃或关闭后立即打开，现在能正常启动。

- 已修复：SharkyClips 崩溃或关闭后立即打开时，有时会等待一段时间然后什么都不显示。现在它会像平常一样正常启动，并打开主界面。
- 如果 SharkyClips 已经在运行（例如更新后正在重启），再次打开只会显示正在运行的那个窗口，而不会启动第二个副本。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
修正：クラッシュや終了の直後に SharkyClips を開いても、正常に起動するようになりました。

</details>

## [1.2.11] - 2026-11-01
SharkyClips' Google connection is now published, and scheduled uploads are safer.

### Improved
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

### İyileştirmeler
- **Ayarlar → YouTube**, yerleşik Google bağlantısını **yayında, henüz doğrulanmadı** olarak
  gösteriyor: Google'ın uyarı ekranından sonra herkes bağlanabilir; Google SharkyClips'i doğrulayana
  kadar en fazla 100 kişi. Google artık seni 7 günde bir oturumdan çıkarmıyor.

### Düzeltmeler
- SharkyClips bir güncellemeden sonra yeniden başlarken ikinci kez açılırsa iki kopya aynı anda
  çalışabiliyor ve ikisi de aynı zamanlanmış klibi hazırlıyordu (iki kez yüklenebilirdi bile). Artık
  yalnızca bir kopya çalışıyor; tekrar açmak çalışan kopyayı gösteriyor.
- Windows (örneğin virüs tarayıcısı) bitmiş dosyayı hâlâ tararken bir dışa aktarma "Erişim engellendi"
  hatasıyla bitebiliyordu. SharkyClips artık biraz bekleyip yeniden deniyor.

<details><summary>Español</summary>

<!-- lang:es -->
La conexión de Google de SharkyClips ya está publicada, y las subidas programadas son más seguras.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A conexão do Google do SharkyClips agora está publicada, e os uploads agendados ficaram mais seguros.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die Google-Verbindung von SharkyClips ist jetzt veröffentlicht, und geplante Uploads sind sicherer.

- Die eingebaute Google-Verbindung ist jetzt **veröffentlicht, noch nicht verifiziert**: bis zu 100
  Personen nach Googles Warnbildschirm; keine Abmeldung mehr alle 7 Tage.
- Behoben: Zwei gleichzeitig laufende SharkyClips (zweiter Start während eines Neustarts) konnten
  denselben geplanten Clip doppelt vorbereiten. Jetzt läuft immer nur eine Kopie.
- Behoben: „Zugriff verweigert“ beim Export, während Windows die Datei noch prüfte.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La connexion Google de SharkyClips est maintenant publiée, et les envois planifiés sont plus sûrs.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A SharkyClips Google-kapcsolata mostantól közzétett, és az ütemezett feltöltések biztonságosabbak.

- A beépített Google-kapcsolat most **közzétéve, még nincs ellenőrizve**: a Google figyelmeztetése
  után legfeljebb 100 ember; nincs többé kijelentkeztetés 7 naponta.
- Javítva: két egyszerre futó SharkyClips (második indítás újraindítás közben) ugyanazt az ütemezett
  klipet kétszer készíthette elő. Most mindig csak egy példány fut.
- Javítva: „Hozzáférés megtagadva” exportáláskor, amíg a Windows még vizsgálta a fájlt.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Подключение SharkyClips к Google теперь опубликовано, а запланированные загрузки стали надёжнее.

- Встроенное подключение Google теперь **опубликовано, ещё не проверено**: до 100 человек после
  экрана предупреждения Google; больше никаких выходов из аккаунта каждые 7 дней.
- Исправлено: две одновременно запущенные копии SharkyClips (второй запуск во время перезапуска)
  могли дважды готовить один и тот же запланированный клип. Теперь работает только одна копия.
- Исправлено: «Отказано в доступе» при экспорте, пока Windows ещё проверяла файл.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح اتصال SharkyClips بـ Google منشورًا، وأصبحت عمليات الرفع المجدولة أكثر أمانًا.

- اتصال Google المدمج صار **منشورًا ولم يُتحقق منه بعد**: حتى 100 شخص بعد شاشة تحذير Google، ولا
  خروج من الحساب كل 7 أيام بعد الآن.
- تم الإصلاح: نسختان من SharkyClips تعملان معًا (تشغيل ثانٍ أثناء إعادة التشغيل) كانتا قد تجهّزان
  المقطع المجدول نفسه مرتين. الآن تعمل نسخة واحدة فقط.
- تم الإصلاح: خطأ «تم رفض الوصول» عند التصدير بينما كان Windows لا يزال يفحص الملف.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
SharkyClips 的 Google 连接已正式发布，定时上传也更安全。

- 内置的 Google 连接现已**发布，尚未验证**：在 Google 警告页面后最多 100 人可连接；不再每 7 天退出登录。
- 已修复：更新重启期间再次打开 SharkyClips 时，两个副本可能同时运行并重复准备同一个定时剪辑。现在始终只运行一个副本。
- 已修复：Windows（例如杀毒软件）仍在扫描文件时，导出可能出现“拒绝访问”。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
SharkyClips の Google 連携が公開され、予約アップロードがより安全になりました。

</details>

## [1.2.10] - 2026-11-01
SharkyClips has a website now, and the privacy policy link in the app works.

### New
- The SharkyClips website is online: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/), with the
  [privacy policy](https://utkualsir.github.io/sharkyclips-site/privacy.html) and the
  [terms of use](https://utkualsir.github.io/sharkyclips-site/terms.html).

### Improved
- **Settings → YouTube**: the privacy policy link opens the new website.
- **Privacy policy and terms** (effective 1 November 2026): they now say clearly that SharkyClips
  only changes or deletes videos it uploaded itself, and only when you ask (editing or
  cancelling a scheduled clip). Questions go to the website's GitHub page.

<!-- lang:tr -->
**Türkçe**

SharkyClips'in artık bir web sitesi var ve uygulamadaki gizlilik politikası bağlantısı çalışıyor.

### Yeni
- SharkyClips web sitesi yayında: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/);
  [gizlilik politikası](https://utkualsir.github.io/sharkyclips-site/privacy.html) ve
  [kullanım koşulları](https://utkualsir.github.io/sharkyclips-site/terms.html) da orada.

### İyileştirmeler
- **Ayarlar → YouTube**: gizlilik politikası bağlantısı yeni web sitesini açıyor.
- **Gizlilik politikası ve koşullar** (1 Kasım 2026'dan itibaren geçerli): SharkyClips'in yalnızca
  kendi yüklediği videoları ve yalnızca sen istediğinde (zamanlanmış bir klibi düzenlerken ya da
  iptal ederken) değiştirdiğini veya sildiğini açıkça söylüyor. Sorular web sitesinin GitHub
  sayfasına.

<details><summary>Español</summary>

<!-- lang:es -->
SharkyClips ya tiene sitio web, y el enlace a la política de privacidad de la app funciona.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O SharkyClips agora tem um site, e o link da política de privacidade no app funciona.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
SharkyClips hat jetzt eine Website, und der Link zur Datenschutzerklärung in der App funktioniert.

- SharkyClips hat jetzt eine Website: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (mit
  Datenschutzerklärung und Nutzungsbedingungen); der Link in Einstellungen → YouTube funktioniert.
- Datenschutzerklärung präzisiert: SharkyClips ändert oder löscht nur selbst hochgeladene Videos,
  und nur auf deinen Wunsch.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
SharkyClips a maintenant un site web, et le lien vers la politique de confidentialité dans l'appli fonctionne.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A SharkyClipsnek már van weboldala, és az alkalmazásban működik az adatvédelmi tájékoztató linkje.

- A SharkyClipsnek most már van weboldala: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/)
  (adatvédelmi irányelvek és felhasználási feltételek); a Beállítások → YouTube hivatkozás működik.
- Pontosított adatvédelem: a SharkyClips csak a saját maga által feltöltött videókat módosítja
  vagy törli, és csak ha kéred.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
У SharkyClips появился сайт, и ссылка на политику конфиденциальности в приложении работает.

- У SharkyClips теперь есть сайт: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (с политикой
  конфиденциальности и условиями); ссылка в Настройки → YouTube работает.
- Уточнена политика: SharkyClips изменяет или удаляет только загруженные им видео и только по
  вашей просьбе.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح لـ SharkyClips موقع إلكتروني، ورابط سياسة الخصوصية في التطبيق يعمل.

- صار لـ SharkyClips موقع ويب: [utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/) (مع سياسة الخصوصية
  وشروط الاستخدام)، ويعمل الرابط في الإعدادات ← يوتيوب.
- توضيح في سياسة الخصوصية: لا يغيّر SharkyClips ولا يحذف إلا الفيديوهات التي رفعها بنفسه، وبطلب منك فقط.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
SharkyClips 现在有了官网，应用中的隐私政策链接也能打开了。

- SharkyClips 现在有了网站：[utkualsir.github.io/sharkyclips-site/](https://utkualsir.github.io/sharkyclips-site/)（含隐私政策和使用条款）；
  设置 → YouTube 中的链接已可用。
- 隐私政策更明确：SharkyClips 只会在你要求时修改或删除它自己上传的视频。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
SharkyClips のウェブサイトができ、アプリ内のプライバシーポリシーのリンクも使えるようになりました。

</details>

## [1.2.9] - 2026-11-01
Connect with Google now works out of the box, and loading your own Google client file works again.

### New
- If an older copy of SharkyClips is still running after an update, a bar at the top says so,
  with a **Restart now** button.
- **Connect with Google** is ready to use: SharkyClips now ships its own Google connection, so
  you don't need a Google Cloud project. Google is still reviewing the app, so for now it shows
  its "unverified app" screen first.

### Fixed
- **Advanced → load your own Google client file**: a valid Google client file could show an
  empty warning with the Save button greyed out. That happened when SharkyClips was updated
  while an older copy was still running in the background. The file box now never blocks a
  valid file, and files saved as UTF-8 with a BOM, UTF-16 ("Unicode" in Notepad) or with
  Windows line endings all load.
- Opening SharkyClips after an update now restarts an older copy that's still running (when
  it's not busy), so you always get the new version.

<!-- lang:tr -->
**Türkçe**

**Google ile bağlan** artık kurulumsuz çalışıyor ve kendi Google istemci dosyanı yüklemek yine çalışıyor.

### Yeni
- Güncellemeden sonra SharkyClips'in eski bir kopyası hâlâ çalışıyorsa, üstte bunu söyleyen ve
  **Şimdi yeniden başlat** düğmesi olan bir şerit çıkıyor.
- **Google ile bağlan** kullanıma hazır: SharkyClips artık kendi Google bağlantısıyla geliyor,
  Google Cloud projesine gerek yok. Google uygulamayı hâlâ inceliyor; şimdilik önce "doğrulanmamış
  uygulama" ekranını gösteriyor.

### Düzeltmeler
- **Gelişmiş → kendi Google istemci dosyanı yükle**: geçerli bir `client_secret….json` boş bir
  uyarı gösterip Kaydet düğmesini soluk bırakabiliyordu. Bu, SharkyClips güncellenirken eski bir
  kopyası arka planda çalışmaya devam ettiğinde oluyordu. Dosya kutusu artık geçerli bir dosyayı
  asla engellemiyor; BOM'lu UTF-8, UTF-16 (Not Defteri'nde "Unicode") ya da Windows satır sonlarıyla
  kaydedilmiş dosyalar da yükleniyor.
- Güncellemeden sonra SharkyClips'i açmak, hâlâ çalışan eski kopyayı (meşgul değilse) yeniden
  başlatıyor; böylece her zaman yeni sürümü kullanıyorsun.

<details><summary>Español</summary>

<!-- lang:es -->
Conectar con Google ya funciona sin configurar nada, y cargar tu propio archivo de cliente de Google vuelve a funcionar.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Conectar com o Google agora funciona sem configurar nada, e carregar seu próprio arquivo de cliente do Google voltou a funcionar.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Mit Google verbinden funktioniert jetzt sofort, und das Laden deiner eigenen Google-Client-Datei klappt wieder.

**Mit Google verbinden** funktioniert jetzt ohne Einrichtung.

- Behoben: Eine gültige `client_secret….json` (Erweitert) zeigte eine leere Warnung, wenn nach
  einem Update noch eine alte SharkyClips-Version lief. Dateien mit BOM, UTF-16 oder
  Windows-Zeilenenden werden jetzt auch geladen.
- Läuft nach einem Update noch die alte Version, startet SharkyClips sie neu (wenn sie nichts
  zu tun hat) oder zeigt eine Leiste mit **Jetzt neu starten**.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Se connecter avec Google marche maintenant sans réglage, et charger ton propre fichier client Google refonctionne.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A Kapcsolódás Google-lal most beállítás nélkül működik, és a saját Google-kliensfájl betöltése is újra megy.

A **Csatlakozás Google-lal** most beállítás nélkül működik.

- Javítva: egy érvényes `client_secret….json` (Speciális) üres figyelmeztetést mutatott, ha
  frissítés után még a régi SharkyClips futott. A BOM-os, UTF-16-os vagy Windows-sorvégű fájlok
  is betöltődnek.
- Ha frissítés után még a régi verzió fut, a SharkyClips újraindítja (ha épp nem dolgozik), vagy
  egy sávot mutat **Újraindítás most** gombbal.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
«Войти через Google» теперь работает сразу, а загрузка своего файла клиента Google снова работает.

**Подключить через Google** теперь работает без настройки.

- Исправлено: корректный `client_secret….json` (Дополнительно) показывал пустое предупреждение,
  если после обновления ещё работала старая версия SharkyClips. Файлы с BOM, в UTF-16 или с
  переводами строк Windows тоже загружаются.
- Если после обновления ещё работает старая версия, SharkyClips перезапускает её (когда она не
  занята) или показывает полосу с кнопкой **Перезапустить**.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح "الاتصال بـ Google" يعمل مباشرة، وعاد تحميل ملف عميل Google الخاص بك للعمل.

صار **الربط عبر Google** يعمل دون أي إعداد.

- تم الإصلاح: كان ملف `client_secret….json` صالح (في متقدم) يُظهر تحذيرًا فارغًا إذا بقي إصدار
  قديم من SharkyClips يعمل بعد التحديث. تُحمَّل الآن أيضًا الملفات بترميز UTF-8 مع BOM أو UTF-16 أو
  بنهايات أسطر Windows.
- إذا بقي الإصدار القديم يعمل بعد التحديث، يعيد SharkyClips تشغيله (إن لم يكن مشغولًا) أو يُظهر
  شريطًا بزر **أعد التشغيل الآن**.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
“使用 Google 连接”现在开箱即用，加载你自己的 Google 客户端文件也恢复正常。

**通过 Google 连接**现在无需任何设置即可使用。

- 已修复：更新后如果旧版 SharkyClips 仍在运行，有效的 `client_secret….json`（高级）会显示空白警告。
  带 BOM、UTF-16 或 Windows 换行的文件现在也能加载。
- 更新后旧版本仍在运行时，SharkyClips 会将其重启（空闲时），或显示带有**立即重启**按钮的提示条。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
「Google で接続」がすぐ使えるように。独自の Google クライアントファイルの読み込みも再び動作します。

</details>

## [1.2.8] - 2026-11-01
Connecting YouTube now takes one click and about 10 seconds. No Google Cloud setup, no codes to copy.

### New
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

### Improved
- Using your own Google Cloud project is still possible, under **Advanced**: a new guide with
  one step per screen, a drawing for each step, buttons that open the exact Google Cloud page
  and a check for each step. Drop the downloaded Google client file on the app or paste its
  contents; SharkyClips checks it and says in plain words what's wrong if it's the wrong file.

<!-- lang:tr -->
**Türkçe**

YouTube'u bağlamak artık tek tık ve yaklaşık 10 saniye. Google Cloud kurulumu yok, kopyalanacak kod yok.

### Yeni
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

### İyileştirmeler
- Kendi Google Cloud projenle bağlanmak hâlâ mümkün, **Gelişmiş** altında: her ekranda tek adım,
  her adım için bir çizim, tam doğru Google Cloud sayfasını açan düğmeler ve her adım için bir
  kontrol içeren yeni bir rehber. İndirdiğin `client_secret….json` dosyasını uygulamaya bırak ya da
  içeriğini yapıştır; SharkyClips dosyayı kontrol eder, yanlış dosyaysa sorunu sade bir dille söyler.

<details><summary>Español</summary>

<!-- lang:es -->
Conectar YouTube ahora es un clic y unos 10 segundos. Sin configurar Google Cloud ni copiar códigos.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Conectar o YouTube agora leva um clique e uns 10 segundos. Sem configurar o Google Cloud, sem copiar códigos.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
YouTube verbinden dauert jetzt einen Klick und etwa 10 Sekunden. Keine Google-Cloud-Einrichtung, keine Codes zum Kopieren.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Connecter YouTube prend maintenant un clic et environ 10 secondes. Pas de Google Cloud à configurer, pas de code à copier.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A YouTube összekötése most egy kattintás és nagyjából 10 másodperc. Nincs Google Cloud-beállítás, nincs kódmásolás.

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
Подключение YouTube теперь — один щелчок и около 10 секунд. Без настройки Google Cloud и копирования кодов.

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
ربط YouTube يحتاج الآن نقرة واحدة ونحو 10 ثوانٍ. بلا إعداد Google Cloud ولا رموز لنسخها.

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
连接 YouTube 现在只需一次点击，约 10 秒。无需设置 Google Cloud，也不用复制代码。

连接 YouTube 现在只需一键、大约 10 秒，无需设置 Google Cloud。

- **使用 Google 连接**：在浏览器中登录、选择账号、点击“允许”，频道名称和头像立即显示。
- 打开前会有图示提示，告诉你在 Google 警告页面上点哪里。
- 首次启动和发布窗口中都有可选的“连接 YouTube”步骤。
- Google 结束登录时，每个页面都会显示带**重新连接**按钮的提示条；取消、没有频道、多个频道也都有引导。
- 仍可在**高级**中使用自己的 Google 项目，新的分步向导会检查 JSON 文件（拖放或粘贴）。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
YouTube の接続はワンクリック、約 10 秒で完了。Google Cloud の設定もコードのコピーも不要です。

</details>

## [1.2.7] - 2026-10-30
Publish to YouTube on a schedule: a new Library for every finished clip, one setup screen per clip, and automatic uploads at your daily limit.

### New
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
  busy, never above your daily limit or Google's daily limit (shown in the Library), and never
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
- Your YouTube sign-in is now stored **encrypted** (with the protection Windows and macOS have built in).
- Views and likes are fetched every 6 hours and teach the viral score, the best release times and
  the A/B hook test by themselves.

- Scheduling, cancelling and playlists need one more YouTube permission: if you connected before,
  press **Reconnect YouTube** once in Settings.

<!-- lang:tr -->
**Türkçe**

YouTube'a zamanlanmış yayın: her hazır klip için yeni bir Kütüphane, klip başına tek bir ayar ekranı ve günlük sınırına göre otomatik yükleme.

### Yeni
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

### İyileştirmeler
**İyileştirildi**
- YouTube oturumun artık **şifreli** saklanıyor (Windows DPAPI, macOS Anahtar Zinciri).
- İzlenme ve beğeniler 6 saatte bir alınıyor; viral puanını, en iyi yayın saatlerini ve A/B kanca
  testini kendiliğinden eğitiyor.

- Zamanlama, iptal ve oynatma listeleri bir YouTube izni daha gerektiriyor: daha önce bağladıysan
  Ayarlar'da bir kez **YouTube'u yeniden bağla**'ya bas.

<details><summary>Español</summary>

<!-- lang:es -->
Publica en YouTube con horario: una nueva Biblioteca para cada clip terminado, una pantalla de ajustes por clip y subidas automáticas hasta tu límite diario.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Publique no YouTube com agenda: uma nova Biblioteca para cada clipe pronto, uma tela de configuração por clipe e uploads automáticos até seu limite diário.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Nach Zeitplan auf YouTube veröffentlichen: eine neue Bibliothek für jeden fertigen Clip, ein Einstellungsbildschirm pro Clip und automatische Uploads bis zu deinem Tageslimit.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Publie sur YouTube selon un planning : une nouvelle Bibliothèque pour chaque clip prêt, un écran de réglage par clip et des envois automatiques jusqu'à ta limite du jour.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Ütemezett közzététel a YouTube-on: új Könyvtár minden kész kliphez, egy beállítóképernyő klipenként, és automatikus feltöltés a napi limitig.

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
Публикация на YouTube по расписанию: новая Библиотека для готовых клипов, один экран настройки на клип и автозагрузки в пределах дневного лимита.

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
انشر على YouTube وفق جدول: مكتبة جديدة لكل مقطع جاهز، وشاشة إعداد واحدة لكل مقطع، ورفع تلقائي ضمن حدّك اليومي.

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
按计划发布到 YouTube：为每个完成的剪辑新增资料库，每个剪辑一个设置界面，并在每日上限内自动上传。

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

<details><summary>日本語</summary>

<!-- lang:ja -->
YouTube へ予約公開：完成したクリップを集めた新しいライブラリ、クリップごとの設定画面、1 日の上限内での自動アップロード。

</details>

## [1.2.6] - 2026-10-27
A safer phone mode, a faster start, better accessibility, and fixes for Mac.

### New
- **Access PIN for other devices.** When you use SharkyClips from your phone, you
  can set a PIN or password in **Settings → Other devices**.
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
- **Mac**: SharkyClips now finds its helper tools when started from the Dock on new Apple
  Silicon Macs; the uninstaller no longer stops halfway, and it closes SharkyClips before
  removing it.

<!-- lang:tr -->
**Türkçe**

Daha güvenli telefon modu, daha hızlı açılış, daha iyi erişilebilirlik ve Mac düzeltmeleri.

### Yeni
- **Diğer cihazlar için erişim PIN'i.** SharkyClips'i telefonundan kullanıyorsan (`--lan` modu)
  **Ayarlar → Diğer cihazlar**'dan (ya da `python cli.py lan-pin` ile) bir PIN veya parola
  belirleyebilirsin. Diğer cihazlar bir kez giriş yapar; bu bilgisayar hiç gerekmez. Yanlış
  denemeler yavaşlatılır ve PIN yalnızca güvenli bir özet (hash) olarak saklanır. PIN yoksa Ayarlar,
  ağındaki herkesin SharkyClips'i açabileceği konusunda uyarır.
- Ayarlar → YouTube artık YouTube Hizmet Şartları'na, Google Gizlilik Politikası'na, SharkyClips'in
  kendi gizlilik politikasına ve erişimi Google hesabından nasıl kaldıracağına bağlantı veriyor.

### İyileştirmeler
**İyileştirildi**
- **Daha hızlı açılış, daha hafif uygulama**: sunucu daha çabuk hazır olur ve yaklaşık 60 MB daha az
  bellek kullanır; uygulama yalnızca kullandığın dili yükler, ilk ekran daha hızlı gelir.
- **Erişilebilirlik**: açık temada ve metin düzenleyicide daha iyi kontrast, ekran okuyucular için
  her düğme ve listenin bir adı var, klavye odağı Hızlı inceleme gibi pencerelerin içine geçiyor.
- Küçük resim yüklemek veya büyük bir sohbet kaydı içe aktarmak artık canlı ilerlemeyi bir anlığına
  dondurmuyor.

### Düzeltmeler
- **Mac**: SharkyClips, yeni Apple Silicon Mac'lerde Dock'tan açıldığında FFmpeg, Git ve Deno'yu
  artık buluyor; kaldırma aracı yarıda kalmıyor ve kaldırmadan önce SharkyClips'i kapatıyor.

<details><summary>Español</summary>

<!-- lang:es -->
Un modo móvil más seguro, un inicio más rápido, mejor accesibilidad y arreglos para Mac.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Um modo celular mais seguro, uma abertura mais rápida, melhor acessibilidade e correções para Mac.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Ein sichererer Handy-Modus, ein schnellerer Start, bessere Barrierefreiheit und Korrekturen für den Mac.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Un mode téléphone plus sûr, un démarrage plus rapide, une meilleure accessibilité et des corrections pour Mac.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Biztonságosabb telefonos mód, gyorsabb indulás, jobb akadálymentesség és javítások Macre.

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
وضع هاتف أكثر أمانًا، وبدء أسرع، وإتاحة أفضل، وإصلاحات لـ Mac.

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
更安全的手机模式、更快的启动、更好的无障碍支持，以及 Mac 修复。

更安全的手机模式、更快的启动、更好的无障碍体验，以及 Mac 修复。

- **新增：其他设备的访问 PIN**（`--lan` 模式）：在 **设置 → 其他设备** 或用 `python cli.py lan-pin`
  设置。错误尝试会被限速，PIN 只以安全哈希保存。未设置 PIN 时设置页会提醒。
- **更快更轻**：服务器更早就绪，内存少用约 60 MB，应用只加载你使用的语言。
- **无障碍**：浅色主题对比度更好，屏幕阅读器可读出名称，键盘焦点会进入弹出窗口。
- **Mac**：从 Dock 启动时能找到 FFmpeg、Git 和 Deno；卸载程序不再中途停止。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
より安全なスマホモード、高速な起動、アクセシビリティの改善、Mac 向けの修正。

</details>

## [1.2.5] - 2026-10-27
Retention tools: seamless loops, story clips from the whole stream, A/B hooks that learn what works on your channel, and exact editor timelines.

### New
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
  fairly across your clips; 48 hours after publishing, views and retention
  are fetched by themselves, and **Stats > Hook styles that work for you** shows each style with
  its number of videos, a likely range and the chance that it's the best. A clip is never uploaded
  twice. If Google keeps your uploads private (a Google project that isn't reviewed yet), SharkyClips says so and
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

İzlenme süresini artıran araçlar: kusursuz döngüler, yayının tamamından hikâye klipleri, kanalında neyin işe yaradığını öğrenen A/B kancalar ve render ile birebir aynı düzenleyici zaman çizelgeleri.

### Yeni
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

### Düzeltmeler
- **Düzenleyici zaman çizelgeleri (DaVinci Resolve, Final Cut Pro, Premiere Pro) artık render'daki
  her şeyi içeriyor**: metin kesimleri ve sessizlik / dolgu kesimleri aynı geçişlerle ayrı klipler
  olarak, bipler (kendi ses izi + işaretçiler), zoom anahtar kareleri, ses kısmalı müzik, ayrı izlerde
  marka kiti, giriş / kapanış kartları ve kanca flaşı. Her kesim, render edilen MP4'teki kareyle aynı
  karede. Final Cut altyazı ve işaretçili dosyaları artık reddetmiyor (yanlış öğe sırası).
- Altyazı dosyaları (SRT / VTT) artık dışa aktarılan videonun kesimlerine ve giriş kartına uyuyor.
- Kanca flaşı ve giriş / kapanış kartları tam planlandığı uzunlukta (bir iki kare uzun olabiliyordu).

<details><summary>Español</summary>

<!-- lang:es -->
Herramientas de retención: bucles perfectos, clips con historia de todo el directo, ganchos A/B que aprenden qué funciona en tu canal y líneas de tiempo exactas.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Ferramentas de retenção: loops perfeitos, clipes com história da live inteira, ganchos A/B que aprendem o que funciona no seu canal e linhas do tempo exatas.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Werkzeuge für die Zuschauerbindung: nahtlose Loops, Story-Clips aus dem ganzen Stream, A/B-Hooks, die lernen, was auf deinem Kanal wirkt, und exakte Schnitt-Zeitleisten.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Outils de rétention : boucles parfaites, clips-histoires tirés de tout le live, accroches A/B qui apprennent ce qui marche sur ta chaîne et timelines de montage exactes.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Nézőmegtartó eszközök: tökéletes hurkok, történetklipek az egész adásból, A/B nyitások, amelyek megtanulják, mi működik a csatornádon, és pontos vágási idővonalak.

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
Инструменты удержания: бесшовные петли, клипы-истории из всего стрима, A/B-зацепки, которые учатся на вашем канале, и точные таймлайны для монтажа.

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
أدوات للاحتفاظ بالمشاهدين: حلقات سلسة، ومقاطع قصصية من البث كله، وافتتاحيات A/B تتعلم ما ينجح على قناتك، وخطوط زمنية دقيقة للمونتاج.

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
留存工具：无缝循环、从整场直播剪出故事剪辑、会学习你频道效果的 A/B 开头，以及精确的剪辑时间线。

提升观看时长的工具：无缝循环、用整场直播组成的故事剪辑、能学习你频道偏好的 A/B 开头，以及与渲染结果完全一致的剪辑软件时间线。

- **新增：无缝循环**：结尾自然接回开头（落在合适的停顿处，绝不在词语中间，没有黑场），编辑器中可**循环预览**，并测量接缝。
- **新增：故事剪辑**（**故事**按钮）：用整场直播的精彩时刻组成 2–3 个 30–60 秒的迷你故事，可调整顺序，转场快速，字幕连贯，音量统一，并有专属发布素材包。
- **新增：A/B 开头**：每个剪辑两个开头，立即打分并说明原因；从应用上传时，真实测试会在 48 小时后了解哪种开头风格最适合你（统计页）。
- **修复：**剪辑软件时间线现在包含渲染中的全部内容，精确到帧；字幕文件也会跟随剪切。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
視聴維持のためのツール：シームレスループ、配信全体からのストーリークリップ、チャンネルで効く冒頭を学ぶ A/B フック、正確な編集タイムライン。

</details>

## [1.2.4] - 2026-10-26
Editing power tools: bleep swear words, cut silences, smart zoom, edit by transcript, your own music, a brand kit and fast review.

### New
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

Düzenleme araçları: küfür bip'leme, sessizlik kesme, akıllı zoom, metinden düzenleme, kendi müziğin, marka kiti, elle klip ekleme ve hızlı inceleme modlu klavye kısayolları.

### Yeni
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

<details><summary>Español</summary>

<!-- lang:es -->
Herramientas de edición: pitar palabrotas, cortar silencios, zoom inteligente, editar por transcripción, tu propia música, kit de marca y revisión rápida.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Ferramentas de edição: bipar palavrões, cortar silêncios, zoom inteligente, editar pela transcrição, sua própria música, kit de marca e revisão rápida.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Starke Schnittwerkzeuge: Schimpfwörter überpiepen, Stille schneiden, Smart-Zoom, per Transkript schneiden, eigene Musik, ein Brand-Kit und schnelle Durchsicht.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Outils de montage : biper les gros mots, couper les silences, zoom intelligent, monter par la transcription, ta propre musique, un kit de marque et une revue rapide.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Erős vágóeszközök: káromkodás kisípolása, csend kivágása, okos zoom, vágás a leirat alapján, saját zene, márkacsomag és gyors átnézés.

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
Мощные инструменты монтажа: запикивание мата, вырезание пауз, умный зум, монтаж по тексту, своя музыка, фирменный стиль и быстрый просмотр.

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
أدوات مونتاج قوية: تغطية الشتائم بالصافرة، وقص الصمت، وتكبير ذكي، وتحرير عبر النص، وموسيقاك الخاصة، وهوية بصرية، ومراجعة سريعة.

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
强大的剪辑工具：哔掉脏话、剪掉静音、智能缩放、按文字稿剪辑、使用你自己的音乐、品牌套件和快速审阅。

剪辑工具：脏话哔声、剪掉静音、智能缩放、按文字稿剪辑、你自己的音乐、品牌套件、手动片段，以及带快速审阅的键盘快捷键。

- **新增：脏话哔声**，支持全部 7 种语言（自动模式用于竖屏视频），也可在字幕中遮住（a**）；词表在**工作室 > 词表**中编辑。
- **新增：剪掉静音和口头禅**，带短暂交叉淡化，绝不在笑声中间剪；另有轻微的**智能缩放**，在高光时刻和你的摄像头画面上推近。
- **新增：按文字稿剪辑**：删除词语即剪掉，拖动 [ ] 修剪片段，可撤销并实时预览。
- **新增：你自己的音乐**（工作室 > 音乐），可标记情绪、按片段推荐、从最有力的部分开始、说话时自动压低、-14 LUFS，并可添加署名；**品牌套件**包含 Logo、@账号、片头 / 片尾和字幕样式。
- **新增：**用 I / O 标记自己的片段、键盘快捷键（按 ? 查看）以及全屏快速审阅。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
強力な編集ツール：汚い言葉のピー音、無音カット、スマートズーム、文字起こしで編集、自分の音楽、ブランドキット、高速レビュー。

</details>

## [1.2.3] - 2026-10-26
A small reliability fix for the Export window.

### Fixed
- The Export window no longer fails to open when the video tool is missing or can't encode H.264. It now
  opens and shows the formats as unavailable, and checks again as soon as the video tool is installed
  (no restart needed).
- Behind the scenes: the automatic tests now run on clean machines too, so every release is
  checked before it reaches you.

<!-- lang:tr -->
**Türkçe**

Dışa Aktar penceresi için küçük bir güvenilirlik düzeltmesi.

### Düzeltmeler
- ffmpeg eksikse veya H.264 kodlayamıyorsa Dışa Aktar penceresi artık açılmamazlık yapmıyor. Pencere
  açılıyor, formatları kullanılamaz olarak gösteriyor ve ffmpeg kurulur kurulmaz yeniden kontrol
  ediyor (yeniden başlatmaya gerek yok).
- Arka planda: otomatik testler artık temiz bilgisayarlarda da çalışıyor; her sürüm sana ulaşmadan
  önce kontrol ediliyor.

<details><summary>Español</summary>

<!-- lang:es -->
Un pequeño arreglo de fiabilidad para la ventana Exportar.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Uma pequena correção de confiabilidade na janela Exportar.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Eine kleine Zuverlässigkeitskorrektur für das Exportfenster.

Eine kleine Zuverlässigkeitskorrektur für das Export-Fenster.

- **Behoben:** Das Export-Fenster öffnet sich jetzt auch ohne ffmpeg (oder ohne H.264-Encoder) und
  zeigt die Formate als nicht verfügbar an. Nach der Installation von ffmpeg wird erneut geprüft,
  ohne Neustart.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
Une petite correction de fiabilité pour la fenêtre Exporter.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Egy kis megbízhatósági javítás az Exportálás ablakhoz.

Egy kis megbízhatósági javítás az Exportálás ablakhoz.

- **Javítva:** Az Exportálás ablak most ffmpeg nélkül (vagy H.264 kódoló nélkül) is megnyílik, és
  nem elérhetőként mutatja a formátumokat. Az ffmpeg telepítése után újraellenőriz, újraindítás nélkül.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Небольшое исправление надёжности окна «Экспорт».

Небольшое исправление надёжности окна экспорта.

- **Исправлено:** окно экспорта теперь открывается и без ffmpeg (или без кодировщика H.264) и
  показывает форматы как недоступные. После установки ffmpeg проверка повторяется без перезапуска.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
إصلاح صغير لموثوقية نافذة التصدير.

إصلاح صغير لموثوقية نافذة التصدير.

- **تم الإصلاح:** تُفتح نافذة التصدير الآن حتى بدون ffmpeg (أو بدون مُرمِّز H.264) وتعرض الصيغ على
  أنها غير متاحة، ثم تتحقق مجددًا فور تثبيت ffmpeg دون إعادة التشغيل.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
对“导出”窗口的一个小稳定性修复。

导出窗口的一个小可靠性修复。

- **修复：** 即使没有 ffmpeg（或没有 H.264 编码器），导出窗口现在也能打开，并将格式显示为不可用；
  安装 ffmpeg 后会自动重新检测，无需重启。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
書き出しウィンドウの小さな安定性修正。

</details>

## [1.2.2] - 2026-10-25
Export your clips for every platform, upload them straight to YouTube, and enjoy a new launch animation.

### New
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
  - **Editor timelines**: timelines for DaVinci Resolve, Final Cut Pro and Premiere Pro,
    with the cut on your original video, the captions and markers for the detected moments (kills,
    laughter, chat spikes...). CapCut has no open project format, so it isn't offered; import the SRT
    file there.
  - Export several clips with one preset in one go; every clip is its own entry in the queue.
- **Direct YouTube upload** through YouTube's free, official upload service:
  - Settings > YouTube walks you through creating your own free Google connection step by step. It is
    stored only on your computer.
  - Per clip: title, description and hashtags filled in from the publish package, visibility
    (private / unlisted / public), scheduled publishing, the "made for kids" answer and a thumbnail
    for 16:9 videos.
  - Uploads run in their own network queue next to rendering (they never wait for the graphics
    card), continue where they stopped after a restart, and the app shows how many uploads are left
    today.
  - SharkyClips remembers each video and fetches its views by itself, so public clips older than
    two days calibrate the viral score automatically (Stats > **Fetch views from YouTube**).
  - Note: Google keeps videos uploaded through a new Google project private until
    Google has reviewed the project (free). Private uploads always work.
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

### Yeni
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

### Düzeltmeler
- Windows'ta uygulama ayar dosyasını okurken bir ayarı kaydetmek ara sıra başarısız olabiliyordu.

<details><summary>Español</summary>

<!-- lang:es -->
Exporta tus clips para cada plataforma, súbelos directamente a YouTube y disfruta de una nueva animación de inicio.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
Exporte seus clipes para cada plataforma, envie direto para o YouTube e curta uma nova animação de abertura.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Exportiere deine Clips für jede Plattform, lade sie direkt zu YouTube hoch und genieße eine neue Startanimation.

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

<details><summary>Français</summary>

<!-- lang:fr -->
Exporte tes clips pour chaque plateforme, envoie-les directement sur YouTube et profite d'une nouvelle animation de démarrage.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Exportáld a klipjeidet minden platformra, töltsd fel őket közvetlenül a YouTube-ra, és élvezd az új indítóanimációt.

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
Экспорт клипов для любой платформы, загрузка прямо на YouTube и новая анимация запуска.

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
صدّر مقاطعك لكل منصة، وارفعها مباشرة إلى YouTube، واستمتع برسوم متحركة جديدة عند التشغيل.

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
为各平台导出剪辑，直接上传到 YouTube，还有全新的启动动画。

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

<details><summary>日本語</summary>

<!-- lang:ja -->
各プラットフォーム向けにクリップを書き出し、YouTube へ直接アップロード。新しい起動アニメーションも。

</details>

## [1.2.1] - 2026-10-25
ClipForge is now SharkyClips, with a new logo, a welcome screen and a working publish package.

### New
- **New name and logo:** ClipForge is now SharkyClips. The logo is a shark fin that is also a play
  button.
- **Welcome screen:** a short animation with "Hunt your best moments." on every start (click or Esc
  skips it, and it never adds waiting time). On the first start a 3-step setup follows: language,
  content types and performance mode, with a quick check of your PC.
- **YouTube description** for every clip: 2-3 natural sentences plus the hashtags, with a copy button.
- **What's new** window after an update, and the version in the footer and in Settings.
- An "Update in progress" banner while a new version is being built; big jobs ask before they start.

### Improved
- Colours: crisp white for headings and key numbers in the dark theme (gold is only the accent), and
  a cleaner, whiter light theme with more room.
- Your settings, liked titles and glossary moved to the new SharkyClips folder by themselves, and
  your shortcuts were renamed.

### Fixed
- **The publish package was empty:** finding highlights again threw away every clip's AI results.
  Clips whose cut didn't change now keep their titles, hashtags and cover idea, and the AI analysis
  continues after a pause or a restart.
- The publish package always says what is going on ("Not analyzed yet", "Waiting: paused", "Analyzing
  3/15" or the error with **Try again**). No more empty grey boxes.
- **No more black console windows** flashing up while SharkyClips works.

<!-- lang:tr -->
**Türkçe**

ClipForge artık **SharkyClips**: yeni logo, karşılama ekranı ve düzgün çalışan yayın paketi.

### Yeni
- Her klip için **YouTube açıklaması**: çıktı dilinde 2-3 doğal cümle ve sonunda etiketler,
  kopyalama düğmesiyle. Daha önce analiz edilen kliplere tek kısa yapay zekâ çağrısı yeter.
- **Yeni ad ve logo**: aynı zamanda oynat düğmesi olan bir köpekbalığı yüzgeci. Ana logo mavi-beyaz;
  koyu tema, sistem tepsisi ve uygulama simgesi için lacivert üzerine beyaz (SVG, PNG, ICO, ICNS, favicon).
- **Karşılama ekranı**: her açılışta "En iyi anların avlanmaya hazır." sloganıyla kısa bir açılış
  (tıklayınca veya Esc ile geçilir; sunucu başlarken oynar, bekleme eklemez). İlk açılışta 3 adımlı
  kurulum: dil, içerik türleri, performans modu + hızlı donanım kontrolü.
- Güncellemeden sonra **Yenilikler** penceresi (bu pencere); sürüm alt bilgide ve Ayarlar'da.
- Yeni sürüm hazırlanırken "Güncelleme yapılıyor" şeridi; ağır işler başlamadan önce sorar.

### İyileştirmeler
- Renkler: koyu temada başlıklar, önemli sayılar ve ikincil düğmeler için net beyaz (altın yalnızca
  vurgu); daha temiz, daha beyaz ve daha ferah açık tema.
- Ayarlar `~/.clipforge` klasöründen `~/.sharkyclips` klasörüne kendiliğinden taşındı (ayarlar,
  çalışma klasörü, beğenilen başlıklar, sözlük, kalibrasyon); masaüstü ve Başlat menüsü kısayolları ile
  Uygulamalar listesindeki kayıt yeniden adlandırıldı. `CLIPFORGE_HOME` hâlâ çalışır.
- Python paketi ve komut satırı artık `sharkyclips`. Sürüm tek bir yerde: `VERSION`.

### Düzeltmeler
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

<details><summary>Español</summary>

<!-- lang:es -->
ClipForge ahora es SharkyClips, con logo nuevo, pantalla de bienvenida y un paquete de publicación que funciona.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O ClipForge agora é SharkyClips, com logo novo, tela de boas-vindas e um pacote de publicação que funciona.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
ClipForge heißt jetzt SharkyClips, mit neuem Logo, Willkommensbildschirm und funktionierendem Veröffentlichungspaket.

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

<details><summary>Français</summary>

<!-- lang:fr -->
ClipForge devient SharkyClips, avec un nouveau logo, un écran d'accueil et un pack de publication qui fonctionne.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A ClipForge mostantól SharkyClips: új logó, üdvözlőképernyő és működő közzétételi csomag.

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
ClipForge теперь называется SharkyClips: новый логотип, экран приветствия и рабочий пакет публикации.

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
أصبح ClipForge الآن SharkyClips، بشعار جديد وشاشة ترحيب وحزمة نشر تعمل.

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
ClipForge 现更名为 SharkyClips，带来新标志、欢迎界面和可用的发布包。

ClipForge 现更名为 **SharkyClips**：新标志、欢迎界面，以及正常工作的发布包。

- **修复：** 重新运行高光分析后发布包为空。剪辑范围未变的片段现在会保留 AI 结果，AI 分析在暂停或重启后会继续。
  发布包始终显示当前状态（尚未分析、等待中、“正在分析 3/15”、出错时可“重试”）。
- **修复：** SharkyClips 工作时不再闪现黑色控制台窗口。
- **新增：** 每个片段的 YouTube 简介（2-3 句 + 话题标签），可一键复制。
- **新增：** 标志（鲨鱼鳍同时也是播放按钮）、带标语的启动画面、首次启动的 3 步设置、本“新功能”窗口，页脚和设置中显示版本号。
- **变更：** 深色主题以白色为品牌色，浅色主题更干净、更留白。设置已自动从 `~/.clipforge` 迁移到 `~/.sharkyclips`。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
ClipForge は SharkyClips に。新しいロゴ、ようこそ画面、ちゃんと動く公開パッケージ。

</details>

## [1.2.0] - 2026-10-25
SharkyClips must never slow down your PC: performance modes, pauses while you play, and a resource monitor in the top bar.

### New
- **Performance modes:** Silent (the default), Balanced and Turbo, in Settings, the top bar and the
  tray menu. Silent works slowly in the background and pauses while you play a game, stream, watch a
  video or use a full-screen app. It works at full speed when you're away.
- **Careful with your PC:** SharkyClips keeps about 2 GB of graphics memory free for your games, stops
  when the graphics card gets too hot, and paused work continues exactly where it stopped.
- **Resource monitor** in the top bar: processor, graphics card, memory and temperature, with
  "Resume anyway". Click it for 5-minute charts of SharkyClips and your other apps.
- **Tray icon:** open SharkyClips, change the performance mode or quit, without a console window.
- A setting to start the local AI with Windows (off by default).

### Improved
- The local AI is unloaded from the graphics card after every job and as soon as a pause starts.
- With no job running and no SharkyClips tab open, SharkyClips does almost nothing.

### Fixed
- The local AI's installer made it start with Windows. SharkyClips now turns that off unless you
  want it.

<!-- lang:tr -->
**Türkçe**

SharkyClips bilgisayarını asla yavaşlatmamalı: performans modları, oyun oynarken duraklama ve üst çubukta kaynak izleyici.

<details><summary>Español</summary>

<!-- lang:es -->
SharkyClips nunca debe ralentizar tu PC: modos de rendimiento, pausas mientras juegas y un monitor de recursos en la barra superior.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O SharkyClips nunca deve deixar seu PC lento: modos de desempenho, pausas enquanto você joga e um monitor de recursos na barra superior.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
SharkyClips soll deinen PC nie ausbremsen: Leistungsmodi, Pausen während du spielst und eine Ressourcenanzeige in der oberen Leiste.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
SharkyClips ne doit jamais ralentir ton PC : modes de performance, pauses pendant que tu joues et un moniteur de ressources dans la barre du haut.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A SharkyClips sosem lassíthatja a gépedet: teljesítménymódok, szünet játék közben és erőforrás-figyelő a felső sávban.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
SharkyClips не должен тормозить ваш ПК: режимы производительности, пауза во время игры и монитор ресурсов в верхней панели.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
يجب ألا يبطئ SharkyClips جهازك أبدًا: أوضاع أداء، وتوقف مؤقت أثناء اللعب، ومراقب للموارد في الشريط العلوي.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
SharkyClips 绝不能拖慢你的电脑：性能模式、玩游戏时自动暂停，以及顶栏中的资源监视器。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
SharkyClips が PC を重くすることはありません：パフォーマンスモード、プレイ中の一時停止、上部バーのリソースモニター。

</details>

## [1.1.0] - 2026-10-25
SharkyClips now reads the screen of League of Legends and Delta Force, so kills, multikills and extractions become clip moments.

### New
- **SharkyClips knows your game:** for League of Legends and Delta Force it reads the game's screen
  and finds the big moments by itself.
  - League of Legends: every kill, death and assist; double, triple, quadra and pentakills; first
    blood, shutdowns, aces, Baron and Dragon steals; victory and defeat; and your champion.
  - Delta Force: kills, multikills, revives, revenge kills, assists, your deaths and extractions.
  - A 4-hour stream is checked in about 6-12 minutes on an NVIDIA graphics card.
  - Big moments (triple kills and up, steals, extractions) always become a clip, and a clip always
    contains the whole moment, for example every kill of a multikill.
  - The moments show as small labels on the clip and help the AI write titles ("Quadra kill with
    Yasuo").
- A game picker per project (Auto, Delta Force, League of Legends, Other).
- **Game detection page:** see the frames SharkyClips checked, every moment it found, and move the
  screen areas it reads if a game update moves them.

<!-- lang:tr -->
**Türkçe**

SharkyClips artık League of Legends ve Delta Force ekranını okuyor; kill'ler, çoklu kill'ler ve tahliyeler klip anı oluyor.

<details><summary>Español</summary>

<!-- lang:es -->
SharkyClips ya lee la pantalla de League of Legends y Delta Force: las bajas, multikills y extracciones se convierten en momentos de clip.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
O SharkyClips agora lê a tela de League of Legends e Delta Force: abates, multikills e extrações viram momentos de clipe.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
SharkyClips liest jetzt den Bildschirm von League of Legends und Delta Force: Kills, Multikills und Extraktionen werden zu Clip-Momenten.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
SharkyClips lit maintenant l'écran de League of Legends et Delta Force : kills, multikills et extractions deviennent des moments de clip.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
A SharkyClips most már olvassa a League of Legends és a Delta Force képernyőjét: a killek, multikillek és kimenekítések klip-pillanatok lesznek.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
SharkyClips теперь читает экран League of Legends и Delta Force: убийства, мультикиллы и эвакуации становятся моментами для клипов.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أصبح SharkyClips يقرأ شاشة League of Legends وDelta Force، فتتحول عمليات القتل والقتل المتعدد والإخلاء إلى لحظات مقاطع.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
SharkyClips 现在能读取《英雄联盟》和《三角洲行动》的画面，击杀、多杀和撤离都会成为剪辑时刻。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
SharkyClips が League of Legends と Delta Force の画面を読み取り、キル・マルチキル・脱出をクリップの見どころにします。

</details>

## [1.0.0] - 2026-10-24
The first public release: find the best moments of your streams and make 9:16 clips, with a one-click installer and updates.

### New
- **Easy install:** a one-click installer for Windows and macOS. It lists what it will set up, asks
  once and reuses what you already have.
- **Desktop shortcut and Start menu entry** with the new icon. They open SharkyClips in your browser
  and reuse a SharkyClips that is already running.
- **Uninstaller:** it asks before deleting your projects, settings or AI models.
- **Settings → Updates:** checks for a new version, installs it and restarts SharkyClips.
- New app icon, a README with screenshots and a demo, and automatic tests for every release.

**Before 1.0.0**
- **Find the best moments:** loudness, key words, laughter and shouting, chat activity and music are
  combined into a hype curve, and the clips start and end on whole words.
- **Clips in 9:16:** a library, a project page with the Hype Map and a live 9:16 preview, facecam
  detection, word-timed captions (also right-to-left Arabic), 7 languages, dark and light theme, and
  use from your phone on the same Wi-Fi.
- **Local AI:** chat replay from YouTube, Twitch or a log file, a viral score, better cuts, titles,
  hashtags, a hook text, a cover idea and translated captions, all on your PC.
- **Natural AI titles** in your style, with a glossary, spell checks and 👍 / 👎 to teach it.
- **Queue, best-of videos and calibration:** one job per clip, a queue that survives restarts, an
  optional shutdown when done, 16:9 best-of videos with chapters, and a viral score tuned with your
  real YouTube views.

<!-- lang:tr -->
**Türkçe**

İlk herkese açık sürüm: yayınlarının en iyi anlarını bul ve 9:16 klipler yap; tek tıkla kurulum ve güncellemeler.

<details><summary>Español</summary>

<!-- lang:es -->
La primera versión pública: encuentra los mejores momentos de tus directos y haz clips 9:16, con instalador de un clic y actualizaciones.

</details>

<details><summary>Português (Brasil)</summary>

<!-- lang:pt -->
A primeira versão pública: encontre os melhores momentos das suas lives e faça clipes 9:16, com instalador de um clique e atualizações.

</details>

<details><summary>Deutsch</summary>

<!-- lang:de -->
Die erste öffentliche Version: Finde die besten Momente deiner Streams und mach 9:16-Clips, mit Ein-Klick-Installation und Updates.

</details>

<details><summary>Français</summary>

<!-- lang:fr -->
La première version publique : trouve les meilleurs moments de tes lives et fais des clips 9:16, avec une installation en un clic et des mises à jour.

</details>

<details><summary>Magyar</summary>

<!-- lang:hu -->
Az első nyilvános kiadás: találd meg az adásaid legjobb pillanatait, és készíts 9:16-os klipeket, egykattintásos telepítéssel és frissítésekkel.

</details>

<details><summary>Русский</summary>

<!-- lang:ru -->
Первый публичный выпуск: находите лучшие моменты стримов и делайте клипы 9:16, с установкой в один щелчок и обновлениями.

</details>

<details><summary>العربية</summary>

<!-- lang:ar -->
أول إصدار عام: اعثر على أفضل لحظات بثوثك واصنع مقاطع 9:16، مع تثبيت بنقرة واحدة وتحديثات.

</details>

<details><summary>中文</summary>

<!-- lang:zh -->
首个公开版本：找到直播中的精彩时刻并制作 9:16 剪辑，支持一键安装和更新。

</details>

<details><summary>日本語</summary>

<!-- lang:ja -->
最初の一般公開版：配信の名場面を見つけて 9:16 クリップを作成。ワンクリックのインストールと更新つき。

</details>

[1.0.0]: https://github.com/utkualsir/sharkyclips/releases/tag/v1.0.0
