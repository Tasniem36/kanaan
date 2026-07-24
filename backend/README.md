# دكّان كنعان — API server

Node/Express API backed by Cloud SQL (PostgreSQL). Auth is JWT-based; managers
vs. customers are enforced in middleware (`lib/auth.js`).

## Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET  | `/api/health` | public | health check |
| POST | `/api/auth/register` | public | create customer account → `{ token, user }` |
| POST | `/api/auth/login` | public | log in → `{ token, user }` |
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
