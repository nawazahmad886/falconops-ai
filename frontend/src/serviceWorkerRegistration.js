/**
 * Registers /service-worker.js (public/service-worker.js — see that file for
 * the caching strategy, which deliberately never caches /api/* so this can't
 * cause a monitoring dashboard to show stale-but-cached "everything is fine"
 * data). Standard register-on-load pattern; only runs in production builds
 * over HTTPS (or localhost) per the Service Worker spec's own requirements.
 */
export function register() {
  if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .catch((error) => {
        console.warn("Service worker registration failed:", error);
      });
  });
}

export function unregister() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => registration.unregister())
      .catch(() => {});
  }
}
