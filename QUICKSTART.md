# MeshCore Station — deployment and upgrade

Source: https://github.com/mgw24/meshcore-station

This guide applies to the current Docker Compose repository. Historical ZIP-based upgrade instructions are preserved in Git history rather than maintained alongside the current release.

## Before updating

Use an Ubuntu VM with the existing Docker Compose installation. Preserve the VM's protected, untracked `.env`, `runtime/`, PostgreSQL and Grafana volumes. Do not force-reset or remove volumes to fix Git merge conflicts.

```bash
cd /opt/meshcore-station
git branch --show-current
git status --short
sudo ./scripts/backup.sh
```

Only fast-forward a clean local `main`. If files are modified or untracked, review and back up those changes first.

```bash
git fetch origin
git pull --ff-only origin main
bash scripts/check-release-version.sh
sudo docker compose config --quiet
```

For ordinary web-only changes, rebuild the `api` service:

```bash
sudo docker compose up -d --build --no-deps api
sudo docker compose ps
sudo docker compose logs --tail=50 api
```

Rebuild the `collector` **only** when a release explicitly changes collector behavior. Restart Grafana separately only if Grafana settings or provisioning changed. Do not use `docker compose down -v`; that removes persistent data.

## External Grafana URL

If using a dedicated Grafana reverse-proxy hostname, set `GRAFANA_PUBLIC_URL=https://grafana.example.net/` **in the VM's local `.env`**, not in GitHub, and configure that hostname in your reverse proxy to forward to Grafana. Recreate `api` and `grafana` to apply a changed URL:

```bash
sudo docker compose up -d --build --force-recreate --no-deps api grafana
```

The default application host port is `8088`, configurable through `APP_PORT`. The container listens on port `8000`. Grafana uses host port `3300` by default.

## Verify

Open the web application, check Radio Monitor, Messages, Channels, and Grafana. An online radio and successful transmit acceptance do **not** guarantee another node received a message.

Review the three retained recent release notes: [0.8.7](RELEASE-0.8.7.md), [0.8.8](RELEASE-0.8.8.md), and [0.8.9](RELEASE-0.8.9.md).

The README contains a prominent **AI Development Disclosure**. All changes should pass the protected `main` branch's automated tests before merging.
