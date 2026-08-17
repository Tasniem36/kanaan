<template>
  <section>
    <div class="d-head">
      <h1>{{ t('dash.title') }}</h1>
      <button class="a-btn d-refresh" :disabled="loading" @click="load">{{ loading ? '…' : t('dash.refresh') }}</button>
    </div>

    <p v-if="error" class="d-error">{{ error }}</p>

    <!-- skeleton in the real layout, so the page doesn't jump when data lands -->
    <div v-if="!data && loading" class="d-tiles" aria-hidden="true">
      <div v-for="n in 4" :key="n" class="d-tile"><span class="sk sk-line" style="width:52%"></span><span class="sk sk-line lg" style="width:74%"></span></div>
    </div>

    <template v-else-if="data">
      <!-- headline numbers -->
      <div class="d-tiles">
        <div class="d-tile">
          <span class="d-k">{{ t('dash.revenueToday') }}</span>
          <b class="d-v">{{ money(data.money.revenue_today) }} <span class="dh" role="img" aria-label="درهم"></span></b>
          <span class="a-muted">{{ t('dash.ordersN', { n: data.money.orders_today }) }}</span>
        </div>
        <div class="d-tile">
          <span class="d-k">{{ t('dash.revenue7d') }}</span>
          <b class="d-v">{{ money(data.money.revenue_7d) }} <span class="dh" role="img" aria-label="درهم"></span></b>
          <span class="a-muted">{{ t('dash.ordersN', { n: data.money.orders_7d }) }}</span>
        </div>
        <div class="d-tile">
          <span class="d-k">{{ t('dash.revenue30d') }}</span>
          <b class="d-v">{{ money(data.money.revenue_30d) }} <span class="dh" role="img" aria-label="درهم"></span></b>
          <span class="a-muted">{{ t('dash.aov') }}: {{ money(data.money.aov_30d) }}</span>
        </div>
        <div class="d-tile">
          <span class="d-k">{{ t('dash.customers') }}</span>
          <b class="d-v">{{ data.customers.total }}</b>
          <span class="a-muted">{{ t('dash.newCustomers', { n: data.customers.new_30d }) }}</span>
        </div>
      </div>

      <!-- 14-day revenue bars. Deliberately not a charting library: a dozen divs
           read fine and cost nothing to load. -->
      <div class="d-card">
        <div class="d-card-head">
          <h2>{{ t('dash.last14') }}</h2>
          <span class="a-muted">{{ t('dash.peak') }}: {{ money(peak) }} <span class="dh" role="img" aria-label="درهم"></span></span>
        </div>
        <div v-if="peak > 0" class="d-bars">
          <div v-for="d in data.daily" :key="d.day" class="d-bar-col" :title="`${fmtDay(d.day)} — ${money(d.revenue)} (${d.orders})`">
            <div class="d-bar" :style="{ height: barHeight(d.revenue) }"></div>
            <span class="d-bar-lbl">{{ dayNum(d.day) }}</span>
          </div>
        </div>
        <p v-else class="a-muted d-empty">{{ t('dash.noSales') }}</p>
      </div>

      <div class="d-two">
        <!-- order pipeline -->
        <div class="d-card">
          <div class="d-card-head"><h2>{{ t('dash.pipeline') }}</h2></div>
          <RouterLink
            v-for="s in data.by_status"
            :key="s.status"
            class="d-row d-row-link"
            :to="{ name: 'manager-orders' }"
          >
            <span class="a-pill" :class="statusClass(s.status)">{{ t(`status.${s.status}`) }}</span>
            <b>{{ s.n }}</b>
          </RouterLink>
        </div>

        <!-- what to restock -->
        <div class="d-card">
          <div class="d-card-head">
            <h2>{{ t('dash.lowStock') }}</h2>
            <span class="a-muted">{{ t('dash.lowStockHint', { n: data.low_stock_threshold }) }}</span>
          </div>
          <p v-if="!data.low_stock.length" class="a-muted d-empty">{{ t('dash.stockHealthy') }}</p>
          <RouterLink
            v-for="p in data.low_stock"
            :key="p.id"
            class="d-row d-row-link"
            :to="{ name: 'product', params: { id: p.id } }"
          >
            <span class="d-name">{{ p.name }}</span>
            <span class="a-pill" :class="p.stock === 0 ? 'pill-low' : 'pill-warn'">
              {{ p.stock === 0 ? t('product.outOfStock') : t('dash.unitsLeft', { n: p.stock }) }}
            </span>
          </RouterLink>
        </div>
      </div>

      <!-- best sellers -->
      <div class="d-card">
        <div class="d-card-head">
          <h2>{{ t('dash.topProducts') }}</h2>
          <span class="a-muted">{{ t('dash.last30') }}</span>
        </div>
        <p v-if="!data.top_products.length" class="a-muted d-empty">{{ t('dash.noSales') }}</p>
        <div v-for="p in data.top_products" :key="p.product_id || p.name" class="d-row">
          <span class="d-name">{{ p.name }}</span>
          <span class="d-qty">×{{ p.qty }}</span>
          <b>{{ money(p.revenue) }} <span class="dh" role="img" aria-label="درهم"></span></b>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'

const { t, locale } = useI18n()

const data = ref(null)
const loading = ref(false)
const error = ref('')

// One request for the whole page — every figure comes from /stats/overview.
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api('/stats/overview')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const money = (n) => Math.round(Number(n || 0) * 100) / 100
const peak = computed(() => Math.max(0, ...(data.value?.daily || []).map((d) => Number(d.revenue) || 0)))
// bars are relative to the best day in the window; a day with sales never reads as empty
const barHeight = (v) => (peak.value > 0 ? `${Math.max(3, (Number(v) / peak.value) * 100)}%` : '0%')

const fmtDay = (d) => new Date(d).toLocaleDateString(locale.value, { day: 'numeric', month: 'short' })
const dayNum = (d) => new Date(d).getDate()
const statusClass = (s) =>
  ({ pending: 'pill-warn', paid: 'pill-ok', preparing: 'pill-warn', fulfilled: 'pill-ok', delivered: 'pill-ok', cancelled: 'pill-low' }[s] || '')

onMounted(load)
</script>

<style scoped>
.d-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1.2rem; }
.d-head h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.7rem; }
.d-refresh { white-space: nowrap; }
.d-error { color: var(--red); margin-bottom: 1rem; }

.d-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; }
.d-tile {
  background: #fff; border-radius: 16px; padding: 1rem 1.1rem;
  box-shadow: 0 8px 30px rgba(60, 74, 39, 0.06);
  display: grid; gap: 0.2rem; align-content: start;
}
.d-k { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.05em; color: var(--muted); }
.d-v { font-family: 'Amiri', serif; font-size: 1.7rem; color: var(--terra-deep); line-height: 1.2; }

.d-card {
  background: #fff; border-radius: 16px; padding: 1.1rem 1.2rem; margin-top: 1rem;
  box-shadow: 0 8px 30px rgba(60, 74, 39, 0.06);
}
.d-card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 0.8rem; margin-bottom: 0.7rem; flex-wrap: wrap; }
.d-card-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.15rem; }
.d-two { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

.d-row {
  display: flex; align-items: center; justify-content: space-between; gap: 0.7rem;
  padding: 0.42rem 0.2rem; border-top: 1px solid rgba(60, 74, 39, 0.08);
  font-size: 0.9rem; color: var(--ink);
}
.d-row:first-of-type { border-top: none; }
.d-row-link { border-radius: 8px; transition: background 0.15s; }
.d-row-link:hover { background: var(--cream-2, rgba(60, 74, 39, 0.06)); }
.d-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.d-qty { color: var(--muted); font-size: 0.84rem; }
.d-empty { padding: 0.6rem 0; }

/* revenue bars */
.d-bars { display: flex; align-items: flex-end; gap: 0.35rem; height: 132px; }
.d-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; gap: 0.25rem; }
.d-bar {
  width: 100%; margin-top: auto; border-radius: 6px 6px 0 0;
  background: linear-gradient(180deg, var(--gold, #b8902f), var(--green, #3c4a27));
  transition: height 0.4s ease;
}
.d-bar-lbl { font-size: 0.62rem; color: var(--muted); flex: 0 0 auto; }

/* shared skeleton shimmer, matching the product page's */
.sk { position: relative; overflow: hidden; background: var(--cream-2, rgba(60, 74, 39, 0.08)); border-radius: 8px; height: 1rem; }
.sk.lg { height: 1.8rem; }
.sk::after {
  content: ""; position: absolute; inset: 0; transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  animation: skshimmer 1.3s infinite;
}
@keyframes skshimmer { 100% { transform: translateX(100%); } }

@media (max-width: 720px) {
  .d-two { grid-template-columns: 1fr; }
  .d-bar-lbl { font-size: 0.56rem; }
}
</style>
