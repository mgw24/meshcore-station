#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[[ -f .env ]] || { echo 'Missing .env; cannot proceed'; exit 1; }
# Remove only the retired simulation service from this Compose project.
mapfile -t old < <(docker ps -aq --filter 'label=com.docker.compose.project=meshcore-station' --filter 'label=com.docker.compose.service=simulator')
if (( ${#old[@]} > 0 )); then
  docker rm -f "${old[@]}"
fi
# Remove obsolete simulation/test scaffolding left by older installations.
rm -rf -- tests .pytest_cache
rm -f -- scripts/switch-to-radio.sh requirements-dev.txt .github/workflows/tests.yml
sed -i '/^SIMULATION=/d' .env
[ -n "$(grep '^RADIO_POWER_SOURCE=' .env || true)" ] || echo 'RADIO_POWER_SOURCE=usb' >> .env
chmod 0600 .env
./scripts/enable-digests.sh
docker compose config --quiet
docker compose up -d --build --remove-orphans db api collector digest grafana prometheus
docker compose ps
printf '\nLive services started. Preview legacy data: sudo ./scripts/remove-simulation-data.sh --preview\n'
