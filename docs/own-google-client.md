# Your own Google client for personal use (owner guide)

Goal: **your** YouTube uploads use your own, separate Google Cloud project with its own daily
limits. The built-in SharkyClips client (the shared pool) stays as it is, for everyone else.

Why: with the built-in client every SharkyClips user shares one daily pool (100 uploads a day for
the whole project). With your own project you get the full pool for yourself, and SharkyClips shows
an exact counter: "X of 100 uploads left today".

Google's rules today (checked 2026-11-27, developers.google.com/youtube/v3/determine_quota_cost):

| What | Daily limit (default) | Cost |
|---|---|---|
| Uploads (`videos.insert`) | its own bucket: **100 a day** | 1 per upload |
| Everything else (thumbnails, edits, deletes, playlists, stats) | 10,000 units | thumbnail 50, update 50, delete 50, list 1 |
| Reset | every day at **00:00 Pacific Time** | = 09:00 in Hungary (08:00 in the few weeks when the US and Europe change clocks on different dates) |

Time needed: about 10 minutes. Cost: free (no billing account needed).

---

## 1. Create a separate project

1. Open <https://console.cloud.google.com/> and sign in with the Google account that owns your
   YouTube channel (or any account; the channel account signs in later).
2. Top bar → project picker → **New project**.
3. Name: `sharkyclips-personal` (any name). Organization: *No organization*. → **Create**.
4. Make sure the project picker now shows `sharkyclips-personal`, **not** the shared SharkyClips
   project. Every following step happens in this new project.

## 2. Turn on the YouTube Data API v3

1. Menu → **APIs & Services → Library**.
2. Search **YouTube Data API v3** → open it → **Enable**.
3. Optional (only for the hook test's retention numbers): also enable **YouTube Analytics API**.

## 3. OAuth consent screen: External, then Publish

1. Menu → **Google Auth Platform** (older consoles: APIs & Services → OAuth consent screen) →
   **Get started**.
2. App information: name `SharkyClips (personal)`, user support email = your email → Next.
3. Audience: **External** → Next.
4. Contact information: your email → Next → agree to the policy → **Create**.
5. **Data access** → **Add or remove scopes** → add
   - `https://www.googleapis.com/auth/youtube`
   - `https://www.googleapis.com/auth/yt-analytics.readonly` (optional, for retention)

   → **Update** → **Save**.
6. **Audience** → *Publishing status: Testing* → **Publish app** → **Confirm**.
   Status now says **In production**.

   Why publish: in *Testing*, Google signs you out after 7 days. In production the sign-in stays.
   You do **not** need Google's verification for personal use: you are the only user, so when the
   sign-in shows "Google hasn't verified this app", click **Advanced → Go to SharkyClips
   (personal) (unsafe)**. That warning is about your own app, which you trust.

## 4. Create a Desktop OAuth client and download the JSON

1. **Google Auth Platform → Clients → Create client**.
2. Application type: **Desktop app**. Name: `SharkyClips desktop`. → **Create**.
3. In the dialog: **Download JSON**. The file is called `client_secret_….json`.
4. Keep it private (it identifies your project). Never put it in the SharkyClips repository.

## 5. Import it in SharkyClips

1. SharkyClips → **Settings → YouTube**.
2. If YouTube is connected through the built-in client: **Disconnect** first (your next sign-in
   must be made with your own client, otherwise uploads still go to the shared pool).
3. **Connect your own Google project** → go to the last step → drop the downloaded JSON file
   (or choose it) → **Connect with Google**.
4. Sign in with your channel's Google account, accept the warning from step 3.6, allow access,
   pick your channel.
5. Check: Settings → YouTube says *"Using your own Google project: sharkyclips-personal"*, and
   **History → Uploads** shows **"X of 100 uploads left today"** with a *See it in Google Cloud
   Console* link.

Your client is stored in `%USERPROFILE%\.sharkyclips\youtube\client.json`; the sign-in token is
encrypted with Windows DPAPI and only ever sent to Google.

## 6. Keep the shared client for everyone else

- Do **not** delete or change the shared project, its OAuth client, or the
  `google_client.json` that SharkyClips uses for other users. Your own client simply wins on your PC.
- Your uploads no longer use the shared pool, so other users get more of it.
- Owner view (optional): Settings → Advanced → **Owner view** → *Show the owner link* adds a link
  to the shared project's quota page in Cloud Console (the real usage of everybody). It is only a
  link: SharkyClips stores no owner password or key.

## Going back

Settings → YouTube → own project → **Remove** (or **Disconnect**, then connect with the built-in sign-in).

## If something goes wrong

| Message | Fix |
|---|---|
| "Access blocked: app has not completed verification" / "only test users" | Step 3.6: the app is still in *Testing*. Publish it, or add yourself under Audience → Test users. |
| "YouTube Data API v3 has not been used in project … or it is disabled" | Step 2 was done in the wrong project. Enable the API in `sharkyclips-personal`. |
| Counter still says "Shared daily pool" | You are still signed in with the built-in client: Disconnect, then connect again (step 5.2). |
| "Today's YouTube uploads are used up (100 a day)" | Your own 100 are used. Upload by hand in YouTube Studio, or wait for 00:00 Pacific Time. More quota: Cloud Console → IAM & Admin → Quotas → YouTube Data API v3 → *Edit quota* (Google reviews the request). |
