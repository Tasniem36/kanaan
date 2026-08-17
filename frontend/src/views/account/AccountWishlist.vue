<template>
  <section class="panel">
    <div class="panel-head">
      <h2>{{ t('wishlist.title') }}</h2>
      <span v-if="wishlist.products.length" class="a-muted">{{ t('wishlist.count', { n: wishlist.products.length }) }}</span>
    </div>

    <Loader v-if="wishlist.loading && !wishlist.loaded" :label="t('common.loading')" />

    <p v-else-if="!wishlist.products.length" class="a-muted">
      {{ t('wishlist.empty') }}
      <RouterLink to="/" style="color:var(--green);text-decoration:underline">{{ t('account.shopNow') }}</RouterLink>
    </p>

    <div v-else class="grid wl-grid">
      <ProductCard
        v-for="(p, i) in wishlist.products"
        :key="p.id"
        :product="p"
        :index="i"
        @added="onAdded"
      />
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useWishlistStore } from '../../stores/wishlist'
import { useToastStore } from '../../stores/toast'
import { pName } from '../../utils/product'
import ProductCard from '../../components/ProductCard.vue'
import Loader from '../../components/Loader.vue'

const { t } = useI18n()
const wishlist = useWishlistStore()
const toast = useToastStore()

function onAdded(p) { toast.show(t('cart.added', { name: pName(p) })) }

// Always refetch on open: prices and stock move, and a card unsaved from another
// tab should be gone by the time this list renders.
onMounted(() => wishlist.fetch().catch((e) => toast.show(e.message)))
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin-bottom: .8rem; }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; }
/* slightly tighter than the storefront grid — the account column is narrower */
.wl-grid { grid-template-columns: repeat(auto-fill, minmax(196px, 1fr)); gap: 1.1rem; }
</style>
