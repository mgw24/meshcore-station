#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ -f .env ] || exit 1
source .env
OUT=${1:-/var/backups/meshcore}
mkdir -p "$OUT"
chmod 0700 "$OUT"
FILE="$OUT/meshcore-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl | gzip -9 > "$FILE"
chmod 0600 "$FILE"
echo "Backup created: $FILE"
echo 'Keep .env separately in a secure vault; this backup does not include radio private keys.'
