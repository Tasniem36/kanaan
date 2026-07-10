import { Router } from 'express'
import { query } from '../lib/db.js'
import { requireManager } from '../lib/auth.js'

export const usersRouter = Router()

// GET /api/users/clients — manager view of all customers with order stats
usersRouter.get('/clients', requireManager, async (_req, res) => {
  const { rows } = await query(
    `select u.id, u.full_name, u.email, u.phone, u.created_at,
            count(o.id)::int                       as orders_count,
            coalesce(sum(o.total), 0)::numeric     as total_spent,
            max(o.created_at)                       as last_order_at
     from users u
     left join orders o on o.user_id = u.id
     where u.role = 'customer'
     group by u.id
     order by last_order_at desc nulls last, u.created_at desc`
  )
  res.json({ clients: rows })
})
