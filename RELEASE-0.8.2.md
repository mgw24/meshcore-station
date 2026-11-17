# MeshCore Station 0.8.2 — Compact Messages & Contextual Replies

## Highlights

- Converted full-width message history from large cards into 38–44-pixel single-line rows (depending on screen width).
- Clicking or tapping a row expands the full message, sender, channel or direct-message type, time, stored status, and supported TX evidence.
- **@ Reply** on incoming channel messages selects the original channel and inserts a textual `@Sender ` prefix into the existing message composer. `@` does not create a guaranteed notification.
- **Reply privately** on incoming direct messages selects a recipient only when a public key or unique prefix matches exactly one contact on the T114. Unknown or ambiguous senders are never guessed.
- Preserves unsent drafts, warns before switching their destination, and enforces the existing 180-character limit.
- Keeps server-side search, direction/channel filters, keyset pagination, older-message loading, and CSV export from 0.8.1.
- Mobile-friendly compact rows, keyboard-accessible native disclosure controls, and escaped message content.
- Consistent `0.8.2` in README, `VERSION`, API, UI, release notes, publisher and tag.

## Upgrade

1. Back up PostgreSQL with `sudo ./scripts/backup.sh` from `/opt/meshcore-station`.
2. Put `meshcore-station-0.8.2-upgrade.zip` in `/tmp/` on the Ubuntu VM.
3. Run:

   ```bash
   sudo mkdir -p /tmp/meshcore-082
   sudo unzip -oq /tmp/meshcore-station-0.8.2-upgrade.zip -d /tmp/meshcore-082
   sudo bash /tmp/meshcore-082/install.sh
   ```

4. Verify `sudo docker compose ps api` and open **Messages** in the browser.
5. Publish with `bash scripts/publish-0.8.2.sh` as the regular Linux user after testing.

## Compatibility and safety

- Upgrades **0.8.1 only** and verifies that the `TxEvidence` database model exists before applying files.
- No database migration, schema change, command queue change, RF setting change or collector restart.
- Does not affect the radio, firmware, email scheduler, Grafana or PostgreSQL data.
- UI tests exercise compact list rendering, channel mentions, direct sender identity matching, ambiguous/unknown sender handling, XSS escaping and narrow-screen layout. No actual radio message is sent during testing.
- Direct replies may be unavailable for historical messages that contain only a short, non-unique sender identifier. This is intentional.
