// Thin fetch wrapper for the API. Reads the JWT straight from localStorage to
// avoid a circular import with the auth store. Base URL is '/api' — the Vite
// dev server and the production nginx both proxy '/api' to the API server.
import { i18n } from '../i18n'
import { reportError } from './report'

const BASE = import.meta.env.VITE_API_URL || '/api'

export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = import.meta.env.SSR ? null : localStorage.getItem('token')
  if (auth && token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(BASE + path, {
    method,
    headers,
    // never serve API data from the browser HTTP cache — always hit the network
    // so a reload shows fresh data (no stale "old then new" flash)
    cache: 'no-store',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const err = new Error(data?.error || i18n.global.t('common.error'))
    err.status = res.status
    // We sent a token and it was refused: it expired, or a password change on another
    // device retired this session (see backend/security.py). Either way it is no use
    // to anyone, so drop it here rather than leaving the app half signed in until
    // something happens to reload it. Signing in is unaffected — that call carries no
    // token, so its 401 means "wrong password" and lands nowhere near this.
    if (res.status === 401 && auth && token) await endSession()
    // only server errors (5xx) — expected 4xx (validation, auth, not-found) are normal flow
    if (res.status >= 500) reportError(`API ${res.status} ${method} ${path}`, data?.error)
    throw err
  }
  return data
}

// Imported lazily: the auth store imports this module, so pulling it in at the top
// would be a cycle (which is also why the token above is read straight from
// localStorage). Falls back to clearing the key alone if the store isn't up yet.
async function endSession() {
  try {
    const { useAuthStore } = await import('../stores/auth')
    useAuthStore().logout()
  } catch {
    localStorage.removeItem('token')
  }
}
