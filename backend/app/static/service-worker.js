"use strict";

// Only the versioned, presentation-only shell is cached. Plan responses,
// prices and every API request deliberately stay on the network.
const SHELL_CACHE = "billigaste-veckomenyn-shell-v17";
const SHELL_ASSETS = Object.freeze([
  "/static/styles.css",
  "/static/complete-recipes.css?v=complete-recipes-1",
  "/static/frontend-bootstrap.js?v=loading-hotfix-20260909",
  "/static/complete-recipes.js?v=municipality-rollout-2",
  "/static/municipal-areas.js?v=1",
  "/static/app.js?v=municipal-20261010",
  "/static/product-search.js?v=comparability-20261010",
  "/static/styles.css?v=personal-v2-1",
  "/static/personal.css?v=option3-1",
  "/static/choices.css?v=option3-1",
  "/static/complete-recipes.js?v=ingredients-20261012",
  "/static/shopping-location.js?v=location-20261011",
  "/static/choice-controls.js?v=option3-1",
  "/static/personal.js?v=option3-1",
  "/static/privacy.js",
  "/static/icons/app-icon.svg",
  "/static/icons/app-icon-maskable.svg",
  "/static/offline.html",
]);
const SHELL_PATHS = new Set(SHELL_ASSETS.map((path) => new URL(path, self.location.origin).pathname));

async function networkFirstShell(request) {
  try {
    const response = await fetch(request, { cache: "no-cache" });
    if (response.ok && response.type === "basic") {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_error) {
    return caches.match(request);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("billigaste-veckomenyn-shell-") && key !== SHELL_CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request, { cache: "no-cache" }).catch(() => caches.match("/static/offline.html")),
    );
    return;
  }

  if (!SHELL_PATHS.has(url.pathname)) return;
  event.respondWith(networkFirstShell(request));
});
