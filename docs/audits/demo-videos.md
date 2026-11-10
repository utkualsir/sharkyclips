# Demo video scripts (with shot lists)

General rules for every video:

- **English UI** (Settings → Language → English), dark or light theme, 1920×1080, 30 fps, MP4.
- Use a clean test channel / test TikTok account, not your main one, and a project made from
  **your own** recording (or the synthetic demo project from `docs/demo/make_demo.py`), never
  third-party content.
- Narrate or add on-screen captions (the shot lists give the caption text). No music.
- Close other tabs, hide bookmarks and notifications; don't show tokens, secrets or emails
  other than the consent screen's account picker.
- Record with OBS (Display Capture). Keep each video short: Google ~3-4 min, TikTok ~3 min.

## A. Google OAuth verification + YouTube API audit

One video serves both reviews. Upload it to YouTube as **unlisted** and paste the link into both
forms. Total ≈ 4 min.

| # | Time | Screen | Action | Caption / narration |
|---|---|---|---|---|
| 1 | 0:00-0:10 | SharkyClips home | App open, title bar visible | "SharkyClips, a desktop app that turns your own stream recordings into short clips." |
| 2 | 0:10-0:25 | Settings → Accounts → YouTube | Hover the notice with the YouTube ToS / Google Privacy Policy / SharkyClips privacy links | "Before connecting, the app links YouTube's Terms, Google's Privacy Policy and our privacy policy." |
| 3 | 0:25-0:45 | Browser, Google sign-in | Click **Connect with Google**; the browser opens. **Zoom into the address bar** until `client_id=…apps.googleusercontent.com` is readable | "This is the OAuth client under review." |
| 4 | 0:45-1:05 | Google consent screen | Pick the test account; show app name "SharkyClips" and both permissions; read them out; **Allow** | "SharkyClips asks for: manage your YouTube videos, and view YouTube Analytics reports." |
| 5 | 1:05-1:15 | Browser tab "Connected" → app | Channel name + avatar appear in Accounts | "`channels.list mine=true`: the app shows which channel is connected." |
| 6 | 1:15-1:50 | Project → a clip → **Publish** | Show title, description, tags, privacy Private, release time, playlist, thumbnail; press **Publish** for YouTube only; progress bar to done; click the link | "`videos.insert`, `thumbnails.set`, `playlistItems.insert`: only after the user presses Publish." |
| 7 | 1:50-2:00 | YouTube Studio (same account) | The new private video is there | "The clip on the user's own channel." |
| 8 | 2:00-2:30 | Library → Schedule calendar | Drag a scheduled clip to another day; then **Cancel** another scheduled clip and confirm | "`videos.update` moves the release time; `videos.delete` cancels a scheduled clip before it is public. Only videos SharkyClips uploaded." |
| 9 | 2:30-2:50 | Stats page | **Fetch views from YouTube**; numbers appear next to clips | "`videos.list` for the user's own uploads: views, likes, privacy." |
| 10 | 2:50-3:15 | A project → Hook test | Show the two openings and the "results in 48 h" note (a finished result if you have one) | "`yt-analytics.readonly`: 48 h after publishing, the average view percentage of that one video tells which opening keeps viewers watching." |
| 11 | 3:15-3:40 | Settings → Accounts → YouTube | **Disconnect**; read the confirm text ("also deletes the views, likes and retention numbers it read from YouTube"); confirm | "Disconnect revokes the token and deletes the data the app read." |
| 12 | 3:40-3:55 | myaccount.google.com/permissions | SharkyClips is no longer listed | "Access is gone on Google's side too." |
| 13 | 3:55-4:05 | Site privacy page | Scroll to "4. YouTube data" → "How long it is kept" | "Data stays on the user's computer; numbers not refreshed for 30 days are deleted." |

Optional (only if you turned it on for the review): live chat "!clip" — Settings → Live, start a
private test live stream, type `!clip` in its chat, show the marker. Caption:
"`liveChatMessages.list`: read-only chat of the user's own live stream."

## B. TikTok app review + Content Posting audit

Record in the **sandbox** of the shared SharkyClips app (see the blocker in
[tiktok-app-review.md](tiktok-app-review.md#0-blocker-sharkyclips-has-no-shared-tiktok-app-yet-decision-needed)),
with your test account added as a target user. For the audit, record the same flow again on the
production app later if TikTok asks. Total ≈ 3 min, under 50 MB (export 1080p at ~2 Mbit/s).

| # | Time | Screen | Action | Caption / narration |
|---|---|---|---|---|
| 1 | 0:00-0:10 | Desktop | Double-click the SharkyClips shortcut; the app opens | "SharkyClips desktop app (Windows)." |
| 2 | 0:10-0:20 | Site home page | Show the site with Privacy / Terms links in the header | "Website, privacy policy and terms." |
| 3 | 0:20-0:45 | Settings → Accounts → TikTok → Connect | Browser opens TikTok's authorize page; show app name **SharkyClips** and the 3 permissions; log in with the test account; **Authorize** | "Login Kit: `user.info.basic`, `video.publish`, `video.list`." |
| 4 | 0:45-0:55 | App, Accounts | The TikTok account's name + avatar appear | "`user.info.basic`: shows which account is connected." |
| 5 | 0:55-1:10 | A project → rendered clip → **Publish**, TikTok on | Post screen opens; point at "Posting to @name (nickname)" and the video preview | "creator_info is read when the screen opens: the account and its options." |
| 6 | 1:10-1:30 | TikTok post settings | Open the privacy dropdown: starts at "Choose…", pick one; show Comment / Duet / Stitch unchecked, tick Comment | "No default privacy; interactions are off until the creator turns them on." |
| 7 | 1:30-1:55 | Disclosure | Turn **Disclose video content** on: Post is blocked; tick **Your brand** → "Promotional content" label; tick **Branded content** → "Paid partnership" label, "Only me" greyed (hover: "Branded content visibility cannot be set to private."), declaration changes to Branded Content Policy + Music Usage | "Commercial content disclosure as in TikTok's guidelines." |
| 8 | 1:55-2:05 | Same | Turn disclosure off again; read the declaration above the Post button | "By posting, you agree to TikTok's Music Usage Confirmation." |
| 9 | 2:05-2:15 | Caption field | Edit the title and a hashtag | "Every preset text is editable." |
| 10 | 2:15-2:35 | Press **Post** | Progress → "Processing" note → "Published"; click the link | "`video.publish` with FILE_UPLOAD; status is polled until TikTok publishes it, which can take a few minutes." |
| 11 | 2:35-2:45 | TikTok (browser), test account | The post is there with the chosen settings | "Posted to the creator's own account." |
| 12 | 2:45-2:55 | Clip card / Library | Views + likes next to the clip (after a refresh) | "`video.list`: views of the creator's own posts." |
| 13 | 2:55-3:05 | Settings → Accounts → TikTok | **Disconnect** | "Disconnect revokes the token at TikTok." |

Unaudited sandbox note: posts are "Only me" and the test account must be private while posting;
say so in a caption at shot 6 if the dropdown only offers "Only me".
