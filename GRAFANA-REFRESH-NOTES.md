# MeshCore Station — Grafana operations dashboard refresh

This is the **Grafana component** of the combined v5 email digest and dashboard update. Follow [V5-COMBINED-RELEASE.md](V5-COMBINED-RELEASE.md) for the unified installation procedure; the Grafana-only steps below are for manual recovery or independent deployment. It does not change the T114, API, collector, firmware, PostgreSQL schema, user credentials, email scheduler, or Grafana datasource UIDs.

## Highlights

- Six compact health cards: radio link, RX/TX counters, noise floor, known nodes, open alerts.
- Reset-aware **packet count per time bucket**, not Prometheus `rate()` on application gauges. Samples that imply a reboot or an excessively long gap are excluded from delta calculations.
- RX errors shown as both counts and an error-share percentage; no-traffic periods are left unknown instead of fabricated as 0%.
- Donut breakdowns for flood/direct RX and TX, with explicit **since boot** labeling.
- Signal profile shows noise floor and last RSSI in dBm; SNR, when available, is on its own dB axis.
- Appropriate stat tiles for uptime and telemetry age, including stale-telemetry warning thresholds.
- Real messaging charts, most-active-channel bars, an all-time outcome donut, and recent-message table. Historical simulator messages are filtered.
- Node-role bar chart, recent contact inventory, and an RX activity table that **distinguishes decoded events from sampled counter changes**.
- Dense 24-column layout with continuous sections and no duplicated noise-floor panels or inactive battery charts.
- Teal RX, amber TX, red errors, purple nodes/route detail, blue signal/message-received. Colors are decorative group cues, not quality guarantees.

## Upgrade safely

From the VM after copying `meshcore-grafana-operations-patch.zip` to `/tmp`:

```bash
cd /opt/meshcore-station
sudo cp -a grafana/dashboards/station.json /tmp/meshcore-station-grafana-before-refresh.json
sudo unzip -o /tmp/meshcore-grafana-operations-patch.zip -d /opt/meshcore-station
sudo docker compose config --quiet
sudo docker compose restart grafana
sudo docker compose logs --tail=50 grafana
```

Visit `http://<VM-IP>:3300` and open **Dashboards → MeshCore → MeshCore Station · Radio Operations**. It keeps the same UID (`meshcore-station`), so bookmarked dashboard URLs remain stable. The file provisioner scans every 30 seconds; restart forces a fresh load. Grafana remains read-only with regard to provisioned dashboards.

If you're not yet using v5, this dashboard only relies on tables and metrics already present in the v4 production schema (`samples`, `messages`, `contacts`, `alerts`, `rx_activity`).

### Validate after installation

1. All six health cards load (or show **No data** if a measurement is truly missing).
2. RX and TX counters match the MeshCore radio-health page.
3. TX flood count changes after a Public channel send, when a new sample arrives.
4. Change time range (Last 1h / 24h / 7d); packet bars should not spike after a radio restart.
5. Messages are real and do not contain the historic `Demo Relay` entries.
6. Check the latest RX activity table: `Counter interval` rows must not be presented as identified frames.
7. If a panel shows **No data**: use **Inspect → Query** and verify datasource/SQL; true absence of messages or SNR is not an error.

### Roll back

```bash
cd /opt/meshcore-station
sudo cp /tmp/meshcore-station-grafana-before-refresh.json grafana/dashboards/station.json
sudo docker compose restart grafana
```

If you do not keep the `/tmp` backup through a VM reboot, store an additional backup in your secure VM backup location. No volume deletion is required.

## Important reporting limitations

- Channel `sent` is radio acceptance only; delivery and repeater retransmission are not assured.
- Counter values reset on radio reboot; their deltas explicitly discard negative changes and intervals over 10 minutes, rather than falsely charting massive bursts.
- RX signal readings may be *last seen* rather than a continuously measured signal; the dashboard labels these accordingly.
- Raw RF reception is not available for every packet through the MeshCore Companion SDK. The RX activity log will show sampled counter changes and only identifiable decoded events the SDK actually emitted.
- This dashboard includes no battery widgets because this T114 is USB-powered without a battery.

## Editing in GitHub

If your repository tracks `MANIFEST.sha256`, refresh the hashes for the changed Grafana files before committing. You can run:

```bash
cd /opt/meshcore-station
python3 -c 'from pathlib import Path; import hashlib; p=Path("MANIFEST.sha256"); lines=p.read_text().splitlines(); files={"grafana/dashboards/station.json","grafana/provisioning/dashboards/dashboards.yml"}; p.write_text("\n".join((hashlib.sha256(Path(s.split("  ",1)[1]).read_bytes()).hexdigest()+"  "+s.split("  ",1)[1]) if "  " in s and s.split("  ",1)[1] in files else s for s in lines)+"\n")'
```

These two JSON/YAML files are safe to commit. Do **not** commit `.env`, any SMTP credentials, runtime folders, or database dumps. Changes to provisioned Grafana dashboards should be made in JSON, not via Grafana's Save button.
