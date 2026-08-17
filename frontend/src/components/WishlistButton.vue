<template>
  <button
    class="wish"
    :class="[{ on: saved }, size]"
    :aria-label="saved ? t('wishlist.remove') : t('wishlist.add')"
    :aria-pressed="saved"
    :title="saved ? t('wishlist.remove') : t('wishlist.add')"
    @click.stop.prevent="toggle"
  >
    <!-- filled when saved, outline when not -->
    <svg viewBox="0 0 24 24" :fill="saved ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 20.3 4.6 13a4.8 4.8 0 0 1 6.8-6.8l.6.6.6-.6A4.8 4.8 0 0 1 19.4 13Z"/>
    </svg>
    <span v-if="label" class="wish-label">{{ saved ? t('wishlist.saved') : t('wishlist.save') }}</span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { useWishlistStore } from '../stores/wishlist'
import { useToastStore } from '../stores/toast'

const props = defineProps({
  product: { type: Object, required: true },
  // 'sm' floats over a product card; 'md' sits in the product page's button row
  size: { type: String, default: 'sm' },
  label: { type: Boolean, default: false },
})

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const wishlist = useWishlistStore()
const toast = useToastStore()

const saved = computed(() => wishlist.has(props.product.id))

async function toggle() {
  // Saving needs an account to save *to*. Send guests to sign in and bring them
  // back to the page they were on.
  if (!auth.isAuthenticated) {
    toast.show(t('wishlist.loginRequired'))
    router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    return
  }
  try {
    const nowSaved = await wishlist.toggle(props.product)
    toast.show(nowSaved ? t('wishlist.added') : t('wishlist.removed'))
  } catch (e) {
    toast.show(e.message)
  }
}
</script>

<style scoped>
.wish {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: none;
  background: transparent;
  color: var(--muted, #7b7768);
  cursor: pointer;
  transition: color 0.2s, transform 0.2s, background 0.2s;
}
.wish:hover { color: var(--red, #9c2b2b); }
.wish.on { color: var(--red, #9c2b2b); }
.wish:active { transform: scale(0.9); }
/* Floating over a card thumbnail, on the opposite corner from the .tag badge so
   the two never overlap (both flip together in RTL). */
.wish.sm {
  position: absolute;
  top: 8px;
  inset-inline-start: 8px;
  z-index: 2;
  width: 34px;
  height: 34px;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 4px 14px -6px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
}
.wish.sm:hover { background: #fff; }
.wish.sm svg { width: 18px; height: 18px; }
/* inline on the product page, matching the Share button's pill */
.wish.md {
  padding: 0.6rem 1.1rem;
  border-radius: 999px;
  border: 2px solid var(--red, #9c2b2b);
  font-family: inherit;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--red, #9c2b2b);
}
.wish.md:hover, .wish.md.on { background: var(--red, #9c2b2b); color: var(--cream, #f5efe3); transform: translateY(-2px); }
.wish.md svg { width: 18px; height: 18px; }
.wish-label { white-space: nowrap; }
@media (prefers-reduced-motion: reduce) {
  .wish { transition: color 0.2s; }
  .wish:active, .wish.md:hover { transform: none; }
}
</style>
