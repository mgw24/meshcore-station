# MeshCore Station v3 — Upgrade checklist

Source: https://github.com/mgw24/meshcore-station

**Production-only:** no simulator service, no test/demo fixtures. Preserves the real radio configuration, PostgreSQL messages, Grafana data and existing VM `.env`.

```bash
cd /opt/meshcore-station
sudo ./scripts/backup.sh
sudo tar -czf /tmp/meshcore-pre-v3-source.tgz --exclude=runtime --exclude=.git .
```

Copy `meshcore-station-production-v3.zip` to `/tmp/` on the Ubuntu VM. Then:

```bash
sudo apt-get install -y unzip
sudo unzip -o /tmp/meshcore-station-production-v3.zip -d /opt/
cd /opt/meshcore-station
sudo chmod +x scripts/*.sh
sudo ./scripts/deploy-production.sh
sudo docker compose restart grafana
sudo docker compose ps
sudo docker compose logs --tail=60 collector
```

Clean out old demo data **only after previewing and confirming it is safe**:

```bash
sudo ./scripts/remove-simulation-data.sh --preview
sudo ./scripts/remove-simulation-data.sh --apply
```

The cleanup command creates a fresh SQL backup before deleting matched simulation data. It does **not** remove live radio contacts, normal messages, channel settings, or firmware history.

Open the station at `http://VM-IP:8088`; Grafana remains at `http://VM-IP:3300`.

Check **Radio Health**, **Channels**, **Nodes & Contacts**, **Node Map**, **Messages**, and **Grafana**. Hard refresh Firefox after deploying. Mobile layout works over the existing VPN; no Tailscale is required. In the map, no coordinates means no plotted node, even if RX packets are increasing.

To publish the code to GitHub, extract the ZIP into your **cloned GitHub working copy**, review changed files, and commit/push to `https://github.com/mgw24/meshcore-station`. See the full README for commands. The package does not automatically push or overwrite your GitHub repository.
