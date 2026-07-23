import { Router } from 'express'
import { query, withTransaction } from '../lib/db.js'
import { requireAuth, requireManager } from '../lib/auth.js'
import { normalizeUaePhone } from '../lib/validate.js'
import { notifyNewOrder } from '../lib/notify.js'
import { createPaymentIntent, getPaymentIntent } from '../lib/ziina.js'

export const ordersRouter = Router()

// restore stock + cancel an order (used if a payment can't be started)
async function cancelAndRestore(orderId) {
  await withTransaction(async (c) => {
    const { rows: its } = await c.query('select product_id, qty from order_items where order_id = $1', [orderId])
    for (const it of its) {
      if (it.product_id) await c.query('update products set stock = stock + $1 where id = $2', [it.qty, it.product_id])
    }
    await c.query("update orders set status = 'cancelled' where id = $1", [orderId])
  })
}

// POST /api/orders — customer or guest. Body:
//   { customer_name, phone, city, street, house, notes, items: [{ product_id, qty }] }
// Prices/stock are validated server-side against the DB (never trust the client).
// Requires login so every order is tied to a customer account (and trackable).
ordersRouter.post('/', requireAuth, async (req, res) => {
  const { customer_name, phone, city, street, house, notes, items } = req.body || {}
  const paymentMethod = req.body?.payment_method === 'ziina' ? 'ziina' : 'cod'
  if (!customer_name || !phone || !city || !street || !house) {
    return res.status(400).json({ error: 'فضلًا أكمل الحقول المطلوبة' })
  }
  const phoneNorm = normalizeUaePhone(phone)
  if (!phoneNorm) return res.status(400).json({ error: 'رقم هاتفٍ إماراتيٍّ غير صالح' })
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
        `insert into orders (user_id, customer_name, phone, city, street, house, notes, total, payment_method)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         returning *`,
        [req.user?.id || null, customer_name, phoneNorm, city, street, house, notes || null, total, paymentMethod]
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

    // Ziina: create a payment intent and hand the redirect URL back to the client.
    if (order.payment_method === 'ziina') {
      const appUrl = process.env.APP_URL || req.headers.origin || ''
      try {
        const intent = await createPaymentIntent({
          amountFils: Math.round(Number(order.total) * 100),
          successUrl: `${appUrl}/pay/return?order=${order.id}`,
          cancelUrl: `${appUrl}/pay/return?order=${order.id}&cancel=1`,
          message: `دكّان كنعان — طلب #${String(order.id).slice(0, 8)}`,
        })
        await query('update orders set ziina_payment_id = $1 where id = $2', [intent.id, order.id])
        return res.status(201).json({ order, redirect_url: intent.redirect_url })
      } catch (e) {
        await cancelAndRestore(order.id).catch(() => {})
        return res.status(e.status || 502).json({ error: e.message || 'تعذّر بدء الدفع عبر Ziina' })
      }
    }

    notifyNewOrder(order) // COD: alert the manager now (Ziina alerts once paid)
    res.status(201).json({ order })
  } catch (err) {
    if (err.status) return res.status(err.status).json({ error: err.message })
    console.error(err)
    res.status(500).json({ error: 'تعذّر إنشاء الطلب' })
  }
})

// POST /api/orders/:id/confirm-payment — verify a Ziina payment, mark paid, alert
ordersRouter.post('/:id/confirm-payment', async (req, res) => {
  try {
    const { rows } = await query('select * from orders where id = $1', [req.params.id])
    const order = rows[0]
    if (!order) return res.status(404).json({ error: 'الطلب غير موجود' })
    if (order.payment_status === 'paid') return res.json({ paid: true, status: order.status })
    if (order.payment_method !== 'ziina' || !order.ziina_payment_id) {
      return res.json({ paid: false, status: order.status })
    }
    const intent = await getPaymentIntent(order.ziina_payment_id)
    if (intent.status === 'completed') {
      const { rows: upd } = await query(
        "update orders set payment_status = 'paid', status = 'paid' where id = $1 returning *",
        [order.id]
      )
      const { rows: its } = await query('select name, price, qty from order_items where order_id = $1', [order.id])
      notifyNewOrder({ ...upd[0], items: its })
      return res.json({ paid: true, status: 'paid' })
    }
    return res.json({ paid: false, status: intent.status })
  } catch (e) {
    if (e.status) return res.status(e.status).json({ error: e.message })
    console.error(e)
    res.status(500).json({ error: 'تعذّر التحقق من الدفع' })
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
