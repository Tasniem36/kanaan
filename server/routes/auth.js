import { Router } from 'express'
import { query } from '../lib/db.js'
import { hashPassword, verifyPassword, signToken, requireAuth } from '../lib/auth.js'
import { EMAIL_RE, STRONG_PW_RE, normalizeUaePhone } from '../lib/validate.js'

export const authRouter = Router()

const publicUser = (u) => ({ id: u.id, email: u.email, full_name: u.full_name, phone: u.phone, role: u.role })

// POST /api/auth/register
authRouter.post('/register', async (req, res) => {
  const { email, password, full_name, phone } = req.body || {}
  if (!email || !password) return res.status(400).json({ error: 'البريد وكلمة المرور مطلوبان' })
  if (!EMAIL_RE.test(String(email))) return res.status(400).json({ error: 'بريد إلكتروني غير صالح' })
  const phoneNorm = normalizeUaePhone(phone)
  if (!phoneNorm) return res.status(400).json({ error: 'رقم هاتفٍ إماراتيٍّ غير صالح' })
  if (!STRONG_PW_RE.test(String(password))) {
    return res.status(400).json({ error: 'كلمة المرور ضعيفة: ٨ أحرفٍ على الأقل مع حرفٍ كبيرٍ وصغيرٍ ورقم' })
  }
  try {
    const hash = await hashPassword(password)
    const { rows } = await query(
      `insert into users (email, password_hash, full_name, phone)
       values ($1, $2, $3, $4)
       returning id, email, full_name, phone, role`,
      [String(email).toLowerCase().trim(), hash, full_name || null, phoneNorm]
    )
    const user = rows[0]
    res.status(201).json({ token: signToken(user), user: publicUser(user) })
  } catch (err) {
    if (err.code === '23505') return res.status(409).json({ error: 'هذا البريد مسجّلٌ مسبقًا' })
    console.error(err)
    res.status(500).json({ error: 'تعذّر إنشاء الحساب' })
  }
})

// POST /api/auth/login
authRouter.post('/login', async (req, res) => {
  const { email, password } = req.body || {}
  if (!email || !password) return res.status(400).json({ error: 'البريد وكلمة المرور مطلوبان' })
  try {
    const { rows } = await query('select * from users where email = $1', [String(email).toLowerCase().trim()])
    const user = rows[0]
    if (!user || !(await verifyPassword(password, user.password_hash))) {
      return res.status(401).json({ error: 'بيانات الدخول غير صحيحة' })
    }
    res.json({ token: signToken(user), user: publicUser(user) })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'تعذّر تسجيل الدخول' })
  }
})

// GET /api/auth/me
authRouter.get('/me', requireAuth, async (req, res) => {
  const { rows } = await query('select id, email, full_name, phone, role from users where id = $1', [req.user.id])
  if (!rows[0]) return res.status(404).json({ error: 'المستخدم غير موجود' })
  res.json({ user: rows[0] })
})
