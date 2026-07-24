// Thin fetch wrapper for the API. Reads the JWT straight from localStorage to
// avoid a circular import with the auth store. Base URL is '/api' — the Vite
// dev server and the production nginx both proxy '/api' to the API server.
import { i18n } from '../i18n'

const BASE = import.meta.env.VITE_API_URL || '/api'

export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = localStorage.getItem('token')
  if (auth && token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const err = new Error(data?.error || i18n.global.t('common.error'))
    err.status = res.status
    throw err
  }
  return data
}
