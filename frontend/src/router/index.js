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
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guestOnly: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { guestOnly: true } },
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
      { path: 'delivery', name: 'manager-delivery', component: () => import('../views/manager/ManagerDelivery.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export function scrollBehavior(to, from, savedPosition) {
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

    // sync the server cart + saved products: on login/boot pull (once per token);
    // on logout clear both locally so they never leak to the next user (the server
    // copies are kept — pushToServer is a no-op when signed out).
    const cart = useCartStore()
    const wishlist = useWishlistStore()
    if (auth.isAuthenticated) {
      if (auth.token !== cartSyncedToken) {
        cartSyncedToken = auth.token
        cart.loadFromServer()
        wishlist.loadIds()
      }
    } else if (cartSyncedToken) {
      cartSyncedToken = null
      cart.clear()
      wishlist.clear()
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
