// The other half of the stale-chunk decision: the tab has to recover, not just go
// quiet in the log. A deploy renames a chunk, an open tab navigates to a route that
// wants the old one, and the page must reload itself once and come back working.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('../views/HomeView.vue', () => ({ default: { render: () => h('div') } }))
vi.mock('../stores/auth', () => ({
  useAuthStore: () => ({ ready: true, isAuthenticated: false, token: null, fetchMe: vi.fn() }),
}))
vi.mock('../stores/cart', () => ({ useCartStore: () => ({ loadFromServer: vi.fn(), clear: vi.fn() }) }))
vi.mock('../stores/wishlist', () => ({ useWishlistStore: () => ({ loadIds: vi.fn(), clear: vi.fn() }) }))

const { registerGuards } = await import('./index')

const blank = { render: () => h('div') }
const PROD_CSS = 'Unable to preload CSS for /assets/OrderDetails-DgT0LjKs.css'

let reload

function routerThatFailsWith(message) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: blank },
      { path: '/track/:id?', component: () => Promise.reject(new Error(message)) },
    ],
  })
  registerGuards(router)
  return router
}

beforeEach(() => {
  reload = vi.fn()
  // jsdom's own location.reload throws "not implemented"
  Object.defineProperty(window, 'location', {
    value: { ...window.location, reload, pathname: '/', search: '' },
    writable: true,
    configurable: true,
  })
  window.sessionStorage.clear()
})

describe('a tab left open across a deploy', () => {
  it('reloads itself when the stylesheet chunk is gone', async () => {
    const router = routerThatFailsWith(PROD_CSS)
    await router.push('/')
    await router.push('/track/abc').catch(() => {})
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('reloads itself when the script chunk is gone', async () => {
    const router = routerThatFailsWith('Failed to fetch dynamically imported module: /assets/a.js')
    await router.push('/')
    await router.push('/track/abc').catch(() => {})
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('reloads only once, so a genuinely missing file cannot loop', async () => {
    const router = routerThatFailsWith(PROD_CSS)
    await router.push('/')
    await router.push('/track/abc').catch(() => {})
    await router.push('/track/def').catch(() => {})
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not reload for an ordinary navigation error', async () => {
    const router = routerThatFailsWith("Cannot read properties of null (reading 'id')")
    await router.push('/')
    await router.push('/track/abc').catch(() => {})
    expect(reload).not.toHaveBeenCalled()
  })
})
