# Google verification prep (YouTube uploads)

Draft material for two separate Google reviews. **Nothing here has been submitted.** Fill in the
`<...>` placeholders, check every answer against the app version you submit, then copy the text
into the forms.

1. **OAuth app verification** (Google Cloud Console → Google Auth Platform → Verification Center).
   Needed because all three scopes are *sensitive*. None is *restricted*, so no paid security
   assessment (CASA) is required.
2. **YouTube API Services audit / quota extension**
   ([form](https://support.google.com/youtube/contact/yt_api_form)). Needed so videos uploaded
   through the project are not forced to private, and for more than 10,000 units a day.

## Read first: which Google project gets verified?

Today every user creates **their own** Google Cloud project and OAuth client (Settings → YouTube
guide). An unverified, unaudited project keeps uploads private, so today each user would need
their own audit, which is not realistic.

Verification only helps users if SharkyClips ships **one shared OAuth client** owned by you,
with the per-user client kept as an "advanced" option. That is a code change I did **not** make
(it changes the setup flow and the quota model: one 10,000-unit daily pool shared by everyone =
6 uploads a day in total until the quota extension is granted). Decide this before submitting.
Notes for that change:

- A "Desktop app" client's secret is not confidential (Google says so for installed apps); it can
  ship in the source. PKCE + loopback redirect are already implemented in `youtube.py`.
- Keep the user's own client as an override, so heavy users keep their own quota.

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
- [ ] OAuth consent screen: app name **SharkyClips**, the 120x120 logo
      (`assets/icon/sharkyclips.png`, resize), support email `<support email>`, authorized domain
      `utkualsir.github.io`, the three URLs above, developer contact `<email>`.
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

`https://www.googleapis.com/auth/youtube.upload`

> Used to upload a clip the user rendered to the user's own channel, when the user presses
> "Upload" for that clip. The user sets the title, description, tags, privacy status, optional
> publish schedule and thumbnail in the upload dialog before anything is sent. Uploads are
> resumable so a large file survives a restart. The app never uploads without that click.

`https://www.googleapis.com/auth/youtube.readonly`

> Used for three read-only calls: (1) `channels.list?mine=true` to show which channel is
> connected (name and avatar) in Settings; (2) `videos.list` for the IDs of videos the user
> uploaded *with SharkyClips* to show their views, likes and privacy status next to each clip and
> to detect when an upload was forced to private; (3) the same numbers calibrate the app's local
> "viral score" to the user's own channel. `youtube.upload` alone cannot read video status or
> statistics. No other channels, comments, subscribers or playlists are read.

`https://www.googleapis.com/auth/yt-analytics.readonly`

> Used only for the optional "hook test": the app renders two versions of a clip's first
> seconds, uploads one version, and 48 hours after it was published reads that video's
> `averageViewPercentage` and `averageViewDuration` (YouTube Analytics `reports.query`,
> `ids=channel==MINE`, filtered to that video ID). The result tells the user which opening style
> keeps *their* viewers watching. These retention metrics are not available through the YouTube
> Data API, so a narrower scope does not exist.

**How is the data stored and shared?**

> All data stays on the user's computer, in the app's settings folder: the OAuth token
> (`~/.sharkyclips/youtube/token.json`), the per-project upload list with the latest statistics
> (`uploads.json`) and derived learning data (`calibration.json`, `hook_tests.json`). The app
> calls Google APIs directly from the user's machine. The developers run no server and never
> receive, store or share any Google user data. Nothing is used for advertising or sold.
> Disconnecting in Settings revokes the token (`oauth2.googleapis.com/revoke`) and deletes it.

**Demo video script** (2-3 minutes, English UI, screen recording, show the browser URL bar
during the Google sign-in so the client ID is visible):

1. Open SharkyClips, Settings → YouTube. Show the notice "SharkyClips uses YouTube API
   Services..." with the links to the YouTube Terms, the Google Privacy Policy and the
   SharkyClips privacy policy.
2. Click **Connect YouTube**. Show the Google consent screen with the app name and all three
   scopes, then allow.
3. Back in Settings: the connected channel name and avatar (`youtube.readonly`).
4. Open a project with a rendered clip → **Upload**. Show the dialog (title, description, tags,
   privacy = Private, schedule, thumbnail), press Upload, show the progress and the finished
   link; open the video on YouTube Studio (`youtube.upload`).
5. Stats → **Fetch views from YouTube**: the clip's views and status appear (`youtube.readonly`).
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
  - YouTube Data API v3: `videos.insert` (resumable), `thumbnails.set`, `channels.list`
    (`mine=true`, `part=snippet`), `videos.list` (`part=statistics,status,snippet`, own video IDs
    only, up to 50 per call).
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
  (thumbnail); statistics cost 1 unit per 50 videos. With a shared client and N active users
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
- **Shared client** (see the top of this page).
