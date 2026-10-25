/*
 * Garuda service worker.
 *
 * Two rules, and they come from the project's honesty contract:
 *
 * 1. The static shell is cached so the app opens without a network.
 * 2. The API is never cached. Answering a question from a cache would repeat
 *    a fact the service can no longer confirm; the app must be free to say
 *    "unavailable" instead.
 *
 * Cache trouble must never reach the page: every cache operation is guarded,
 * and the last resort is a failed response the browser handles, not a
 * service worker that dies mid-fetch.
 */

const CACHE = 'garuda-shell-v1';

const SHELL = ['/', '/index.html', '/manifest.json', '/favicon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      // A partial precache must not block installation; runtime caching
      // covers whatever the first visit fails to pick up.
      .catch(() => undefined),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
      .catch(() => undefined),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Fonts and other third-party hosts are not ours to cache.
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(
        () =>
          new Response(
            JSON.stringify({
              error: {
                code: 'offline',
                message: 'Offline: live data could not be fetched.',
                status: 503,
              },
            }),
            { status: 503, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );
    return;
  }

  event.respondWith(staleWhileRevalidate(request));
});

async function staleWhileRevalidate(request) {
  let cache = null;
  let cached = null;

  try {
    cache = await caches.open(CACHE);
    cached = await cache.match(request);
  } catch {
    // No usable cache: fall through and answer from the network.
  }

  const network = fetch(request)
    .then((response) => {
      if (cache && response && response.ok) {
        cache.put(request, response.clone()).catch(() => undefined);
      }
      return response;
    })
    .catch((error) => {
      // Offline: the cached copy stands in, if there is one.
      if (cached) return cached;
      throw error;
    });

  if (cached) {
    // Answer now, revalidate quietly. A failed revalidation must not surface.
    network.catch(() => undefined);
    return cached;
  }

  try {
    return await network;
  } catch {
    // Nothing cached and nothing from the network. Hand the browser a failed
    // response rather than letting this promise reject and blank the page.
    return Response.error();
  }
}
