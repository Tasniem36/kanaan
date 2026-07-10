import { Router } from 'express'
import { query, withTransaction } from '../lib/db.js'
import { requireAuth } from '../lib/auth.js'

export const addressesRouter = Router()
addressesRouter.use(requireAuth) // all address routes require a logged-in user

// GET /api/addresses — the current user's saved delivery locations
addressesRouter.get('/', async (req, res) => {
  const { rows } = await query(
    'select * from addresses where user_id = $1 order by is_default desc, created_at',
    [req.user.id]
  )
  res.json({ addresses: rows })
})

// POST /api/addresses — add a delivery location
addressesRouter.post('/', async (req, res) => {
  const { label, city, street, house, notes, is_default } = req.body || {}
  if (!city || !street || !house) return res.status(400).json({ error: 'المدينة والشارع ورقم المنزل مطلوبة' })
  const address = await withTransaction(async (client) => {
    if (is_default) {
      await client.query('update addresses set is_default = false where user_id = $1', [req.user.id])
    }
    const { rows } = await client.query(
      `insert into addresses (user_id, label, city, street, house, notes, is_default)
       values ($1, $2, $3, $4, $5, $6, $7) returning *`,
      [req.user.id, label || null, city, street, house, notes || null, !!is_default]
    )
    return rows[0]
  })
  res.status(201).json({ address })
})

// PATCH /api/addresses/:id — edit one of the user's addresses
addressesRouter.patch('/:id', async (req, res) => {
  const allowed = ['label', 'city', 'street', 'house', 'notes', 'is_default']
  const fields = Object.keys(req.body || {}).filter((k) => allowed.includes(k))
  if (!fields.length) return res.status(400).json({ error: 'لا توجد حقول للتحديث' })
  const address = await withTransaction(async (client) => {
    if (req.body.is_default) {
      await client.query('update addresses set is_default = false where user_id = $1', [req.user.id])
    }
    const set = fields.map((f, i) => `${f} = $${i + 1}`).join(', ')
    const values = fields.map((f) => req.body[f])
    const { rows } = await client.query(
      `update addresses set ${set} where id = $${fields.length + 1} and user_id = $${fields.length + 2} returning *`,
      [...values, req.params.id, req.user.id]
    )
    return rows[0]
  })
  if (!address) return res.status(404).json({ error: 'العنوان غير موجود' })
  res.json({ address })
})

// DELETE /api/addresses/:id
addressesRouter.delete('/:id', async (req, res) => {
  const { rowCount } = await query('delete from addresses where id = $1 and user_id = $2', [req.params.id, req.user.id])
  if (!rowCount) return res.status(404).json({ error: 'العنوان غير موجود' })
  res.status(204).end()
})
