// Road Ready CT service worker: cache the app on install, serve offline.
// Natural-voice audio lives in its own cache ("roadready-audio-*"), filled by the page, and is never deleted on updates.
var CACHE = "roadready-39b76819963434";
var FILES = ["./", "index.html", "questions.json", "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(FILES); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE && k.indexOf("roadready-audio") !== 0; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  var url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  // Audio: the page reads clips straight from its own cache; never copy them into the app cache.
  if (url.pathname.indexOf("/audio/") !== -1) return;
  // App files: cache first (works offline); refresh in the background when online.
  e.respondWith(caches.open(CACHE).then(function (c) {
    return c.match(e.request, { ignoreSearch: true }).then(function (hit) {
      var net = fetch(e.request).then(function (r) {
        if (r && r.ok) c.put(e.request, r.clone());
        return r;
      }).catch(function () { return hit; });
      return hit || net;
    });
  }));
});
