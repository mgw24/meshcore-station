#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ "${1:-}" ] && [ -f "$1" ] || { echo 'Usage: sudo ./scripts/restore.sh /path/to/backup.sql.gz'; exit 1; }
read -rp 'This will REPLACE data in the current database. Type RESTORE: ' CONFIRM
[ "$CONFIRM" = RESTORE ] || exit 1
source .env
# The API/collector must not write while restoring.
docker compose --profile radio stop collector api >/dev/null 2>&1 || true
docker compose --profile simulation stop simulator >/dev/null 2>&1 || true
docker compose up -d db
sleep 3
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
gzip -dc "$1" | docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
# Recreate read-only Grafana access after schema replacement.
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c 'GRANT USAGE ON SCHEMA public TO grafana_reader; GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;'
./scripts/start.sh
