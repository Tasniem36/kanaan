<template>
  <article class="card reveal" :style="{ transitionDelay: (index * 70) + 'ms' }">
    <div class="thumb">
      <span class="tag" v-if="product.tag">{{ product.tag }}</span>
      <span class="tag" v-else-if="product.stock === 0" style="background:var(--red)">{{ t('product.outOfStock') }}</span>
      <img v-if="images.length" :src="images[idx]" :alt="product.name" loading="lazy" class="thumb-link" @click="goDetail">
      <span v-else class="thumb-empty thumb-link" @click="goDetail">{{ t('image.noImage') }}</span>
      <template v-if="images.length > 1">
        <button class="car-nav prev" @click.stop="prev" :aria-label="t('image.prev')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></button>
        <button class="car-nav next" @click.stop="next" :aria-label="t('image.next')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></button>
        <div class="car-dots">
          <button v-for="(im, i) in images" :key="i" :class="{ on: i === idx }" @click.stop="idx = i" :aria-label="`${i + 1}`"></button>
        </div>
      </template>
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
import { ref, computed } from 'vue'
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

// gallery: use the images array, falling back to the single image_url
const images = computed(() => {
  const imgs = props.product.images
  if (Array.isArray(imgs) && imgs.length) return imgs
  return props.product.image_url ? [props.product.image_url] : []
})
const idx = ref(0)
function prev() { idx.value = (idx.value - 1 + images.value.length) % images.value.length }
function next() { idx.value = (idx.value + 1) % images.value.length }
function goDetail() { router.push({ name: 'product', params: { id: props.product.id } }) }

function add() {
  if (cart.qty(props.product.id) >= props.product.stock) return
  cart.add(props.product)
  emit('added', props.product)
}
</script>
