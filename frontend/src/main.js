import { ViteSSG } from 'vite-ssg'
import { createPinia } from 'pinia'
import App from './App.vue'
import { routes, scrollBehavior, registerGuards } from './router'
import { i18n } from './i18n'
import './style.css'

// vite-ssg owns the app/router lifecycle: it prerenders the public routes to static
// HTML at build time (Node) and hydrates the same app in the browser. It creates the
// router from `routes` (memory history on the server, web history in the browser) and
// mounts for us — so we only install plugins and register the client-only auth guard.
export const createApp = ViteSSG(
  App,
  { routes, scrollBehavior },
  ({ app, router, isClient }) => {
    app.use(createPinia())
    app.use(i18n)
    if (isClient) registerGuards(router)
  },
)
