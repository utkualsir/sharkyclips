# Phase D5 / 1.2.75: Upload stats + honest YouTube quota

## Kısa rapor (Türkçe)

**Yayınlandı: 1.2.75.** Neler yapıldı:

- **Test hızı (adım 0, önceden yapılmamıştı):** yerel `scripts/quick-check.py` (ruff + sadece
  değişen dosyaların testleri + isteğe bağlı küçük layout seti), pytest-xdist (paralel testler),
  CI'da layout matrisi 4 paralel parçaya bölündü, Playwright tarayıcıları önbellekte. Öncesi/sonrası
  süreler: `docs/test-speed.md` (tüm testler yerelde 24,5 dk → 9,4 dk; tek modül değişikliği 3–31 sn; layout smoke 30 sn).
- **Yüklemeler sekmesi** (Geçmiş sayfası): bugün / bu hafta / toplam, YouTube / Instagram / TikTok /
  elle. Her sayı ve çubuk üzerine gelince, odaklanınca ya da dokununca altta klipler listelenir
  (saat, platform, bağlantı, durum). Son 14 günün yığılmış grafiği; renkler temada
  (`--chart-1..4`), renk körlüğü testi geçti.
- **Dürüst YouTube kotası:** paylaşılan SharkyClips istemcisinde artık uydurma "X kaldı" yok:
  "Ortak günlük havuz, senin saatinle 09:00'da sıfırlanır" + bugün senin yüklediklerin.
  quotaExceeded gelince: "Bugünkü ortak yükleme hakkı doldu. 09:00'da sıfırlanır." + "Elle yükle" /
  "Kendi Google istemcini kullan". Kendi istemcinde tam sayaç: "Bugün 100 yüklemeden X kaldı"
  (Google'ın güncel kuralı: yükleme kendi kovasında, günde 100, her biri 1).
- **Hata düzeltmesi:** quotaExceeded sonrası "bugün yüklediğin" sayısı 100'e fırlıyordu; artık gerçek.
- **Sahip görünümü** (Ayarlar → Gelişmiş, varsayılan kapalı): Cloud Console kota sayfasına bağlantı.
  Hiçbir sahip bilgisi/anahtarı uygulamada yok.
- **Ortak havuz sayacı hazır, KAPALI:** `workers/shared-pool/worker.js` (Cloudflare Worker, salt-okur
  servis hesabı sadece Worker secret'ında). Uygulama tarafı `poolcounter.py`, ayar kapalı ve adres
  boş. Senin yapacakların aşağıda ("Owner TODO").
- **Rehber:** `docs/own-google-client.md`: kendi kişisel Google projeni kurma adımları.
- 11 dil, layout + axe, testler, CHANGELOG (11 dil), sürüm, etiket, CI.

**Senin yapacakların (sıra önemli değil):**
1. `docs/own-google-client.md` ile kendi projeni kur (10 dk). Sonra Geçmiş → Yüklemeler'de
   "100 yüklemeden X kaldı" görmelisin.
2. Google doğrulaması onaylanınca: aşağıdaki "Shared-pool counter setup" adımları + gizlilik
   politikası cümlesi (taslak aşağıda, YAYINLANMADI).

---

## Decisions (logged while working unattended)

1. **Test speed first.** `docs/test-speed.md` did not exist, so step 0 was done before the feature.
2. **Local parallelism capped at 6 workers.** `-n auto` (24 workers) on the dev PC crashed with
   `MemoryError` during collection: every worker imports the whole backend. CI keeps `-n auto`
   (2-4 cores). `--dist loadfile` everywhere: files that share module state stay on one worker.
3. **Layout matrix in 4 shards** (`LAYOUT_SHARD=i/n`, round-robin over every preset × language ×
   theme × size combination). Each shard has its own fixture server (composite action
   `.github/actions/fixture-server`). The preview / mini game / axe / browser checks moved to their
   own job, the presets job keeps axe + personalization (their layout runs in the matrix).
4. **Playwright browsers cached** (`actions/cache` v4, pinned SHA, key = lockfile + browser list);
   on a hit only the system packages are installed.
5. **Stats source = upload history** (`history.py`), not the platform records: it already holds
   every post incl. "I posted it", survives project deletes and has the link. A manual post counts
   only under "By hand" so the four groups add up to the total; the details row still names the
   platform.
6. **Week = since Monday**, local time of this PC (the server runs on the user's PC). Shown as
   "since Monday, Nov 23" so nobody has to guess.
7. **Hover details as a fixed panel under the chart, not a floating tooltip.** Hover, keyboard focus
   and tap all "pick" a number or bar; the panel keeps the last pick, so its links can be clicked
   (a tooltip disappears when the pointer moves to it) and phones work the same way. `aria-live`
   announces the pick. Every number and bar is a real button (`aria-pressed`, `aria-controls`).
8. **Chart colours** are 4 new theme tokens (`--chart-1..4`, YouTube / Instagram / TikTok / by hand),
   because the platform brand colours are all reds. Validated with the dataviz palette checker on
   the dark (#111a2e) and light (#ffffff) surfaces: lightness band, chroma, CVD ΔE ≥ 9.8, normal
   ΔE ≥ 20, 3:1 contrast. All presets inherit them.
9. **Quota rules re-checked** on Google's page (2026-11-27): `videos.insert` has its own bucket,
   100 calls a day, 1 per upload; 10,000 units for everything else; reset at midnight Pacific.
   So "own client" = an exact "X of 100".
10. **Shared client never shows a count** unless the pool counter gives the real project number.
    This PC can't know what other users uploaded; the old "X uploads left today" (100 minus mine)
    was wrong for the shared client. The Share pill, Accounts, Publish dialog, Library summary and
    publish tools now say "Shared daily pool · yours today: N". Uploads are still gated locally by
    the old counter (it is the upper bound) and by Google's quotaExceeded answer.
11. **quotaExceeded keeps "my count" true:** `quota.json` stores `uploads_full: true` instead of
    overwriting `uploads` with 100. `uploads_used()` (gating) still returns the full bucket.
12. **"Upload manually" in the quota card** opens the Library (sharing by hand is per clip, from
    its Share page). **"Use your own Google client"** opens Settings at the YouTube card.
13. **Owner view = only a link** (`console.cloud.google.com/apis/api/youtube.googleapis.com/quotas?project=<id>`),
    behind `owner_view` (off). The own client's quota page is always linked (it is the user's
    own project).
14. **Pool counter off twice:** `poolcounter.DEFAULT_ON = False` and `POOL_URL = ""`. A user can't
    switch it on by accident (needs the toggle AND an https address). The app sends a bare GET
    (no parameters, cookies or IDs, `User-Agent: SharkyClips`, no redirects), caches 5 minutes,
    validates the answer (whole numbers, sane limit, reset within 49 h) and silently falls back to
    "Shared daily pool".
15. **Worker reads Cloud Monitoring**, not the Service Usage API: `quota/rate/net_usage` summed
    from Pacific midnight (`ALIGN_SUM` + `REDUCE_SUM`), `quota/limit` (newest in 2 days, `LIMIT`
    var as fallback). DST days (23 h / 25 h) are handled and tested. The exact `quota_metric` name of
    the new upload bucket is not documented publicly, so it is a Worker variable the owner copies
    from the Quotas page.
16. **History table on phones** became small cards (it scrolled sideways). Found because the layout
    fixture now has upload history (it had none before, so the table was never checked with rows).
17. **No privacy policy change published.** Draft below.

## Shared-pool counter setup (owner, after Google verification)

Free tier is enough: Workers free plan = 100,000 requests a day; the app asks at most every
5 minutes per running SharkyClips (~288 a day), the Worker answers from its own 5-minute cache, so
Google Monitoring sees about 12 reads an hour per Cloudflare location.

1. **Google Cloud (the SHARED SharkyClips project)**
   1. APIs & Services → Library → **Cloud Monitoring API** → Enable.
   2. IAM & Admin → **Service accounts** → Create: name `sharkyclips-pool-reader`, role
      **Monitoring Viewer** (`roles/monitoring.viewer`) only. No other role.
   3. The account → **Keys → Add key → Create new key → JSON**. The file downloads once.
      Keep it out of the repo (`.gitignore` already blocks `workers/**/*key*.json`).
   4. Find the quota metric: IAM & Admin → **Quotas & System Limits** → filter
      *Service: YouTube Data API v3* → the per-day upload (`videos.insert`) row → details: copy the
      **metric** name (looks like `youtube.googleapis.com/...`). Cross-check in Monitoring →
      Metrics explorer: `serviceruntime.googleapis.com/quota/rate/net_usage`, filter
      `service = youtube.googleapis.com`, group by `quota_metric`.
2. **Cloudflare** (free account, <https://dash.cloudflare.com/sign-up>)
   ```bash
   cd workers/shared-pool
   cp wrangler.toml.example wrangler.toml      # git-ignored
   # edit wrangler.toml: PROJECT_ID = the shared project id, QUOTA_METRIC = the metric from 1.4
   npx wrangler login
   npx wrangler secret put SA_KEY              # paste the WHOLE JSON key file, then Enter
   npx wrangler deploy                         # prints https://sharkyclips-pool.<you>.workers.dev
   ```
   Then delete the downloaded key file from your Downloads (the secret now lives only in Cloudflare).
3. **Check**: `curl https://sharkyclips-pool.<you>.workers.dev/` → `{"used":N,"limit":100,"resets_at":"…Z"}`.
   Compare `used` with the Cloud Console quota page.
4. **Owner test in SharkyClips**: Settings → Advanced → Owner view → *Counter address* = the Worker
   URL → Save → turn on *Shared pool counter (test)*. History → Uploads shows
   "Shared pool: X of 100 left today" with "used today by everyone / updated / resets".
5. **Ship it for everyone** (only after Google approves verification): a release that sets
   `poolcounter.POOL_URL` to the Worker URL and `DEFAULT_ON = True`, plus the privacy sentence
   below on the website (privacy page, all 11 languages).
6. Rotating the key: create a new key, `wrangler secret put SA_KEY`, delete the old key in Cloud.

### Privacy policy addition (DRAFT, not published)

> When the shared upload counter is on, SharkyClips asks our own small server (a Cloudflare Worker)
> how much of the shared daily YouTube upload limit is used; the request contains no account,
> channel, video or other personal data, the server only reads the project-wide quota number from
> Google Cloud, and like any web server Cloudflare processes your IP address to deliver the answer,
> which we do not log.

## What was not done / known limits

- The Worker is not deployed (needs your Cloudflare + Google accounts). Its logic is tested
  against a fake Google (node, generated RSA key) in `test_upload_stats.py`.
- The real metric name of the upload bucket is unknown until you look it up (step 1.4).
- Stats count what SharkyClips knows (its uploads + "I posted it"); posts made elsewhere aren't seen.
