<template>
  <div class="portal">
    <PortalBar drawer>
      <nav class="tabs">
        <RouterLink :to="{ name: 'manager-orders' }">
          {{ t('manager.orders') }}<span v-if="newCount" class="nbadge">{{ newCount }}</span>
        </RouterLink>
        <RouterLink :to="{ name: 'manager-products' }">{{ t('manager.products') }}</RouterLink>
        <RouterLink :to="{ name: 'manager-clients' }">{{ t('manager.clients') }}</RouterLink>
      </nav>
    </PortalBar>
    <main class="portal-body">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PortalBar from '../components/PortalBar.vue'
import { useOrdersStore } from '../stores/orders'
import { useToastStore } from '../stores/toast'

const { t } = useI18n()
const route = useRoute()
const ordersStore = useOrdersStore()
const toast = useToastStore()

// "new" = orders created after the last time the manager viewed the Orders tab
const lastSeen = ref(Number(localStorage.getItem('mgr_orders_seen') || 0))
const newCount = computed(
  () => ordersStore.orders.filter((o) => new Date(o.created_at).getTime() > lastSeen.value).length
)
let prev = 0
let timer = null

function markSeen() {
  lastSeen.value = Date.now()
  localStorage.setItem('mgr_orders_seen', String(lastSeen.value))
  prev = 0
}

// short chime via Web Audio (no asset needed)
function beep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    const ac = new Ctx()
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.connect(gain)
    gain.connect(ac.destination)
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.setValueAtTime(0.12, ac.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 0.35)
    osc.start()
    osc.stop(ac.currentTime + 0.35)
  } catch { /* audio not allowed — badge/toast still show */ }
}

async function poll() {
  await ordersStore.fetch().catch(() => {})
  if (newCount.value > prev) {
    beep()
    toast.show(t('manager.newOrder'))
  }
  prev = newCount.value
  if (route.name === 'manager-orders') markSeen()
}

onMounted(async () => {
  if (!lastSeen.value) markSeen() // first-ever visit: baseline = now, don't flag old orders
  await ordersStore.fetch().catch(() => {})
  prev = newCount.value // silent baseline (no chime on load)
  if (route.name === 'manager-orders') markSeen()
  timer = setInterval(poll, 30000) // check every 30s
})
onUnmounted(() => clearInterval(timer))
watch(() => route.name, (n) => { if (n === 'manager-orders') markSeen() })
</script>

<style scoped>
.portal { min-height: 100vh; background: var(--cream, #f7f3e9); }
.portal-body { max-width: 1000px; margin: 0 auto; padding: 1.8rem 1.2rem 4rem; }
.nbadge {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin-inline-start: 0.35rem;
  border-radius: 9px;
  background: var(--red, #9c2b2b);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  vertical-align: middle;
}
</style>
