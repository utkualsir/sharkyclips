// SharkyClips approval page: a minimal service worker so phones can install it as an app.
// It caches nothing: every request goes to the SharkyClips on your PC (always fresh clips).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
