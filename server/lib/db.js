import pg from 'pg'
import 'dotenv/config'

const { Pool } = pg

// Two connection modes:
//  • Local dev  → Cloud SQL Auth Proxy exposes the DB on 127.0.0.1:5432
//                 (set DB_HOST=127.0.0.1). Or any host/port you point at.
//  • Cloud Run  → connect over the Unix socket Google mounts at
//                 /cloudsql/<INSTANCE_CONNECTION_NAME> (set that env var,
//                 leave DB_HOST unset).
const useSocket = !!process.env.INSTANCE_CONNECTION_NAME && !process.env.DB_HOST

export const pool = new Pool(
  useSocket
    ? {
        host: `/cloudsql/${process.env.INSTANCE_CONNECTION_NAME}`,
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME,
      }
    : {
        host: process.env.DB_HOST || '127.0.0.1',
        port: Number(process.env.DB_PORT || 5432),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME,
        ssl: process.env.DB_SSL === 'true' ? { rejectUnauthorized: false } : undefined,
      }
)

export const query = (text, params) => pool.query(text, params)

// Run fn inside a transaction, auto commit/rollback.
export async function withTransaction(fn) {
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    const result = await fn(client)
    await client.query('COMMIT')
    return result
  } catch (err) {
    await client.query('ROLLBACK')
    throw err
  } finally {
    client.release()
  }
}
