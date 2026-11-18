# MeshCore Station v7 — TX Evidence + SMTP Diagnostics

This update builds on v6 Routing & Regions and does not change firmware, radio
frequency, TX power, path-hash size, channel keys, or region scopes.

## TX confirmation behavior

- **Messages** displays evidence-based outbound status rather than implying
  delivery from radio-command success.
- **Radio Health → TX confirmation tracking** lists the latest outbound messages
  and an aggregate count of radio-accepted sends, exact direct ACKs, candidate
  channel echoes, and unconfirmed sends.
- **Database** gains an additive `tx_evidence` table created at API/collector
  startup. Existing message rows are not deleted or rewritten.
- **Direct messages** become `acknowledged` only after a matching four-byte ACK
  checksum is received for a recently sent direct message.
- **Channel messages** can show "Matching channel repeat heard" only if the
  firmware delivers a decoded echo with matching channel index, exact text,
  original sending timestamp (15 seconds tolerance) and a nonzero path length.
  A repeat is **not** proof that a particular recipient received or read the
  message. Some Companion builds do not expose such echoes; their messages
  correctly remain unconfirmed.
- **No raw packet payloads or channel secrets** are stored by this feature.
- Old messages cannot be retrospectively classified from packet counters.

## Install

Copy the update ZIP to the Ubuntu VM, for example
`/tmp/meshcore-station-v7-tx-confirmation.zip`, then:

```sh
sudo apt-get install -y unzip
sudo mkdir -p /tmp/meshcore-v7-install
sudo unzip -oq /tmp/meshcore-station-v7-tx-confirmation.zip -d /tmp/meshcore-v7-install
sudo bash /tmp/meshcore-v7-install/install.sh
```

The installer verifies your source files match the packaged v6 baseline,
backs up the database and source, and rebuilds only `api` and `collector`.
The collector will briefly reconnect to the T114. Other services remain running.

After deployment:

```sh
cd /opt/meshcore-station
sudo docker compose ps api collector
sudo docker compose logs --tail=60 collector
```

Open `http://YOUR-VM-IP:8088` and inspect **Radio Health → TX confirmation
tracking**. Send a short test channel message and a direct message to a
cooperating node. Ask the node to acknowledge the direct message. Old messages
retain their historical unconfirmed status.

## GitHub

Review the staged paths before publishing:

```sh
cd /opt/meshcore-station
bash scripts/publish-v7-release.sh
```

This script never stages `.env`, runtime data or backups and does not perform a
silent push.

## Rollback

The installer prints its backup directory under `/var/backups/meshcore/`.
To rollback, restore the archived source files from there and rebuild the
`api` and `collector` containers. The additive `tx_evidence` database table may
safely remain; it does not affect v6 application behavior.

## Limitations

A radio's ACK is not proof a person read a direct message. A heard channel echo
is evidence of propagation but not delivery to all interested nodes. SDK/firmware
versions lacking raw echo events may never report a channel repeat. This update
is tested statically and with unit tests; live T114/ESXi behavior must be
verified on the VM.

## SMTP delivery diagnostics

Email Digests now has **Test SMTP connection**, distinct from **Send test email**.
The new job is processed by the existing digest worker and does not access the
radio or send an email. It tests hostname resolution, SMTP connection, TLS mode,
and (when configured) SMTP authentication. Diagnostic results appear in Delivery
History (`passed` or `failed`); passwords and SMTP server replies are excluded.

**Troubleshooting on the VM**:

```sh
cd /opt/meshcore-station
sudo docker compose ps digest
sudo docker compose logs --tail=100 digest
```

In the browser, **save** SMTP settings, run **Test SMTP connection**, refresh
Delivery History, then use **Send test email**. If the connection passes but mail
doesn't arrive, check the sender address, spam filtering, and SMTP provider's
accepted-message/delivery logs. A `sent` history entry means only that the SMTP
server accepted the mail, not that a recipient inbox delivered it. Running tests
requires a healthy `digest` service, even with scheduled digests disabled.

An authentication failure usually calls for an app password or provider-specific
SMTP authorization; do not enter an ordinary account password into logs or chat.
