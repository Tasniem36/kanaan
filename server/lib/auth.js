import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'

const SECRET = process.env.JWT_SECRET || 'dev-secret-change-me'
const EXPIRES_IN = '24h' // keep users signed in for 24 hours

export const hashPassword = (pw) => bcrypt.hash(pw, 10)
export const verifyPassword = (pw, hash) => bcrypt.compare(pw, hash)

export function signToken(user) {
  return jwt.sign({ sub: user.id, role: user.role }, SECRET, { expiresIn: EXPIRES_IN })
}

// Populate req.user from a Bearer token if present (does not reject).
export function attachUser(req, _res, next) {
  const header = req.headers.authorization || ''
  const token = header.startsWith('Bearer ') ? header.slice(7) : null
  if (token) {
    try {
      const payload = jwt.verify(token, SECRET)
      req.user = { id: payload.sub, role: payload.role }
    } catch {
      /* invalid/expired token → treated as anonymous */
    }
  }
  next()
}

// Reject anonymous requests.
export function requireAuth(req, res, next) {
  if (!req.user) return res.status(401).json({ error: 'مطلوب تسجيل الدخول' })
  next()
}

// Reject non-managers.
export function requireManager(req, res, next) {
  if (!req.user) return res.status(401).json({ error: 'مطلوب تسجيل الدخول' })
  if (req.user.role !== 'manager') return res.status(403).json({ error: 'صلاحيات المدير مطلوبة' })
  next()
}
