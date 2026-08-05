/* Web Push service worker for دكّان كنعان.
   Push-only (no fetch/caching), so it doesn't change how the app loads. */
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = {}
  try { data = event.data ? event.data.json() : {} } catch (_) { data = {} }
  const title = data.title || 'دكّان كنعان'
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || '',
    icon: '/icon-180.png',
    badge: '/icon-96.png',
    tag: data.tag || 'dukkan',
    data: { url: data.url || '/' },
    dir: 'rtl',
    lang: 'ar',
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    for (const c of wins) {
      if ('focus' in c) { await c.focus(); if ('navigate' in c) { try { await c.navigate(url) } catch (_) {} } return }
    }
    if (self.clients.openWindow) return self.clients.openWindow(url)
  })())
})
