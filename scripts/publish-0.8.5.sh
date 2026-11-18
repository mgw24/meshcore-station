#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) -ne 0 ]] || { echo 'Run as regular Git user, not sudo.' >&2; exit 1; }
[[ $(git branch --show-current) == main ]] || { echo 'Switch to main before publishing.' >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.5
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo 'Unexpected Git remote.' >&2; exit 1; }
# Do not publish while missing the repaired 0.8.4 collector dependency.
for file in station/worker.py station/tx_tracking.py station/radio_trends.py station/node_adverts.py; do
  [[ -s "$file" ]] || { echo "Required collector file missing: $file" >&2; exit 1; }
done
for path in .env runtime backups; do
  if git ls-files -- "$path" | grep -q .; then echo "Private path tracked: $path" >&2; exit 1; fi
done
# Always check ancestry before staging and never force push.
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then
  echo 'GitHub main contains commits not in local main. Stop and integrate them first. No force push.' >&2; exit 1
fi
# Whitelist repository source. Never include .env, runtime/ or database dumps.
git add -- VERSION README.md QUICKSTART.md RELEASE-0.8.5.md MANIFEST.sha256 \
  .dockerignore .gitignore .env.example Dockerfile compose.yaml requirements.txt \
  station/ static/ scripts/ tests/ grafana/ prometheus/ firmware-agent/
if git diff --cached --name-only | grep -Eq '(^|/)(\.env$|runtime|backups)(/|$)'; then
  echo 'Unexpected private path staged. Inspect with git diff --cached --name-only and unstage it.' >&2; exit 1
fi
git diff --cached --check
printf '\nFiles to publish:\n'; git diff --cached --stat
printf '\nRepository status:\n'; git status --short
read -r -p 'Publish MeshCore Station 0.8.5 to origin/main? Type yes: ' answer
[[ "$answer" == yes ]] || { echo 'Cancelled: no push.'; exit 0; }
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.5 consolidated Radio Monitor'; fi
git push origin main
remote_sha="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$(git rev-parse HEAD)" == "$remote_sha" ]] || { echo 'Remote HEAD mismatch; do not tag.' >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.5 >/dev/null; then
  [[ "$(git rev-list -n 1 v0.8.5)" == "$(git rev-parse HEAD)" ]] || { echo 'v0.8.5 tag exists at a different commit. Stop.' >&2; exit 1; }
else
  git tag -a v0.8.5 -m 'MeshCore Station 0.8.5'
fi
git push origin v0.8.5
printf '\nGitHub 0.8.5 main and tag updated successfully.\n'
