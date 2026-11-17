# MeshCore Station 0.8.0 — Radio Diagnostics

## Changes
- Semantic version 0.8.0 visible in sidebar, API `/api/version` and application metadata.
- New **Radio Diagnostics** page: collector heartbeat, reset-aware RX/TX/error counts, flood/direct values, radio configuration and region/hash readback.
- Per-message outbound evidence timeline (accepted, matching channel copy, direct ACK).
- No changes to TX power, frequency, firmware, channel keys or email scheduler.
- All diagnostic requests use existing PostgreSQL telemetry; they never open the USB serial device.

## Interpretation
- RX/TX totals are sums of **observed counter changes** within the chosen window. The first sample has no baseline; missing counters and reboot intervals are excluded. They are not perfect on-air packet accounting.
- Radio accepted does not prove a transmission reached another node. A repeated channel copy is not a recipient acknowledgment. Direct ACK is presented only when an exact recorded checksum matches.
- Sampled RSSI does not necessarily belong to the latest message.

## Upgrade
See `scripts/install-0.8.0.sh` and the instructions in the upgrade archive. **Keep `.env` and database volumes out of GitHub.**

## Rollback
The upgrade script saves an archive in `/opt/meshcore-backups/` before changing files. Restore its files and rebuild only `api`; no database schema changes are required.
