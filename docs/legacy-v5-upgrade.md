# MeshCore Station v5 — Email Digests + Grafana Operations (combined release)

This package upgrades the working v4 station on Ubuntu Server 24.04 LTS **in one operation**. It combines the v5 Email Digests page and worker with the new Grafana Radio Operations dashboard. It does **not** change the USB collector, firmware, T114 radio parameters, or existing PostgreSQL/Grafana volumes.

Source repository: https://github.com/mgw24/meshcore-station

## What changes

- **Email Digests** in the web interface: SMTP/TLS server and credentials, recipients, local timezone, delivery time, daily/twice-daily/weekly schedule, selectable report sections, preview, test email, delivery history. Scheduler initially **disabled**.
- **Grafana Radio Operations**: concise status cards, RX/TX and error-rate panels calculated from stored samples (reboot-aware), signal and uptime charts, non-simulated messages, node roles, and decoded RX activity. No battery-percent panels for USB-only hardware.
- Existing map, address book, channel configuration, node icons, firmware manager, and messages stay in place.

## One-pass upgrade

1. On a **computer**, download `meshcore-station-v5-combined-update.zip` and transfer it to the Ubuntu VM at `/tmp/meshcore-station-v5-combined-update.zip` using your preferred file-transfer tool.
2. In Ubuntu, run:

   ```bash
   sudo apt-get update
   sudo apt-get install -y unzip
   sudo unzip -oq /tmp/meshcore-station-v5-combined-update.zip -d /tmp/
   sudo bash /tmp/meshcore-station-v5-combined/install.sh
   ```

   The installer checks the payload hashes, backs up the current source, the PostgreSQL database and `.env` under `/var/backups/meshcore/`, preserves Docker volumes, sets up the SMTP encryption key (if absent), updates only release files, rebuilds **api** and **digest**, and restarts **Grafana**. It does **not** restart the collector.

3. Verify:

   ```bash
   cd /opt/meshcore-station
   sudo docker compose ps api digest grafana collector db
   sudo docker compose logs --tail=50 digest
   sudo docker compose logs --tail=50 grafana
   ```

4. Refresh your browser, open **Email Digests**, and configure SMTP and recipient addresses. Leave automatic scheduling off until **Send Test Email** succeeds. Then open **Grafana → MeshCore → MeshCore Station · Radio Operations** and check charts over Last 1 hour and Last 24 hours. Missing metrics should say **No data**, not zero.

5. Publish the upgraded source to GitHub **after verifying the deployment**:

   ```bash
   cd /opt/meshcore-station
   git status --short
   bash scripts/publish-v5-release.sh
   ```

   Run Git as the normal `meshcore` user, not through `sudo`. The publishing script checks the remote, branch, staging area, and sensitive file paths, then requests confirmation before committing and pushing to `main`.

## GitHub authentication

If the push asks for an HTTPS password or reports authentication failure, configure the GitHub CLI as your regular Linux user:

```bash
sudo apt-get install -y gh
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh auth status
```

You can open the device verification URL in a browser on **any computer**. Do not paste authentication codes or tokens into support chats. The repository is not updated until `git push` succeeds.

After publishing, confirm the local commit hash matches GitHub's `main`:

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short
```

`git status --short` should be empty and the hashes should agree. No application secrets, runtime data or backups should be tracked.

## Data safety and rollback

- Never run `docker compose down -v` during an upgrade or rollback.
- The installer's backup directory is shown in its final output. Its `.env` copy is sensitive and has mode `0600`.
- Keep the original `DIGEST_ENCRYPTION_KEY` from `.env` when upgrading. If it is lost, an SMTP password encrypted using that key cannot be recovered from the database.
- If Grafana fails after upgrade, copy `grafana/dashboards/station.json` from the saved `source-before.tar.gz` and restart Grafana. The dashboard retains UID `meshcore-station`.
- If app code must be reverted, use your saved source archive or a known good Git commit, then rebuild the `api` and stop the `digest` service. New digest tables may be left in place; removing volumes is unnecessary.
- A database restore is a separate, destructive action and should only be done after reviewing a consistent database backup.
- SMTP test emails do not include mesh message content; full digests can include sensitive direct or private-channel messages, so review recipients and report sections before enabling.
- Grafana TX status denotes radio acceptance, not confirmed reception by another node. RX counter increments aren't necessarily decoded chat messages.
- Chart queries and email delivery require a live check on your VM; packaged syntax checks are not a substitute for operational verification.

## Generic firmware-recovery guidance

For future firmware maintenance, use a compatible **computer** capable of USB firmware recovery if ESXi detaches the T114 during bootloader re-enumeration. The combined upgrade does not flash the device.
