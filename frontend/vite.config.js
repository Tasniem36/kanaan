import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // vite-ssg (static generation) options.
  ssgOptions: {
    // Prerender ONLY the public, mostly-static pages. Everything else stays a
    // client-rendered SPA route served via the index.html fallback. Authenticated
    // pages (/account, /manager/*) must never prerender — they read localStorage at
    // setup time and have no SEO value; dynamic pages (/product/:id, /category/:cat)
    // are data-driven with base64 images, so we don't bake them either.
    includedRoutes: () => ['/', '/login', '/register'],
    formatting: 'minify',
  },
  server: {
    // In dev, proxy API calls to the local API server so the frontend can
    // just call '/api/...' (same as in production behind nginx).
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
