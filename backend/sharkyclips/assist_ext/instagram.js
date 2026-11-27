// SharkyClips Helper (1.2.70): fills in instagram.com's "New post" dialog for a Reel, then STOPS.
// Instagram has no data-e2e attributes, so the buttons are found by their words in the 11 UI
// languages SharkyClips speaks (aria-labels and button texts). The Share button is only outlined
// and watched for the person's own click: this script never clicks it. Anything it can't find
// stops the filling and SharkyClips falls back to the by-hand steps.
(async () => {
  const P = "reels";
  const W = {
    create: /^(new post|create|yeni gönderi|oluştur|neuer beitrag|erstellen|új bejegyzés|létrehozás|новая публикация|создать|منشور جديد|إنشاء|新帖子|创建|nueva publicación|crear|nova publicação|criar|nouvelle publication|créer|新規投稿|作成)$/i,
    post: /^(post|gönderi|beitrag|bejegyzés|публикация|منشور|帖子|publicación|publicação|publication|投稿)$/i,
    next: /^(next|ileri|weiter|tovább|далее|التالي|下一步|siguiente|avançar|suivant|次へ)$/i,
    ok: /^(ok|tamam|okay|rendben|ок|حسنًا|موافق|好|确定|aceptar|entendi|d'accord|ok\s*!)$/i,
    share: /^(share|paylaş|teilen|megosztás|поделиться|مشاركة|分享|compartir|compartilhar|partager|シェア)$/i,
    crop: /(select crop|crop|kırp|zuschneiden|vágás|обрез|اقتصاص|裁剪|recortar|rogner|切り取り)/i,
    original: /^(original|orijinal|eredeti|оригинал|الأصلية|原始|オリジナル)$/i,
    shared: /(shared|paylaşıldı|geteilt|megosztva|опубликован|تمت مشاركة|已分享|compartid|partagé|シェアされました)/i,
  };
  const label = (el) => SCX.norm(el.getAttribute("aria-label") || el.innerText || el.textContent || "");
  const buttons = (root) => SCX.qa('button, [role="button"], a[role="link"], a[href="#"]', root).filter(SCX.vis);
  const byWords = (re, root) =>
    buttons(root).find((b) => re.test(label(b))) ||
    SCX.qa("svg[aria-label]", root)
      .filter((s) => re.test(s.getAttribute("aria-label") || ""))
      .map((s) => s.closest('button, [role="button"], a, [role="link"]'))
      .find((b) => b && SCX.vis(b));
  const dialog = () => SCX.qa('[role="dialog"]').filter(SCX.vis).pop() || null;
  const editor = () => {
    const d = dialog();
    return d ? d.querySelector('[contenteditable="true"][role="textbox"], [contenteditable="true"]') : null;
  };
  const guard = () => {
    const p = location.pathname;
    if (p.startsWith("/accounts/login") || SCX.q('input[name="username"]')) return "login";
    if (p.startsWith("/challenge") || p.startsWith("/auth_platform") || SCX.q('iframe[src*="captcha" i], [id*="captcha" i]')) return "captcha";
    return "";
  };

  if (!(await SCX.claim())) return; // 1.2.74: another copy of the Helper fills this page (or none is paired)
  let r = await SCX.send({ type: "task", platform: P, url: location.href });
  let task = r && r.task;
  if (!task) return;
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
        if (g === "login") SCX.banner("act", (S.login || "Log in to {p} here once.").replace("{p}", "Instagram"), S.login_sub || "");
        else SCX.banner("act", S.captcha || "Please complete this in the browser.", S.captcha_sub || "");
        await rep({ event: g === "login" ? "login" : "captcha", reason: g, step });
      }
      await SCX.sleep(1500);
    }
  }
  const okPopup = () => {
    const d = dialog();
    const b = d && byWords(W.ok, d);
    if (b) SCX.press(b);
    return Boolean(b);
  };
  async function next(step) {
    const d = await SCX.waitFor(() => {
      okPopup();
      const dd = dialog();
      return dd && byWords(W.next, dd);
    }, 30000);
    if (!d) return false;
    SCX.press(d);
    await SCX.sleep(1200);
    await rep({ event: "step", step });
    return true;
  }

  async function watch(shareBtn) {
    let clicked = task.state === "post_clicked";
    let tick = 0;
    for (;;) {
      if (stopped) return;
      const d = dialog();
      const b = shareBtn && shareBtn.isConnected ? shareBtn : d && byWords(W.share, d);
      if (b) {
        SCX.ring(b);
        SCX.onPersonClick(b, () => {
          clicked = true;
          SCX.banner("wait", S.posting || "Posting…");
          rep({ event: "post_clicked" });
        });
      }
      if (clicked && guard()) await clear("after post");
      const text = d ? SCX.norm(d.innerText) : "";
      // Instagram's "Your reel has been shared" screen (only ever after Share), or the dialog gone after your click
      if (!editor() && ((d && W.shared.test(text)) || (clicked && !d))) {
        stopped = true;
        SCX.banner("ok", (S.posted || "Shared to {p} ✓").replace("{p}", "Instagram"), S.posted_sub || "");
        await rep({ event: "posted", url: null });
        return;
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

  async function fill() {
    await rep({ event: "claimed" });
    SCX.banner("wait", S.filling || "SharkyClips is filling in your post…", S.filling_sub || "");
    if (!(await clear("open"))) return;
    let input = SCX.q('[role="dialog"] input[type="file"]');
    if (!input) {
      const c = await SCX.waitFor(() => byWords(W.create), 20000);
      if (!c) return fail("ui_changed", "open", "no New post button");
      SCX.press(c);
      await SCX.sleep(900);
      const sub = byWords(W.post); // the newer menu: Post / Live video / Ad
      if (sub && !SCX.q('[role="dialog"] input[type="file"]')) SCX.press(sub);
      input = await SCX.waitFor(() => SCX.q('[role="dialog"] input[type="file"]') || SCX.q('form input[type="file"]'), 20000);
    }
    if (!input) return fail("ui_changed", "open", "no file box");
    await rep({ event: "step", step: "uploading" });
    let file;
    try {
      file = await SCX.getFile(task.id);
    } catch (e) {
      return fail("file", "file", e.message);
    }
    SCX.setFiles(input, file);
    await SCX.sleep(1500);
    okPopup(); // "Video posts are now shared as reels"
    const notes = [];
    // the crop: "Original" keeps the 9:16 picture (best effort; the person checks it)
    const d0 = await SCX.waitFor(() => dialog() && byWords(W.next, dialog()) && dialog(), 60000);
    if (!d0) return fail("ui_changed", "crop", "no Next button");
    const cropBtn = byWords(W.crop, d0);
    let cropped = false;
    if (cropBtn) {
      SCX.press(cropBtn);
      await SCX.sleep(500);
      const orig = byWords(W.original) || SCX.qa("svg[aria-label]").map((s) => (W.original.test(s.getAttribute("aria-label") || "") ? s.closest('button, [role="button"]') : null)).find(Boolean);
      if (orig) {
        SCX.press(orig);
        cropped = true;
        await SCX.sleep(400);
      }
    }
    if (!cropped) notes.push(S.note_crop || "Check the crop before you share.");
    if (!(await next("edit"))) return fail("ui_changed", "crop", "Next");
    if (!(await next("caption"))) return fail("ui_changed", "edit", "Next");
    await rep({ event: "step", step: "filling" });
    const ed = await SCX.waitFor(editor, 20000);
    if (!ed) return fail("ui_changed", "caption", "no caption box");
    if (!(await SCX.fillEditor(ed, task.text, () => ed.innerText))) return fail("ui_changed", "caption", "caption reads differently");
    const d = dialog();
    const share = d && byWords(W.share, d);
    if (!share) return fail("ui_changed", "share", "no Share button");
    SCX.banner("ok", S.ready_ig || "Everything is ready. Check and click Share.", notes.join(" ") || S.ready_sub || "");
    await rep({ event: "ready", notes });
    return watch(share);
  }

  if (["posted", "failed", "cancelled", "confirm"].includes(task.state)) return;
  if (guard() === "login") {
    await clear("login");
    if (task.upload_url && !location.href.startsWith(task.upload_url)) location.href = task.upload_url;
    return;
  }
  if (task.state === "post_clicked" || (task.state === "ready" && editor())) return watch(null);
  return fill();
})();
