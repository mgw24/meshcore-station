# MeshCore Station 0.8.5

## Radio Monitor consolidation

The former **Radio Health**, **Radio Diagnostics**, and **Telemetry** navigation pages are now one **Radio Monitor** page. This is a web/API presentation update based on the corrected 0.8.4 release; it does not alter the T114 firmware, radio settings, collector, PostgreSQL schema, or existing Grafana dashboards.

- One connection / traffic / receive-error / uptime / suspected-reset summary instead of repeated cards.
- One shared **1h / 6h / 24h / 7d** range for reset-aware trends and outbound diagnostics; Refresh reads both existing endpoints.
- Main RX and TX packets-per-minute graph, with collapsible **Signal & Power** (RSSI, noise floor, SNR, battery only when present).
- Collapsible **Packet Analysis & Uptime**: flood/direct RX and TX, errors, reset events, and explicit *since-boot* counters distinct from rates.
- Collapsible **Transmission Evidence**: transmission outcome totals and a single per-message outbound evidence timeline.
- Collapsible **Advanced Diagnostics**: radio/routing readback, filtered RX event log, and raw telemetry JSON.
- Removed duplicated cumulative packet/error graphs, separate diagnostic traffic bars, and repeated TX lists. No history or endpoints are deleted.
- Improved layout and chart legend/axis spacing on desktop and narrow screens; updated interface and API version to 0.8.5.
- Short project-focused README retained.

## Upgrade

Apply `meshcore-station-0.8.5-upgrade.zip` to an existing **0.8.4** installation. The upgrade installer checks SHA-256 checksums and existing-file baseline hashes, makes a source backup, updates UI/API source, and rebuilds only the API service. No database migration is required.

Verify `docker compose ps api collector` and visit **Radio Monitor**. Use the provided publish script from your normal (non-root) Git user only after confirming the station is healthy. Avoid force pushes, and never delete database volumes.

## Observability note

The packet rates are averages between valid telemetry samples, not individually timestamped RF packets. Suspected resets are based on telemetry counter/uptime discontinuities. Firmware-supplied RSSI and SNR are not estimated when missing, and radio acceptance does not establish delivery.
