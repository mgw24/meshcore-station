# MeshCore Station — Production Edition v3

GitHub source: **https://github.com/mgw24/meshcore-station**

Self-hosted **Heltec T114 V2 USB Companion** console for **Ubuntu Server 24.04 LTS Minimal on VMware vSphere / ESXi**. The T114 is permanently attached to the ESXi host with USB passthrough. Access is provided over the existing VPN; no Tailscale component is included.

## What's included

- Browser-based two-way channel and direct messaging, message history and CSV export.
- **Radio Health** page: confirmed RX/TX counters, errors, flood/direct RX, uptime, RSSI, noise, sample age and historical graphs. Raw RF packet counts are **not** synonymous with chat messages.
- New **Channel Management** page: read slots 0–7, edit channel names while retaining existing keys, assign a **16-byte key encoded as 32 hex characters**, delete channels with typed confirmation. Secrets never appear in UI responses or logs, are encrypted while queued in PostgreSQL and scrubbed from completed/failed command records.
- **Node/Repeater Map** with native browser renderer, pan/zoom, OpenStreetMap raster tiles, mobile and Firefox handling, a coordinate grid fallback and manual position overrides. Only advertised or user-entered coordinates are plotted; no made-up locations from RSSI.
- Node inventory counts based on T114 *contacts*, with recent contact-sync summary. RX packets may be repeats or adverts, and do not automatically create contacts. “Last seen” on older data may be time of contact-list sync, not an RF sighting.
- Grafana + Prometheus: live radio packet counters, receive errors, uptime, telemetry freshness, radio noise, RSSI, and contacts. PostgreSQL retains historical radio measurements.
- Optional SMTP collector-down alerts, USB-only power status (no battery installed), firmware update page backed by the existing host agent.
- No simulator container or simulation/test fixtures in the production package.

**Important:** This is a community-built reference implementation, not an official MeshCore product. Python/API and browser checks have been run, but the new channel-write, map and firmware workflows require verification on your actual VM and T114 before relying on them. Your earlier tests confirmed real RF reception and a working serial radio connection, not end-to-end delivery of every channel message.

## Upgrading the existing installation

**Keep the existing `.env`, `runtime/`, Docker volumes, and T114 Companion firmware.** Do **not** remove the PostgreSQL Docker volume or run `docker compose down -v`.

1. Optional vSphere snapshot (not a substitute for a consistent database backup).
2. Back up PostgreSQL and the installed application:

   ```bash
   cd /opt/meshcore-station
   sudo ./scripts/backup.sh
   sudo tar -czf /tmp/meshcore-pre-v3-source.tgz \
     --exclude=runtime --exclude=.git .
   ```

3. Transfer `meshcore-station-production-v3.zip` onto the VM at `/tmp/meshcore-station-production-v3.zip`.
4. Extract the package on top of the **existing** `/opt/meshcore-station` folder. The archive has an `meshcore-station/` top-level directory and excludes `.env` and `runtime/`:

   ```bash
   sudo apt-get install -y unzip
   sudo unzip -o /tmp/meshcore-station-production-v3.zip -d /opt/
   cd /opt/meshcore-station
   sudo chmod +x scripts/*.sh
   sudo ./scripts/deploy-production.sh
   ```

   `deploy-production.sh` removes the former simulator container (only for the `meshcore-station` Compose project), removes `SIMULATION=` from the private `.env`, and recreates/upgrades the live application and collector without erasing persistent volumes.

5. Restart Grafana to load new provisioned panels:

   ```bash
   sudo docker compose restart grafana
   sudo docker compose ps
   sudo docker compose logs --tail=60 collector
   ```

6. **Preview** old simulation records, then optionally delete *only matched demo records* after inspecting the counts:

   ```bash
   sudo ./scripts/remove-simulation-data.sh --preview
   sudo ./scripts/remove-simulation-data.sh --apply
   ```

   `--apply` requires typed confirmation and makes a fresh PostgreSQL SQL backup in `backups/` before any deletion. It removes known demo messages/contacts/samples/events, not real data. Unidentifiable historic events are intentionally left alone rather than risking false deletion. The script does **not** erase Grafana volumes, channel secrets on the T114, or firmware history. `backups/` and `.env` must not be committed to GitHub.

7. Hard refresh the browser (`Ctrl+Shift+R` / `Cmd+Shift+R`) and verify Overview, Radio Health, Channels, Map, messaging, and Grafana.

### Publishing this version to GitHub

The archive is **not automatically pushed** to your account. On a computer with your GitHub authentication configured:

```bash
# On your computer, not the Ubuntu VM
unzip meshcore-station-production-v3.zip -d /tmp/meshcore-v3
# Clone to a new temporary working directory; review changes before committing
git clone https://github.com/mgw24/meshcore-station.git
rsync -av /tmp/meshcore-v3/meshcore-station/ meshcore-station/
cd meshcore-station
git rm -r --ignore-unmatch tests .github/workflows/tests.yml scripts/switch-to-radio.sh
git status --short
git add -A
git commit -m "Production v3: radio health, channels, Firefox/mobile map, clean simulator"
git push origin main
```

The zip includes no credentials or live messages. Review `git status` before committing, and never add `.env`, `runtime/`, `backups/`, or flash packages.

## Fresh installation

1. Create an Ubuntu Server 24.04 LTS Minimal VM (2 vCPU, 4–8 GB RAM, 60 GB disk), connect the T114 to ESXi as **Host USB Device** passthrough, confirm Ubuntu sees `/dev/ttyACM0` and `/dev/serial/by-id/`.
2. Clone the repo to `/opt/meshcore-station` *after* pushing this version to GitHub. Run `sudo ./scripts/install.sh`, then `sudo ./scripts/start.sh`.
3. Set private LAN IP and unique admin password; record the separate Grafana password. Restrict the private VM IP/ports 8088 and 3300 to trusted LAN/VPN users.
4. Open `http://VM-IP:8088` (station), `http://VM-IP:3300` (Grafana). Use HTTPS via a VPN-side reverse proxy if entering private channel secrets over an untrusted shared network.

## Channel management and safety

1. Select **Channels → Read channels from T114**. Slots 0–7 show names only; existing keys are not revealed.
2. To rename an existing configured channel: select the slot, enter a new name, leave the key blank, type `SAVE CHANNEL`, submit. The collector reads the current secret *from the radio* and preserves it.
3. To add or rotate a channel key: provide exactly **32 hex characters** corresponding to the agreed 16-byte key; this replaces the existing key. Retain a private backup of the previous key first.
4. To delete a channel, enter `DELETE CHANNEL N` using the actual slot index and confirm. Deletion wipes the radio channel slot; it does not delete message history.
5. Avoid editing slot 0 (`Public`) unless you explicitly intend to change the public channel. A channel named Public with the wrong secret will not decode other users' public messages.
6. Channel writes are queued so **only the collector** opens `/dev/meshcore`. Keep `.env` secure and use an HTTPS reverse proxy for web administration when feasible. A firmware outage during a channel write may require confirming the final channel state on the radio.

## Radio health and known-node counts

- **RX** is the number of successfully decoded RF packets since the last radio boot. It includes repeats, advertisements and non-chat packets.
- **RX errors** count failed radio receptions/CRC errors; these may increase without chat messages.
- **Known nodes** is the number of contacts returned by the Companion and saved in PostgreSQL, not the RX count. `New in sync` is the count of new public keys first saved on the most recent contact refresh. The collector refreshes the contact list about every 5 minutes, or on demand via **Nodes → Refresh from radio**.
- **Unmapped nodes** don't have advertised coordinates. Add manual coordinates if they are known and appropriate to publish on your own private map.
- **Telemetry age** over 240 seconds while the collector is connected triggers a Prometheus alert after a grace period.
- The dashboard never treats the T114 as battery-powered in this deployment. USB power is shown without a false battery percentage.
- Grafana's historical panel values represent radio counters since the last boot. Counter reset after a power cycle is expected.

## Map and Firefox/mobile troubleshooting

The map no longer loads Leaflet from a CDN. It renders tiles through HTTPS requests to `tile.openstreetmap.org` and overlays node markers using its own DOM. If OpenStreetMap is blocked by browser settings, tracking protection or the VPN, the map still displays a coordinate grid and node pins. Internet access is only required for the raster basemap, not for the station or local inventory.

On Firefox, use a hard refresh once after upgrading. If you see only the grid, check whether the browser is allowed to load HTTPS images from `tile.openstreetmap.org`. On mobile, navigate via the horizontally scrollable tabs and use the map's `+` / `−` buttons and touch dragging. Open the page with the VPN connected.

## Service architecture

```text
Browser (desktop/mobile) through existing VPN
  ├── :8088   FastAPI + local JS/CSS; no public internet exposure
  └── :3300   Grafana
                  │
             PostgreSQL 16
                  │
             command queue → collector (only serial owner) → /dev/meshcore
                  │                                          │
           Prometheus scrape/alerts                  ESXi USB passthrough → T114 V2

Firmware upload → protected spool → Ubuntu systemd host firmware agent
                                    (stops collector before Nordic serial DFU)
```

**Firmware caveat:** ESXi can detach the radio when DFU changes its USB identity. Successful unattended flashing cannot be guaranteed until confirmed on your hardware. Keep a Mac UF2 recovery path available.

## Useful maintenance

```bash
cd /opt/meshcore-station
sudo docker compose ps
sudo docker compose logs --tail=80 collector
sudo docker compose logs --tail=80 api
sudo ./scripts/diagnose.sh
sudo ./scripts/backup.sh
sudo ./scripts/remove-simulation-data.sh --preview
```

See `QUICKSTART.md` for the shorter upgrade checklist.
