// SharkyClips Helper (1.2.74): the toolbar popup. Asks the background part whether this copy has
// its key and reaches SharkyClips; a copy from a store pairs here with the 6-digit code shown in
// SharkyClips (Settings > the Helper guide > "Show connection code").
const msg = (k, fb) => {
  try {
    return chrome.i18n.getMessage(k) || fb || k;
  } catch (e) {
    return fb || k;
  }
};
document.documentElement.lang = msg("lang", "en");
document.documentElement.dir = msg("dir", "ltr");
for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = msg(el.dataset.i18n, el.textContent);

const state = document.getElementById("state");
const form = document.getElementById("pair");
const code = document.getElementById("code");
const go = document.getElementById("go");
const err = document.getElementById("err");

const ask = (m) =>
  new Promise((res) => {
    try {
      chrome.runtime.sendMessage(m, (r) => {
        void chrome.runtime.lastError;
        res(r || {});
      });
    } catch (e) {
      res({});
    }
  });

function show(s) {
  state.className = "state " + (s.paired && s.app ? "ok" : "bad");
  state.textContent = s.paired && s.app ? msg("state_ok", "Connected to SharkyClips on this PC.")
    : s.paired ? msg("state_no_app", "SharkyClips isn't running on this PC.")
    : msg("state_off", "Not connected to SharkyClips yet.");
  form.hidden = !!(s.paired && s.app) || !s.store;
}

async function refresh() {
  state.textContent = msg("state_checking", "Checking...");
  show(await ask({ type: "status" }));
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  err.textContent = "";
  go.disabled = true;
  const r = await ask({ type: "pair", code: code.value });
  go.disabled = false;
  if (r.ok) {
    code.value = "";
    await refresh();
  } else {
    err.textContent = r.error === "no_app" ? msg("state_no_app", "SharkyClips isn't running on this PC.")
      : msg("pair_wrong", "That code didn't work. Show a new code in SharkyClips and try again.");
    code.focus();
  }
});

refresh();
