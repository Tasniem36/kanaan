<template>
  <article class="card reveal" :style="{ transitionDelay: (index * 70) + 'ms' }">
    <div class="thumb">
      <span class="tag" v-if="product.tag">{{ product.tag }}</span>
      <span class="tag" v-else-if="product.stock === 0" style="background:var(--red)">{{ t('product.outOfStock') }}</span>
      <img v-if="image" :src="image" :alt="product.name" loading="lazy" class="thumb-link" @click="goDetail">
      <span v-else class="thumb-empty thumb-link" @click="goDetail">{{ t('image.noImage') }}</span>
    </div>
    <div class="body">
      <h3 class="thumb-link" @click="goDetail">{{ product.name }}</h3>
      <p class="desc">{{ product.description }}</p>
      <div class="foot">
        <span class="price">{{ ar(product.price) }} <span class='dh' role='img' aria-label='درهم'></span> <small>/ {{ product.unit }}</small></span>
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
function goDetail() { router.push({ name: 'product', params: { id: props.product.id } }) }

function add() {
  if (cart.qty(props.product.id) >= props.product.stock) return
  cart.add(props.product)
  emit('added', props.product)
}
</script>
