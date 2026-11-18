#!/usr/bin/env bash
# Publish only files belonging to this v5 combined release.
# Run as the unprivileged meshcore user after verifying production.
set -euo pipefail
REPO=/opt/meshcore-station
cd "$REPO"
if [ "$(id -u)" -eq 0 ]; then echo 'Run as the regular meshcore user, not root/sudo.' >&2; exit 1; fi
if [ "$(git branch --show-current)" != main ]; then echo 'Expected main branch.' >&2; exit 1; fi
REMOTE=$(git remote get-url origin)
case "$REMOTE" in
 https://github.com/mgw24/meshcore-station.git|https://github.com/mgw24/meshcore-station|git@github.com:mgw24/meshcore-station.git|ssh://git@github.com/mgw24/meshcore-station.git) ;;
 *) echo "Unexpected origin remote: $REMOTE" >&2; exit 1;;
esac
if ! git diff --cached --quiet; then
  echo 'The Git staging area already has changes. Review/unstage them before this release.' >&2
  git diff --cached --name-only
  exit 1
fi
FILES=(
  compose.yaml .env.example README.md QUICKSTART.md V5-RELEASE-NOTES.md
  V5-COMBINED-RELEASE.md MANIFEST.sha256
  station/db.py station/web.py station/digest.py station/digest_worker.py
  static/index.html static/app.js static/style.css
  scripts/deploy-production.sh scripts/enable-digests.sh scripts/start.sh scripts/install.sh
  scripts/publish-v5-release.sh
  grafana/dashboards/station.json grafana/provisioning/dashboards/dashboards.yml
  GRAFANA-REFRESH-NOTES.md
)
for file in "${FILES[@]}"; do [ -f "$file" ] || { echo "Missing release file: $file" >&2; exit 1; }; done
git add -- "${FILES[@]}"
if git diff --cached --quiet; then echo 'No new release changes to commit.'; exit 0; fi
STAGED=$(git diff --cached --name-only)
if printf '%s\n' "$STAGED" | grep -Ei '(^|/)(\.env$|runtime/|backups/)|\.sql(\.gz)?$|\.db$|\.sqlite$|\.zip$|\.tar(\.gz)?$'; then
  echo 'Potential secret/runtime file staged. Aborting.' >&2; exit 1
fi
git diff --cached --check
printf '\nFiles staged for v5 combined release:\n%s\n' "$STAGED"
printf '\nSummary:\n'
git diff --cached --stat
printf '\nReview all staged file content for secrets before proceeding.\n'
read -r -p 'Type PUBLISH to commit and push this release to GitHub: ' answer
[ "$answer" = PUBLISH ] || { echo 'Not published. Staged files remain for review.'; exit 1; }
git commit -m 'MeshCore Station v5: email digests and Grafana operations dashboard'
git push origin main
printf '\nLocal commit: '; git rev-parse HEAD
printf 'Remote main: '; git ls-remote origin refs/heads/main
printf '\nRemaining local changes:\n'; git status --short
