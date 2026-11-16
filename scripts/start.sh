#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ -f .env ] || { echo 'Missing .env; run install.sh'; exit 1; }
docker compose up -d --build db api collector grafana prometheus
docker compose ps
