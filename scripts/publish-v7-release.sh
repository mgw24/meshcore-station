#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[ "$(git branch --show-current)" = main ] || { echo 'Not on main'; exit 1; }
[ "$(git remote get-url origin)" = 'https://github.com/mgw24/meshcore-station.git' ] || { echo 'Unexpected origin'; exit 1; }
for f in station/db.py station/worker.py station/web.py station/tx_tracking.py station/digest.py station/digest_worker.py static/app.js static/index.html static/style.css tests/test_tx_tracking.py tests/test_smtp_probe.py V7-RELEASE-NOTES.md README.md MANIFEST.sha256 scripts/publish-v7-release.sh; do
  git add -- "$f"
done
git diff --cached --check
echo 'Staged files:'; git diff --cached --name-only
if git diff --cached --name-only | grep -Eq '(^|/)(\.env|runtime|backups|.*secret)'; then
  echo 'Refusing to stage secrets or runtime files' >&2; exit 1
fi
read -rp 'Commit and push reviewed v7 changes to main? (yes/no): ' confirm
[ "$confirm" = yes ] || { echo 'Nothing published'; exit 0; }
git commit -m 'MeshCore Station v7: TX evidence and SMTP diagnostics'
git push origin main
printf 'Local: '; git rev-parse HEAD
printf 'Remote: '; git ls-remote origin refs/heads/main
