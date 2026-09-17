// A localStorage the tests can actually rely on.
//
// The stores persist the basket and the session through it, and several tests are
// about precisely what is left in it after a sign-out — a reload reads it back, so
// "the basket looked empty" and "the basket is empty" are different claims and only
// this one settles the second. Neither runtime gives us a working one by default:
// Node 22+ defines a built-in `localStorage` that is inert unless the process was
// started with --localstorage-file, and the jsdom environment's own getter answers
// undefined beside it. So rather than depend on either, install one.
function memoryStorage() {
  const data = new Map()
  return {
    get length() { return data.size },
    key: (i) => [...data.keys()][i] ?? null,
    getItem: (k) => (data.has(String(k)) ? data.get(String(k)) : null),
    setItem: (k, v) => { data.set(String(k), String(v)) },
    removeItem: (k) => { data.delete(String(k)) },
    clear: () => { data.clear() },
  }
}

if (typeof globalThis.localStorage?.getItem !== 'function') {
  // One object behind both names, or code reaching through `window` and code
  // reaching through the bare global would each get their own half of the state.
  const store = memoryStorage()
  const shared = { value: store, configurable: true, writable: true }
  Object.defineProperty(globalThis, 'localStorage', shared)
  if (typeof window !== 'undefined') Object.defineProperty(window, 'localStorage', shared)
}
