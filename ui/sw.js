// Offline support: the app shell is cached; prices are fetched fresh when there is signal
// and the last downloaded prices are shown when there isn't (the app marks them stale by date).
const CACHE = "modely-v1";
const SHELL = ["./", "index.html", "styles.css", "app.js", "icon.svg", "manifest.webmanifest", "data/app-data.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const fresh = url.pathname.endsWith("app-data.js") || url.pathname.endsWith("app.js") || req.mode === "navigate";
  if (fresh) {   // network first, fall back to cache
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res;
    }).catch(() => caches.match(req).then((r) => r || caches.match("index.html"))));
  } else {       // cache first (styles, icon, fonts)
    e.respondWith(caches.match(req).then((r) => r || fetch(req).then((res) => {
      if (res.ok && (url.origin === location.origin || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com"))) {
        const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy));
      }
      return res;
    })));
  }
});
