// The server cart, and the one thing it must never do: show one customer's basket
// to another.
//
// The pull that fetches it is the only request in the app whose answer can outlive
// the question — a whole round-trip separates the two — so the session that asked
// for a basket may be gone by the time it arrives. Applying it then hands the last
// customer's shopping to whoever is holding the browser, and persist() writes it to
// localStorage, where the next reload finds it and it stops looking like a glitch.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('../services/api', () => ({ api: apiMock }))

const { useCartStore } = await import('./cart')
const { useAuthStore } = await import('./auth')

const OIL = { id: 'p-oil', name: 'زيت زيتون', price: 55 }
const ZAATAR = { id: 'p-zaatar', name: 'زعتر', price: 20 }

/** A response we can hold open, so a sign-out can land in the middle of it. */
function deferred() {
  let settle
  return { promise: new Promise((r) => { settle = r }), arrive: (v) => settle(v) }
}

const line = (product, qty) => ({ [product.id]: { product, qty } })
const stored = () => JSON.parse(localStorage.getItem('cart') || '{}')

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  // stray calls (the debounced push-back) must resolve, not explode in a timer
  apiMock.mockReset()
  apiMock.mockResolvedValue({})
})

describe('a sign-out while the basket is being fetched', () => {
  it('does not restore the signed-out customer’s basket', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    const pull = deferred()
    apiMock.mockReturnValueOnce(pull.promise)
    const sync = cart.loadFromServer()      // A's basket is on its way

    auth.logout()                            // ...and A signs out before it lands
    expect(cart.count).toBe(0)

    pull.arrive({ items: line(OIL, 3) })     // the old answer arrives anyway
    await sync

    expect(cart.count).toBe(0)
    expect(cart.list).toEqual([])
  })

  it('leaves nothing of it in localStorage either', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    const pull = deferred()
    apiMock.mockReturnValueOnce(pull.promise)
    const sync = cart.loadFromServer()
    auth.logout()
    pull.arrive({ items: line(OIL, 3) })
    await sync

    // the part that turns a flicker into a basket: a reload reads this back
    expect(stored()).toEqual({})
  })

  it('does not carry it over to the next customer to sign in', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    const aPull = deferred()
    apiMock.mockReturnValueOnce(aPull.promise)
    const aSync = cart.loadFromServer()

    auth.logout()
    auth.setSession('token-B', { id: 'B' })  // B picks up the same browser

    aPull.arrive({ items: line(OIL, 3) })    // A's basket, addressed to nobody now
    await aSync

    apiMock.mockResolvedValueOnce({ items: line(ZAATAR, 1) })
    await cart.loadFromServer()

    expect(cart.list.map((i) => i.id)).toEqual([ZAATAR.id])
    expect(stored()[OIL.id]).toBeUndefined()
  })

  it('does not push the stale basket back to the server', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    const pull = deferred()
    apiMock.mockReturnValueOnce(pull.promise)
    const sync = cart.loadFromServer()
    auth.logout()
    pull.arrive({ items: line(OIL, 3) })
    await sync

    expect(apiMock.mock.calls.filter(([, o]) => o?.method === 'PUT')).toEqual([])
  })
})

describe('whenSynced', () => {
  it('does not resolve against the previous session’s pull', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    const pull = deferred()
    apiMock.mockReturnValueOnce(pull.promise)
    const stale = cart.loadFromServer()
    auth.logout()

    // Its callers are the paths that take a paid order back out of the basket. They
    // wait here precisely because a merge landing after a removal undoes it — so a
    // promise left over from the last session means one customer's payment quietly
    // restoring another's shopping.
    expect(cart.whenSynced()).not.toBe(stale)

    // A's pull is never allowed to arrive. Racing a timer rather than counting
    // microtask ticks: the queue drains before any timer does, so this says
    // "settled on its own" without depending on how many ticks Pinia adds.
    const outcome = await Promise.race([
      cart.whenSynced().then(() => 'settled'),
      new Promise((r) => { setTimeout(() => r('still waiting on the old session'), 0) }),
    ])
    expect(outcome).toBe('settled')
  })
})

describe('the ordinary sign-in', () => {
  it('still pulls the basket and keeps it', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    auth.setSession('token-A', { id: 'A' })

    apiMock.mockResolvedValueOnce({ items: line(OIL, 2) })
    await cart.loadFromServer()

    expect(cart.count).toBe(2)
    expect(cart.total).toBe(110)
    expect(stored()[OIL.id].qty).toBe(2)
  })

  it('still merges what was added before signing in, keeping the larger quantity', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    cart.add(ZAATAR)                         // added as a guest
    cart.add(OIL)

    auth.setSession('token-A', { id: 'A' })
    apiMock.mockResolvedValueOnce({ items: line(OIL, 4) })
    await cart.loadFromServer()

    expect(cart.qty(OIL.id)).toBe(4)         // the server's larger count wins
    expect(cart.qty(ZAATAR.id)).toBe(1)      // and the guest line survives
  })

  it('keeps the local basket when the pull fails', async () => {
    const auth = useAuthStore()
    const cart = useCartStore()
    cart.add(OIL)
    auth.setSession('token-A', { id: 'A' })

    apiMock.mockRejectedValueOnce(new Error('offline'))
    await cart.loadFromServer()

    expect(cart.qty(OIL.id)).toBe(1)
  })

  it('asks for nothing at all when nobody is signed in', async () => {
    const cart = useCartStore()
    await cart.loadFromServer()
    expect(apiMock).not.toHaveBeenCalled()
  })
})
