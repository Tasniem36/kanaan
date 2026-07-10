// Applies schema.sql then seed.sql, and optionally bootstraps a manager
// account from SEED_MANAGER_EMAIL / SEED_MANAGER_PASSWORD. Run: npm run migrate
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import bcrypt from 'bcryptjs'
import { pool } from '../lib/db.js'

const here = dirname(fileURLToPath(import.meta.url))

async function run(file) {
  const sql = await readFile(join(here, file), 'utf8')
  await pool.query(sql)
  console.log(`✓ applied ${file}`)
}

async function seedManager() {
  const email = process.env.SEED_MANAGER_EMAIL
  const password = process.env.SEED_MANAGER_PASSWORD
  if (!email || !password) return
  const hash = await bcrypt.hash(password, 10)
  // create as manager, or promote+reset an existing account
  await pool.query(
    `insert into users (email, password_hash, full_name, role)
     values ($1, $2, 'المدير', 'manager')
     on conflict (email) do update set role = 'manager', password_hash = excluded.password_hash`,
    [email.toLowerCase().trim(), hash]
  )
  console.log(`✓ manager account ready: ${email}`)
}

try {
  await run('schema.sql')
  await run('seed.sql')
  await seedManager()
  console.log('Migration complete.')
} catch (err) {
  console.error('Migration failed:', err.message)
  process.exitCode = 1
} finally {
  await pool.end()
}
