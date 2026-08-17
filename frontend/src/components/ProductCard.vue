<template>
  <article class="card reveal" :style="{ transitionDelay: (index * 70) + 'ms' }">
    <div class="thumb">
      <!-- Sold-out takes the badge over a promo tag, since it changes what the
           shopper can do. Remaining quantity is deliberately NOT shown — low
           stock is manager information (see the dashboard's restock list). -->
      <span v-if="product.stock === 0" class="tag tag-out">{{ t('product.outOfStock') }}</span>
      <span v-else-if="tag" class="tag">{{ tag }}</span>
      <WishlistButton :product="product" />
      <img v-if="image" :src="image" :alt="name" loading="lazy" decoding="async" class="thumb-link" @click="goDetail">
      <span v-else class="thumb-empty thumb-link" @click="goDetail">{{ t('image.noImage') }}</span>
    </div>
    <div class="body">
      <h3 class="thumb-link" @click="goDetail">{{ name }}</h3>
      <p class="desc">{{ desc }}</p>
      <div class="foot">
        <span class="price">{{ ar(product.price) }} <span class='dh' role='img' aria-label='درهم'></span> <small>/ {{ unit }}</small></span>
        <span v-if="product.stock === 0" class="add" style="opacity:.5;pointer-events:none">{{ t('product.outOfStock') }}</span>
        <button v-else-if="!cart.qty(product.id)" class="add" @click="add">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>{{ t('product.add') }}
        </button>
        <span v-else class="stepper">
          <button @click="cart.dec(product.id)" aria-label="إنقاص">−</button>
          <span>{{ ar(cart.qty(product.id)) }}</span>
          <button @click="add" aria-label="زيادة" :disabled="cart.qty(product.id) >= product.stock">+</button>
        </span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { pName, pDesc, pUnit, pTag } from '../utils/product'
import WishlistButton from './WishlistButton.vue'

const { t } = useI18n()
const router = useRouter()

const props = defineProps({
  product: { type: Object, required: true },
  index: { type: Number, default: 0 },
})
const emit = defineEmits(['added'])

const cart = useCartStore()
const ar = (n) => String(n)

// lists carry only a light thumbnail; the full gallery loads on the detail page
const image = computed(() => props.product.thumb_url || props.product.image_url || (props.product.images?.[0]) || '')
// product copy follows the active language, falling back to Arabic
const name = computed(() => pName(props.product))
const desc = computed(() => pDesc(props.product))
const unit = computed(() => pUnit(props.product))
const tag = computed(() => pTag(props.product))
function goDetail() { router.push({ name: 'product', params: { id: props.product.id } }) }

function add() {
  if (cart.qty(props.product.id) >= props.product.stock) return
  cart.add(props.product)
  emit('added', props.product)
}
</script>

<style scoped>
.tag-out { background: var(--red, #9c2b2b); }
</style>
