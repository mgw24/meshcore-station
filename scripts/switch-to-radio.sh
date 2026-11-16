#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ -n "${1:-}" ] && [ -e "$1" ] || { echo 'Usage: sudo ./scripts/switch-to-radio.sh /dev/serial/by-id/your-device'; exit 1; }
read -rp "Switch from simulation to physical device $1? [y/N]: " ANSWER
[[ "$ANSWER" = y || "$ANSWER" = Y ]] || exit 1
sed -i 's/^SIMULATION=.*/SIMULATION=false/' .env
sed -i "s|^RADIO_DEVICE=.*|RADIO_DEVICE=$1|" .env
./scripts/start.sh
