#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ -f .env ] || { echo 'Missing .env; run install.sh'; exit 1; }
./scripts/enable-digests.sh
docker compose up -d --build db api collector digest grafana prometheus
docker compose ps
