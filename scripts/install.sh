#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo 'Run: sudo ./scripts/install.sh'; exit 1; fi
. /etc/os-release
if [ "$ID" != ubuntu ] || [ "$VERSION_ID" != '24.04' ]; then
  echo "This installer targets Ubuntu Server 24.04 LTS; detected $PRETTY_NAME"; exit 1
fi
if [ "$(pwd -P)" != /opt/meshcore-station ]; then
  echo 'Clone or copy the repository to /opt/meshcore-station first.'; exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg git jq usbutils udev python3 python3-venv python3-pip unzip zip picocom
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<REPO
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
REPO
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  docker compose version >/dev/null || { echo 'Docker Compose plugin is required'; exit 1; }
fi
systemctl enable --now docker
mkdir -p /opt/meshcore-flasher-venv
if [ ! -x /opt/meshcore-flasher-venv/bin/python ]; then
  rm -rf /opt/meshcore-flasher-venv
  python3 -m venv /opt/meshcore-flasher-venv
fi
/opt/meshcore-flasher-venv/bin/pip install --upgrade pip wheel
/opt/meshcore-flasher-venv/bin/pip install adafruit-nrfutil
for p in jobs packages states logs; do mkdir -p "/opt/meshcore-station/runtime/spool/$p"; done
chown -R 10001:10001 /opt/meshcore-station/runtime/spool
chmod 0750 /opt/meshcore-station/runtime/spool /opt/meshcore-station/runtime/spool/*
[ -f .env ] || ./scripts/configure.sh
chmod 0600 .env
./scripts/enable-digests.sh
install -m 0644 firmware-agent/meshcore-firmware-agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now meshcore-firmware-agent
printf '\nInstalled host dependencies. Next: sudo ./scripts/start.sh\n'
