# MeshCore Station v6 — Routing & Regions

This is an incremental update to **v5 combined** on Ubuntu 24.04. It does not reflash your T114 or change its 910.525 MHz radio preset, TX power, existing channels, PostgreSQL schema, or Grafana dashboards.

## Features

- Routing & Regions page under Maintenance on desktop and mobile.
- Reads the radio path hash mode (1, 2, or 3 bytes per hop) via the USB Companion SDK.
- Explicit apply plus actual radio readback for path hash changes; older repeaters may silently drop longer hashes.
- Manage local saved region identifiers (up to 32); no claim that they are confirmed by community repeaters.
- Explicitly configure the Companion's default outgoing flood scope, including Unscoped.
- Optional scope per channel (inherit, unscoped, or a saved region). A scoped channel message temporarily applies its override then restores the configured default.
- Scope is applied only after explicit user confirmation. On collector reconnect, a Station-configured default is reapplied; without such a configuration the firmware scope is left alone.
- Settings are queued through PostgreSQL so only the collector accesses the T114 serial port.
- Scope state is **app-managed** because the installed SDK cannot independently read it from firmware. Do not interpret the UI as hardware-verifying the scope.

## Caveats

* The station uses **Companion** firmware. It **does not manage repeater region trees, allow/deny lists, `region put`, `region allowf`, `region save`**, etc.
* A community region name is not a US FCC operating band, country code, or radio-frequency preset.
* Per-channel scopes require an explicitly set default. A temporary override is restored even when send fails. If scope restoration fails, message transmission is suspended for subsequent scoped sends until the default is reapplied.
* Hash mode writes and scope writes are separate firmware operations. A partial change can occur if a later step fails; inspect status and retry deliberately.
* If firmware/SDK does not support a command, the request fails rather than faking a successful configuration.
* For your Spokane installation, **keep 1-byte path hashes and unscoped transmission unless local repeater operators confirm that longer paths or a specific region are appropriate**.

## Upgrade

1. Securely back up `.env` and your PostgreSQL data.
2. Extract this update ZIP to `/tmp/meshcore-v6-update` on Ubuntu.
3. Run `sudo bash /tmp/meshcore-v6-update/install.sh` (or adjust the path to where you extracted it).
4. Open MeshCore Station → Routing & Regions → Read path hash from T114.
5. Optionally add region names; type `APPLY ROUTING` to save. **Nothing changes on the radio until you explicitly select a radio setting and confirm it.**
6. Check `sudo docker compose -f /opt/meshcore-station/compose.yaml ps api collector` and the collector logs.
7. Run `bash scripts/publish-v6-release.sh` from the Git working tree **without sudo**, only after validation.

### GitHub note

The full-source ZIP is for reproducible archiving. The update ZIP writes only six source files plus release notes and publisher script. It does not contain `.env`, passwords, PostgreSQL dumps, or runtime data. Publishing must be performed from your VM with your existing GitHub authentication.

### Rollback

The installer backs up replaced files under `/var/backups/meshcore/v6-routing-<timestamp>`. Restore those files manually from the backup and rebuild only `api` and `collector`. Any radio hash/scope changes made through the UI **are not automatically reverted by rolling back application files**; restore those separately through the v6 controls before rolling back if necessary.
