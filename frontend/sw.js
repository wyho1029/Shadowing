// Service worker：network-first，令前端更新即時生效；冇網絡先用 cache 做後備。
const CACHE = "shadowing-v2";
const SHELL = ["/", "/index.html", "/app.js", "/style.css",
               "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  self.skipWaiting();   // 新版即刻接手，唔使等所有分頁閂晒
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;   // API 一律走網絡
  // network-first：攞最新；失敗（離線）先用 cache
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
