# دكّان كنعان — API server

Node/Express API backed by Cloud SQL (PostgreSQL). Auth is JWT-based; managers
vs. customers are enforced in middleware (`lib/auth.js`).

## Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET  | `/api/health` | public | health check |
| POST | `/api/auth/register` | public | create customer account → `{ token, user }` |
| POST | `/api/auth/login` | public | log in → `{ token, user }` |
| POST | `/api/auth/password/forgot` | public | e-mail a reset code → `{ sent: true }`, the same answer whether or not the address has an account |
| POST | `/api/auth/password/reset` | public | spend the code on a new password → `{ token, user }` |
| GET  | `/api/auth/me` | auth | current user |
| GET  | `/api/products` | public | list products (managers see inactive too) |
| POST | `/api/products` | manager | create product |
| PATCH| `/api/products/:id` | manager | update product |
| POST | `/api/products/:id/restock` | manager | add stock `{ qty }` |
| POST | `/api/orders` | public/auth | place order (validates stock + prices, decrements stock) |
| GET  | `/api/orders` | auth | manager → all; customer → own |
| PATCH| `/api/orders/:id/status` | manager | update order status |

## One-time GCP setup

1. **Create a GCP project** and make sure **billing is enabled** (required even
   for the free trial credit).
2. **Enable APIs**: Cloud SQL Admin API, and (for deploy later) Cloud Run.
3. **Create the Cloud SQL instance** — PostgreSQL, cheapest tier
   (Enterprise · Sandbox, shared-core). Set a password for the `postgres` user
   and pick a nearby region. Note the **Instance connection name**
   (`project:region:instance`).
4. **Create a database** named `dukkan` on that instance.

## Connect locally (via Cloud SQL Auth Proxy)

```bash
# download the proxy once (macOS arm64 shown; see Google docs for other OS)
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.1/cloud-sql-proxy.darwin.arm64
chmod +x cloud-sql-proxy

# run it (keep this terminal open) — exposes the DB on 127.0.0.1:5432
./cloud-sql-proxy PROJECT:REGION:INSTANCE
```

Then:

```bash
cd server
cp .env.example .env      # fill DB_PASSWORD, DB_NAME=dukkan, JWT_SECRET
npm install
npm run migrate           # creates tables + seeds the 8 products
npm run dev               # API on http://localhost:8080
```

## Make yourself a manager

Register through the app (Phase 2), then once:

```sql
update users set role = 'manager' where email = 'you@example.com';
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                    # 131 tests, no database needed
```

The default run patches the database out, so it's fast and works offline. It
covers request handling, access control, the image pipeline, and the SQL each
endpoint *builds* (filters, the sort whitelist, parameterisation).

A second tier exercises the SQL for real — window-function counts, the CTEs,
stock restores, and the dashboard's revenue arithmetic. It's skipped unless you
point it at a PostgreSQL server:

```bash
TEST_PG_DSN=postgresql://postgres@127.0.0.1:5432/postgres pytest   # 152 tests
```

It creates a scratch database called `dukkan_pytest`, applies `db/schema.sql`
(twice, to prove migrations stay idempotent), and drops it afterwards — so point
it at a local/throwaway server, never at production.

## Verification email landing in spam

The code sends over plain SMTP, so whether a message reaches the inbox is decided
by *authentication*, not by the app. In order of impact:

1. **`SMTP_FROM` must match `SMTP_USER`.** A From on another domain (e.g.
   `noreply@dukkan-kanaan.com` while authenticating as a `gmail.com` account)
   fails SPF/DKIM alignment at the receiver, and the mail is treated as forged.
   Leave `SMTP_FROM` empty to use the authenticated address. The API logs a loud
   warning when the two don't match — the failure is otherwise entirely silent.

2. **A free Gmail account is not a sending domain.** Mail from `@gmail.com` for a
   shop at `dukkan-kanaan.com` is a mismatch recipients' filters notice, and Gmail
   rate-limits and reputation-scores personal accounts sending automated mail.
   This is a ceiling no code change lifts.

   The durable fix is a transactional provider (Resend, Brevo, Mailgun, SendGrid —
   all have free tiers well above this shop's volume) authenticated for
   `dukkan-kanaan.com`: publish their SPF and DKIM records, add a DMARC record,
   then point `SMTP_HOST/USER/PASS` at them. Nothing else in the code changes.

3. **Check what receivers actually see.** In Gmail, open the message → ⋮ →
   *Show original*: `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS` are what matter.
   Any `FAIL`/`NONE` explains the spam filing precisely.

Optional environment variables: `SMTP_FROM_NAME` (sender display name, defaults to
دكّان كنعان) and `SMTP_REPLY_TO` (defaults to the From address).
