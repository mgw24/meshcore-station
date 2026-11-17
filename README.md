# MeshCore Station 0.8.1

**Self-hosted MeshCore Companion console** for the Heltec T114 V2, Ubuntu Server 24.04 LTS Minimal, Docker Compose and VMware ESXi USB passthrough.

**Current version: `0.8.1`** · [Release notes](RELEASE-0.8.1.md) · [GitHub source](https://github.com/mgw24/meshcore-station)

This is a community-built project, **not an official MeshCore release**. It is intended for a privately reachable web interface (for example, your existing VPN). There is no Tailscale dependency.

## Features

- **Messaging:** compact send form above a full-width message history, searchable by sender/text/destination, filterable by direction/channel, with timestamp-based pagination, expandable transmission evidence and CSV export.
- **Radio diagnostics:** serial connection state, traffic deltas, receiver errors, RSSI, noise floor, uptime, and conservative TX confirmation tracking (radio accepted, channel echo, direct ACK where available).
- **Routing and regions:** 1-, 2-, or 3-byte path-hash controls and Companion outgoing flood scopes, with warnings and verification. Region scope is distinct from radio frequency and repeater-side permissions.
- **Contacts:** discovered nodes, repeater/client/room-server/sensor icons, address book with notes and favorites, contact synchronization status, and a map with manually assigned or advertised coordinates.
- **Channels:** read and manage channel slots 0–7 while protecting shared keys.
- **Monitoring:** PostgreSQL history, Prometheus, and a redesigned Grafana operations dashboard.
- **Optional email digests:** SMTP configuration, recipients, schedules, preview, test mail, and delivery history.
- **Firmware management:** host-side flashing agent and web-controlled update jobs, subject to ESXi USB re-enumeration behavior.

## System architecture

One Docker collector owns the T114 serial device (`/dev/meshcore` inside the container) and stores decoded events in PostgreSQL. The web API uses the database and a command queue; it **never opens a second serial connection**. The digest service and Grafana read stored data without accessing the radio. The separate host flashing agent handles firmware updates.

The T114 runs MeshCore **USB Companion**, not Repeater firmware. A separate repeater is required to forward other mesh users' packets.

## Updating an existing 0.8.0 station to 0.8.1

1. From the Ubuntu VM, back up the database: `cd /opt/meshcore-station && sudo ./scripts/backup.sh`.
2. Transfer the release ZIP from a **computer** to `/tmp/meshcore-station-0.8.1-upgrade.zip` on the VM.
3. Extract and run the installer:

   ```bash
   sudo mkdir -p /tmp/meshcore-081
   sudo unzip -oq /tmp/meshcore-station-0.8.1-upgrade.zip -d /tmp/meshcore-081
   sudo bash /tmp/meshcore-081/install.sh
   ```

4. Check `sudo docker compose ps api`, `sudo docker compose logs --tail=40 api`, and open **Messages**. The collector, radio, Grafana and digest do **not** need a restart.
5. Once verified, publish from your Git working tree using `bash scripts/publish-0.8.1.sh` (regular user, **no sudo**). The script refuses a non-fast-forward push, so it cannot overwrite later GitHub commits.

The upgrade backs up source files under `/var/backups/meshcore` and does not remove `.env`, `runtime/`, Docker volumes or database records. Never run `docker compose down -v` during an upgrade.

## Version policy

- `VERSION`, README, API `/api/version`, web footer and the current release notes must agree.
- Git tags use `vMAJOR.MINOR.PATCH`, for example `v0.8.1`.
- `scripts/check-release-version.sh` validates the release metadata before the publishing script commits or tags.
- Published code is the source of truth; configuration secrets and database contents are never committed.

## Radio and delivery caveats

The Public channel is not acknowledged individually. A message labeled **Radio accepted · delivery unconfirmed** has been submitted to the T114, but that does not demonstrate that a repeater heard it or that another user read it. A matching channel echo is evidence of a repeated copy, not a delivery receipt. Direct-message ACKs are reported only when positively matched.

Packet counters include non-chat traffic, and counter resets must be accounted for. A saved contact's refresh timestamp does not necessarily establish a new RF sighting. Geographical map coordinates are shown only when advertised or explicitly entered, not guessed from RSSI.

## Documentation and operations

- [Quick start](QUICKSTART.md)
- [0.8.1 release details](RELEASE-0.8.1.md)
- [0.8.0 radio diagnostics](RELEASE-0.8.0.md)
- [Grafana notes](GRAFANA-REFRESH-NOTES.md)
- [Historical v7, v6, v5, v4 notes](V7-RELEASE-NOTES.md)

Store `.env` and radio settings securely. Back up PostgreSQL and the firmware agent's private files independently of GitHub. Inspect the `scripts/` directory before running administrative or firmware operations.
