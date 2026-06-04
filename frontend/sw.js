// 最簡 service worker：cache 靜態外殼，API 一律走網絡。
const CACHE = "shadowing-v1";
const SHELL = ["/", "/index.html", "/app.js", "/style.css",
               "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;  // API 唔 cache
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
