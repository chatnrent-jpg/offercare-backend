const CACHE_NAME = "vettedcare-portal-v2";
const SHELL_URLS = [
  "/portal/",
  "/portal/index.html",
  "/portal/styles.css",
  "/portal/app.js",
  "/portal/manifest.webmanifest",
  "/portal/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) return;
  if (!url.pathname.startsWith("/portal")) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok && url.pathname.startsWith("/portal")) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || caches.match("/portal/")),
      ),
  );
});

self.addEventListener("push", (event) => {
  let payload = { title: "VettedCare.ai", body: "New shift alert" };
  try {
    if (event.data) {
      payload = { ...payload, ...event.data.json() };
    }
  } catch {
    // keep defaults
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "VettedCare.ai", {
      body: payload.body || "New shift alert",
      data: payload,
      icon: "/portal/icon.svg",
      badge: "/portal/icon.svg",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const offerId = event.notification?.data?.offer_id;
  const target = offerId ? `/portal/?offer=${encodeURIComponent(offerId)}` : "/portal/";
  event.waitUntil(clients.openWindow(target));
});
