// Stale-chunk errors: a tab left open across a deploy.
//
// Two consumers act on the same judgement — the router reloads the page, and this
// module keeps the row out of the manager's log. They used to carry a pattern list
// each, the CSS spelling was missing from both, and a customer got a dead navigation
// plus an error report nobody could act on. These pin the shared predicate.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isStaleChunkError, reportError } from './report'

// the real string, copied from a production error report
const PROD_CSS = 'Unable to preload CSS for /assets/OrderDetails-DgT0LjKs.css'

describe('isStaleChunkError', () => {
  it('recognises the CSS spelling that reached production', () => {
    expect(isStaleChunkError(PROD_CSS)).toBe(true)
  })

  it.each([
    'Failed to fetch dynamically imported module: https://x/assets/a.js', // Chrome
    'Importing a module script failed.',                                  // Safari
    'error loading dynamically imported module',                          // Firefox
    'Unable to preload CSS for /assets/x.css',                            // Vite, any
  ])('recognises %s', (msg) => {
    expect(isStaleChunkError(msg)).toBe(true)
  })

  // The router matched the bare middle phrase before this list replaced its regex.
  // Anything it used to rescue a stale tab from, the shared list still has to catch.
  it('stays at least as broad as the regex it replaced', () => {
    expect(isStaleChunkError('TypeError: dynamically imported module not available'))
      .toBe(true)
  })

  it('is not fooled by case, which differs between browsers', () => {
    expect(isStaleChunkError('UNABLE TO PRELOAD CSS for /a.css')).toBe(true)
  })

  it.each([
    "Cannot read properties of null (reading 'id')",
    'NetworkError when attempting to fetch resource.',
    '',
    null,
    undefined,
  ])('leaves an ordinary failure alone: %s', (msg) => {
    expect(isStaleChunkError(msg)).toBe(false)
  })
})

describe('reportError', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => Promise.resolve({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    // reportError throttles bursts to one per 1.5s; each test is its own burst
    vi.useFakeTimers()
    vi.setSystemTime(Date.now() + 10_000)
  })

  it('does not file a stale chunk — the router is already reloading the page', () => {
    reportError(`Unhandled: ${PROD_CSS}`, 'at HTMLLinkElement.<anonymous>')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('still files a genuine failure', () => {
    reportError('Unhandled: Cannot read properties of null', 'at OrderDetails.vue:12')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/errors')
  })

  it('drops third-party noise as before', () => {
    reportError('Script error.', ':')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
