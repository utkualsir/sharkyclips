# Google OAuth app verification (SharkyClips)

Where: Google Cloud Console → project `sharkyclips` → **Google Auth Platform** → Branding / Data
access / **Verification Center**. Prepared for SharkyClips 1.2.38. Nothing has been submitted.
Text in quote blocks is meant to be pasted as is; `<...>` are the few things only you can fill in.

**Why verification is needed:** the shipped client (`backend/sharkyclips/google_client.json`,
"Desktop app" type, status `production`) uses two **sensitive** scopes. Unverified, it shows the
"Google hasn't verified this app" screen and stops at **100 users** for the project's lifetime.
Neither scope is *restricted*, so no CASA security assessment is required.

## 1. Branding page

| Field | Value |
|---|---|
| App name | `SharkyClips` (exactly as in the app and on the site) |
| User support email | `<your Google account email>` |
| App logo | leave empty for the first review (a logo adds a brand review). Later: `docs/logo-120.png` |
| Application home page | `https://utkualsir.github.io/sharkyclips-site/` |
| Privacy policy | `https://utkualsir.github.io/sharkyclips-site/privacy.html` |
| Terms of service | `https://utkualsir.github.io/sharkyclips-site/terms.html` |
| Authorized domains | `utkualsir.github.io` (verify it in Search Console first, see checklist) |
| Developer contact | `<your email>` |

## 2. Data access page (scopes)

Add exactly these two (they must match `youtube.SCOPES` in `backend/sharkyclips/youtube.py`):

- `https://www.googleapis.com/auth/youtube`
- `https://www.googleapis.com/auth/yt-analytics.readonly`

Do **not** add `youtube.upload`, `youtube.force-ssl`, `youtube.readonly` or any Drive/Gmail scope.

## 3. Verification form answers

**App type / platform**

> Installed desktop application (Windows and macOS), open source (MIT):
> https://github.com/utkualsir/sharkyclips. It runs a local web UI on 127.0.0.1. There is no
> SharkyClips server: the app calls Google APIs directly from the user's own computer.

**Describe your app (what it does)**

> SharkyClips is a free desktop app for streamers and video creators. It finds the best moments
> in the user's own stream recording on the user's computer and renders them as vertical short
> videos with subtitles. Connecting YouTube is optional: it lets the user upload, schedule,
> change or cancel the clips they made with SharkyClips on their own channel, see how those
> clips perform, and run an optional A/B "hook test" on the opening of a clip. All processing
> happens locally; the developer never receives any user data.

**How will the `https://www.googleapis.com/auth/youtube` scope be used?**

> The app acts only on the authenticated user's own channel, and only on videos the user
> publishes with SharkyClips:
> 1. `videos.insert` (resumable upload) to upload a clip the user set up on the publish screen
>    (title, description, tags, category, language, made-for-kids, privacy, optional release
>    time, playlist). Scheduled clips are uploaded as private with `status.publishAt`, so
>    YouTube itself publishes them at the chosen time.
> 2. `videos.update` when the user edits the details of such a video, moves its release time in
>    the app's calendar, or presses "Publish now".
> 3. `videos.delete` when the user cancels a scheduled clip before it is public.
> 4. `thumbnails.set` for the thumbnail the user picked (16:9 videos).
> 5. `playlists.list` / `playlists.insert` (`mine=true`) and `playlistItems.insert` to put the
>    clip into a playlist the user picks or creates.
> 6. `channels.list` (`mine=true`) to show which channel is connected, and `videos.list` for the
>    views, likes, privacy status and publish time of the user's own SharkyClips uploads
>    (shown next to each clip; used locally to calibrate the clip score to the user's channel).
> 7. Optional, off by default: `liveBroadcasts.list` (`mine=true`) and `liveChatMessages.list`
>    to read the chat of the user's own live stream, so the user and their moderators can type
>    "!clip" to mark a moment. Read-only, nothing is posted.
>
> Why no narrower scope works: `youtube.upload` can upload but cannot update, schedule-move or
> delete a video, or create playlists; `youtube.readonly` cannot upload; `youtube.force-ssl` adds
> comment access the app doesn't need. Nothing happens without the user setting up the clip and
> pressing Upload / Schedule / Cancel first.

**How will the `https://www.googleapis.com/auth/yt-analytics.readonly` scope be used?**

> Only for the optional hook test. The user renders two versions of a clip's first seconds; the
> app uploads one, and about 48 hours after it was published it calls YouTube Analytics
> `reports.query` with `ids=channel==MINE`, `dimensions=video`, filtered to that one video ID,
> `metrics=views,averageViewDuration,averageViewPercentage`. The result tells the user which
> opening style keeps their own viewers watching. Retention metrics are not available in the
> YouTube Data API, and there is no narrower Analytics scope.

**How is user data stored, protected and deleted?**

> Only on the user's computer. The OAuth token is encrypted with Windows DPAPI or a key in the
> macOS Keychain (`~/.sharkyclips/youtube/token.enc`). Upload records and the fetched numbers are
> in local JSON files. The developer runs no server and never receives, stores, sells or shares
> Google user data; nothing is used for advertising. Fetched numbers are refreshed every few
> hours while the app runs and deleted automatically when they were not refreshed for 30 days.
> "Disconnect" revokes the token (`oauth2.googleapis.com/revoke`), deletes it and deletes every
> number the app read from YouTube; if Google ends the sign-in and the user doesn't reconnect,
> the numbers are deleted after 7 days. The app's use of information received from Google APIs
> adheres to the Google API Services User Data Policy, including the Limited Use requirements.

**OAuth flow (if asked)**

> Authorization code flow with PKCE (S256), `access_type=offline`, loopback redirect
> `http://127.0.0.1:<random port>/` opened per sign-in and closed right after (or after 10
> minutes). The client secret ships in the app, as Google documents for installed apps; PKCE and
> the loopback redirect protect the code exchange.

**Demo video:** YouTube link, **unlisted**: `<link>` (script: [demo-videos.md](demo-videos.md#a-google-oauth-verification--youtube-api-audit)).

## 4. Before you press Submit

See the Turkish checklist in [README.md](README.md). The usual reasons Google sends a form back:
the app name on the consent screen differs from the app/site, the privacy policy doesn't name the
scopes or the data, the authorized domain isn't verified, or the demo video doesn't show the
client ID in the browser's address bar.
