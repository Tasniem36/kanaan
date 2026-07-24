import { Router } from 'express'
import { query } from '../lib/db.js'
import { requireAuth, requireManager } from '../lib/auth.js'

export const discountsRouter = Router()

// Evaluate a code for a given user + subtotal. `q` is query or a client.query.
// Returns { dc, percent, discount } on success, or { error } (Arabic message).
export async function evaluateCode(q, { code, userId, subtotal }) {
  if (!code) return { discount: 0 }
  const { rows } = await q('select * from discount_codes where code = $1', [String(code).toUpperCase().trim()])
  const dc = rows[0]
  if (!dc || !dc.active) return { error: 'كود الخصم غير صالح' }
  if (dc.expires_at && new Date(dc.expires_at) < new Date()) return { error: 'انتهت صلاحية كود الخصم' }
  if (dc.max_uses != null && dc.used_count >= dc.max_uses) return { error: 'انتهت مرّات استخدام هذا الكود' }
  if (dc.first_order_only) {
    const { rows: c } = await q("select count(*)::int as n from orders where user_id = $1 and status <> 'cancelled'", [userId])
    if (c[0].n > 0) return { error: 'هذا الكود صالحٌ للطلب الأوّل فقط' }
  }
  const discount = Math.round(Number(subtotal) * dc.percent) / 100
  return { dc, percent: dc.percent, discount }
}

// POST /api/discounts/validate — preview a code at checkout (auth required)
discountsRouter.post('/validate', requireAuth, async (req, res) => {
  const { code, subtotal } = req.body || {}
  const r = await evaluateCode(query, { code, userId: req.user.id, subtotal: Number(subtotal) || 0 })
  if (r.error) return res.status(400).json({ valid: false, error: r.error })
  res.json({ valid: true, percent: r.percent, discount: r.discount, code: r.dc.code })
})

// ---- admin management ----
discountsRouter.get('/', requireManager, async (_req, res) => {
  const { rows } = await query('select * from discount_codes order by created_at desc')
  res.json({ codes: rows })
})

discountsRouter.post('/', requireManager, async (req, res) => {
  const { code, percent, first_order_only, active, max_uses, expires_at } = req.body || {}
  if (!code || !percent) return res.status(400).json({ error: 'الكود والنسبة مطلوبان' })
  const p = Number(percent)
  if (!Number.isInteger(p) || p < 1 || p > 100) return res.status(400).json({ error: 'النسبة يجب أن تكون بين ١ و ١٠٠' })
  try {
    const { rows } = await query(
      `insert into discount_codes (code, percent, first_order_only, active, max_uses, expires_at)
       values ($1, $2, $3, $4, $5, $6) returning *`,
      [String(code).toUpperCase().trim(), p, first_order_only !== false, active !== false,
       max_uses ? Number(max_uses) : null, expires_at || null]
    )
    res.status(201).json({ code: rows[0] })
  } catch (err) {
    if (err.code === '23505') return res.status(409).json({ error: 'هذا الكود موجودٌ مسبقًا' })
    console.error(err)
    res.status(500).json({ error: 'تعذّر إنشاء الكود' })
  }
})

discountsRouter.patch('/:id', requireManager, async (req, res) => {
  const allowed = ['percent', 'first_order_only', 'active', 'max_uses', 'expires_at']
  const fields = Object.keys(req.body || {}).filter((k) => allowed.includes(k))
  if (!fields.length) return res.status(400).json({ error: 'لا توجد حقول للتحديث' })
  const set = fields.map((f, i) => `${f} = $${i + 1}`).join(', ')
  const values = fields.map((f) => req.body[f])
  const { rows } = await query(`update discount_codes set ${set} where id = $${fields.length + 1} returning *`, [...values, req.params.id])
  if (!rows[0]) return res.status(404).json({ error: 'الكود غير موجود' })
  res.json({ code: rows[0] })
})

discountsRouter.delete('/:id', requireManager, async (req, res) => {
  const { rowCount } = await query('delete from discount_codes where id = $1', [req.params.id])
  if (!rowCount) return res.status(404).json({ error: 'الكود غير موجود' })
  res.status(204).end()
})
