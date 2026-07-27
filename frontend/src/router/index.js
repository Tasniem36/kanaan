import { createRouter, createWebHistory, START_LOCATION } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import HomeView from '../views/HomeView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/product/:id', name: 'product', component: () => import('../views/ProductView.vue') },
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
    ],
  },
  {
    path: '/manager',
    component: () => import('../views/ManagerView.vue'),
    meta: { requiresManager: true },
    children: [
      { path: '', redirect: { name: 'manager-orders' } },
      { path: 'orders', name: 'manager-orders', component: () => import('../views/manager/ManagerOrders.vue') },
      { path: 'products', name: 'manager-products', component: () => import('../views/manager/ManagerProducts.vue') },
      { path: 'clients', name: 'manager-clients', component: () => import('../views/manager/ManagerClients.vue') },
      { path: 'codes', name: 'manager-codes', component: () => import('../views/manager/ManagerCodes.vue') },
      { path: 'audit', name: 'manager-audit', component: () => import('../views/manager/ManagerAudit.vue') },
      { path: 'content', name: 'manager-content', component: () => import('../views/manager/ManagerContent.vue') },
      { path: 'delivery', name: 'manager-delivery', component: () => import('../views/manager/ManagerDelivery.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // fresh page load / hard refresh → always start at the top
    if (from === START_LOCATION) return { top: 0 }
    // returning via back/forward → restore where the customer was
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchMe() // resolve session once on first navigation

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
