# Google verification (YouTube uploads)

> **Türkçe özet:** Amaç, SharkyClips'in Google OAuth uygulamasını doğrulatıp 100 kullanıcı sınırını
> kaldırmak. Hazır olanlar: `utkualsir.github.io` alan adı için Search Console doğrulama dosyası
> yayında (https://utkualsir.github.io/google182e06ea924d62bd.html), site ve gizlilik politikası
> Google/YouTube kurallarına göre güncellendi, 120x120 logo `docs/logo-120.png`. Senin yapacakların:
> (1) Search Console'da `https://utkualsir.github.io/` için "HTML dosyası" yöntemiyle **Doğrula**'ya
> bas, (2) aşağıdaki "Branding" alanlarını Google Cloud Console'a kopyala, (3) iki kapsamı (scope)
> ekleyip gerekçe metinlerini yapıştır, (4) demo videosunu senaryoya göre kaydedip YouTube'a
> **liste dışı** yükle ve bağlantısını forma ekle, (5) **Doğrulamaya gönder**. Uygulama iki kapsam
> istiyor: `youtube` ve `yt-analytics.readonly` (sadece yükleme değil; gizlilik politikası buna göre
> doğru yazıldı). İkisi de "hassas" kapsam, "kısıtlı" değil, bu yüzden ücretli güvenlik denetimi
> (CASA) gerekmez.

Everything below is ready to paste into **Google Cloud Console → Google Auth Platform**. Nothing
has been submitted yet. Older and longer answers (plus the TikTok review) are in
[docs/audits/](audits/README.md).

## 1. Domain proof (Search Console)

- Property: **URL prefix** `https://utkualsir.github.io/` (domain properties need DNS, which
  GitHub Pages does not give you).
- Method: **HTML file**. The file is live:
  https://utkualsir.github.io/google182e06ea924d62bd.html (returns
  `google-site-verification: google182e06ea924d62bd.html`, HTTP 200).
- It is served by the public repo
  [utkualsir/utkualsir.github.io](https://github.com/utkualsir/utkualsir.github.io) (your GitHub
  Pages user site). Its `index.html` redirects to the SharkyClips site. **Do not delete that file
  or repo**: Google re-checks it from time to time.
- `github.io` is on the Public Suffix List, so `utkualsir.github.io` counts as your own domain and
  can be an authorized domain. The SharkyClips site at `/sharkyclips-site/` is under that domain.

## 2. Branding (OAuth consent screen)

| Field | Value |
|---|---|
| App name | `SharkyClips` (exactly as the app and the site show it) |
| User support email | Pick your own Google account's address from the dropdown (or a Google Group you own). Google only offers addresses you control. Users see it on the consent screen. |
| App logo | `docs/logo-120.png` (120x120 PNG, made by `python installer/make_icons.py --google`). Optional: a logo adds a brand check and can make the review slower. |
| Application home page | `https://utkualsir.github.io/sharkyclips-site/` |
| Application privacy policy link | `https://utkualsir.github.io/sharkyclips-site/privacy.html` |
| Application terms of service link | `https://utkualsir.github.io/sharkyclips-site/terms.html` |
| Authorized domains | `utkualsir.github.io` |
| Developer contact information | Your own email address (Google uses it to send review messages; it is not shown to users). |

What the site already covers (checked 26 Nov 2026):

- The homepage describes SharkyClips, has a "How SharkyClips uses YouTube" section with both
  scopes, and links to the privacy policy and the terms (top menu, footer and the YouTube section).
- The privacy policy explains what Google/YouTube data is used and why (a table for each scope),
  that it is stored **locally on the user's computer only** (encrypted token, no server), how long
  it is kept, how to revoke access (Disconnect in the app, plus links to
  https://myaccount.google.com/permissions and
  https://security.google.com/settings/security/permissions), and links to the
  [YouTube Terms of Service](https://www.youtube.com/t/terms), the
  [Google Privacy Policy](https://policies.google.com/privacy) and the Google API Services User
  Data Policy (Limited Use).
- All three pages load without a login (HTTP 200).

## 3. Scopes (Data access)

The app requests exactly these two scopes (`SCOPES` in `backend/sharkyclips/youtube.py`, sent
together in one sign-in). Add exactly these, nothing else:

| Scope | Type | Shown to the user as |
|---|---|---|
| `https://www.googleapis.com/auth/youtube` | Sensitive | Manage your YouTube account |
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Sensitive | View YouTube Analytics reports for your YouTube content |

Neither scope is restricted, so no CASA security assessment is needed.

### Justification: `https://www.googleapis.com/auth/youtube`

> SharkyClips is a free, open-source desktop app for streamers. It finds the best moments in a
> stream recording on the user's own computer and turns them into short vertical clips. The main
> use of this scope is uploading a clip the user chose to the user's own YouTube channel
> (videos.insert, resumable). Scheduled clips are uploaded as private with status.publishAt, so
> YouTube publishes them at the time the user picked. Around those uploads the app also needs to:
> change the title, description or release time of a clip it uploaded, or publish it early, when
> the user edits it in the app's calendar (videos.update); delete a scheduled clip that the user
> cancels before it is public (videos.delete); put the clip into a playlist the user picks or
> creates (playlists.list, playlists.insert, playlistItems.insert); set a thumbnail
> (thumbnails.set); show which channel is connected (channels.list, mine=true); and show the
> views, likes and privacy status of the user's own SharkyClips uploads (videos.list, only the IDs
> of videos the app uploaded). If the user turns on live chat reading, the app reads the chat of
> the user's own live stream to find "!clip" markers; it never posts. The narrower youtube.upload
> scope cannot update, schedule-change or delete a video, and youtube.force-ssl would add comment
> access the app does not need. The app never changes or deletes videos it did not upload, and
> never acts without the user starting the action. All data stays on the user's computer; the
> developers run no server and never receive it.

### Justification: `https://www.googleapis.com/auth/yt-analytics.readonly`

> Used only for the optional "hook test". SharkyClips makes two versions of the first seconds of
> a clip, uploads one, and 48 hours after it was published reads the averageViewPercentage and
> averageViewDuration of that one video (YouTube Analytics reports.query, ids=channel==MINE,
> filtered to that video ID). The result tells the user which opening style keeps their own
> viewers watching. Retention numbers are not available through the YouTube Data API, so there is
> no narrower scope. The numbers are stored only on the user's computer, are deleted when the user
> disconnects, and are never shared.

### How the sign-in works (if the reviewer asks)

- OAuth 2.0 authorization code flow with **PKCE (S256)**, `access_type=offline`,
  `prompt=select_account consent`, client type **Desktop app**.
- Redirect: a one-time loopback listener on `http://127.0.0.1:<random port>/`, closed right after
  Google redirects back (or after 10 minutes / Cancel).
- The token is stored encrypted on the user's computer only (Windows DPAPI / macOS Keychain).
  **Disconnect** revokes it at `https://oauth2.googleapis.com/revoke` and deletes it, together with
  every number the app read from YouTube.

## 4. Demo video (2-3 minutes, English UI, English captions)

Record the screen at 1080p with the app in English. Upload to YouTube as **Unlisted** and paste the
link into the form. Burn in the captions below (or upload them as an English subtitle track). Use
a test channel. Before recording, disconnect YouTube in the app and remove SharkyClips from
https://myaccount.google.com/permissions so the full consent screen appears.

| Time | What to show | Caption |
|---|---|---|
| 0:00-0:15 | SharkyClips home screen, then a project with finished clips. | "This is SharkyClips, a free desktop app that turns stream recordings into short clips. It runs on the user's own computer." |
| 0:15-0:30 | Settings → YouTube. Point at the notice "SharkyClips uses YouTube API Services..." and its links (YouTube Terms of Service, Google Privacy Policy). | "YouTube is optional. The user connects their own channel here. The YouTube Terms and the Google Privacy Policy are linked next to the button." |
| 0:30-0:40 | Click **Connect YouTube** (in the dialog, **Connect with Google**). The system browser opens. | "The user clicks Connect YouTube. Google's sign-in opens in the browser." |
| 0:40-0:55 | **Zoom into the browser URL bar** and hold for 3 seconds so `client_id=...apps.googleusercontent.com` can be read. | "The URL shows the OAuth client ID of the project under review." |
| 0:55-1:20 | Pick the account. Show the consent screen: the app name **SharkyClips** at the top and both permissions ("Manage your YouTube account", "View YouTube Analytics reports for your YouTube content"). Scroll slowly so both are visible, then click **Continue / Allow**. | "The consent screen shows the app name SharkyClips and the two permissions it asks for: managing the user's YouTube uploads, and reading YouTube Analytics for its own uploads." |
| 1:20-1:30 | The browser tab says it is connected. Back in the app, the channel name and picture appear. | "Connected. The app shows which channel it will upload to." |
| 1:30-2:05 | Open a project's clip → **Upload**. Show the dialog: title, description, tags, **Privacy = Private**. Press Upload, show the progress bar and the finished link. Open the link in YouTube Studio and show the video is **Private**. | "The user picks a clip, sets the details and uploads it as private. This uses the youtube scope to insert the video on the user's own channel." |
| 2:05-2:20 | Library calendar: drag a scheduled clip to another day, then cancel one. | "Scheduled clips can be moved or cancelled. The app only changes or deletes videos it uploaded itself." |
| 2:20-2:35 | The hook test screen (A/B openings). | "For the optional hook test, 48 hours after publishing, the app reads the average view percentage of that one video. This uses yt-analytics.readonly." |
| 2:35-2:55 | Settings → YouTube → **Disconnect** → confirm. Then open https://myaccount.google.com/permissions and show SharkyClips is gone. | "To stop access, the user clicks Disconnect. The app revokes the token and deletes the YouTube data it stored. Access can also be removed on the Google account permissions page." |
| 2:55-3:00 | Homepage with the privacy policy link. | "All data stays on the user's computer. Privacy policy: utkualsir.github.io/sharkyclips-site/privacy.html" |

## 5. After approval

- Set `verification` to `verified` in the shipped `google_client.json` (kept out of the repo, see
  `docs/SECURITY_AUDIT.md`) and release an app update, so Settings stops showing the 100-user note.
- OAuth verification removes the 100-user cap and the "Google hasn't verified this app" screen. It
  does **not** lift the YouTube rule that uploads from unaudited API projects stay private, and it
  does not raise the 10,000 units a day quota. Those need the separate
  [YouTube API Services audit / quota form](https://support.google.com/youtube/contact/yt_api_form);
  the answers are in [docs/audits/](audits/README.md).

## Decision log (26 Nov 2026, unattended session)

- **Created the public repo `utkualsir/utkualsir.github.io`** as asked (GitHub Pages user site,
  branch `main`, root). It holds only the Search Console file, a redirect `index.html` and
  `.nojekyll`. Commits use the GitHub no-reply address. The main `sharkyclips` repo's visibility
  was not touched.
- **Privacy policy says what the code really does, not "upload only".** The app requests
  `youtube` and `yt-analytics.readonly`, and also schedules, edits, cancels, reads stats of its
  own uploads and (opt-in) reads the user's own live chat. Writing "upload only" would not match
  the scopes, and Google rejects policies that don't match. So the new summary box says uploading
  is the main use and lists the rest. Existing policy text was kept.
- **Privacy policy additions:** an "In short" box (data used, stored locally, how to revoke, YouTube
  Terms and Google Privacy Policy links), the Google security settings link
  (security.google.com/settings/security/permissions, named by the YouTube API Developer
  Policies) next to the account permissions link, and a "Last updated" date.
- **Fixed one wrong sentence:** the policy said the site's fonts come from Google Fonts; since
  1.2.65 they are served from the site itself.
- **Homepage:** the YouTube section now also links to the YouTube Terms of Service, the Google
  Privacy Policy and the terms of use.
- **Logo:** regenerated with `installer/make_icons.py --google`; only `docs/logo-120.png`
  changed.
- **Support email:** not written into this file because the repo is public. Pick it from the
  dropdown in the console.
- **Another session's work was left alone:** a 1.2.66 session had uncommitted app changes and its
  own "under construction" flag in this working tree. This session committed only its own docs
  files and did not touch that flag. No app code changed, so no version bump.
