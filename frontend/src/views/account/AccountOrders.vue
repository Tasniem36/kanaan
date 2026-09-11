<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.orders') }}</h2></div>
    <Loader v-if="ordersStore.loading" :label="t('common.loading')" />
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('account.noOrders') }} <RouterLink to="/" style="color:var(--green);text-decoration:underline">{{ t('account.shopNow') }}</RouterLink></p>
    <div v-else>
      <div class="a-card" v-for="o in visibleOrders" :key="o.id">
        <div class="a-row">
          <div>
            <!-- The number on their confirmation e-mail, not the id prefix: this list
                 used to call an order something nothing else in the shop had ever
                 called it, so nobody could quote it back over WhatsApp. -->
            <span style="font-family:monospace;color:var(--green)" dir="ltr">{{ orderNumber(o) }}</span>
            <span class="a-muted"> · {{ fmtDate(o.created_at) }}</span>
          </div>
          <div class="a-row" style="gap:.6rem">
            <!-- Formatted the way every other price in the shop is; this list printed
                 the raw number, so ٦٥ on the tracking page read 65 here. -->
            <span class="a-total">{{ money(o.total, locale) }} <span class='dh' role='img' aria-label='درهم'></span></span>
            <span class="a-pill" :class="statusClass(o.status)">{{ t(statusLabelKey(o)) }}</span>
          </div>
        </div>
        <!-- The same component the tracking page renders, folded down to a list row:
             a signed-in customer is told exactly what a guest with a link is told. -->
        <OrderDetails :order="o" compact @changed="ordersStore.fetch({ mine: true })" />
      </div>
      <div v-if="hasMore" ref="sentinel" class="load-more"><span class="ld-spin"></span></div>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import Loader from '../../components/Loader.vue'
import OrderDetails from '../../components/OrderDetails.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { longDate } from '../../utils/datetime'
import { money, orderNumber, statusLabelKey } from '../../utils/order'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()

const { visible: visibleOrders, sentinel, hasMore } = useInfiniteScroll(() => ordersStore.orders, 10)

const statusClass = (s) => ({ pending: 'pill-warn', paid: 'pill-ok', preparing: 'pill-warn', fulfilled: 'pill-ok', delivered: 'pill-ok', cancelled: 'pill-low' }[s] || '')
const fmtDate = (d) => longDate(d, locale.value)

onMounted(() => ordersStore.fetch({ mine: true }))
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; margin-bottom: .8rem; }
</style>
