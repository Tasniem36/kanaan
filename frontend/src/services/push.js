// Web Push (device notifications) client helpers.
import { api } from './api'

export function pushSupported() {
  return typeof window !== 'undefined' &&
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

function urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

let regPromise = null
function getReg() {
  if (!regPromise) regPromise = navigator.serviceWorker.register('/sw.js')
  return regPromise
}

export async function isPushOn() {
  if (!pushSupported() || Notification.permission !== 'granted') return false
  try {
    const reg = await getReg()
    return !!(await reg.pushManager.getSubscription())
  } catch { return false }
}

// Ask permission, subscribe, and register the subscription with the backend.
export async function enablePush() {
  if (!pushSupported()) throw new Error('unsupported')
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('denied')
  const { key } = await api('/push/key', { auth: false })
  if (!key) throw new Error('not-configured')
  const reg = await getReg()
  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(key) })
  }
  await api('/push/subscribe', { method: 'POST', body: { subscription: sub.toJSON() } })
  return true
}

export async function disablePush() {
  if (!pushSupported()) return
  try {
    const reg = await getReg()
    const sub = await reg.pushManager.getSubscription()
    if (sub) {
      await api('/push/unsubscribe', { method: 'POST', body: { subscription: { endpoint: sub.endpoint } } }).catch(() => {})
      await sub.unsubscribe().catch(() => {})
    }
  } catch { /* ignore */ }
}
