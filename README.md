# MeshCore Station 0.8.3

**Self-hosted MeshCore Companion console** for the Heltec T114 V2, Ubuntu Server 24.04 LTS Minimal, Docker Compose and VMware ESXi USB passthrough.

**Current version: `0.8.3`** · [Release notes](RELEASE-0.8.3.md) · [GitHub source](https://github.com/mgw24/meshcore-station)

This is a community-built project, **not an official MeshCore release**. It is intended for a privately reachable web interface (for example, your existing VPN). There is no Tailscale dependency.

## Features

- **Messaging:** compact composer above a full-width, dense single-line message history. Click or tap a row to view the full message, metadata and TX evidence. Contextual `@ Reply` now extracts the channel sender name from the MeshCore `Name: message` envelope, prefilling an `@Name ` mention; uniquely identified direct replies are retained; search, filters, pagination and CSV export are retained.
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

## Updating an existing 0.8.2 station to 0.8.3

This is a focused Messages page hotfix. It corrects missing channel `@username` mentions when the sender name appears inside the received MeshCore text envelope (for example, `HamHock: Hello`). It also handles Channel 0 when represented as the number `0`.

1. From Ubuntu, back up PostgreSQL: `cd /opt/meshcore-station && sudo ./scripts/backup.sh`.
2. Transfer `meshcore-station-0.8.3-upgrade.zip` from a **computer** to `/tmp/meshcore-station-0.8.3-upgrade.zip` on the VM.
3. Extract and run the installer:

   ```bash
   sudo mkdir -p /tmp/meshcore-083
   sudo unzip -oq /tmp/meshcore-station-0.8.3-upgrade.zip -d /tmp/meshcore-083
   sudo bash /tmp/meshcore-083/install.sh
   ```

4. Verify `sudo docker compose ps api`, refresh the Messages page, and click **@ Reply** on a received Public message whose content starts with `Sender: text`.
5. After verification, publish from your normal Git working tree with `bash scripts/publish-0.8.3.sh` (without `sudo`). The publisher refuses non-fast-forward pushes and checks version consistency.

The upgrade backs up replaced source files and rebuilds **only the API container**. It never changes radio settings, firmware, message history, channel keys, Grafana or digest service configuration. Do not run `docker compose down -v` for this update.

**Reply behavior:** `@Name` is ordinary channel text, not a guaranteed notification. Direct replies continue to require a uniquely identified MeshCore contact. When no sender name can be identified, the app leaves the draft unchanged instead of inventing one.

## Version policy

- `VERSION`, README, API `/api/version`, web footer and the current release notes must agree.
- Git tags use `vMAJOR.MINOR.PATCH`, for example `v0.8.3`.
- `scripts/check-release-version.sh` validates the release metadata before the publishing script commits or tags.
- Published code is the source of truth; configuration secrets and database contents are never committed.

## Radio and delivery caveats

The Public channel is not acknowledged individually. A message labeled **Radio accepted · delivery unconfirmed** has been submitted to the T114, but that does not demonstrate that a repeater heard it or that another user read it. A matching channel echo is evidence of a repeated copy, not a delivery receipt. Direct-message ACKs are reported only when positively matched.

Packet counters include non-chat traffic, and counter resets must be accounted for. A saved contact's refresh timestamp does not necessarily establish a new RF sighting. Geographical map coordinates are shown only when advertised or explicitly entered, not guessed from RSSI.

## Documentation and operations

- [Quick start](QUICKSTART.md)
- [0.8.3 reply fix](RELEASE-0.8.3.md)
- [0.8.2 compact messages](RELEASE-0.8.2.md)
- [0.8.1 message archive release](RELEASE-0.8.1.md)
- [0.8.0 radio diagnostics](RELEASE-0.8.0.md)
- [Grafana notes](GRAFANA-REFRESH-NOTES.md)
- [Historical v7, v6, v5, v4 notes](V7-RELEASE-NOTES.md)

Store `.env` and radio settings securely. Back up PostgreSQL and the firmware agent's private files independently of GitHub. Inspect the `scripts/` directory before running administrative or firmware operations.
