// SharkyClips Helper (1.2.70): helpers shared by the TikTok and Instagram content scripts.
// Rule: these scripts fill in the upload page and STOP. Nothing here ever clicks Post / Share:
// the person checks the post and clicks it. A CAPTCHA, a verification or a login is never touched
// either: the banner asks the person to finish it, and the script waits.
/* eslint-disable no-unused-vars */
var SCX = (() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const send = (msg) =>
    new Promise((res) => {
      try {
        chrome.runtime.sendMessage(msg, (r) => {
          void chrome.runtime.lastError;
          res(r || { error: "no_reply" });
        });
      } catch (e) {
        res({ error: "gone" }); // the extension was reloaded: this page's script is orphaned
      }
    });
  const vis = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && s.visibility !== "hidden" && s.display !== "none" && s.opacity !== "0";
  };
  const q = (sel, root) => (root || document).querySelector(sel);
  const qa = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const norm = (s) =>
    (s || "")
      .replace(/[​﻿]/g, "")
      .replace(/ /g, " ")
      .replace(/\s+/g, " ")
      .trim();
  async function waitFor(fn, ms, every) {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      let v = null;
      try {
        v = fn();
      } catch (e) {
        v = null;
      }
      if (v) return v;
      await sleep(every || 250);
    }
    return null;
  }

  // a click the page's own code sees like a person's (pointer + mouse events, then click)
  function press(el) {
    if (!el) return false;
    try {
      el.scrollIntoView({ block: "center", inline: "nearest" });
    } catch (e) {
      /* fine */
    }
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    for (const t of ["pointerover", "pointerenter", "mouseover", "pointerdown", "mousedown", "pointerup", "mouseup"]) {
      try {
        el.dispatchEvent(t.startsWith("pointer") ? new PointerEvent(t, { ...o, pointerType: "mouse" }) : new MouseEvent(t, o));
      } catch (e) {
        /* fine */
      }
    }
    el.click();
    return true;
  }

  function setFiles(input, file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // the video from SharkyClips, in pieces over a port (see bg.js)
  function getFile(taskId, onPart) {
    return new Promise((resolve, reject) => {
      const port = chrome.runtime.connect({ name: "file" });
      const parts = [];
      let meta = null;
      let got = 0;
      port.onMessage.addListener((m) => {
        if (m.type === "start") meta = m;
        else if (m.type === "chunk") {
          const bin = atob(m.data);
          const u8 = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
          parts.push(u8);
          got += u8.length;
          if (onPart && meta) onPart(got / Math.max(1, meta.size));
        } else if (m.type === "end") {
          port.disconnect();
          resolve(new File(parts, (meta && meta.name) || "clip.mp4", { type: (meta && meta.mime) || "video/mp4" }));
        } else if (m.type === "error") {
          port.disconnect();
          reject(new Error(m.error));
        }
      });
      port.postMessage({ task: taskId });
    });
  }

  function selectAll(el) {
    el.focus();
    const sel = window.getSelection();
    const r = document.createRange();
    r.selectNodeContents(el);
    sel.removeAllRanges();
    sel.addRange(r);
  }

  // Text into a rich editor (TikTok: Draft.js, Instagram: Lexical). First a paste (the editors take
  // the line breaks from it), then typing by insertText if the page ignored the paste.
  async function fillEditor(el, text, readBack) {
    const want = norm(text);
    for (let round = 0; round < 3; round++) {
      selectAll(el);
      await sleep(120);
      if (round === 0) {
        const dt = new DataTransfer();
        dt.setData("text/plain", text);
        const ev = new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true });
        el.dispatchEvent(ev);
        if (!ev.defaultPrevented) document.execCommand("insertText", false, text);
      } else {
        document.execCommand("delete", false);
        const lines = text.split("\n");
        for (let i = 0; i < lines.length; i++) {
          if (lines[i]) document.execCommand("insertText", false, lines[i]);
          if (i < lines.length - 1) document.execCommand("insertParagraph", false);
          await sleep(10);
        }
      }
      await sleep(500);
      // a suggestion list (hashtags / mentions) may be open: close it without picking anything
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
      await sleep(250);
      const got = norm(readBack ? readBack() : el.innerText);
      if (got === want || got.replace(/ /g, "") === want.replace(/ /g, "")) return true;
    }
    return false;
  }

  // ---------------------------------------------------------------- the banner in the tab
  let host = null;
  function banner(kind, text, sub) {
    if (!host || !host.isConnected) {
      host = document.createElement("div");
      host.id = "sharkyclips-assist";
      host.style.cssText = "all:initial;position:fixed;z-index:2147483647;top:10px;left:50%;transform:translateX(-50%);";
      const sh = host.attachShadow({ mode: "open" });
      sh.innerHTML = `<style>
        .b{font:600 14px/1.4 system-ui,"Segoe UI",sans-serif;display:flex;gap:12px;align-items:center;max-width:min(720px,92vw);
           padding:10px 14px;border-radius:10px;background:#0f1b33;color:#f5f1e6;border:2px solid #d4a72c;box-shadow:0 6px 24px rgba(0,0,0,.35)}
        .b.ok{border-color:#2fbf71}.b.wait{border-color:#d4a72c}.b.act{border-color:#ff8a3d}.b.err{border-color:#e5484d}
        .tag{font:700 11px/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#d4a72c;white-space:nowrap}
        .t{flex:1}.s{display:block;font-weight:400;font-size:12.5px;opacity:.85;margin-top:2px}
        button{all:unset;cursor:pointer;font:600 12px system-ui,sans-serif;padding:4px 8px;border-radius:6px;background:rgba(255,255,255,.12)}
        button:focus-visible{outline:2px solid #d4a72c}</style>
        <div class="b" role="status" aria-live="polite"><span class="tag">SharkyClips</span>
        <span class="t"><span class="m"></span><span class="s"></span></span><button type="button" class="x">×</button></div>`;
      sh.querySelector(".x").addEventListener("click", () => {
        host.style.display = "none";
      });
      (document.body || document.documentElement).appendChild(host);
    }
    const sh = host.shadowRoot;
    host.style.display = "";
    sh.querySelector(".b").className = `b ${kind}`;
    sh.querySelector(".m").textContent = text || "";
    sh.querySelector(".s").textContent = sub || "";
    const x = sh.querySelector(".x");
    x.setAttribute("aria-label", (SCX.strings && SCX.strings.hide) || "Hide");
  }
  function bannerOff() {
    if (host) host.remove();
    host = null;
  }

  // a soft ring around the button the person clicks (the script itself never clicks it)
  function ring(el) {
    if (!el) return;
    el.style.outline = "3px solid #2fbf71";
    el.style.outlineOffset = "3px";
    el.style.borderRadius = el.style.borderRadius || "8px";
  }

  // a person's own click on an element (isTrusted: never a script's)
  function onPersonClick(el, fn) {
    if (!el || el.__scWatched) return;
    el.__scWatched = true;
    el.addEventListener(
      "click",
      (ev) => {
        if (ev.isTrusted) fn();
      },
      true,
    );
  }

  const report = (body) => send({ type: "report", body });

  // 1.2.74: the Helper can be in one browser twice (the copy SharkyClips adds + one from a store).
  // Only one fills the page: the first copy that has its key marks the page; the other stays quiet.
  // A store copy without a key (not paired yet) only speaks if no other copy took the page.
  const MARK = "data-sharkyclips-helper";
  async function claim() {
    const root = document.documentElement;
    const r = await send({ type: "ready" });
    if (root.hasAttribute(MARK)) return false;
    if (r && r.ok) {
      root.setAttribute(MARK, "1");
      return true;
    }
    await sleep(2500);
    if (root.hasAttribute(MARK)) return false;
    const msg = (k, fb) => {
      try {
        return chrome.i18n.getMessage(k) || fb;
      } catch (e) {
        return fb;
      }
    };
    banner("act", msg("pair_banner", "Connect the SharkyClips Helper first."),
      msg("pair_banner_sub", "Click the Helper's icon in the toolbar and type the code SharkyClips shows you."));
    return false;
  }

  return { sleep, send, vis, q, qa, norm, waitFor, press, setFiles, getFile, fillEditor, banner, bannerOff, ring, onPersonClick, report, claim, strings: null };
})();
