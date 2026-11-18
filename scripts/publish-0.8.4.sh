#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) -ne 0 ]] || { echo 'Run without sudo.' >&2; exit 1; }
[[ $(git branch --show-current) == main ]] || { echo 'Switch to main.' >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.4
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo 'Unexpected Git remote.' >&2; exit 1; }
for path in .env runtime backups; do if git ls-files -- "$path" | grep -q .; then echo "Private path tracked: $path" >&2; exit 1; fi; done
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then echo 'Remote main has commits not in this branch; integrate before publishing. No force push.' >&2; exit 1; fi
files=(VERSION README.md RELEASE-0.8.4.md MANIFEST.sha256 scripts/check-release-version.sh scripts/publish-0.8.4.sh
  station/web.py station/worker.py station/tx_tracking.py station/radio_trends.py station/node_adverts.py
  static/index.html static/app.js static/style.css grafana/dashboards/station.json
  tests/test_radio_trends_084.py tests/test_node_adverts_084.py)
for file in "${files[@]}"; do [[ -f "$file" ]] || { echo "Missing $file" >&2; exit 1; }; done
git add -- "${files[@]}"
if git diff --cached --name-only | grep -E '(^|/)(\.env|runtime|backups)(/|$)'; then echo 'Secrets staged: aborting' >&2; exit 1; fi
git diff --cached --check
git diff --cached --stat
read -r -p 'Publish 0.8.4 to origin/main? Type yes: ' answer
[[ $answer == yes ]] || exit 0
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.4 radio health and advertisements'; fi
git push origin main
[[ $(git rev-parse HEAD) == $(git ls-remote origin refs/heads/main | awk '{print $1}') ]] || { echo 'Remote mismatch' >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.4 >/dev/null; then
  [[ $(git rev-list -n 1 v0.8.4) == $(git rev-parse HEAD) ]] || { echo 'Tag v0.8.4 points to another commit' >&2; exit 1; }
else git tag -a v0.8.4 -m 'MeshCore Station 0.8.4'; fi
git push origin v0.8.4
