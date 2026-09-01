import dns from 'node:dns'
import http from 'node:http'
import https from 'node:https'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  // Vite loads .env files for the app, not for this file — so read them here
  // ourselves. A shell variable still wins over the file, for a one-off run.
  const env = { ...loadEnv(mode, process.cwd(), 'VITE_'), ...process.env }

  // Where '/api' and '/media' go: a local API server by default, or the live
  // site (VITE_API_PROXY=https://dukkan-kanaan.com) when you'd rather not run
  // one. Proxying keeps every request same-origin, so no CORS is involved.
  const proxy = () => {
    const target = env.VITE_API_PROXY || 'http://localhost:8080'
    const agent = target.startsWith('https')
      ? new https.Agent({ keepAlive: true, lookup: rememberingLookup() })
      : new http.Agent({ keepAlive: true, lookup: rememberingLookup() })
    return {
      '/api': { target, changeOrigin: true, agent },
      // product images served by the API from its media volume
      '/media': { target, changeOrigin: true, agent },
    }
  }

  return {
    plugins: [vue()],
    // vite-ssg (static generation) options.
    ssgOptions: {
      // Prerender ONLY the public, mostly-static pages. Everything else stays a
      // client-rendered SPA route served via the index.html fallback. Authenticated
      // pages (/account, /manager/*) must never prerender — they read localStorage at
      // setup time and have no SEO value; dynamic pages (/product/:id, /category/:cat)
      // are data-driven with base64 images, so we don't bake them either.
      includedRoutes: () => ['/', '/login', '/register', '/forgot-password'],
      formatting: 'minify',
    },
    server: { proxy: proxy() },
    // `vite preview` (serving the built dist) uses the same proxy, so a local
    // production build can talk to the same API.
    preview: { proxy: proxy() },
  }
})

// One page asks for dozens of /media thumbs at once, and a resolver behind a VPN
// drops the odd query under that much parallelism — which surfaced as
// `http proxy error: ... getaddrinfo ENOTFOUND`, a whole request lost to one bad
// lookup. So keep the last address that worked for a host and answer from it when
// a lookup fails. Paired with keepAlive, a page settles into one connection and
// stops re-resolving at all.
function rememberingLookup() {
  const known = new Map()
  return (hostname, options, callback) => {
    // `all: true` answers with an array of addresses, otherwise (address, family)
    // — cache per shape so a hit never replays the wrong one.
    const key = `${hostname}:${options?.all ? 'all' : 'one'}`
    dns.lookup(hostname, options, (err, ...answer) => {
      if (!err) {
        known.set(key, answer)
        return callback(null, ...answer)
      }
      const last = known.get(key)
      if (last) return callback(null, ...last)
      callback(err)
    })
  }
}
