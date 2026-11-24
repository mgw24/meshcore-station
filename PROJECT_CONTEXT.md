# MeshCore Station — project context

This file is a durable, non-secret reference for future development sessions.
Use the repository's `VERSION` and latest release notes as the source of truth,
not examples or older instructions.

## System

- Heltec T114 V2 running MeshCore USB Companion firmware, connected to an Ubuntu
  VM using USB serial.
- Docker Compose stack: `api`, serial-owning `collector`, PostgreSQL `db`,
  `grafana`, `prometheus`, and `digest`.
- FastAPI backend: `station/web.py`; worker: `station/worker.py`.
- Browser UI: `static/index.html`, `static/app.js`, `static/style.css`.
- Production configuration: local `.env` file, **never committed**.
- Application port defaults to 8088 on a configured bind IP; internal app port is
  8000. Grafana host port defaults to 3300 and internal port is 3000.
- The collector is the only process using the serial device. Web APIs enqueue
  commands; do not add a second radio reader.
- PostgreSQL and Grafana use named Docker volumes; preserve them on upgrades.

## Current baseline and feature history

- 0.8.7: Overview shows named channels rather than generic `channel` senders.
- 0.8.8: Full-archive channel filtering and global channel/date sorting;
  safer CSV export, stable pagination, and startup lifespan cleanup.
- 0.8.9: Human-readable radio uptime, three-recent-release-note retention,
  and the prior Grafana/channel-management fixes consolidated into a release.
- Tests: `PYTHONPATH=. pytest -q` and `for f in tests/*.cjs; do node "$f"; done`.
- Browser assets have versioned query parameters in `static/index.html`.
  Change the cache key whenever JavaScript or CSS changes in a release.

## Reverse proxy and Grafana

- The application can be published through an existing HTTPS reverse proxy.
- Configure `GRAFANA_PUBLIC_URL` in **local** `.env` to the separate external
  Grafana reverse-proxy address (e.g. `https://grafana.example.net`).
- The application navigation uses the explicit Grafana URL when supplied.
  Grafana's `GF_SERVER_ROOT_URL` is also aligned to this value by Compose.
- If unset, the interface falls back to the accessed hostname and local Grafana
  port. That fallback may not work from outside a private network.
- A separate proxy host/route must actually forward to Grafana; setting a URL
  does not create the proxy route or make Grafana publicly reachable.
- Secure external access with appropriate proxy authentication/access controls.

## Safe release workflow

1. Read latest source and release notes before editing.
2. Branch from `main`; do not overwrite a running deployment or push secrets.
3. Keep changes narrowly scoped. Add tests and a reviewable pull request.
4. Run Python/Node tests, syntax checks and Docker Compose validation on a
   suitable machine before merging.
5. Confirm `.env`, node coordinates, message history, API credentials,
   private keys, SMTP credentials, and local backups are not committed.
6. Back up before deploying; deploy only with the local protected `.env`.
7. Validate messaging, collector health, channel names and Grafana after rollout.

## Important constraints

- USB Companion firmware does **not** turn the T114 into a mesh repeater.
- RF send acceptance is not proof of delivery.
- Never store or publish channel secrets or private messaging payloads in logs.
- Avoid hardcoding a private individual's hostnames, IPs or identity in source.
- Published repository may be public: assume all committed text is world-readable.
- Direct GitHub integration is not access to the user's VM or Portainer.
