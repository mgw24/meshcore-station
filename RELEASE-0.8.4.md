# MeshCore Station 0.8.4

## Radio health and station identity

- Adds reset-aware RX/TX packets-per-minute and flood/direct rate time series calculated from PostgreSQL samples. Consecutive counters, not raw RF packets, determine averages. Counter rollbacks and uptime decreases mark reset candidates; gaps over 10 minutes are not graphed as reliable interval rates.
- Adds error-rate history, separate RSSI/noise (dBm) and SNR (dB) charts, and uptime/reset history. SNR is shown only if firmware reports it.
- Preserves existing Grafana layout and adds SNR and uptime reset panels instead of duplicating older traffic charts.
- Adds a private fixed node location stored in PostgreSQL, optionally shown as a special marker on the Node Map. Entering coordinates does **not** change the T114 or transmit anything.
- Adds separately confirmed radio actions: apply coordinates with location hidden, enable sharing, and disable sharing. Uses `set_coords()` and `set_advert_loc_policy()` via the collector. Firmware readback is marked unavailable when unsupported.
- Adds controlled zero-hop and flood advertisements, 5-minute and 2-hour respective cool-downs, command-status monitoring, and acceptance/failure history. A radio-accepted advert does not establish that another radio received it. Automatic advertisements remain off.
- Keeps USB collector as sole serial owner; preserves firmware, RF frequency, TX power, channel secrets, path hashes, and existing region settings.
- Includes README/version/GitHub publishing consistency checks.
- Simplifies the GitHub README to general project information, features, and capabilities; installation and upgrade procedures remain in separate documentation.
- Simplifies the GitHub README to general project information, features, and capabilities; installation and upgrade procedures remain in separate documentation.

## Deployment

Use `meshcore-station-0.8.4-upgrade.zip` with the included `install.sh`; see `UPGRADE-INSTRUCTIONS.md` in the upgrade archive for exact commands. Upgrade from 0.8.3 after backing up PostgreSQL. The installer does not run `docker compose down -v` and does not publish to GitHub automatically.

## Testing limitations

Software, syntax and mocked-radio command tests cannot prove actual RF transmissions, T114 firmware readback, or browser/VM behavior. Verify those against the physical radio after deployment. Location sharing and flood adverts require explicit user action.
