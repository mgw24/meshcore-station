#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ -f .env ] || { echo 'Missing .env; run install.sh'; exit 1; }
SIMULATION=$(grep '^SIMULATION=' .env | cut -d= -f2)
if [ "$SIMULATION" = true ]; then
  docker compose --profile radio stop collector >/dev/null 2>&1 || true
  docker compose --profile simulation up -d --build db api simulator grafana prometheus
else
  docker compose --profile simulation stop simulator >/dev/null 2>&1 || true
  docker compose --profile radio up -d --build db api collector grafana prometheus
fi
docker compose ps
