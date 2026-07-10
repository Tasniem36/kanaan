import express from 'express'
import cors from 'cors'
import 'dotenv/config'

import { attachUser } from './lib/auth.js'
import { authRouter } from './routes/auth.js'
import { productsRouter } from './routes/products.js'
import { ordersRouter } from './routes/orders.js'
import { addressesRouter } from './routes/addresses.js'
import { usersRouter } from './routes/users.js'

const app = express()

app.use(cors({ origin: process.env.CORS_ORIGIN?.split(',') || true }))
app.use(express.json({ limit: '6mb' })) // headroom for uploaded (base64) product images
app.use(attachUser) // populates req.user when a valid Bearer token is present

app.get('/api/health', (_req, res) => res.json({ ok: true }))
app.use('/api/auth', authRouter)
app.use('/api/products', productsRouter)
app.use('/api/orders', ordersRouter)
app.use('/api/addresses', addressesRouter)
app.use('/api/users', usersRouter)

app.use((_req, res) => res.status(404).json({ error: 'المسار غير موجود' }))

const port = Number(process.env.PORT || 8080)
app.listen(port, () => console.log(`API listening on :${port}`))
