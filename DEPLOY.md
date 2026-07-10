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
```bash
# option A: git
git clone <your-repo-url> app && cd app
# option B: from your Mac, copy the folder up
# scp -r dukkan-kanaan-vue root@SERVER_IP:/root/app   (then: cd /root/app)
```

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

## Updating later
```bash
git pull                                 # or re-copy the files
docker compose -f docker-compose.prod.yml up -d --build
```

## Troubleshooting
- **Cert not issued:** ensure the DNS A record points to the server and ports 80/443 are open; check `docker compose -f docker-compose.prod.yml logs caddy`.
- **See what's running:** `docker compose -f docker-compose.prod.yml ps`
- **API logs:** `docker compose -f docker-compose.prod.yml logs api`
