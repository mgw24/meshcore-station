#!/usr/bin/env bash
# Delete ONLY records positively identified as old simulation data.
set -euo pipefail
cd /opt/meshcore-station
MODE=${1:---preview}
[[ "$MODE" == --preview || "$MODE" == --apply ]] || { echo 'Usage: sudo ./scripts/remove-simulation-data.sh [--preview|--apply]'; exit 2; }
if [[ "$MODE" == --apply ]]; then
  read -rp 'Delete matched simulation data? Type REMOVE SIMULATION: ' CONFIRM
  [[ "$CONFIRM" == 'REMOVE SIMULATION' ]] || { echo 'Cancelled'; exit 1; }
  mkdir -p backups
  chmod 0700 backups
  backup="backups/pre-sim-clean-$(date -u +%Y%m%d-%H%M%S).sql"
  echo "Backing up PostgreSQL to $backup"
  docker compose exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup"
  chmod 0600 "$backup"
fi
docker compose exec -T -e CLEANUP_MODE="$MODE" api python - <<'PY'
import os
from sqlalchemy import text
from station.db import Session
mode=os.getenv('CLEANUP_MODE','--preview')
# PostgreSQL JSON (not JSONB) extraction; only definite simulation records are matched.
demo1='a1'*32
demo2='b2'*32
filters={
 'Messages': ('messages', "status = 'simulated' OR meta->>'simulated' = 'true' OR (sender='Demo Relay' AND body='Simulated incoming mesh message')"),
 'Samples': ('samples', "stats->>'simulated' = 'true'"),
 'Locations': ('node_locations', f"public_key IN ('{demo1}','{demo2}')"),
 'Contacts': ('contacts', f"(public_key='{demo1}' AND name='Demo Relay') OR (public_key='{demo2}' AND name='Demo Companion')"),
 'Radio events': ('radio_events', "detail->>'simulated' = 'true' OR (kind='connected' AND detail->>'mode'='simulation')"),
 'Commands': ('commands', "result->>'simulated' = 'true'"),
}
with Session.begin() as db:
    for label,(table,where) in filters.items():
        count=db.execute(text(f'SELECT count(*) FROM {table} WHERE {where}')).scalar_one()
        print(f'{label}: {count}')
        if mode=='--apply': db.execute(text(f'DELETE FROM {table} WHERE {where}'))
    print('Matched legacy simulation rows removed.' if mode=='--apply' else
          'Preview only; nothing changed. Use --apply after reviewing counts.')
PY
