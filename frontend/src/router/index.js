import { START_LOCATION } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { useWishlistStore } from '../stores/wishlist'
import HomeView from '../views/HomeView.vue'

// Plain route table. vite-ssg builds the router from this (createWebHistory in the
// browser, createMemoryHistory during prerender), so we don't create it ourselves.
export const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/product/:id', name: 'product', component: () => import('../views/ProductView.vue') },
  { path: '/category/:cat', name: 'category', component: () => import('../views/CategoryView.vue') },
  { path: '/search', name: 'search', component: () => import('../views/SearchView.vue') },
  { path: '/pay/return', name: 'pay-return', component: () => import('../views/PayReturn.vue') },
  // public order status page — the ?t= token in the link is the credential, so a
  // guest who checked out without an account can still follow their order
  // /track/:id opens a specific order from the e-mailed link; bare /track shows the
  // "find my order" form (number + phone/e-mail) for a guest who lost the link
  { path: '/track/:id?', name: 'track', component: () => import('../views/TrackView.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guestOnly: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { guestOnly: true } },
  { path: '/forgot-password', name: 'forgot-password', component: () => import('../views/ForgotPasswordView.vue'), meta: { guestOnly: true } },
  {
    path: '/account',
    component: () => import('../views/AccountView.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: { name: 'account-profile' } },
      { path: 'profile', name: 'account-profile', component: () => import('../views/account/AccountProfile.vue') },
      { path: 'orders', name: 'account-orders', component: () => import('../views/account/AccountOrders.vue') },
      { path: 'wishlist', name: 'account-wishlist', component: () => import('../views/account/AccountWishlist.vue') },
    ],
  },
  {
    path: '/manager',
    component: () => import('../views/ManagerView.vue'),
    meta: { requiresManager: true },
    children: [
      { path: '', redirect: { name: 'manager-dashboard' } },
      { path: 'dashboard', name: 'manager-dashboard', component: () => import('../views/manager/ManagerDashboard.vue') },
      { path: 'orders', name: 'manager-orders', component: () => import('../views/manager/ManagerOrders.vue') },
      { path: 'products', name: 'manager-products', component: () => import('../views/manager/ManagerProducts.vue') },
      { path: 'clients', name: 'manager-clients', component: () => import('../views/manager/ManagerClients.vue') },
      { path: 'codes', name: 'manager-codes', component: () => import('../views/manager/ManagerCodes.vue') },
      { path: 'audit', name: 'manager-audit', component: () => import('../views/manager/ManagerAudit.vue') },
      { path: 'errors', name: 'manager-errors', component: () => import('../views/manager/ManagerErrors.vue') },
      { path: 'content', name: 'manager-content', component: () => import('../views/manager/ManagerContent.vue') },
      { path: 'reviews', name: 'manager-reviews', component: () => import('../views/manager/ManagerReviews.vue') },
      { path: 'delivery', name: 'manager-delivery', component: () => import('../views/manager/ManagerDelivery.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export function scrollBehavior(to, from, savedPosition) {
  // an anchored target ('/#reviews', from a review notification) — checked before the
  // rules below so it survives a cold open, which is how a push notification arrives
  if (to.hash && document.getElementById(to.hash.slice(1))) {
    return { el: to.hash, behavior: 'smooth' }
  }
  // fresh page load / hard refresh → always start at the top
  if (from === START_LOCATION) return { top: 0 }
  // returning via back/forward → restore where the customer was
  if (savedPosition) return savedPosition
  return { top: 0 }
}

// Auth guard. Registered on the CLIENT only — it resolves the session from a JWT in
// localStorage, which doesn't exist during prerender (and authed pages never render
// on the server anyway).
let cartSyncedToken = null
export function registerGuards(router) {
  // After a deploy, a still-open tab may try to lazy-load an old chunk whose name
  // changed → "Failed to fetch dynamically imported module". Reload once to pull the
  // fresh files (guarded against a reload loop; cleared on the next good navigation).
  router.onError((err) => {
    const msg = String(err?.message || '')
    if (/dynamically imported module|Importing a module script failed|error loading dynamically/i.test(msg)) {
      if (!sessionStorage.getItem('chunk-reloaded')) {
        sessionStorage.setItem('chunk-reloaded', '1')
        window.location.reload()
      }
    }
  })
  router.afterEach(() => sessionStorage.removeItem('chunk-reloaded'))

  router.beforeEach(async (to) => {
    const auth = useAuthStore()
    if (!auth.ready) await auth.fetchMe() // resolve session once on first navigation

    // Pull the server cart + saved products once per token, on login/boot. Clearing
    // them on the way out is auth.logout()'s job — a sign-out doesn't always reach a
    // guard. Forgetting the token here still matters: sign out and straight back in
    // and the new JWT can be byte-identical to the old one (same subject, same
    // second), which would read as "already synced" and skip the pull.
    if (auth.isAuthenticated) {
      if (auth.token !== cartSyncedToken) {
        cartSyncedToken = auth.token
        useCartStore().loadFromServer()
        useWishlistStore().loadIds()
      }
    } else {
      cartSyncedToken = null
    }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.requiresManager && !auth.isManager) {
      return auth.isAuthenticated ? { name: 'home' } : { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { name: 'home' }
    }
  })
}
