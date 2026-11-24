# MeshCore Station 0.8.9

## Radio Monitor readability

- Radio Uptime now displays **days, hours, and minutes** instead of raw seconds: `14,639 s` becomes `4h 3m`, and values above one day appear as `2d 7h 15m`.
- The historical uptime chart also displays duration-formatted vertical-axis labels while continuing to use actual measured seconds internally.
- Unknown or invalid uptime is displayed as an em dash, not an invented zero.
- The API, PostgreSQL metrics, Grafana data, collector timing and firmware continue to use their original numeric units. This is a presentation-only change to uptime.

## Consolidated fixes since the 0.8.8 tag

- Grafana navigation supports an optional `GRAFANA_PUBLIC_URL` configured only in the VM's protected `.env`, correctly linking through a separate HTTPS reverse proxy.
- Channel saves no longer require typed `SAVE CHANNEL` or a second JavaScript confirmation. The form displays progress and errors.
- New hashtag channels such as `#test` derive their standard shared key without typing it. Existing channel keys are preserved when omitted; new private channels still require an explicit shared key.
- The README prominently discloses that most development is AI-generated or AI-assisted.
- A non-secret `PROJECT_CONTEXT.md` and GitHub Actions regression tests support continuity and quality checks.

## Documentation retention

- Keep only `RELEASE-0.8.7.md`, `RELEASE-0.8.8.md`, and `RELEASE-0.8.9.md` in the current Git tree.
- Legacy v4–v7 and older numbered release-note documents are removed from the current tree, but remain accessible in Git commit history and previous release tags.
- GitHub releases, tags, database volumes, channel secrets and local configuration are not altered by documentation cleanup.
- Older publishing scripts and their checksum files are historical artifacts; use GitHub pull requests and the current deployment guide for new changes.

## Deployment and validation

- Review `git status --short` and back up before updating a deployed VM; retain the local `.env`.
- From a clean local `main` after the PR is merged: `git fetch origin && git pull --ff-only origin main`.
- Rebuild just the web API for this release's uptime display: `sudo docker compose up -d --build --no-deps api`.
- Hard-refresh the browser; confirm the Radio Monitor uptime is human-readable and messages, channel management and Grafana still work.
- The v0.8.9 changes themselves do not require radio firmware, collector, database, Grafana or other service restarts.
- GitHub Actions runs `PYTHONPATH=. pytest -q`, all `tests/*.cjs`, Node syntax, shell syntax and a placeholder-only Docker Compose configuration check.

**AI Development Disclosure:** Most project code and documentation were generated or developed with ChatGPT assistance under human direction. Review and test independently before deploying.
