#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
if [ "$(id -u)" -eq 0 ]; then echo 'Run as the ordinary Git user, not root.' >&2; exit 1; fi
[ "$(git branch --show-current)" = main ] || { echo 'Not on main.' >&2; exit 1; }
case "$(git remote get-url origin)" in
 https://github.com/mgw24/meshcore-station.git|https://github.com/mgw24/meshcore-station|git@github.com:mgw24/meshcore-station.git) ;;
 *) echo 'Unexpected GitHub remote; refusing push.' >&2; exit 1;;
esac
if ! git diff --cached --quiet; then echo 'Staged changes already exist; review them first.' >&2; exit 1; fi
files=(README.md MANIFEST.sha256 V6-RELEASE-NOTES.md station/routing.py station/web.py station/worker.py static/app.js static/index.html static/style.css scripts/publish-v6-release.sh)
for f in "${files[@]}"; do [ -f "$f" ] || { echo "Missing $f" >&2; exit 1; }; done
git add -- "${files[@]}"
git diff --cached --check
if git diff --cached --quiet; then echo 'No v6 changes to commit'; exit 0; fi
git diff --cached --stat
printf '
Please review staged diff for secrets before continuing.
'
read -r -p 'Type PUBLISH to commit and push to main: ' answer
[ "$answer" = PUBLISH ] || { echo 'Canceled; changes remain staged.'; exit 1; }
git commit -m 'MeshCore Station v6: Companion path hashes and region scopes'
git push origin main
printf 'Local: '; git rev-parse HEAD
printf 'Remote: '; git ls-remote origin refs/heads/main
