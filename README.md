# MeshCore Station — Ubuntu 24.04 / T114 V2 / VMware

A GitHub-ready, self-hosted MeshCore Companion station for **Ubuntu Server 24.04 LTS Minimal** running as a VMware ESXi guest. One permanent **Heltec T114 V2** connects via ESXi USB passthrough. Accessible privately through your existing VPN; **Tailscale not needed**.

> **Project status:** Functional reference implementation and simulation/test scaffold. It has **not been proven against your actual T114, ESXi host, or live RF network**. Review and test with simulation first. This is not an official MeshCore project.

## Included

| Capability | Implementation |
|---|---|
| Secure browser console | FastAPI + self-contained responsive JavaScript/CSS, admin login, signed HttpOnly cookie, CSRF protection |
| Direct messaging | Outgoing via official `meshcore` Python serial SDK; incoming events archived |
| Channel messaging | Send/receive on configured channel indexes; channels read from radio when available |
| Discovery | Local Companion contacts plus advertisement/route event log |
| Logging | PostgreSQL persistent messages, contacts, events, telemetry, alerts, command history |
| Telemetry graphs | Web SVG charts (battery, noise, packet counters, RSSI) and provisioned Grafana dashboard |
| Monitoring | Prometheus scrape and alert rules; dashboard alerts and optional SMTP for collector failures |
| Firmware Manager | Web-uploaded verified Nordic DFU ZIP → restricted host systemd agent → pause collector → `adafruit-nrfutil` → resume collector |
| Operations | Install, configure, simulation, transition to hardware, diagnostic, backup/restore, update |

**Radio role:** The USB-connected T114 runs **Companion** firmware. It can send, receive, and observe messages, but it **does not act as a MeshCore repeater**. To relay other people's traffic you need a separate repeater radio (or switch this T114 to repeater firmware and give up the Companion web messaging features). This stack is designed for the Companion role.

### Architecture

```text
           Existing VPN / LAN (no public exposure)
               │              │
        :8088 MeshCore UI   :3300 Grafana
               │              │
          FastAPI container ───┼── PostgreSQL (no published DB port)
               │              │
           command queue       └── Prometheus (internal only)
               │
        collector container ←→ T114 V2 Companion USB serial
               │                       │
           events/metrics          ESXi USB passthrough

  Browser firmware upload → spool → host systemd agent (root)
                                    │
                            stops collector only
                                    │
                     adafruit-nrfutil /dev/ttyACM*
                                    │
                            restarts collector
```

## 1. Prepare the ESXi VM

- Ubuntu **Server 24.04 LTS Minimal**, 2 vCPU, 4 GB RAM (8 GB preferred), 60 GB disk; VMXNET3 NIC.
- Choose a static LAN IP address, static DHCP lease, or consistently assigned address. Existing VPN must have a route to this address.
- Enable OpenSSH during Ubuntu installation.
- Add a virtual USB controller if missing (USB 2.0/3.0 as available). Physically plug the T114 into the **ESXi host**, then in vSphere **Edit Settings → Add New Device → Host USB Device**, selecting the T114.
- For first flash use the Mac; once it is running USB Companion firmware connect it to ESXi.
- Turn off vMotion/migration expectations for this VM: the radio is tied to a physical USB port. After radio bootloader changes USB VID/PID, ESXi may require re-attaching a different USB device.
- Mount the LoRa antenna **before transmitting**. Locate the radio/antenna outside the ESXi server's metal chassis (e.g. a short powered USB extension) if possible for better RF performance.

### Identify the radio inside Ubuntu

```bash
lsusb
sudo dmesg --follow   # Plug in the device, Ctrl+C to exit
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
ls -l /dev/serial/by-id/ 2>/dev/null
```

Use `/dev/serial/by-id/...` if the radio has a stable identity; otherwise `/dev/ttyACM0` is common for nRF52. **Keep track of the real path**. Only one software process can own the serial connection.

## 2. Flash the T114 V2 initially from your Mac

1. While your currently paired iPhone/BLE Companion still works, **export its settings** and back up any available identity/private key and channel settings (treat as secrets). Firmware changes can affect identity and settings.
2. Connect T114 V2 to the Mac with a USB **data** cable.
3. Open the official [MeshCore flasher](https://flasher.meshcore.io/) in Chrome/Edge. Choose **Heltec T114** for your hardware, confirm firmware branch/board information, and select **Companion USB/Serial**. Some newer releases also offer a *Full* build that supports USB plus Bluetooth; the included Firmware Manager currently **intentionally accepts USB Companion ZIPs only**.
4. For a UF2 initial flash, download the **`.uf2`** of `Heltec_t114_companion_radio_usb...` (not repeater/room server/BLE-only).
5. Double-press **RESET** quickly to enter the Nordic bootloader. A removable USB drive should appear; copy the UF2 to that drive. It should reboot when finished. If it doesn't enumerate, try another data cable or the flasher's supported serial method.
6. Power cycle the T114 and connect it to the physical ESXi host; confirm a `/dev/ttyACM*` or stable `/dev/serial/by-id/` in Ubuntu. **Do not expect a BLE-only build to speak serial.**
7. If you reflash/erase settings, restore the desired regional frequencies, channels, radio presets, and device identity using a compatible management client before live operation. Radio settings must match the local MeshCore network and legal region.

MeshCore upstream references: [Official firmware flasher](https://flasher.meshcore.io/), [MeshCore FAQ — serial DFU and T114](https://github.com/meshcore-dev/MeshCore/blob/main/docs/faq.md), [MeshCore Python SDK](https://github.com/meshcore-dev/meshcore_py), [Flasher targets](https://github.com/meshcore-dev/flasher.meshcore.io/blob/main/config.json).

## 3. Install the new station from a GitHub clone

Upload this repository to your private GitHub repository (without `.env` or `runtime/`). On the **new VM**, use SSH:

```bash
sudo apt update && sudo apt install -y git
sudo git clone https://github.com/YOUR-ACCOUNT/meshcore-station.git /opt/meshcore-station
cd /opt/meshcore-station
sudo ./scripts/install.sh
```

The installer validates **Ubuntu 24.04**, installs `curl`, `ca-certificates`, `gnupg`, `git`, `jq`, `usbutils`, `udev`, `python3`, `python3-venv`, `python3-pip`, `unzip`, `zip`, `picocom`; sets up the **official Docker CE** repository and Compose plugin; installs **adafruit-nrfutil in `/opt/meshcore-flasher-venv`**, creates private spool directories, and enables the systemd firmware agent. Application Python dependencies are inside Docker, not installed on system Python.

When prompted, enter the VM's **private** IP reachable over your VPN, choose a strong admin password, and choose **simulation mode first**. The installer generates `.env` secrets, displays Grafana's initial admin password once, and stores `.env` with mode `0600`. Save the password to your password manager.

```bash
sudo ./scripts/start.sh
sudo docker compose --profile simulation ps
sudo docker compose --profile simulation logs -f simulator
```

Open:

- Web application: `http://VM_PRIVATE_IP:8088`
- Grafana: `http://VM_PRIVATE_IP:3300` (admin + generated Grafana password)

The application creates its tables automatically. Grafana provisions a read-only PostgreSQL datasource, a Prometheus datasource, and the **MeshCore Station Overview** dashboard.

**Note:** If you chose `127.0.0.1` in `configure.sh`, only local access works until you change `BIND_IP` in `.env` to the VM's private NIC IP and restart. Choose an IP restricted to the VPN/LAN, not a public interface.

## 4. Simulation verification

Before attaching the T114:

1. Confirm the dashboard shows **SIMULATION** and **Online**.
2. Verify two fake nodes are present in **Nodes & Contacts**.
3. Transmit a test channel message; its status must read **simulated**, with **no RF transmission**.
4. Check **Messages**, **Telemetry**, and Grafana for simulated data. The simulator emits an incoming sample message periodically.
5. Run `sudo ./scripts/diagnose.sh` and `sudo ./scripts/backup.sh`.

## 5. Switch to the real T114

Run the diagnostic script first and identify the serial path:

```bash
sudo ./scripts/diagnose.sh
sudo ./scripts/switch-to-radio.sh /dev/ttyACM0
# Or use your stable by-id path:
# sudo ./scripts/switch-to-radio.sh /dev/serial/by-id/usb-YOUR-RADIO
sudo docker compose --profile radio logs -f collector
```

The script updates `.env`, stops the simulator, and starts the real **collector** container. The collector is the only serial owner. It discovers contacts, starts automatic message fetching, subscribes to radio events, polls battery and radio statistics, and processes queued web commands.

**Verify:** Overview status is Online/USB SERIAL. Use **Refresh from radio**, review contacts, send a known-contact direct message, and check **acknowledged** vs **sent_unconfirmed** carefully. **The latter means handed to the radio; it does not prove delivery.** Channel broadcasts likewise do not imply delivery.

Radio discovery only sees contacts/advertisements that reach **your** T114. It does not provide a global map of every node in a city. If no contacts appear, check the frequency and radio preset, antenna and placement, firmware role, and receiver coverage.

## 6. Firmware updates from the web interface

The **Firmware Manager** accepts a vetted **T114 USB Companion Nordic DFU `.zip` only**, not `.uf2`, other board models, or repeater images. It validates the filename, archive structure, size, SHA-256, and explicit confirmation phrase. Choose the correct package from the official [flasher](https://flasher.meshcore.io/).

Procedure:

1. Back up any available radio settings/identity and export a fresh DB backup.
2. Confirm physical access to the ESXi host or a recovery option, in case USB passthrough detaches in Nordic bootloader mode.
3. Upload the approved ZIP in the Firmware Manager and type `FLASH T114`.
4. The web app writes a job to a private spool. A separate systemd agent verifies it again, stops **collector only**, runs:

   ```bash
   /opt/meshcore-flasher-venv/bin/adafruit-nrfutil --verbose dfu serial \
     --package YOUR_FIRMWARE.zip -p /dev/ttyACM0 -b 115200 --singlebank --touch 1200
   ```

5. Agent restarts the collector. The web interface remains available and displays job status and log output.
6. Verify the radio is **Online** and can send/receive messages. A successful DFU process is **not** proof the collector has reconnected.

**ESXi limitation:** Nordic bootloader re-enumeration may cause VMware to detach the USB device. Auto-flashing is **best effort and requires testing on your exact ESXi host**. If this happens, reattach the bootloader USB device from vSphere. For failed DFU/soft-brick recovery, physically double-press RESET and use the official UF2 method from a directly connected computer (such as your Mac).

The privileged host agent is deliberately **not** exposed through HTTP, Docker socket mounts, or remote command endpoints. Only allow trusted GitHub repo administrators to modify this source.

## 7. Alerts and graphing

- **Web console:** failed collector connections create alerts, auto-resolved on successful reconnect. Repeated alerts rate-limited to once per 15 minutes. Messages/events stored in PostgreSQL.
- **Grafana:** provisioned PostgreSQL+Prometheus dashboard with message counts, battery, noise floor, and collector availability.
- **Prometheus:** internal scrape plus rules for an unavailable collector or API; these are **rule evaluations**, not automatically emailed notifications. To send Prometheus rules externally, configure Alertmanager or Grafana contact points.
- **Optional email:** populate `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `ALERT_EMAIL` in `.env`, restart collector (`sudo ./scripts/start.sh`), and it will send STARTTLS notification emails on collector failure. Test your SMTP provider before relying on it.

Some radio counters are firmware-dependent; null/empty metrics simply mean your firmware or MeshCore SDK didn't expose them. No data is fabricated in serial mode.

## 8. Routine commands

```bash
cd /opt/meshcore-station
sudo ./scripts/diagnose.sh
sudo docker compose --profile radio logs -f --tail=200 collector
sudo docker compose logs -f --tail=200 api
sudo journalctl -u meshcore-firmware-agent -f
sudo ./scripts/backup.sh
sudo ./scripts/backup.sh /mnt/your-backup-volume
sudo ./scripts/restore.sh /path/to/backup.sql.gz   # destructive; requires confirmation

# Update your GitHub checkout, then rebuild services:
sudo git pull --ff-only
sudo ./scripts/start.sh
```

Automate `scripts/backup.sh` through a root cron/systemd timer if desired. Copy the SQL backup, `.env`, and any radio identity backup securely **off the VM**; the SQL dump alone cannot restore your radio's private key.

If migrating existing PostgreSQL tables or your older collector, **do not run both live collectors against the same T114**. This new repository starts with its own schema and does **not automatically import** your existing MeshCore PostgreSQL tables. Export/migrate historical data separately after inspecting the old schema.

## 9. Security

- Restrict ports **8088** and **3300** to the VPN/private subnet with network ACLs or a reverse proxy. PostgreSQL and Prometheus have **no published host ports**.
- Docker-published ports can bypass `ufw` rules! Configure vSphere/network firewall policy or Docker's `DOCKER-USER` chain rather than assuming UFW alone protects the VM. [Docker official note](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations).
- HTTP over the existing VPN is functional, but for browser credential protection in a shared LAN, prefer **HTTPS** via your own reverse proxy, set `COOKIE_SECURE=true`, and update your proxy headers/host restrictions. The provided stack does **not** configure HTTPS automatically.
- Keep `.env`, radio backups, firmware spool, and SQL backups outside Git; `.gitignore` is defensive, not a substitute for reviewing `git status`.
- Restrict GitHub write access and review future updates: the **firmware agent runs as root** and can control Docker and flash hardware.
- Do not expose Portainer or Docker API publicly. Portainer is optional; the supplied Compose CLI is the deployment source of truth.
- MeshCore radio traffic, message contents, metadata, and contact public keys are retained in PostgreSQL: use encrypted VM backups and appropriate retention policies.

## 10. Troubleshooting

| Symptom | Checks |
|---|---|
| `No such device` for collector | `ls -l /dev/ttyACM*`, `dmesg`, ESXi USB passthrough; edit `.env` and restart; choose `/dev/serial/by-id` if present |
| Collector offline | USB Companion firmware, not BLE-only; VM sees radio; `docker compose --profile radio logs collector` |
| Permission denied serial | `ls -l` device group, Docker `group_add: dialout`; compare group IDs; confirm no ModemManager competing with device |
| Flash update stalled | `sudo journalctl -u meshcore-firmware-agent -f`; check device re-enumerated on ESXi; reattach USB if needed |
| No nodes found | Regional radio frequency/BW/SF/CR must match mesh; antenna; location/range; contact advertisements need time |
| Grafana empty | Wait for collector samples and messages; inspect PostgreSQL datasource and readonly `grafana_reader` grants |
| Login failure | Use web admin password from configuration; Grafana password is separate |
| VM snapshot | Snapshot before major changes, but also do real SQL backups; snapshots alone are not a database backup strategy |

## Development and validation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python3 -m compileall -q station firmware-agent
node --check static/app.js
```

The tests validate web authentication, CSRF, command queuing, firmware package validation, and simulation. Real radio, ESXi passthrough, Docker image availability, firmware updates, and RF delivery **must be tested on the VM**.

Licensed for your own deployment and modification. Upstream MeshCore and its SDK maintain their respective licenses.

### Optional retention cleanup

`sudo ./scripts/prune.sh 90` deletes **telemetry samples and non-message event logs** older than 90 days after explicit confirmation; it does **not** remove messages, contacts, or firmware logs. Docker container logs are rotated (`10 MB × 5` files/service). Review disk usage regularly with `df -h` and `docker system df`.
