# MeshCore Station 0.8.1 — Messages Interface Refresh

## What's new

- **Compact message composer above the history**, no longer side-by-side.
- **Full-width message history** with search across message text, sender and destination.
- Filter by incoming/outgoing messages, channel 0–7, or direct messages.
- **Server-side, timestamp/id cursor pagination**: load older history without fetching the entire database.
- Message rows show sender, local timestamp, destination, and conservative status. Expand **Message details** to inspect stored TX evidence.
- Mobile and Firefox-friendly responsive layout with keyboard-accessible controls.
- Unified `0.8.1` application version in `VERSION`, API, navigation footer, README, and release notes.
- Added a GitHub publishing script that checks release consistency, protects private files, verifies a fast-forward push, then publishes `v0.8.1`.

## Important behavior

- "Radio accepted" **does not mean delivered**. Channel echoes indicate a copy was heard, not an acknowledgement from a recipient. Direct acknowledgements are shown only when recorded.
- Messages are displayed using saved PostgreSQL data. No USB serial connection is opened by the history interface.
- The older `/api/messages` JSON list endpoint is retained for existing integrations.
- Email digests, node map, address book, Grafana dashboards, radio firmware, and routing settings are unchanged.

## Deployment and rollback

1. Back up PostgreSQL and the current source (the upgrade installer also backs up replaced source files).
2. Unzip `meshcore-station-0.8.1-upgrade.zip` to `/tmp/meshcore-081` and run `sudo bash /tmp/meshcore-081/install.sh`.
3. Rebuild/restart the **API only**, performed by the installer. Collector and digest remain running.
4. Verify `docker compose ps api` and the Messages page. Hard-refresh your browser if it cached old assets.
5. After verification, run `bash scripts/publish-0.8.1.sh` as your regular Git user. No force-push is used.

The installer creates a timestamped source backup under `/var/backups/meshcore/`; roll back by restoring those files and rebuilding the API. Existing database tables are not migrated or removed.
