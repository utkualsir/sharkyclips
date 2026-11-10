# TikTok app review + Content Posting API (Direct Post) audit

Where: developers.tiktok.com → Manage apps → your app → **App review** (products + scopes), then
the **Content Posting API audit** application (linked from the Content Posting API product page).
Prepared for SharkyClips 1.2.38 against TikTok's App Review Guidelines and Content Sharing
Guidelines (both last updated 4 Aug 2026). Nothing has been submitted.

## 0. Blocker: SharkyClips has no shared TikTok app yet (decision needed)

Today every user creates **their own** TikTok developer app and pastes its client key + secret
into SharkyClips (Settings → Accounts → TikTok). That works unaudited (posts are "Only me", the
account must be private, max. 5 posting users per 24 h), but it can't pass a review:

- TikTok rejects apps "for private or personal use" and "a utility tool that uploads content to
  accounts you or your team manage". One user's personal app is exactly that.
- TikTok also says: keep `client_secret` confidential and don't embed it in open-source
  projects. TikTok's token endpoint needs the secret (unlike Google's installed-app flow), so a
  shared SharkyClips app can't ship its secret in this public repo.

**Options**

| | What | Review possible? | Cost / trade-off |
|---|---|---|---|
| A | Keep "bring your own app" (today) | No (personal use) | Posts stay "Only me"; users make them public by hand in TikTok |
| **B (recommended)** | One shared **SharkyClips** TikTok app + a tiny token relay that holds the secret | Yes | ~100 lines, e.g. a free Cloudflare Worker: it only forwards `/v2/oauth/token/` (code exchange + refresh) and `/v2/oauth/revoke/`, stores and logs nothing. Videos and every other call still go straight from the user's PC to TikTok. The privacy policy must then say that sign-in tokens pass through this relay. |
| C | Per-user apps, each user applies for an audit | No | Same "personal use" rejection |

I did not build B: it means running a server under your accounts and changes the "no
SharkyClips server" promise in the privacy policy, so it's your call. Everything below assumes B
(app name **SharkyClips**, owned by you). Option A keeps working unchanged in the meantime.

## 1. App details (App review page)

| Field | Value |
|---|---|
| App name | `SharkyClips` (no "TikTok" in the name, matches the site and the app) |
| App icon | `assets/icon/sharkyclips.png` (1024×1024, the shark-fin play button; not TikTok-like) |
| Category | Video / Entertainment tools (pick the closest: "Video editing") |
| Description (users see it) | see below |
| Terms of Service URL | `https://utkualsir.github.io/sharkyclips-site/terms.html` |
| Privacy Policy URL | `https://utkualsir.github.io/sharkyclips-site/privacy.html` |
| Website URL | `https://utkualsir.github.io/sharkyclips-site/` (Privacy + Terms links are in its header, visible without a menu) |
| Platform | Desktop (Windows, macOS) |
| Redirect URI | `http://127.0.0.1` loopback (the app's callback is `http://127.0.0.1:<port>/api/platforms/tiktok/callback`, port 8000-8010; register the form TikTok's portal accepts for desktop apps) |

**Description**

> SharkyClips is a free desktop app for streamers. It finds the best moments in your own stream
> recordings on your computer and turns them into vertical clips with subtitles. When a clip is
> ready, you can post it to your TikTok account from SharkyClips: you see which account it goes
> to, choose who can view it, comments / Duet / Stitch and the content disclosure on TikTok's post
> screen, and SharkyClips shows when TikTok has published it.

## 2. Products and scopes

Products: **Login Kit** (Desktop) and **Content Posting API** with **Direct Post** turned on.
Remove every other product/scope before submitting (TikTok delays reviews with unused ones).

| Scope | Used for (paste as the explanation) |
|---|---|
| `user.info.basic` | "Shows which TikTok account a clip will be posted to (display name and avatar) on the post screen and in Settings → Accounts, as TikTok's sharing guidelines require." |
| `video.publish` | "Posts a clip the user made in SharkyClips to their own account with Direct Post (FILE_UPLOAD from the user's computer), after the user picked the privacy level, interaction settings and content disclosure and pressed Post. The app reads creator_info before showing the post screen and polls the publish status afterwards." |
| `video.list` | "Shows views and likes of the user's own posts next to each clip in SharkyClips, so creators see which clips work. Read-only, own posts only." |

Not requested: `video.upload` (inbox drafts; SharkyClips posts directly), `user.info.profile`,
`user.info.stats`. If you want a minimal first review, drop `video.list` (the app then simply
shows no TikTok views; it already handles a token without it).

**How the products enrich the user experience (review text)**

> Creators finish a clip in SharkyClips and post it without exporting, moving the file to their
> phone and typing the caption again. Login Kit connects their own account once; Direct Post
> sends the finished clip with their caption; the post screen follows TikTok's Content Sharing
> Guidelines (creator shown, no default privacy, interactions off by default, commercial content
> disclosure, Music Usage Confirmation). The status shows "processing" until TikTok publishes it.

**Demo video:** recorded in the **sandbox** (add your test TikTok account as a target user),
script: [demo-videos.md](demo-videos.md#b-tiktok-app-review--content-posting-audit). Up to 5
videos, 50 MB each; MP4.

## 3. Content Posting API audit (lifts "Only me" + the private-account rule)

The application form sits behind the developer login, so its exact fields couldn't be read from
outside. Answers to what it asks for (usage estimates, use case, UX proof):

**Use case**

> Creators post short clips they made from their own stream recordings with SharkyClips
> (a desktop app) to their own TikTok account. Content is original, made by the creator; the app
> does not copy content from other platforms and adds no SharkyClips watermark or branding.

**Expected usage** (sets TikTok's 24-hour creator cap; give realistic numbers):

> `<N>` creators posting per day, about 1-3 posts per creator per day (TikTok's own per-creator
> limit is around 15 a day; SharkyClips also spaces planned posts out).

**UX compliance (where each rule is met in SharkyClips 1.2.38)**

| TikTok rule | SharkyClips |
|---|---|
| Fetch creator_info every time the post screen opens | 1.2.38: opening the post screen calls `creator_info/query` fresh, and the post job queries it again right before posting |
| Show the creator's nickname | "Posting to @username (nickname)" at the top of TikTok post settings |
| Stop when the creator can't post now | creator_info errors become a blocking problem ("cannot_post") with TikTok's message |
| Check `max_video_post_duration_sec` | the length limit comes from creator_info; a too-long clip blocks TikTok for that clip ("too_long" problem) and the job refuses it too |
| Privacy from `privacy_level_options`, no default | dropdown starts at "Choose…", nothing pre-selected; Post is blocked until chosen |
| Comment / Duet / Stitch off by default, greyed out when disabled in the creator's settings | all three unchecked by default; disabled ones are greyed with "(off in your TikTok settings)" |
| Content disclosure toggle off by default; "Your brand" / "Branded content"; at least one when on | toggle off; publish blocked while on with nothing chosen; hint text is TikTok's sentence |
| Label notices ("Promotional content" / "Paid partnership") | shown under the checkboxes |
| Branded content can't be private | "Only me" disabled with "Branded content visibility cannot be set to private."; "Branded content" disabled while "Only me" is picked |
| Declaration before the Post button (Music Usage / Branded Content Policy, linked) | `TikTokDeclaration`, switches text when Branded content is on |
| Preview of the content | phone-frame video preview per platform in the publish dialog |
| Express consent before upload | nothing is sent before Post; the request carries `consent: true` |
| Editable preset title / hashtags | caption fully editable per platform |
| No promotional watermark / logo | SharkyClips adds none (the user's optional own brand kit is the user's own content) |
| Tell users processing takes a few minutes | toast after posting + "processing" status |
| Poll `publish/status/fetch` | status polled until published / failed; shown per clip |
| Disconnect revokes access | 1.2.38: `/v2/oauth/revoke/` on Disconnect |

**Screenshots for the audit:** take them from the sandbox run of the demo (post screen with the
dropdown open, disclosure on with both boxes, the declaration, the processing status).
