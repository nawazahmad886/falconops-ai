/**
 * FalconOps AI — service worker.
 *
 * This is a monitoring platform — a service worker that ever serves a cached,
 * stale copy of live monitoring data would be actively dangerous (an operator
 * looking at a stale "all healthy" screen during a real outage). So the caching
 * strategy here is deliberately narrow:
 *
 *   - /api/* and any cross-origin request: NEVER intercepted, NEVER cached —
 *     always goes straight to the network. This is the one rule that matters
 *     most in this file.
 *   - HTML navigation requests: network-first, falling back to the cached app
 *     shell ONLY when the network is genuinely unreachable (offline), so the
 *     app can at least show something instead of a browser error page.
 *   - Static build assets (CRA's /static/ output — JS/CSS/fonts, all
 *     content-hashed by webpack): cache-first. Safe to cache aggressively
 *     because a new deploy produces new hashed filenames, not new content
 *     under the same URL.
 *
 * Enables installability (the point of this file existing) without turning
 * this into an "offline dashboard that lies about system health."
 */

const CACHE_VERSION = "falconops-shell-v1";
const SHELL_URLS = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL_URLS)).catch(() => {
      // Non-fatal — install still succeeds even if pre-caching the shell fails
      // (e.g. dev server), fetch-time caching below still works.
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

function isApiRequest(url) {
  return url.pathname.startsWith("/api/");
}

function isStaticAsset(url) {
  return url.pathname.startsWith("/static/") || /\.(js|css|woff2?|ttf|svg|png|jpg|jpeg|ico)$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Cross-origin (API calls typically go to a different backend origin in this
  // app's deployment, but even same-origin /api/* is excluded explicitly) —
  // never intercepted. This is the safety-critical rule; everything else below
  // is pure performance/installability.
  if (url.origin !== self.location.origin || isApiRequest(url)) {
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/index.html"))
    );
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((resp) => {
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone));
          }
          return resp;
        });
      })
    );
  }
  // Everything else: default browser behavior, not intercepted.
});
