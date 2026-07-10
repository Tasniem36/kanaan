import { Router } from 'express'
import { query } from '../lib/db.js'
import { requireManager } from '../lib/auth.js'

export const productsRouter = Router()

// GET /api/products — public; managers also see inactive items
productsRouter.get('/', async (req, res) => {
  const isManager = req.user?.role === 'manager'
  const { rows } = await query(
    `select id, name, description, price, unit, category, tag, image_url, stock, is_active
     from products
     ${isManager ? '' : 'where is_active = true'}
     order by created_at`
  )
  res.json({ products: rows })
})

// POST /api/products — manager only
productsRouter.post('/', requireManager, async (req, res) => {
  const { name, description, price, unit, category, tag, image_url, stock } = req.body || {}
  if (!name || price == null || !category) {
    return res.status(400).json({ error: 'الاسم والسعر والقسم مطلوبة' })
  }
  if (!['pantry', 'pottery'].includes(category)) {
    return res.status(400).json({ error: 'قسم غير صالح' })
  }
  const { rows } = await query(
    `insert into products (name, description, price, unit, category, tag, image_url, stock)
     values ($1, $2, $3, $4, $5, $6, $7, $8)
     returning *`,
    [name, description || null, price, unit || null, category, tag || null, image_url || null, Number(stock) || 0]
  )
  res.status(201).json({ product: rows[0] })
})

// PATCH /api/products/:id — manager only (partial update)
productsRouter.patch('/:id', requireManager, async (req, res) => {
  const allowed = ['name', 'description', 'price', 'unit', 'category', 'tag', 'image_url', 'stock', 'is_active']
  const fields = Object.keys(req.body || {}).filter((k) => allowed.includes(k))
  if (!fields.length) return res.status(400).json({ error: 'لا توجد حقول للتحديث' })
  const set = fields.map((f, i) => `${f} = $${i + 1}`).join(', ')
  const values = fields.map((f) => req.body[f])
  const { rows } = await query(
    `update products set ${set} where id = $${fields.length + 1} returning *`,
    [...values, req.params.id]
  )
  if (!rows[0]) return res.status(404).json({ error: 'المنتج غير موجود' })
  res.json({ product: rows[0] })
})

// DELETE /api/products/:id — manager only. Soft-delete (is_active=false) so
// existing orders keep their line items; hard-delete if it was never ordered.
productsRouter.delete('/:id', requireManager, async (req, res) => {
  const { rows } = await query('select 1 from order_items where product_id = $1 limit 1', [req.params.id])
  if (rows.length) {
    const { rowCount } = await query('update products set is_active = false where id = $1', [req.params.id])
    if (!rowCount) return res.status(404).json({ error: 'المنتج غير موجود' })
    return res.json({ removed: 'soft' })
  }
  const { rowCount } = await query('delete from products where id = $1', [req.params.id])
  if (!rowCount) return res.status(404).json({ error: 'المنتج غير موجود' })
  res.json({ removed: 'hard' })
})

// POST /api/products/:id/restock — manager only ({ qty })
productsRouter.post('/:id/restock', requireManager, async (req, res) => {
  const qty = Number(req.body?.qty)
  if (!Number.isFinite(qty) || qty <= 0) return res.status(400).json({ error: 'كمية غير صالحة' })
  const { rows } = await query(
    'update products set stock = stock + $1 where id = $2 returning *',
    [qty, req.params.id]
  )
  if (!rows[0]) return res.status(404).json({ error: 'المنتج غير موجود' })
  res.json({ product: rows[0] })
})
