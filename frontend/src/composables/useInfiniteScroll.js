import { ref, computed, watch, onBeforeUnmount, nextTick } from 'vue'

// Progressive "load more on scroll" for any list.
// `source` is a getter returning the full array; attach `sentinel` to a
// bottom element rendered only while `hasMore` is true.
export function useInfiniteScroll(source, pageSize = 12) {
  const shown = ref(pageSize)
  const sentinel = ref(null)
  const all = computed(() => source() || [])
  const visible = computed(() => all.value.slice(0, shown.value))
  const hasMore = computed(() => visible.value.length < all.value.length)

  let io = null
  function attach() {
    if (io) io.disconnect()
    if (!sentinel.value) return
    io = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting)) shown.value = Math.min(shown.value + pageSize, all.value.length) },
      { rootMargin: '400px 0px' }
    )
    io.observe(sentinel.value)
  }

  // re-arm when the list changes, more rows reveal, or the sentinel (un)mounts
  watch([() => all.value.length, shown, sentinel], () => nextTick(attach))
  // if the source shrinks, keep `shown` in range
  watch(() => all.value.length, (n) => { if (shown.value > n) shown.value = Math.max(pageSize, n) })
  onBeforeUnmount(() => io && io.disconnect())

  return { visible, sentinel, hasMore }
}
