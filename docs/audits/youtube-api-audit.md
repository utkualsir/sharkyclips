# YouTube API Services audit and quota extension (SharkyClips)

Where: the **YouTube API Services - Audit and Quota Extension Form**
(https://support.google.com/youtube/contact/yt_api_form). Prepared for SharkyClips 1.2.38;
nothing has been submitted. Google changes the form now and then; map these answers to the
current fields. Submit **after** the OAuth verification (or together with it): the reviewer
looks at the same consent screen and site.

**Why:** until the audit passes, every video uploaded through the project is locked to private
(the app detects this and tells the user), and all users share the project's 10,000 units a day
(about 6 uploads).

## Form answers

| Question | Answer |
|---|---|
| Organization / developer | `<your full name>`, individual developer, open-source project |
| Contact email | `<your email>` |
| API client / product name | SharkyClips |
| Google Cloud project number | `<number: Cloud Console → Dashboard → Project info>` |
| Project ID | `sharkyclips` |
| Website | https://utkualsir.github.io/sharkyclips-site/ |
| Source code | https://github.com/utkualsir/sharkyclips (public, MIT) |
| Privacy policy | https://utkualsir.github.io/sharkyclips-site/privacy.html |
| Terms of use | https://utkualsir.github.io/sharkyclips-site/terms.html |
| Platform | Installed desktop app (Windows, macOS); local web UI on 127.0.0.1; optional phone page on the same Wi-Fi (PIN protected) |
| Monetization | None. Free, no ads, no paid tier |
| Users | Streamers and video creators uploading their own clips to their own channel |
| Expected users | `<number>` active users in the next 6 months (be honest; a modest start is fine) |

**Describe how your API client uses the YouTube API Services**

> SharkyClips turns the user's own stream recordings into short vertical clips on the user's
> computer. With the YouTube API the user uploads those clips to their own channel, schedules
> them (private + publishAt), changes or cancels scheduled clips, adds them to a playlist, and
> sees their views and likes. An optional A/B hook test reads the average view percentage of one
> of the user's own clips through the YouTube Analytics API. Every action is started by the user;
> the app never touches videos it didn't upload, other channels, comments or subscribers.

**APIs and methods**

- YouTube Data API v3: `videos.insert` (resumable), `videos.update`, `videos.delete` (only own
  scheduled clips), `videos.list` (`part=statistics,status,snippet`, own video IDs, up to 50 per
  call), `thumbnails.set`, `channels.list` (`mine=true`), `playlists.list` / `playlists.insert`
  (`mine=true`), `playlistItems.insert`, optional `liveBroadcasts.list` (`mine=true`) +
  `liveChatMessages.list` (own live stream, read-only, off by default).
- YouTube Analytics API v2: `reports.query` (`ids=channel==MINE`, `dimensions=video`,
  `metrics=views,averageViewDuration,averageViewPercentage`, filtered to own video IDs).

**Authentication**

> OAuth 2.0 authorization code flow with PKCE and a loopback redirect, scopes `youtube` and
> `yt-analytics.readonly`. Tokens are stored encrypted on the user's computer only.

**Is API data shown to anyone other than the authenticated user?**

> No. It is shown only in the user's own local app.

**Do you store API data? For how long? How is it deleted?**

> Only on the user's computer: video IDs of the user's own SharkyClips uploads, and the latest
> views / likes / privacy / retention of those videos. While YouTube is connected and the app
> runs, the numbers are refreshed every few hours (statistics about twice a day). Any number not
> refreshed for 30 days is deleted automatically (`backend/sharkyclips/ytdata.py`). Disconnect
> revokes the token and deletes every fetched number at once; if Google ends the sign-in and the
> user doesn't reconnect, the numbers are deleted after 7 days. The developer stores nothing.

**Do you aggregate data across users / combine with other data?**

> No. There is no central server; each installation only sees its own user's data. Locally the
> app combines the user's own clip numbers with its own analysis of the user's own clips (to
> calibrate the clip score). Nothing is shared or sold, nothing is used for advertising.

**Quota requested**

> `<100,000>` units/day. One upload = 1,600 (insert) + 50 (thumbnail) + 50 (playlist item) ≈
> 1,700 units; changing or cancelling a scheduled clip 50; statistics 1 unit per 50 videos.
> With the shared client and N active users posting ~2 clips a day: N × ~3,400 units. The app
> counts units locally, never plans more uploads than the quota allows, waits for the daily
> reset when Google says the quota is used up, and lets heavy uploaders use their own Google
> project (Settings → YouTube → Advanced). We'll ask for more with real usage numbers.

**Branding / ToS display**

> The word "YouTube" appears as plain text only; no YouTube logo, no embedded player. Next to
> the Connect button the app links the YouTube Terms of Service, the Google Privacy Policy and
> the SharkyClips privacy policy, and says that SharkyClips uses YouTube API Services.

**Screencast / documentation:** the same unlisted demo video as for OAuth verification, plus
the audit part of the script ([demo-videos.md](demo-videos.md#a-google-oauth-verification--youtube-api-audit)).

## Policy points a reviewer checks (and where SharkyClips stands)

| Policy | Status |
|---|---|
| Refresh or delete stored API data within 30 days | Done in 1.2.38 (`ytdata.purge`, daily) |
| Delete authorized data when access is revoked | Done in 1.2.38 (Disconnect; revoked sign-in after 7 days) |
| Link YouTube ToS + Google Privacy Policy before sign-in | Done (Settings → YouTube, publish dialog) |
| Privacy policy names the data, scopes, storage, deletion | Done (site, section 4, updated 10 Nov 2026) |
| Don't misrepresent uploads as YouTube's | Done (no logos, plain text) |
| Synthetic / AI voice disclosure on uploads | Done since 1.2.19 (`containsSyntheticMedia` + description line when a dub voice is used) |
| Users can disconnect in the app | Done (Settings → Accounts / YouTube) |
