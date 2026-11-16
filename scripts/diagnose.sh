#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
. /etc/os-release
echo "OS: $PRETTY_NAME"
echo "Docker: $(docker --version)"; docker compose version
printf '\nRadio-related device nodes:\n'; ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
printf '\nPersistent serial links:\n'; ls -la /dev/serial/by-id/ 2>/dev/null || true
printf '\nUSB inventory:\n'; lsusb || true
printf '\nServices:\n'; docker compose --profile radio --profile simulation ps
printf '\nFirmware agent:\n'; systemctl --no-pager status meshcore-firmware-agent || true
printf '\nCollector logs:\n'; docker compose --profile radio logs --tail 45 collector || true
