// SharkyClips Helper (1.2.70): the background part. It talks to the SharkyClips app on this PC
// (http://127.0.0.1:8000-8010) for the content scripts: they ask for the post to fill in, get the
// video file and report every step. It never posts anything; it only ever talks to 127.0.0.1.
importScripts("config.js"); // self.SC = {token, base, ports, version} (written by SharkyClips)

let BASE = null;
const HDR = () => ({ "X-SharkyClips-Assist": self.SC.token });

async function findBase() {
  const cands = [];
  const add = (u) => u && !cands.includes(u) && cands.push(u);
  add(BASE);
  add(self.SC.base);
  for (const p of self.SC.ports || []) add(`http://127.0.0.1:${p}`);
  for (const b of cands) {
    try {
      const r = await fetch(`${b}/api/assist/ext/hello`, { headers: HDR(), signal: AbortSignal.timeout(1500) });
      if (r.ok) {
        const j = await r.json();
        if (j && j.app === "sharkyclips") {
          BASE = b;
          return b;
        }
      }
    } catch (e) {
      /* not this port */
    }
  }
  BASE = null;
  return null;
}

async function call(method, path, body) {
  for (let i = 0; i < 2; i++) {
    const b = BASE || (await findBase());
    if (!b) throw new Error("no_app");
    try {
      const r = await fetch(b + path, {
        method,
        headers: { ...HDR(), "Content-Type": "application/json" },
        body: body ? JSON.stringify({ ...body, ua: navigator.userAgent }) : undefined,
      });
      if (r.status === 403 || r.status === 404) {
        BASE = null; // another SharkyClips (other settings) on that port: look again
        continue;
      }
      return await r.json();
    } catch (e) {
      BASE = null;
    }
  }
  throw new Error("no_app");
}

async function claimed() {
  try {
    const s = await chrome.storage.session.get("tabs");
    return s.tabs || {};
  } catch (e) {
    return {};
  }
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  const tab = sender.tab ? sender.tab.id : null;
  const win = sender.tab ? sender.tab.windowId : null;
  (async () => {
    try {
      if (msg.type === "task") {
        const r = await call("POST", "/api/assist/ext/task", { platform: msg.platform, url: msg.url, tab });
        if (r && r.task && tab != null) {
          const tabs = await claimed();
          tabs[tab] = r.task.id;
          try {
            await chrome.storage.session.set({ tabs });
          } catch (e) {
            /* storage is optional */
          }
        }
        reply(r);
      } else if (msg.type === "report") {
        reply(await call("POST", "/api/assist/ext/report", { ...msg.body, tab }));
      } else if (msg.type === "focus" && tab != null) {
        // "Show the browser" in SharkyClips: this tab comes to the front
        await chrome.tabs.update(tab, { active: true });
        if (win != null) await chrome.windows.update(win, { focused: true, drawAttention: true });
        reply({ ok: true });
      } else {
        reply({ error: "unknown" });
      }
    } catch (e) {
      reply({ error: String((e && e.message) || e) });
    }
  })();
  return true;
});

// The video goes to the page in pieces over a port (a message can't carry a Blob).
function b64(u8) {
  let s = "";
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "file") return;
  port.onMessage.addListener(async (msg) => {
    try {
      const b = BASE || (await findBase());
      if (!b) throw new Error("no_app");
      const r = await fetch(`${b}/api/assist/ext/file/${encodeURIComponent(msg.task)}`, { headers: HDR() });
      if (!r.ok) throw new Error(`file ${r.status}`);
      const buf = new Uint8Array(await r.arrayBuffer());
      port.postMessage({
        type: "start",
        size: buf.length,
        name: decodeURIComponent(r.headers.get("X-File-Name") || "clip.mp4"),
        mime: r.headers.get("Content-Type") || "video/mp4",
      });
      const CH = 1 << 20;
      for (let i = 0; i < buf.length; i += CH) port.postMessage({ type: "chunk", data: b64(buf.subarray(i, i + CH)) });
      port.postMessage({ type: "end" });
    } catch (e) {
      port.postMessage({ type: "error", error: String((e && e.message) || e) });
    }
  });
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const tabs = await claimed();
  if (!(tabId in tabs)) return;
  const task = tabs[tabId];
  delete tabs[tabId];
  try {
    await chrome.storage.session.set({ tabs });
  } catch (e) {
    /* optional */
  }
  call("POST", "/api/assist/ext/report", { id: task, tab: tabId, event: "tab_closed" }).catch(() => {});
});

const hello = () => call("POST", "/api/assist/ext/report", { event: "hello" }).catch(() => {});
chrome.runtime.onInstalled.addListener(hello);
chrome.runtime.onStartup.addListener(hello);
