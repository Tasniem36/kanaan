import { Router } from 'express'
import { query, withTransaction } from '../lib/db.js'
import { requireAuth, requireManager } from '../lib/auth.js'

export const ordersRouter = Router()

// POST /api/orders — customer or guest. Body:
//   { customer_name, phone, city, street, house, notes, items: [{ product_id, qty }] }
// Prices/stock are validated server-side against the DB (never trust the client).
ordersRouter.post('/', async (req, res) => {
  const { customer_name, phone, city, street, house, notes, items } = req.body || {}
  if (!customer_name || !phone || !city || !street || !house) {
    return res.status(400).json({ error: 'فضلًا أكمل الحقول المطلوبة' })
  }
  if (!Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: 'السلّة فارغة' })
  }

  try {
    const order = await withTransaction(async (client) => {
      // Lock the ordered products and validate stock.
      const ids = items.map((i) => i.product_id)
      const { rows: products } = await client.query(
        'select id, name, price, stock from products where id = any($1::uuid[]) for update',
        [ids]
      )
      const byId = new Map(products.map((p) => [p.id, p]))

      let total = 0
      const lines = []
      for (const item of items) {
        const p = byId.get(item.product_id)
        const qty = Number(item.qty)
        if (!p) throw { status: 400, message: 'منتجٌ غير موجود' }
        if (!Number.isInteger(qty) || qty <= 0) throw { status: 400, message: 'كمية غير صالحة' }
        if (p.stock < qty) throw { status: 409, message: `الكمية المتوفّرة من «${p.name}» غير كافية` }
        total += Number(p.price) * qty
        lines.push({ product_id: p.id, name: p.name, price: p.price, qty })
      }

      const { rows: orderRows } = await client.query(
        `insert into orders (user_id, customer_name, phone, city, street, house, notes, total)
         values ($1, $2, $3, $4, $5, $6, $7, $8)
         returning *`,
        [req.user?.id || null, customer_name, phone, city, street, house, notes || null, total]
      )
      const newOrder = orderRows[0]

      for (const line of lines) {
        await client.query(
          'insert into order_items (order_id, product_id, name, price, qty) values ($1, $2, $3, $4, $5)',
          [newOrder.id, line.product_id, line.name, line.price, line.qty]
        )
        await client.query('update products set stock = stock - $1 where id = $2', [line.qty, line.product_id])
      }

      newOrder.items = lines
      return newOrder
    })

    res.status(201).json({ order })
  } catch (err) {
    if (err.status) return res.status(err.status).json({ error: err.message })
    console.error(err)
    res.status(500).json({ error: 'تعذّر إنشاء الطلب' })
  }
})

// GET /api/orders — manager: all orders; customer: own orders. Includes items.
ordersRouter.get('/', requireAuth, async (req, res) => {
  const isManager = req.user.role === 'manager'
  const { rows: orders } = await query(
    `select * from orders ${isManager ? '' : 'where user_id = $1'} order by created_at desc`,
    isManager ? [] : [req.user.id]
  )
  if (orders.length) {
    const { rows: items } = await query(
      'select order_id, name, price, qty from order_items where order_id = any($1::uuid[])',
      [orders.map((o) => o.id)]
    )
    const byOrder = new Map()
    for (const it of items) {
      if (!byOrder.has(it.order_id)) byOrder.set(it.order_id, [])
      byOrder.get(it.order_id).push(it)
    }
    orders.forEach((o) => (o.items = byOrder.get(o.id) || []))
  }
  res.json({ orders })
})

// PATCH /api/orders/:id/status — manager only
ordersRouter.patch('/:id/status', requireManager, async (req, res) => {
  const { status } = req.body || {}
  if (!['pending', 'paid', 'fulfilled', 'cancelled'].includes(status)) {
    return res.status(400).json({ error: 'حالة غير صالحة' })
  }
  const { rows } = await query('update orders set status = $1 where id = $2 returning *', [status, req.params.id])
  if (!rows[0]) return res.status(404).json({ error: 'الطلب غير موجود' })
  res.json({ order: rows[0] })
})
