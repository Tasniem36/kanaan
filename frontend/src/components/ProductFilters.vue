<template>
  <div class="filters">
    <!-- sub-type (صحون / أكواب …) — only when the category actually uses types -->
    <label v-if="types.length" class="f-field">
      <span class="f-label">{{ t('filters.type') }}</span>
      <select class="a-input f-select" :value="type" @change="emit('update:type', $event.target.value)">
        <option value="">{{ t('home.allTypes') }}</option>
        <option v-for="ty in types" :key="ty" :value="ty">{{ ty }}</option>
      </select>
    </label>

    <label class="f-field">
      <span class="f-label">{{ t('filters.sort') }}</span>
      <select class="a-input f-select" :value="sort" @change="emit('update:sort', $event.target.value)">
        <option v-for="o in SORT_OPTIONS" :key="o.value" :value="o.value">{{ t(o.label) }}</option>
      </select>
    </label>

    <div class="f-field f-price">
      <span class="f-label">{{ t('filters.price') }}</span>
      <div class="f-price-row">
        <input
          class="a-input f-num" type="number" min="0" inputmode="decimal" dir="ltr"
          :placeholder="t('filters.min')" :aria-label="t('filters.min')"
          :value="minPrice" @input="onPrice('update:minPrice', $event)"
        >
        <span class="f-dash" aria-hidden="true">—</span>
        <input
          class="a-input f-num" type="number" min="0" inputmode="decimal" dir="ltr"
          :placeholder="t('filters.max')" :aria-label="t('filters.max')"
          :value="maxPrice" @input="onPrice('update:maxPrice', $event)"
        >
      </div>
    </div>

    <button v-if="dirty" class="f-clear" @click="clearAll">{{ t('filters.clear') }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// value keys must match SORT_SQL in backend/routers/products.py
const SORT_OPTIONS = [
  { value: 'featured', label: 'filters.sortFeatured' },
  { value: 'newest', label: 'filters.sortNewest' },
  { value: 'price_asc', label: 'filters.sortPriceAsc' },
  { value: 'price_desc', label: 'filters.sortPriceDesc' },
  { value: 'name', label: 'filters.sortName' },
]

const props = defineProps({
  types: { type: Array, default: () => [] },
  type: { type: String, default: '' },
  sort: { type: String, default: 'featured' },
  minPrice: { type: [Number, String], default: '' },
  maxPrice: { type: [Number, String], default: '' },
})
const emit = defineEmits(['update:type', 'update:sort', 'update:minPrice', 'update:maxPrice'])

const { t } = useI18n()

const dirty = computed(
  () => !!props.type || (props.sort && props.sort !== 'featured') || props.minPrice !== '' || props.maxPrice !== ''
)

// Keep the emitted value a string or '' — a half-typed "1." parses to NaN and
// would blank the field the customer is still typing in.
function onPrice(event, e) {
  const v = e.target.value
  emit(event, v === '' ? '' : v)
}

function clearAll() {
  emit('update:type', '')
  emit('update:sort', 'featured')
  emit('update:minPrice', '')
  emit('update:maxPrice', '')
}
</script>

<style scoped>
.filters {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.9rem;
  margin-bottom: 2rem;
}
.f-field { display: grid; gap: 0.3rem; }
.f-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--muted, #7b7768);
}
.f-select { min-width: 150px; background: var(--paper, #fff); cursor: pointer; }
.f-price-row { display: flex; align-items: center; gap: 0.4rem; }
.f-num { width: 84px; background: var(--paper, #fff); }
/* the browser's number spinners crowd an 84px field */
.f-num::-webkit-outer-spin-button, .f-num::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.f-num { -moz-appearance: textfield; appearance: textfield; }
.f-dash { color: var(--muted, #7b7768); }
.f-clear {
  align-self: flex-end;
  padding: 0.5rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(60, 74, 39, 0.25);
  background: transparent;
  color: var(--green, #3c4a27);
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.f-clear:hover { background: var(--green, #3c4a27); color: var(--cream, #f5efe3); }
@media (max-width: 560px) {
  .filters { gap: 0.7rem; }
  .f-select { min-width: 128px; }
}
</style>
