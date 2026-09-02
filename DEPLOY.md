# نشر دكّان كنعان على الإنترنت — Deploy guide

Deploys the whole store (web + API + Postgres) on one small server with HTTPS.

## 0. What you need
- A cloud server (VM) — Hetzner (cheapest, ~€4/mo), DigitalOcean, or a GCP `e2-small`.
  Pick **Ubuntu 22.04/24.04**, 1–2 GB RAM.
- A domain name (see "Domain" below).

## 1. Buy a domain
Recommended registrar: **Cloudflare** (at-cost pricing, free DNS, easy).
1. Create a Cloudflare account → **Registrar → Register Domain**.
2. Search a name (see suggestions your assistant gave) and buy the `.com` (~$10/yr).
3. Keep the tab open — you'll add a DNS record in step 4.

## 2. Create the server
1. On your provider, create an Ubuntu VM. Note its **public IP** (e.g. `203.0.113.10`).
2. In the provider's firewall, allow inbound **80** and **443** (and 22 for SSH).
3. SSH in:  `ssh root@203.0.113.10`

## 3. Install Docker on the server
```bash
curl -fsSL https://get.docker.com | sh
```

## 4. Point the domain at the server
In Cloudflare → your domain → **DNS → Add record**:
- Type `A`, Name `@`, IPv4 = your server IP, Proxy status **DNS only (grey cloud)**.
- Type `A`, Name `www`, IPv4 = your server IP, **DNS only**.

(Grey cloud matters so Caddy can issue the certificate. You can turn on the orange proxy later.)

## 5. Get the code onto the server
The repo is public, so clone it directly (no token needed):
```bash
git clone https://github.com/Tasniem36/kanaan.git app
cd app
```
(If you later make the repo private: clone with a token instead —
`git clone https://Tasniem36:YOUR_TOKEN@github.com/Tasniem36/kanaan.git app`)

## 6. Configure secrets
```bash
cp .env.prod.example .env
nano .env          # set DOMAIN, DB_PASSWORD, JWT_SECRET, SEED_MANAGER_*
```
Generate a strong JWT secret with:  `openssl rand -hex 32`

## 7. Launch 🚀
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
This builds everything, creates the database + tables, seeds the products, creates
your manager account, and Caddy fetches the HTTPS certificate automatically.

Open **https://your-domain.com** — the store is live, and
**https://your-domain.com/manager** is your dashboard (log in with the
SEED_MANAGER email/password from `.env`).

## 8. Backups (recommended)
```bash
./scripts/backup.sh                     # manual backup → backups/
crontab -e                              # then add:
# 0 3 * * * cd /root/app && ./scripts/backup.sh
```

## 8b. Housekeeping (optional)
The customer activity log grows forever. `python migrate.py` trims it on every deploy,
so this is only needed if you deploy rarely:
```bash
crontab -e                              # then add, after the backup line:
# 30 3 * * * cd /root/app && docker compose -f docker-compose.prod.yml exec -T api python maintenance.py --apply
```
Without `--apply` it only reports what it would remove, which is the safe way to check
it. It never touches any other table.
Activity is kept 90 days by default. To change it, set `AUDIT_RETENTION_DAYS` in
`.env` (minimum 7 — a typo can shorten the window, never empty the table). Note the
dashboard's "most opened products" and "where visitors come from" panels read those
same rows, so they can only look back as far as the window.

## Push to GitHub (from your Mac, one time)
1. Create a token: GitHub → Settings → Developer settings → **Fine-grained tokens**
   → Generate → repo access: only **kanaan** → Permissions: **Contents = Read and write**.
2. Push:
   ```bash
   git push https://Tasniem36:YOUR_TOKEN@github.com/Tasniem36/kanaan.git main
   git branch --set-upstream-to=origin/main main
   ```
   (After this, plain `git push` works from your Mac.)

## WhatsApp order alerts (optional, free)
Get a WhatsApp message whenever a customer places an order, using CallMeBot (free):
1. Save the CallMeBot number **+34 644 51 95 23** to your contacts.
2. From your WhatsApp, send it: **`I allow callmebot to send me messages`**
3. It replies with your **apikey**.
4. On the server, edit `.env` and set:
   ```
   WHATSAPP_PHONE=9715XXXXXXXX      # your number, international form, no + or spaces
   WHATSAPP_APIKEY=the-apikey-it-gave-you
   ```
5. Re-deploy: `docker compose -f docker-compose.prod.yml up -d --build`

Now every new order sends you a WhatsApp with the customer, items, and total.
(The in-app dashboard badge + chime work with no setup at all.)

## WhatsApp updates to the customer (optional, paid)
The section above messages **you** when an order arrives. This one messages **the
customer** when their order moves — which is the only way to reach a guest who
checked out without an e-mail address: they have no account, so no in-app
notification and no push. The phone is the one detail every order carries.

It needs Meta's WhatsApp Business Cloud API, not CallMeBot — CallMeBot can only
write to a number that has already messaged the bot.

1. In **Meta for Developers**, create an app of type *Business*, add the
   **WhatsApp** product, and connect a sender phone number. Note the
   **Phone number ID** (a number, not the phone number itself).
2. Create a **permanent access token**: Business Settings → System users → add a
   system user with the `whatsapp_business_messaging` permission, then generate a
   token that does not expire. A temporary 24-hour token works for a first test.
3. Submit two **message templates** for approval, category *Utility*. Business-initiated
   messages have to be templates. Body text, with the placeholders exactly as shown:

   `order_placed` —
   ```
   شكرًا لك! استلمنا طلبك {{1}}. الإجمالي {{2}} درهم.
   تابع حالة طلبك من هنا: {{3}}
   ```
   `order_status` —
   ```
   طلبك {{1}}: {{2}}
   تابع التفاصيل من هنا: {{3}}
   ```
   Approval usually takes minutes. Keep the placeholder order — the server fills
   {{1}} with the order number, {{2}} with the total or the new status, {{3}} with
   the tracking link.
4. On the server, edit `.env`:
   ```
   WA_CLOUD_TOKEN=your-permanent-access-token
   WA_CLOUD_PHONE_ID=your-phone-number-id
   # optional:
   # WA_TEMPLATE_PLACED=order_placed   # if you named the templates differently
   # WA_TEMPLATE_STATUS=order_status
   # WA_TEMPLATE_LANG=ar
   # WA_NOTIFY_ALL=true                # message account holders too (see below)
   ```
5. Re-deploy: `docker compose -f docker-compose.prod.yml up -d --build`

By default only customers with **no other channel** are messaged — a guest with no
e-mail. Account holders already get the in-app notification and the device push, and
every template message is billed, so they're left alone unless you set
`WA_NOTIFY_ALL=true`.

Leave `WA_CLOUD_TOKEN` unset and nothing is sent — the shop takes orders exactly as
before. Sends happen in the background and never delay an order or a status change;
failures are logged (`[whatsapp] send failed: …`) and affect nothing else. While your
app is in test mode, Meta only delivers to numbers you've added to its allowed list.

## Online payments with Ziina (optional)
Lets customers pay by card / Apple Pay / Google Pay at checkout (alongside cash on delivery).
1. In your **Ziina Business** dashboard, create an **API key** (with payment-intent write access).
2. On the server, edit `.env`:
   ```
   ZIINA_API_KEY=your-ziina-api-key
   ZIINA_TEST=true      # true = test mode (no real charges); set false to go live
   ```
   (`APP_URL` is set automatically from your DOMAIN in docker-compose.)
3. Re-deploy: `docker compose -f docker-compose.prod.yml up -d --build`

Checkout then offers "Pay now with Ziina" and "Cash on delivery". Ziina orders are
marked **paid** only after the payment is confirmed, and the WhatsApp alert is sent then.
Test with `ZIINA_TEST=true` first, then flip to `false` for real payments.

## Updating later
```bash
# on your Mac: commit + push changes
git add -A && git commit -m "update" && git push
# on the server:
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

## Troubleshooting
- **Cert not issued:** ensure the DNS A record points to the server and ports 80/443 are open; check `docker compose -f docker-compose.prod.yml logs caddy`.
- **See what's running:** `docker compose -f docker-compose.prod.yml ps`
- **API logs:** `docker compose -f docker-compose.prod.yml logs api`
