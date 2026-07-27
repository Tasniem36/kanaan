import { ref, computed, watch } from 'vue'

// Numbered pagination over a reactive list. `source` is a getter returning the
// full array. Returns the current page, total page count, and the visible slice.
export function usePagination(source, perPage = 10) {
  const page = ref(1)
  const all = computed(() => source() || [])
  const pageCount = computed(() => Math.max(1, Math.ceil(all.value.length / perPage)))
  const visible = computed(() => all.value.slice((page.value - 1) * perPage, page.value * perPage))
  // keep the page in range when the list shrinks
  watch(pageCount, (n) => { if (page.value > n) page.value = n })
  return { page, pageCount, visible }
}
