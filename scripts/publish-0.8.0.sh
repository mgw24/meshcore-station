#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
[[ "$(git branch --show-current)" == main ]] || { echo "Expected main branch"; exit 1; }
if git diff --quiet -- .env 2>/dev/null; then :; fi
if git ls-files --error-unmatch .env >/dev/null 2>&1; then echo 'ERROR: .env tracked in Git'; exit 1; fi
git add -A
if git diff --cached --name-only | grep -Eq '(^|/)(runtime|backups|\.env)(/|$)'; then echo 'ERROR: private paths staged'; exit 1; fi
git diff --cached --check
git diff --cached --stat
read -r -p 'Commit and push 0.8.0 to origin/main? Type yes: ' answer
[[ "$answer" == yes ]] || exit 1
git commit -m 'MeshCore Station 0.8.0 radio diagnostics'
git push origin main
git tag -a v0.8.0 -m 'MeshCore Station 0.8.0' || true
git push origin v0.8.0
printf '\nLocal: '; git rev-parse HEAD
printf 'Remote: '; git ls-remote origin refs/heads/main
