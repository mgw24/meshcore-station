#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
DAYS=${1:-90}
[[ "$DAYS" =~ ^[0-9]{1,4}$ ]] && [ "$DAYS" -ge 7 ] || { echo 'Usage: sudo ./scripts/prune.sh 90 (minimum 7 days)'; exit 1; }
read -rp "Delete telemetry samples and non-message events older than $DAYS days? Type PRUNE: " CONFIRM
[ "$CONFIRM" = PRUNE ] || exit 1
source .env
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v days="$DAYS" <<'SQL'
DELETE FROM samples WHERE ts < now() - (:'days' || ' days')::interval;
DELETE FROM radio_events WHERE ts < now() - (:'days' || ' days')::interval;
SQL
echo 'Messages and contact inventory were not deleted.'
