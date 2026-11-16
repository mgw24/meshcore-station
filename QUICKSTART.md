# Start here — MeshCore Station

**Recommended operating system:** Ubuntu Server 24.04 LTS Minimal, 2 vCPU, 4–8 GB RAM, 60 GB disk, private static IP. Existing VPN is the access path; no Tailscale.

## 1. Put this repository in GitHub

Extract the supplied ZIP on your Mac/PC and push the **contents** as a new repository named `meshcore-station`. Do **not** commit `.env`, private keys, backups, or firmware files. The zip contains no credentials.

Example from the folder containing `compose.yaml`:

```bash
git init
git add .
git commit -m "Initial MeshCore Station"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/meshcore-station.git
git push -u origin main
```

Create the empty private GitHub repo first. Substitute your own account/repo URL and authenticate using GitHub's supported methods.

## 2. Install on the clean Ubuntu VM

```bash
sudo apt update && sudo apt install -y git
sudo git clone https://github.com/YOUR-ACCOUNT/meshcore-station.git /opt/meshcore-station
cd /opt/meshcore-station
sudo ./scripts/install.sh
sudo ./scripts/start.sh
```

Use simulation mode first. The installer installs Docker, Compose, flashing utility, and OS packages, then prompts for web password and VM private IP. Grafana's separate password is printed once; save it.

## 3. Test without radio

Go to `http://VM_PRIVATE_IP:8088`, sign in, send a test channel message, check the demo contacts/graphs. Grafana: `http://VM_PRIVATE_IP:3300`.

## 4. Flash T114 USB Companion and pass through ESXi

Export settings from the currently paired iPhone first. On your Mac, download `Heltec_t114_companion_radio_usb*.uf2` from https://flasher.meshcore.io (verify correct device and role). Double-press RESET, copy UF2 to the USB bootloader drive, reconnect board to physical ESXi host. In vSphere, add host USB device to the VM. Ubuntu: `lsusb`, `ls -l /dev/ttyACM* /dev/serial/by-id/`.

## 5. Switch to physical radio

```bash
cd /opt/meshcore-station
sudo ./scripts/switch-to-radio.sh /dev/ttyACM0
sudo docker compose --profile radio logs -f collector
```

If the device has a persistent `/dev/serial/by-id/...` path, prefer it. Verify the dashboard reports USB SERIAL / Connected; refresh contacts and test sending. Do **not** run your old collector against the same USB radio.

## 6. Update firmware from browser

In Firmware Manager, upload the exact **T114 Companion USB Nordic DFU ZIP** from official flasher. It will stop the collector, flash, and restart. The **web application stays up**. Test re-enumeration on your ESXi host before relying on this; if ESXi detaches the bootloader, use vSphere to reattach and recover manually via UF2 if needed.

For full troubleshooting, ports, HTTPS/security, backups, notifications, and source references, see `README.md`.
