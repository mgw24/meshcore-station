# MeshCore Station 0.8.9

**MeshCore Station** is a self-hosted web console for operating and monitoring a MeshCore USB Companion radio. It is built for a Heltec T114 V2 connected to an Ubuntu Linux server or virtual machine, with browser access from desktop and mobile devices.

The project combines messaging, radio diagnostics, node discovery, maps, and historical monitoring in one interface. It is an independent community project, **not an official MeshCore release**.

## AI Development Disclosure

**Most of MeshCore Station has been generated or developed with AI assistance, primarily using OpenAI's ChatGPT.** This includes substantial portions of the application code, architecture, tests, documentation, and development scripts. A human project maintainer directs the work, chooses requirements, configures the deployment, and provides testing and feedback.

**AI-generated or AI-assisted software can contain bugs, security vulnerabilities, and unexpected behavior.** Anyone using or modifying this project should independently review the source code and test it in their own environment before relying on it—especially for radio hardware, firmware updates, message handling, credentials, or services exposed through a network.

MeshCore Station is an independent community project, **not an official MeshCore release** and not endorsed or supported by OpenAI. It is provided under the repository's license, without warranties or guarantees of security, reliability, or fitness for a particular purpose.

## Quick start — fresh installation (latest `main`)

> **New installs only.** These commands target a **fresh Ubuntu Server 24.04 LTS** machine or VM. If MeshCore Station is already installed, **do not reinstall it**: see [Updating an existing installation](#updating-an-existing-installation) below or [QUICKSTART.md](QUICKSTART.md).

**Before you begin:**

- Connect a compatible **Heltec T114 V2** flashed with **MeshCore USB Companion** firmware (not repeater firmware). Use the appropriate MeshCore firmware flashing instructions for your board before starting Station.
- Have a working network connection, `sudo` access, and the radio connected by a USB data cable. Identify its Linux serial device (usually `/dev/ttyACM0`); only one service should control it.
- Choose an IPv4 address for the Ubuntu VM that your browser can reach over a trusted LAN/VPN. The installer defaults to `127.0.0.1`, which allows access **only from the VM**; use your VM's private address for access from another device. Do not bind the dashboard directly to an untrusted public network.

**1. Install Git and clone the current build:**

```bash
sudo apt-get update
sudo apt-get install -y git

# Keep the Git checkout owned by your normal Ubuntu account.
sudo install -d -o "$(id -un)" -g "$(id -gn)" /opt/meshcore-station
git clone https://github.com/mgw24/meshcore-station.git /opt/meshcore-station
cd /opt/meshcore-station
```

For a specific, immutable release rather than the newest `main`, check out an [existing release tag](https://github.com/mgw24/meshcore-station/tags) *after cloning*. Do not assume a tag exists until it is listed on GitHub.

**2. Run the installer and start the stack:**

```bash
cd /opt/meshcore-station
sudo ./scripts/install.sh
sudo ./scripts/start.sh
```

The installer checks for **Ubuntu 24.04**, installs host prerequisites and Docker/Compose if needed, sets up the firmware-flashing agent, and runs interactive configuration **only when `.env` does not exist**. At the prompts, enter the VM's reachable private IPv4 address, radio device (for example `/dev/ttyACM0`), web admin username, and a password of at least 12 characters. The installer generates PostgreSQL, Grafana and session credentials in the **local `.env`** and prints a randomly generated Grafana admin password: save that password privately.

**3. Check services and sign in:**

```bash
cd /opt/meshcore-station
sudo docker compose ps
sudo docker compose logs --tail=60 collector
```

Open these addresses from a computer that can reach the selected VM address:

| Service | Default address | Credentials |
| --- | --- | --- |
| MeshCore Station | `http://<VM_PRIVATE_IP>:8088/` | Web admin username/password chosen during setup |
| Grafana | `http://<VM_PRIVATE_IP>:3300/` | Username `admin` and generated Grafana password |

If you selected `127.0.0.1`, those URLs work only **on the VM** (replace `<VM_PRIVATE_IP>` with `127.0.0.1`). Port **8088** is the default host web port; port **8000** is used **inside** the API container. Check the **Radio Monitor** for a connected T114, the **Channels** page for radio channel slots, and Grafana for monitoring. A connected radio alone does not guarantee mesh reception or message delivery.

**4. Optional — HTTPS reverse proxy / Grafana link:**

You can route separate HTTPS hostnames through your existing reverse proxy to the VM's **8088** (Station) and **3300** (Grafana) host ports. To make the Station navigation open the correct Grafana hostname, set `GRAFANA_PUBLIC_URL=https://grafana.example.net/` **only in the VM's local `.env`**, then apply that setting with:

```bash
sudo docker compose up -d --build --force-recreate --no-deps api grafana
```

Configure the actual reverse-proxy routes and HTTPS/access controls separately. Changing `GRAFANA_PUBLIC_URL` does **not** set up a proxy or DNS. Use `COOKIE_SECURE=true` in `.env` when the dashboard is accessed exclusively through HTTPS, and recreate `api` after changing it. Never commit `.env` or paste passwords, private channel keys, or node coordinates into an issue.

### Updating an existing installation

Do **not** repeat the fresh-install steps or overwrite your existing `.env`. Check `git status --short`, make a backup with `sudo ./scripts/backup.sh`, then follow [QUICKSTART.md](QUICKSTART.md) and the [latest release notes](RELEASE-0.8.9.md) for a safe fast-forward pull and only the Docker services changed by that release. **Never use `docker compose down -v`** on a deployment with data you want to keep.

## Features and capabilities

- **Messaging:** Send channel and direct messages, browse a compact searchable history and an Overview preview with configured channel names, filter by named channel or direct messages, sort by date or channel across the full archive, and export records, expand messages for details, and compose `@name` channel replies or replies to identified direct contacts.
- **Transmission diagnostics:** Show when the radio accepts a message and record matching channel echoes or supported direct-message acknowledgments. Delivery remains unconfirmed without evidence.
- **Radio Monitor:** One consolidated page for radio health, telemetry, routing diagnostics and outbound evidence. Track RX/TX packet rates, flood versus direct traffic, receive errors, RSSI, SNR when available, noise floor, uptime, and suspected radio resets.
- **Nodes and contacts:** Discover MeshCore contacts, identify companions, repeaters, room servers, and sensors with distinct markers, and maintain a separate address book with nicknames, favorites, and notes.
- **Node map:** Plot nodes with advertised or manually assigned coordinates, including a private location marker for the local station.
- **Radio configuration:** Manage supported radio parameters, messaging channels, path-hash modes, and outgoing region scopes through the web interface.
- **Identity and advertisements:** Configure the local node's fixed coordinates and location-sharing policy, and manually issue local or flood advertisements with confirmation and cooldown safeguards.
- **Monitoring and history:** Store telemetry, messages, and events in PostgreSQL; visualize long-term trends in Grafana and collect operational metrics with Prometheus.
- **Email digests:** Optionally schedule operational summaries of messages, radio health, and issues using configurable SMTP delivery.
- **Firmware management:** Manage supported firmware update jobs through a separate host-side flashing agent.

## How it works

A Docker-based collector communicates with the T114 over USB serial and records radio information in PostgreSQL. The web application reads stored information and submits commands through a queue, keeping the collector as the sole owner of the serial connection. Grafana, Prometheus, and the optional email service run alongside the application.

MeshCore Station runs with **USB Companion firmware**; it does not turn the connected radio into a mesh repeater. Radio acceptance or a transmitted-packet count does not by itself prove that another node received a message. Private map coordinates are not broadcast unless location sharing is explicitly enabled.

**Current release:** `0.8.9` · [Project source](https://github.com/mgw24/meshcore-station)
