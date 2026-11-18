# MeshCore Station v4 — UI-first production update

**Scope:** UX and observation only. Does not change T114 frequency, bandwidth, spreading factor, TX power, USB passthrough, installed firmware, radio channel secrets, or Docker volume names.

## Included
- **Radio Health > RX activity:** decoded RX event metadata (when available) and separately labelled, time-aggregated RX/error counter changes. Auto-refreshes on the existing 10-second UI poll. RX log retention is 7 days with a 50,000-entry cap. Raw RF packet payloads and keys are not stored in the new log.
- **Address Book:** persistent local PostgreSQL records, aliases, notes, tags, favorite status, manual entries, saved discovered contacts, and direct-message shortcut when the contact is already known to the T114. No automatic radio or Public channel changes.
- **TX status:** your radio's configured node name appears for new outgoing messages; the status says "Radio accepted · delivery unconfirmed" rather than implying receipt. Radio Health also displays available flood/direct TX counters.
- **Node styling:** distinct symbols and restrained colors for companions, repeaters, room servers, sensors, and unknown nodes, using the existing Firefox/mobile map renderer.

## Upgrade a live v3 station

1. Take a PostgreSQL backup **before** installing:

   ```sh
   cd /opt/meshcore-station
   sudo ./scripts/backup.sh
   ```

2. Copy `meshcore-station-v4-ui-update.zip` to `/tmp/` on the VM. The archive is a **file overlay** (relative paths, no enclosing directory):

   ```sh
   cd /opt/meshcore-station
   sudo unzip -o /tmp/meshcore-station-v4-ui-update.zip -d /opt/meshcore-station
   sudo docker compose config --quiet
   sudo docker compose up -d --build --no-deps api collector
   sudo docker compose ps
   sudo docker compose logs --tail=50 api collector
   ```

3. Hard reload desktop Firefox (`Ctrl+Shift+R`), or reopen the page in your phone's browser. Verify **Address Book**, **Radio Health → RX activity**, Messages and Node Map.

4. Check `GET /api/radio/rx-log` via the logged-in web browser, or wait for new radio traffic. The log may initially be empty; existing historical packet counters are not backfilled. Ordinary RX counter changes are reported only after two consecutive fresh telemetry samples (~1 minute apart).

5. To publish after verification:

   ```sh
   cd /opt/meshcore-station
   git status --short
   git diff --check
   git add README.md station/db.py station/web.py station/worker.py station/health.py static/app.js static/style.css static/index.html
   git diff --cached --name-only
   git commit -m "MeshCore Station v4: RX activity and address book"
   git push origin main
   ```

   Do **not** commit `.env`, `runtime/`, database volumes, backups, firmware packages, or private channel keys. Confirm `git rev-parse HEAD` matches `git ls-remote origin refs/heads/main`.

## Important distinctions
- An `RX_LOG_DATA` event can contain RSSI/SNR and other metadata; however the firmware/SDK may not expose every raw RF packet. The sampled `counter_delta` rows do not claim an individual sender, packet timestamp, or signal strength.
- A `Radio accepted` send status means the USB Companion accepted the send command. It does **not** prove a repeater or recipient heard it.
- Entries saved to the address book are independent of the radio contact store. A valid full 64-character public key alone does not mean the T114 knows a route to that contact.
- Rebuilding `api` and `collector` temporarily interrupts the serial collector, but does **not** remove PostgreSQL/Grafana volumes. New tables are additive (`address_book`, `rx_activity`).
- This package is validated statically and with an isolated SQLite API/collector smoke test; on-device MeshCore reception and browser behavior must still be tested on your running VM.
