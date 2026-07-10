#!/usr/bin/env bash
# Dump the production database to a timestamped, gzipped file.
# Usage: DB_NAME=dukkan ./scripts/backup.sh   (run from the project root on the server)
# Automate daily with cron:  0 3 * * * cd /path/to/app && ./scripts/backup.sh
set -euo pipefail

mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
FILE="backups/dukkan-${STAMP}.sql.gz"

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U postgres "${DB_NAME:-dukkan}" | gzip > "$FILE"

echo "✓ Backup written to $FILE"
# keep only the 14 most recent backups
ls -1t backups/dukkan-*.sql.gz | tail -n +15 | xargs -r rm --
