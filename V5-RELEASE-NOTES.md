# MeshCore Station v5 — Email Digests

Built against the existing MeshCore Station v4 source package. This combined release updates the web application, database models, deployment, and the provisioned Grafana operations dashboard. It does not change the T114 firmware, radio configuration, collector serial access, or Grafana data volume. Use [V5-COMBINED-RELEASE.md](V5-COMBINED-RELEASE.md) for the recommended single-package upgrade.

## New features

- **Email Digests** page, available from the station's maintenance navigation, including responsive mobile layout.
- Configurable SMTP host, port, sender, recipients (up to 20), optional username/app password, STARTTLS, implicit TLS (SMTPS), or an unauthenticated *plaintext* private relay. SMTP login over plaintext is prohibited.
- SMTP password encrypted at rest in PostgreSQL with a separate `DIGEST_ENCRYPTION_KEY` in the VM's local `.env` file. The password is never returned by the API. Empty password input retains existing credentials; Clear Stored Password explicitly deletes them.
- Configurable daily, twice-daily (12 hours apart), and weekly schedules, with time of day, weekday and IANA timezone (`America/Los_Angeles` by default). Scheduled delivery is disabled by default.
- Select which sections to include: received messages, outgoing messages, radio diagnostics, unresolved/new alerts and issues, new known contacts, and RX activity metadata.
- Message-count limit and authenticated report preview. Simulated messages are excluded.
- **Send Test Email** sends no mesh content. **Send Digest Now** sends the selected data for the latest interval. Both are queued to a separate worker.
- Delivery history with success/error status, recipient count and the number of messages included.
- Dedicated `digest` Docker Compose service, with no USB device access. It sends via SMTP and reads the existing PostgreSQL database.
- Idempotent scheduled slots prevent repeated sends after normal restarts. If a worker crashes while an email is being transmitted, its status is `unknown` (delivery uncertain), and it is **not** resent automatically to avoid duplicate mail.
- New PostgreSQL tables `digest_settings` and `digest_deliveries` created automatically. Existing data is retained.

## Upgrade (existing Ubuntu 24.04 deployment)

1. Back up PostgreSQL (and separately protect your `.env`):

   ```bash
   cd /opt/meshcore-station
   sudo ./scripts/backup.sh
   ```

2. Copy `meshcore-station-v5-email-digest-patch.zip` to `/tmp/` on the VM and install:

   ```bash
   cd /opt/meshcore-station
   sudo unzip -o /tmp/meshcore-station-v5-email-digest-patch.zip -d /opt/meshcore-station
   sudo chmod +x scripts/enable-digests.sh
   sudo ./scripts/enable-digests.sh
   sudo docker compose config --quiet
   sudo docker compose up -d --build --no-deps api digest
   sudo docker compose ps
   sudo docker compose logs --tail=40 digest
   ```

   This **does not** rebuild or restart the T114 collector, PostgreSQL, or Grafana.

3. Hard refresh your browser (Ctrl+Shift+R / Cmd+Shift+R), sign in, and open **Email Digests**. Configure SMTP, sender, recipients, timezone, delivery time and report sections. Keep scheduled delivery disabled until you've tested SMTP.
4. Click **Save digest settings**, **Send Test Email**, and check **Delivery history** (the worker polls every ~30 seconds). Use **Preview report** and **Send digest now** only when you are ready to email message content.
5. Enable scheduled delivery and save. The first automated email is sent at the *next* scheduled time, not immediately for an earlier slot.
6. Back up the private `.env` separately in a secure location. Losing `DIGEST_ENCRYPTION_KEY` means the SMTP password stored in PostgreSQL cannot be decrypted.

## SMTP troubleshooting

- For SMTP submission: `STARTTLS` + port `587` is typical; `SSL` + port `465` is also common. Check your provider's requirements. Providers often require an app password or SMTP token rather than an interactive login password.
- For an internal unauthenticated relay, choose `None` and leave the SMTP username/password empty. This **does not encrypt mail in transit** and should only be used on a network you trust.
- Ensure the VM/container can resolve the SMTP hostname and reach the configured outbound port. Some environments or providers block port 25.
- `docker compose logs --tail=60 digest` reports generic error categories **without passwords or email bodies**. The UI shows a sanitized delivery error in Delivery History.
- Test email is deliberately content-free. Use **Preview report** to confirm the sections before **Send digest now**.
- Dates are calculated in your selected IANA timezone, including daylight-saving changes. All database timestamps are UTC.
- Scheduled digest email is independent of the existing collector's **immediate collector-offline alert** SMTP settings (`SMTP_HOST`, `ALERT_EMAIL`) in `.env`. Those legacy alerts remain unchanged; the new web UI controls digest delivery only.

## Privacy, scope and limits

- All digest settings and actions require station sign-in; modifications require CSRF authorization.
- Messages can contain sensitive private channel/direct-message content. Do **not** enable message sections unless you trust your recipients and SMTP provider. The UI never exposes the SMTP password after saving.
- The `digest` service reads the database and emails a **report**; it does not scrape raw LoRa packets or transmit over MeshCore.
- Reception and transmission counters are diagnostic, not delivery acknowledgments. Count changes after a radio reboot can be unavailable.
- The digest provides a point-in-time report of the station database. It cannot include mesh messages the radio did not receive or that were not saved.
- No changes to T114/ESXi USB passthrough, firmware agent or existing collector. The provisioned Grafana dashboard JSON is replaced; its data sources and volumes are preserved.
- The patch has Python syntax and isolated API/schedule/report tests. SMTP delivery on your actual server and the rendered browser UI still require live verification.

## Rollback

The existing v4 source can be restored from a protected backup or Git. You can stop the new worker without affecting the radio:

```bash
cd /opt/meshcore-station
sudo docker compose stop digest
```

New tables do not affect earlier v4 code; leave them intact unless you intentionally want to erase email configuration and delivery history. Never run `docker compose down -v` for an application rollback.
