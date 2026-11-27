# YouTube uploads with your own Google project

Since 1.2.52 SharkyClips ships **no** Google OAuth client. Uploads to YouTube go through a free
Google Cloud project that **you** own. That keeps your quota (since June 2026: 100 uploads a day in their own bucket, plus
10,000 units for everything else) to yourself and nobody else's app can be blocked or abused in your name.

## The guided way (recommended)

Settings → YouTube → **Connect your own Google project** ("Kendi Google projeni bağla"). The guide
walks you through five steps with links that open the right Google Cloud pages:

1. Create a project (any name).
2. Turn on **YouTube Data API v3**.
3. Set up the consent screen (type *External*, add yourself as a test user).
4. Create an OAuth client of type **Desktop app** and download its JSON.
5. Drop that JSON file into SharkyClips. Then click **Connect with Google**.

The client is stored in your settings folder (`~/.sharkyclips/youtube/client.json`); the sign-in
token is encrypted there (Windows DPAPI / macOS Keychain) and only ever sent to Google.

While the consent screen is in *Testing*, Google ends the sign-in after 7 days; publish the app
(*In production*) in Google Auth Platform → Audience to stay signed in.

## The file way (advanced)

You can also save a Desktop app client as `google_client.json` in the **settings folder**
(Windows `%USERPROFILE%\.sharkyclips`, macOS / Linux `~/.sharkyclips`), never in the SharkyClips
folder. `backend/sharkyclips/google_client.example.json` shows the format. Then click
Settings → YouTube → **Reload Google client** ("Google istemcisini yeniden yükle").

Rotated the client secret in Google Cloud? Put the new JSON in place and click **Reload Google
client**: with the same client ID your sign-in keeps working. A different client ID needs a new
sign-in (the app tells you).

## Quota

1.2.75: History → Uploads shows "X of 100 uploads left today" with your own client, and
"Shared daily pool" (never a guessed number) with the built-in one. Step-by-step owner guide for a
separate personal project: [own-google-client.md](own-google-client.md).

Settings → YouTube shows today's use. SharkyClips stops starting new uploads before the limit
(it keeps 300 units free for thumbnails and edits, setting `youtube_quota_reserve`) and queues
the rest: they upload automatically after Google's daily reset (midnight Pacific Time).
