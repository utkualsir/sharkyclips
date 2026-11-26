// SharkyClips Helper (1.2.70): fills in TikTok Studio's upload page, then STOPS.
// Selectors are TikTok's data-e2e attributes (the same ones the 1.2.42 automation used), so every
// UI language works. The Post button is only outlined and watched for the person's own click:
// this script never clicks it.
(async () => {
  const P = "tiktok";
  const SEL = {
    file: '[data-e2e="select_video_container"] input[type="file"], input[type="file"][accept*="video"]',
    status: '[data-e2e="upload_status_container"]',
    caption: '[data-e2e="caption_container"] .public-DraftEditor-content, [data-e2e="caption_container"] [contenteditable="true"]',
    visibility: '[data-e2e="video_visibility_container"]',
    more: '[data-e2e="advanced_settings_container"]',
    aigc: '[data-e2e="aigc_container"]',
    postNow: 'input[name="postSchedule"][value="post_now"]',
    draft: '[data-e2e="local_draft_container"]',
    dialog: '.TUXModal-overlay [role="dialog"]',
    tour: ".react-joyride__tooltip",
  };
  const POST_BUTTON = '[data-e2e="post_video_button"]'; // outlined + watched, never clicked
  const UPLOADED = /(yüklendi|uploaded|hochgeladen|feltöltve|feltöltöttük|загружено|已上传|上传成功|تم التحميل|تم الرفع|subido|cargado|enviado|carregado|téléversé|importé|アップロード済み|アップロードしました)/i;
  const UPLOAD_FAILED = /(fail|başarısız|hata|error|fehlgeschlagen|sikertelen|ошибк|не удалось|失败|فشل|falló|falhou|échec|失敗)/i;
  const EVERYONE = /^\s*(herkes|everyone|public|alle|mindenki|все|所有人|公开|الجميع|todos|tout le monde|public|全員|公開)\s*$/i;

  const path = location.pathname;
  const onStudio = path.startsWith("/tiktokstudio");
  const onUpload = path.startsWith("/tiktokstudio/upload");
  const onContent = path.startsWith("/tiktokstudio/content") || path.startsWith("/tiktokstudio/post");
  const onLogin = path.startsWith("/login");

  const guard = () => {
    const any = (sel) => SCX.qa(sel).some(SCX.vis);
    if (location.pathname.startsWith("/login")) return "login";
    if (any('#captcha-verify-container, #captcha_container, [id*="captcha" i], [class*="captcha" i], iframe[src*="captcha"], [class*="secsdk" i]')) return "captcha";
    if (any('[data-e2e="login-modal"], #loginContainer, [data-e2e="login-form"], [class*="login-modal" i]')) return "login";
    if (any('[class*="verify-bar" i], [class*="verification-code" i], [data-e2e*="verify" i]')) return "verify";
    return "";
  };

  let r = await SCX.send({ type: "task", platform: P, url: location.href });
  let task = r && r.task;
  if (!task) return; // a TikTok page SharkyClips didn't open for a post: nothing to do
  const S = (SCX.strings = task.strings || {});
  const rep = async (body) => {
    const res = await SCX.report({ id: task.id, platform: P, ...body });
    if (res && res.task) task = { ...task, ...res.task };
    return res || {};
  };
  let stopped = false;
  const fail = async (reason, step, detail) => {
    stopped = true;
    SCX.banner("err", S.failed || "SharkyClips couldn't fill in this page.", S.failed_sub || "");
    await rep({ event: "failed", reason, step, detail: String(detail || "").slice(0, 200) });
  };

  // a CAPTCHA, a verification or a login: the person finishes it, SharkyClips waits
  async function clear(step) {
    let said = "";
    for (;;) {
      if (stopped || task.state === "cancelled") return false;
      const g = guard();
      if (!g) {
        if (said) await rep({ event: "resume", step });
        return true;
      }
      if (g !== said) {
        said = g;
        if (g === "login") SCX.banner("act", (S.login || "Log in to TikTok here once.").replace("{p}", "TikTok"), S.login_sub || "");
        else SCX.banner("act", S.captcha || "Please complete this in the browser.", S.captcha_sub || "");
        await rep({ event: g === "login" ? "login" : "captcha", reason: g, step });
      }
      await SCX.sleep(1500);
    }
  }

  // TikTok's one-time hints that cover the page (known ones only)
  function dismiss() {
    let did = false;
    for (const dlg of SCX.qa(SEL.dialog)) {
      if (!SCX.vis(dlg) || !dlg.querySelector('.modal-form [class*="Checkbox"]')) continue;
      const x = dlg.querySelector('[class*="modal-close"]') || dlg.querySelector('button[data-type="neutral"], button[class*="secondary"]');
      if (x) did = SCX.press(x) || did;
    }
    const tip = SCX.q(SEL.tour);
    if (tip && SCX.vis(tip)) {
      const b = tip.querySelector('[data-action="skip"], [data-action="close"]') || Array.from(tip.querySelectorAll("button")).pop();
      if (b) did = SCX.press(b) || did;
    }
    return did;
  }

  async function discardDraft() {
    const bar = SCX.q(SEL.draft);
    if (!bar || !SCX.vis(bar)) return true;
    const bs = bar.querySelectorAll("button");
    if (bs.length < 2) return false;
    SCX.press(bs[0]); // "Discard" (the profile is SharkyClips' own: the draft is an earlier try)
    const ok = await SCX.waitFor(() => SCX.q(`${SEL.dialog} [class*="TUXButton--primary"]`), 8000);
    if (!ok) return false;
    await SCX.sleep(400);
    SCX.press(ok);
    return Boolean(await SCX.waitFor(() => !SCX.vis(SCX.q(SEL.draft)), 10000));
  }

  async function waitUpload() {
    const end = Date.now() + 15 * 60 * 1000;
    let lastPct = -1;
    let lastRep = Date.now();
    while (Date.now() < end) {
      if (Date.now() - lastRep > 20000) {
        // still uploading (TikTok can sit at 99% for a while): SharkyClips must not take a slow
        // upload for a page that stopped answering
        lastRep = Date.now();
        rep({ event: "progress", step: "uploading", progress: lastPct >= 0 ? lastPct / 100 : null });
      }
      if (!(await clear("upload"))) return false;
      const c = SCX.q(SEL.status);
      const text = SCX.norm(c ? c.innerText : "");
      if (text && UPLOAD_FAILED.test(text) && !UPLOADED.test(text)) {
        await fail("upload_failed", "upload", text);
        return false;
      }
      if (c && UPLOADED.test(text) && !text.includes("%")) return true;
      const m = text.match(/(\d{1,3})\s*%/);
      if (m && Number(m[1]) !== lastPct) {
        lastPct = Number(m[1]);
        SCX.banner("wait", (S.uploading || "Uploading the video… {pct}%").replace("{pct}", String(lastPct)));
        if (lastPct % 10 === 0) rep({ event: "progress", step: "uploading", progress: lastPct / 100 });
      }
      await SCX.sleep(1000);
    }
    await fail("upload_failed", "upload", "timeout");
    return false;
  }

  function checked(el) {
    const t = el.matches("input,[role=switch],[role=checkbox],[aria-checked]") ? el : el.querySelector("input[type=checkbox],[role=switch],[role=checkbox],[aria-checked]");
    if (!t) return null;
    return t.matches("input") ? t.checked : t.getAttribute("aria-checked") === "true";
  }

  async function everyone() {
    const box = await SCX.waitFor(() => SCX.q(SEL.visibility), 20000);
    if (!box) return false;
    const opener = box.querySelector('[role=combobox], button, [class*="select" i]');
    const cur = () => SCX.norm((opener || box).innerText);
    const isAll = (t) => EVERYONE.test(t) || t.split(/[\n·|]/).some((x) => EVERYONE.test(x));
    if (isAll(cur())) return true;
    SCX.press(opener || box);
    await SCX.sleep(500);
    const opt = SCX.qa('[role=option], [role=listbox] li, [class*="option" i]').find((o) => SCX.vis(o) && EVERYONE.test(SCX.norm(o.innerText)));
    if (!opt) return false;
    SCX.press(opt);
    await SCX.sleep(500);
    return isAll(cur());
  }

  async function aiLabel(want) {
    if (!want) return true;
    if (!SCX.vis(SCX.q(SEL.aigc))) {
      const more = SCX.q(SEL.more);
      if (!more) return false;
      SCX.press(more.querySelector("button, [role=button]") || more);
      if (!(await SCX.waitFor(() => SCX.vis(SCX.q(SEL.aigc)), 8000))) return false;
    }
    const box = SCX.q(SEL.aigc);
    const sw = box.querySelector("input[type=checkbox],[role=switch],[role=checkbox]");
    if (!sw) return false;
    for (let i = 0; i < 2 && checked(sw) !== true; i++) {
      SCX.press(sw.matches("input") ? sw.closest("label") || sw.parentElement || sw : sw);
      await SCX.sleep(400);
    }
    return checked(sw) === true;
  }

  async function postNow() {
    const rd = SCX.q(SEL.postNow);
    if (!rd) return true; // no planner on the page: it posts right away anyway
    if (rd.checked) return true;
    SCX.press(rd.closest("label") || rd);
    await SCX.sleep(300);
    return rd.checked;
  }

  const captionNow = () => {
    const ed = SCX.q(SEL.caption);
    return ed ? SCX.norm(ed.innerText) : "";
  };

  // ---------------------------------------------------------------- after Post: find the link
  async function findLink() {
    const want = SCX.norm(task.title || "").toLowerCase().replace(/[^\p{L}\p{N} ]+/gu, " ").replace(/\s+/g, " ").trim().slice(0, 32);
    if (want.length < 6) return null;
    const end = Date.now() + 25000;
    while (Date.now() < end) {
      for (const el of SCX.qa("a[href*='/video/']")) {
        let row = el;
        for (let k = 0; k < 8 && row; k++, row = row.parentElement) {
          const t = SCX.norm(row.innerText).toLowerCase().replace(/[^\p{L}\p{N} ]+/gu, " ").replace(/\s+/g, " ");
          if (t.includes(want)) {
            try {
              return "https://www.tiktok.com" + new URL(el.href).pathname;
            } catch (e) {
              return el.href;
            }
          }
          if (t.length > 3000) break;
        }
      }
      await SCX.sleep(1500);
    }
    return null;
  }

  async function posted() {
    if (stopped) return;
    stopped = true;
    SCX.banner("ok", (S.posted || "Shared to {p} ✓").replace("{p}", "TikTok"), S.posted_sub || "");
    const url = await findLink();
    await rep({ event: "posted", url });
  }

  // ---------------------------------------------------------------- waiting for the person
  async function watch() {
    let clicked = task.state === "post_clicked";
    let tick = 0;
    const startUrl = location.pathname;
    for (;;) {
      if (stopped) return;
      const btn = SCX.q(POST_BUTTON);
      if (btn) {
        SCX.ring(btn);
        SCX.onPersonClick(btn, () => {
          clicked = true;
          SCX.banner("wait", S.posting || "Posting…");
          rep({ event: "post_clicked" });
        });
      }
      const p = location.pathname;
      if (p !== startUrl && (p.startsWith("/tiktokstudio/content") || p.startsWith("/tiktokstudio/post"))) return posted();
      if (clicked) {
        const g = guard();
        if (g) await clear("after post");
        // the form went back to "select a video" right after the click: the post went out
        if (!SCX.q(SEL.caption) && SCX.q(SEL.file) && !SCX.q(POST_BUTTON)) return posted();
      }
      if (++tick % 2 === 0) {
        const res = await rep({ event: "ping" });
        if (task.state === "cancelled" || task.state === "confirm" || res.gone) {
          SCX.bannerOff();
          stopped = true;
          return;
        }
        if (res.focus) SCX.send({ type: "focus" });
      }
      await SCX.sleep(1500);
    }
  }

  // ---------------------------------------------------------------- filling in
  async function fill() {
    await rep({ event: "claimed" });
    SCX.banner("wait", S.filling || "SharkyClips is filling in your post…", S.filling_sub || "");
    if (!(await clear("open"))) return;
    if (!(await discardDraft())) return fail("ui_changed", "draft", "draft bar");
    const input = await SCX.waitFor(() => SCX.q(SEL.file), 30000);
    if (!input) {
      if (!(await clear("open"))) return;
      return fail("ui_changed", "open", "no file input");
    }
    await rep({ event: "step", step: "uploading" });
    let file;
    try {
      file = await SCX.getFile(task.id);
    } catch (e) {
      return fail("file", "file", e.message);
    }
    SCX.setFiles(input, file);
    if (!(await waitUpload())) return;
    await SCX.sleep(800);
    dismiss();
    await rep({ event: "step", step: "filling" });
    SCX.banner("wait", S.filling || "SharkyClips is filling in your post…", S.filling_sub || "");
    const ed = await SCX.waitFor(() => {
      dismiss();
      return SCX.q(SEL.caption);
    }, 60000);
    if (!ed) return fail("ui_changed", "caption", "no caption box");
    const ok = await SCX.fillEditor(ed, task.text, () => ed.innerText);
    if (!ok) return fail("ui_changed", "caption", `reads ${captionNow().length} chars`);
    const typed = captionNow();
    dismiss();
    const notes = [];
    if (!(await everyone())) notes.push(S.note_visibility || "Set \"Who can watch\" to Everyone.");
    if (!(await aiLabel(Boolean(task.ai_label)))) notes.push(S.note_ai || "Switch on \"AI-generated content\" (Show more).");
    if (!(await postNow())) notes.push(S.note_now || "Choose \"Now\" under When to post.");
    await SCX.sleep(300);
    if (captionNow() !== typed) return fail("ui_changed", "caption", "caption changed");
    if (!(await clear("ready"))) return;
    if (!SCX.q(POST_BUTTON)) return fail("ui_changed", "post", "no Post button");
    SCX.banner("ok", S.ready || "Everything is ready. Check and click Post.", notes.join(" ") || S.ready_sub || "");
    await rep({ event: "ready", notes });
    return watch();
  }

  // ---------------------------------------------------------------- where this page stands
  if (["posted", "failed", "cancelled", "confirm"].includes(task.state)) return;
  if (onLogin || guard() === "login") {
    await clear("login");
    return;
  }
  if (task.state === "login" && !onUpload && task.upload_url) {
    location.href = task.upload_url; // logged in: back to the upload page
    return;
  }
  if (onContent && (task.state === "post_clicked" || task.state === "ready")) return posted();
  if (task.state === "post_clicked" && onUpload) return watch();
  if (onUpload) return fill();
  if (onStudio && task.upload_url) location.href = task.upload_url;
})();
