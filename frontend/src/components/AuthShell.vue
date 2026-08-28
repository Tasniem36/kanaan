<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- The panel: a photograph of what the shop actually sells, with the brand on
           it and a line worth reading. On a phone it collapses away entirely — the
           form is the only thing anyone came here for on a small screen. -->
      <aside class="auth-panel">
        <img class="auth-photo" :src="image" alt="" aria-hidden="true" decoding="async">
        <RouterLink to="/" class="auth-mark"><span class="g">دكّان</span> كنعان</RouterLink>
        <figure class="auth-quote">
          <blockquote v-if="quote">{{ quote }}</blockquote>
          <figcaption v-if="caption">{{ caption }}</figcaption>
        </figure>
      </aside>

      <!-- The form side: white, and quiet enough that the only strong colour on it
           is the button you're meant to press. -->
      <section class="auth-form">
        <div class="auth-top">
          <RouterLink to="/" class="auth-back" :aria-label="t('product.backToStore')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
            <span>{{ t('product.backToStore') }}</span>
          </RouterLink>
          <LangToggle />
        </div>
        <div class="auth-inner">
          <slot />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useContentStore } from '../stores/content'
import LangToggle from './LangToggle.vue'

const { t, locale } = useI18n()
const content = useContentStore()

const props = defineProps({
  // which of the three panels this is — the key the manager's copy is saved under
  section: { type: String, required: true },
  // the bundled photograph, used until the manager picks another
  photo: { type: String, default: '/images/olives.jpg' },
})

// The manager's saved copy wins where they've written something; everything they
// haven't touched falls back to the wording and photograph that ship with the app.
// Same rule as the home page's editable sections — an emptied field is a decision
// to remove that line, which is why '' is honoured rather than replaced.
const saved = computed(() => content.sections[props.section])
const image = computed(() => saved.value?.image || props.photo)
const quote = computed(() =>
  saved.value ? (saved.value[`title_${locale.value === 'ar' ? 'ar' : 'en'}`] || '') : t('auth.panelQuote'))
const caption = computed(() =>
  saved.value ? (saved.value[`desc_${locale.value === 'ar' ? 'ar' : 'en'}`] || '') : t('auth.panelCaption'))

// these pages are prerendered, so the panel starts on the bundled copy and swaps
// to the manager's the moment it arrives — never a blank while it loads
onMounted(() => { if (!content.loaded) content.fetch() })
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: clamp(0rem, 2vw, 2.5rem);
  background: #eeeae2;
}
.auth-card {
  width: min(1080px, 100%);
  min-height: min(680px, 100dvh);
  display: grid;
  grid-template-columns: 38% 1fr;
  background: #fff;
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 30px 70px -40px rgba(20, 23, 14, .45);
}

/* --- the panel --- */
.auth-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2rem 1.9rem;
  color: #fff;
  overflow: hidden;
}
.auth-photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* the photo is a backdrop for text, so it's darkened rather than shown as-is */
  filter: brightness(.62) saturate(.9);
}
/* a second, vertical wash keeps the quote legible over a busy part of the image */
.auth-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(20, 23, 14, .45) 0%, rgba(20, 23, 14, .1) 38%, rgba(20, 23, 14, .78) 100%);
}
.auth-mark, .auth-quote { position: relative; z-index: 1; }
.auth-mark {
  font-family: 'Amiri', serif;
  font-size: 1.5rem;
  color: #fff;
  text-shadow: 0 2px 14px rgba(0, 0, 0, .4);
}
.auth-mark .g { color: var(--gold-2, #d4b25e); }
.auth-quote { margin: 0; }
.auth-quote blockquote {
  font-family: 'Amiri', serif;
  font-size: 1.45rem;
  line-height: 1.65;
  margin: 0 0 1.1rem;
  text-shadow: 0 2px 18px rgba(0, 0, 0, .45);
}
.auth-quote figcaption {
  font-size: .84rem;
  line-height: 1.65;
  opacity: .8;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* --- the form side --- */
.auth-form {
  background: #fff;
  display: flex;
  flex-direction: column;
  padding: 1.1rem 1.2rem 2rem;
}
.auth-top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.auth-back {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
  font-size: .82rem;
  font-weight: 600;
  color: var(--muted, #6b6455);
  padding: .4rem .55rem;
  border-radius: 10px;
  transition: color .2s, background .2s;
}
.auth-back:hover { color: var(--green, #3c4a27); background: rgba(60, 74, 39, .06); }
.auth-back svg { width: 16px; height: 16px; }
/* the back arrow points the way "back" actually is in the current direction */
[dir="rtl"] .auth-back svg { transform: scaleX(-1); }
.auth-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: min(360px, 100%);
  margin-inline: auto;
  padding: 1.5rem 0;
}

@media (max-width: 860px) {
  /* the photograph is the first thing to go: on a phone the form is the whole point */
  .auth-card { grid-template-columns: 1fr; min-height: 100dvh; border-radius: 0; box-shadow: none; }
  .auth-panel { display: none; }
  .auth-page { padding: 0; background: #fff; }
}
</style>
