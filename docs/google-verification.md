# Google verification prep (YouTube uploads)

Draft material for two separate Google reviews. **Nothing here has been submitted.** Fill in the
`<...>` placeholders, check every answer against the app version you submit, then copy the text
into the forms.

1. **OAuth app verification** (Google Cloud Console → Google Auth Platform → Verification Center).
   Needed because both scopes are *sensitive*. None is *restricted*, so no paid security
   assessment (CASA) is required.
2. **YouTube API Services audit / quota extension**
   ([form](https://support.google.com/youtube/contact/yt_api_form)). Needed so videos uploaded
   through the project are not forced to private, and for more than 10,000 units a day.

## Read first: the shared client (since 1.2.8)

SharkyClips now ships **one built-in Google OAuth client** ("Desktop app" type) that the owner
creates once: `backend/sharkyclips/google_client.json`. That client is what gets verified and
audited. Users click **Connect with Google** and are done; nobody else needs a Google Cloud
project. The user's own client stays available under Settings → YouTube → **Advanced** (heavy
uploaders keep their own 10,000-unit quota; it also always works if the shared client is full).

How the sign-in works (what reviewers will ask):

- OAuth 2.0 authorization code + **PKCE (S256)**, `access_type=offline`,
  `prompt=select_account consent`.
- Redirect: a one-shot listener on **`http://127.0.0.1:<random port>/`**, started per sign-in
  and closed right after Google redirects back (or after 10 minutes / Cancel). Google allows any
  loopback port for Desktop clients, so no redirect URI is registered.
- The client secret ships in the source. Google documents that an installed app's secret is not
  confidential; PKCE + the loopback redirect protect the code exchange.
- The token is stored encrypted on the user's computer only (DPAPI / macOS Keychain).

`google_client.json` fields: `client_id`, `client_secret`, `project_id`, `verification`
(`testing` | `unverified` | `in_review` | `verified`, shown in Settings) and `user_cap`
(100 = Google's limit for unverified apps with sensitive scopes, shown in Settings). Update
`verification` there when Google's status changes; the app picks it up after the next update.

### Limits while the shared client is unverified

- **Publishing status "Testing":** only listed test users (max. 100) can sign in, and Google
  ends their sign-in after **7 days**. Use this only for your own first test.
- **Publishing status "In production", not verified:** anyone can sign in after Google's
  "Google hasn't verified this app" screen (the app shows an illustrated tip before opening the
  browser), up to **100 users in total** for the lifetime of the project until verified.
- **Quota:** all users share the project's 10,000 units a day (about 6 uploads) until the
  quota extension is granted. The app counts units locally per user; when Google says the quota
  is used up, uploads wait for the next reset.
- **Private lock:** until the YouTube API audit passes, every video uploaded through the
  project stays private. The app detects this and says so.

## Before you submit (checklist)

- [ ] Repo public, and the site published: run the **Project site** workflow
      (`.github/workflows/pages.yml`) after setting Settings → Pages → Source to "GitHub Actions".
- [ ] Homepage `https://utkualsir.github.io/sharkyclips/`, privacy policy
      `.../privacy.html`, terms `.../terms.html` load without login.
- [ ] Verify `utkualsir.github.io` in [Google Search Console](https://search.google.com/search-console)
      (URL-prefix property, HTML file method: put the file into `docs/site/` and rerun the
      workflow). `github.io` is on the Public Suffix List, so this subdomain counts as your own
      domain. If Google still rejects it, a cheap custom domain pointing at Pages fixes it
      (then update `PRIVACY_URL` in `frontend/src/components/Publish.tsx`).
- [ ] OAuth consent screen (Branding): app name **SharkyClips** (exactly as in the app), the
      120x120 logo (PNG, square, no extra text; resize `assets/icon/sharkyclips.png`), support
      email `<support email>`, homepage / privacy / terms = the three URLs above, authorized
      domain `utkualsir.github.io`, developer contact `<email>`. The logo needs extra review
      time; leave it out for the first, unverified phase if you want to publish faster.
- [ ] `google_client.json` filled in and released (an app update), `verification` set.
- [ ] Scopes on the consent screen exactly match `youtube.SCOPES`.
- [ ] Record the demo video (script below), upload it to YouTube as **unlisted**.
- [ ] App name and logo on the consent screen match the app (Google checks this).

## OAuth verification form

**App name:** SharkyClips

**What does your app do? (short description)**

> SharkyClips is a free, open-source desktop app (Windows and macOS) for streamers. It finds the
> best moments in a stream recording on the user's own computer and renders them as vertical
> short videos with subtitles. Users can optionally upload a finished clip to their own YouTube
> channel from inside the app. The app runs entirely locally; it has no server and no account.

**Scope justifications**

`https://www.googleapis.com/auth/youtube`

> Used only on the user's own channel and only for videos the user publishes with SharkyClips:
> (1) `videos.insert` (resumable) to upload a clip the user set up in the publish screen (title,
> description, tags, category, language, made-for-kids, privacy, optional release time and
> playlist); scheduled clips are uploaded as private with `status.publishAt`, so YouTube itself
> publishes them at the chosen time; (2) `videos.update` when the user edits the details of such a
> video or moves its release time in the app's calendar, and to publish a scheduled video now;
> (3) `videos.delete` when the user cancels a scheduled video before it is public; (4)
> `playlists.list` / `playlists.insert` / `playlistItems.insert` to put the clip into a playlist
> the user picks or creates; (5) `thumbnails.set` for 16:9 videos; (6) `channels.list?mine=true`
> to show the connected channel and `videos.list` for the views, likes and privacy of the user's
> own SharkyClips uploads (shown next to each clip, used to calibrate the local viral score and to
> notice when uploads are forced to private). `youtube.upload` cannot change, schedule or delete a
> video, and `youtube.force-ssl` would add comment access the app doesn't need. Nothing is done
> without the user setting up and scheduling the clip first.

`https://www.googleapis.com/auth/yt-analytics.readonly`

> Used only for the optional "hook test": the app renders two versions of a clip's first
> seconds, uploads one version, and 48 hours after it was published reads that video's
> `averageViewPercentage` and `averageViewDuration` (YouTube Analytics `reports.query`,
> `ids=channel==MINE`, filtered to that video ID). The result tells the user which opening style
> keeps *their* viewers watching. These retention metrics are not available through the YouTube
> Data API, so a narrower scope does not exist.

**How is the data stored and shared?**

> All data stays on the user's computer, in the app's settings folder: the OAuth token
> (`~/.sharkyclips/youtube/token.enc`, encrypted with Windows DPAPI or a key in the macOS
> Keychain), the per-project upload list with the latest statistics
> (`uploads.json`) and derived learning data (`calibration.json`, `hook_tests.json`). The app
> calls Google APIs directly from the user's machine. The developers run no server and never
> receive, store or share any Google user data. Nothing is used for advertising or sold.
> Disconnecting in Settings revokes the token (`oauth2.googleapis.com/revoke`) and deletes it.

**Demo video script** (2-3 minutes, English UI, screen recording, show the browser URL bar
during the Google sign-in so the client ID is visible):

1. Open SharkyClips, Settings → YouTube. Show the notice "SharkyClips uses YouTube API
   Services..." with the links to the YouTube Terms, the Google Privacy Policy and the
   SharkyClips privacy policy.
2. Click **Connect with Google**. The system browser opens Google's sign-in: zoom into the URL
   bar so the `client_id` of the project under review is visible. Pick the account, show the
   consent screen with the app name and both scopes (read them out), then **Allow**.
3. The browser tab shows "Connected!"; back in the app the channel name and avatar appear at
   once (`youtube`: `channels.list mine=true`).
4. Library → select clips → **Schedule** (auto-plan), show the calendar and drag one clip to
   another day (`videos.update`), cancel one (`videos.delete`). Then a project's clip → **Upload**. Show the dialog (title, description, tags,
   privacy = Private, schedule, thumbnail), press Upload, show the progress and the finished
   link; open the video on YouTube Studio (`youtube`).
5. Stats → **Fetch views from YouTube**: the clip's views and status appear (`youtube`).
6. Show the hook test screen and explain that 48 hours after publishing the app reads the
   average view percentage of that one video (`yt-analytics.readonly`).
7. Settings → YouTube → **Disconnect**, then show the app gone from
   myaccount.google.com/permissions.

## YouTube API Services audit / quota extension form

Answers for the usual questions. Google changes the form now and then; map them to the current
fields.

- **Organization / developer:** `<your name>` (individual developer), open-source project.
- **API client name:** SharkyClips · **Google Cloud project number:** `<number>`
- **Website:** https://utkualsir.github.io/sharkyclips/ · **Source:** https://github.com/utkualsir/sharkyclips
- **Privacy policy:** https://utkualsir.github.io/sharkyclips/privacy.html
- **Terms of use:** https://utkualsir.github.io/sharkyclips/terms.html
- **Platform:** desktop app (Windows, macOS), local web UI on 127.0.0.1.
- **Who uses it:** streamers and video creators uploading their own clips to their own channel.
- **APIs and methods used:**
  - YouTube Data API v3: `videos.insert` (resumable, private + `publishAt` for scheduled clips),
    `videos.update` (details / release time of own videos), `videos.delete` (cancel a scheduled
    upload), `thumbnails.set`, `playlists.list` / `playlists.insert` (`mine=true`),
    `playlistItems.insert`, `channels.list` (`mine=true`, `part=snippet`), `videos.list`
    (`part=statistics,status,snippet`, own video IDs only, up to 50 per call).
  - YouTube Analytics API v2: `reports.query` (`ids=channel==MINE`, `dimensions=video`,
    `metrics=views,averageViewDuration,averageViewPercentage`, filtered to own video IDs).
- **How do users authenticate?** OAuth 2.0 authorization code flow with PKCE and a loopback
  redirect (`http://127.0.0.1:<port>/`), `access_type=offline`.
- **Is API data shown to anyone other than the authenticated user?** No. It is shown only in the
  local app of the user who connected the channel.
- **Is API data stored? How long?** Only on the user's computer: video IDs of their own uploads,
  plus the latest view/like counts and retention for those videos, refreshed when the app syncs
  (about twice a day while it runs). Kept until the user deletes the project, clears calibration
  or disconnects/uninstalls. The developers store nothing.
- **Do you aggregate or combine data across users?** No. There is no central server; each
  installation only sees its own user's data.
- **Do you use the data for advertising?** No.
- **Quota requested:** `<number>` units/day. Reasoning: one upload = 1,600 units (insert) + 50
  (thumbnail) + 50 (playlist); changing or cancelling a scheduled video 50; statistics cost 1 unit
  per 50 videos. The app's scheduler never plans more uploads a day than the quota allows. With a shared client and N active users
  uploading ~2 clips a day: N × 3,300 units. Start with a modest request (e.g. 100,000/day ≈ 30
  uploads/day) and increase with real usage. The app already counts units locally, stops before
  the limit and shows the remaining uploads to the user.
- **Branding:** the app does not use YouTube logos except as plain text ("YouTube"); no
  YouTube player is embedded. Links to YouTube Terms of Service and Google Privacy Policy are shown
  next to the Connect button.

## Known gaps to fix before (or explain in) the audit

- **Stored statistics after disconnect.** Disconnect deletes the token, but the view counts
  already fetched stay in `uploads.json` / `calibration.json` until the user clears them. The
  YouTube Developer Policies ask clients to delete stored authorized data when access is revoked
  (and to refresh or delete it regularly). Suggested follow-up: a "Also delete fetched
  statistics" checkbox in the disconnect dialog, and dropping fetched numbers older than 30 days
  that could not be refreshed.
- **Shared quota.** One 10,000-unit pool for every user of the built-in client until the
  quota extension is granted (see "Quota requested").
