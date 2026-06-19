// 相對路徑 shell（GitHub Pages 子路徑）；network-first 取最新，離線用 cache。
// 音檔（Drive 跨 origin）以 cache-first 存起，令離線可重播近期 clip。
const CACHE = "shadowing-v4";
const SHELL = ["./", "./index.html", "./app.js", "./compare.js",
               "./practice-core.js", "./config.js", "./style.css",
               "./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // 音檔：完全唔攔截，交畀瀏覽器原生處理（range/seek、串流）—— SW 攔截會拖慢媒體
  if (url.pathname.indexOf("/audio/") !== -1) return;
  // Drive 音檔：cache-first（離線可重播）
  if (url.hostname.indexOf("drive.google.com") !== -1 ||
      url.hostname.indexOf("googleusercontent.com") !== -1) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return resp;
      }))
    );
    return;
  }
  // Apps Script API：一律走網絡（要最新 manifest/progress）
  if (url.href.indexOf("script.google.com") !== -1) return;
  // 其餘（shell）：network-first，離線用 cache
  e.respondWith(
    fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match(e.request))
  );
});
