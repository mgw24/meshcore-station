# MeshCore Station 0.8.8 — Quality validation

The release is based on the 0.8.7 full-source archive, matching the GitHub release baseline at the start of the build. No physical T114 or user's running VM was modified during development.

Validation:

- Run `PYTHONPATH=. pytest -q` to cover API history filters, all four sort modes, cursor pagination (including channel boundaries and tied timestamps), CSV export, message reply behavior, radio health, and existing services.
- Run `for file in tests/*.cjs; do node "$file"; done` for channel labels, sorting controls, and reply behavior.
- Run `node --check static/app.js` and `bash -n scripts/*.sh` for syntax.
- Browser smoke at desktop and 390px phone width: channel name option, combined channel/sort request parameters, message expansion, and no horizontal overflow.
- Verify ZIP integrity and sha256 manifests before installation.

After installation, check the filter using channels 0 and 5, sort in both channel directions, load an older page, and verify normal transmit and reply behaviors. The collector, database and Grafana are unchanged by this release.
