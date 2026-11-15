/* PYRAMID service worker: cache ΜΟΝΟ του app shell (HTML, JS, CSS, fonts, icons).
   Τίποτα από το /api/ δεν μπαίνει ποτέ στο cache (ούτε φωτογραφία, ούτε απάντηση με δεδομένα του παιδιού).
   Το όνομα του cache αλλάζει σε κάθε build (το γράφει το vite.config.ts στη σταθερά VERSION· πηγή: src/sw/sw.js). */
const VERSION = '__SW_VERSION__';
const SHELL = `pyramid-shell-${VERSION}`;
const PRECACHE = ['/', '/index.html', '/manifest.json', '/fonts/fonts.css', '/icons/icon-192.png', '/icons/icon-512.png', '/mark.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(PRECACHE).catch(() => undefined)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return; // δίκτυο μόνο: ποτέ cache για το API
  }
  if (req.mode === 'navigate') {
    // App shell: δίκτυο πρώτα, αλλιώς το αποθηκευμένο index.html (S04δ, S01δ)
    event.respondWith(fetch(req).catch(() => caches.match('/index.html')));
    return;
  }
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok && (url.pathname.startsWith('/assets/') || PRECACHE.includes(url.pathname))) {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(req, copy));
      }
      return res;
    })),
  );
});
