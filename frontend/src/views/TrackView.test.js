// What the tracking page says when it cannot show the order.
//
// Two failures reach the same catch and they are not the same thing to a customer:
// a link that opens nothing, and a shop that could not be asked. Telling someone
// their link is wrong when the API was down sends them to re-type an order number
// into a form calling the same API — so the distinction is the whole point of these.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

const apiMock = vi.fn()
const reportErrorMock = vi.fn()

vi.mock('../services/api', () => ({ api: (...a) => apiMock(...a) }))
vi.mock('../services/report', () => ({ reportError: (...a) => reportErrorMock(...a) }))
vi.mock('../components/Loader.vue', () => ({ default: { render: () => h('div', 'loading') } }))
vi.mock('../components/OrderDetails.vue', () => ({ default: { render: () => h('div', 'details') } }))
vi.mock('../components/NeedHelp.vue', () => ({
  default: { render: () => h('div', { class: 'need-help' }, 'help') },
}))

const { i18n } = await import('../i18n')
const TrackView = (await import('./TrackView.vue')).default

async function openTrackPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      // the page links home in its header; without this every mount warns
      { path: '/', name: 'home', component: { render: () => h('div') } },
      { path: '/track/:id?', name: 'track', component: TrackView },
    ],
  })
  await router.push({ name: 'track', params: { id: 'abc' }, query: { t: 'tok' } })
  await router.isReady()

  const el = document.createElement('div')
  document.body.appendChild(el)
  const app = createApp({ render: () => h(TrackView) })
  app.use(createPinia()).use(router).use(i18n)
  app.mount(el)
  // let the watcher's load() settle
  await new Promise((r) => setTimeout(r, 10))
  return el
}

const err = (status) => Object.assign(new Error(status ? `HTTP ${status}` : 'Failed to fetch'), { status })

beforeEach(() => {
  apiMock.mockReset()
  reportErrorMock.mockReset()
  i18n.global.locale.value = 'ar'
})

describe('the tracking page when the order will not load', () => {
  it('blames the link when the shop answered that it opens nothing', async () => {
    apiMock.mockRejectedValue(err(404))
    const el = await openTrackPage()
    const text = el.textContent

    expect(text).toContain(i18n.global.t('track.notFoundTitle'))
    expect(text).not.toContain(i18n.global.t('track.unreachableTitle'))
    expect(reportErrorMock, 'a wrong link is the customer\'s, not a shop failure')
      .not.toHaveBeenCalled()
  })

  it('does not blame the link when the shop could not be reached at all', async () => {
    apiMock.mockRejectedValue(err(undefined))   // fetch never landed
    const el = await openTrackPage()
    const text = el.textContent

    expect(text).toContain(i18n.global.t('track.unreachableTitle'))
    expect(text, 'their link and their order are both fine')
      .not.toContain(i18n.global.t('track.notFoundMsg'))
  })

  it('treats a 500 the same way — the shop failed, not the link', async () => {
    apiMock.mockRejectedValue(err(500))
    const el = await openTrackPage()
    expect(el.textContent).toContain(i18n.global.t('track.unreachableTitle'))
  })

  it('puts the shop\'s own failure in the log the manager reads', async () => {
    apiMock.mockRejectedValue(err(503))
    await openTrackPage()
    expect(reportErrorMock).toHaveBeenCalledTimes(1)
    expect(String(reportErrorMock.mock.calls[0][0])).toContain('503')
  })

  it('offers a way to reach a human when the form below cannot help either', async () => {
    apiMock.mockRejectedValue(err(undefined))
    const el = await openTrackPage()
    expect(el.querySelector('.need-help'), 'the lookup form calls the same dead API')
      .toBeTruthy()
  })
})
