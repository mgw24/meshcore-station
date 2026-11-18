#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(id -u)" -ne 0 ]] || { echo "Do not publish with sudo." >&2; exit 1; }
[[ "$(git branch --show-current)" == main ]] || { echo "Switch to the main branch first." >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.3
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo "Unexpected origin remote; review it before publishing." >&2; exit 1; }
if git ls-files --error-unmatch .env >/dev/null 2>&1; then echo "ERROR: private .env is tracked" >&2; exit 1; fi
if git status --porcelain=v1 | grep -E '^(.. )?(\.env($|/)|runtime/|backups/)' ; then echo "WARNING: private files appear in Git status. Review .gitignore." >&2; exit 1; fi
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then
  echo "Remote main has commits not included locally. Push refused (no force-push)." >&2
  echo "Review: git log --oneline --left-right HEAD...origin/main" >&2
  echo "Integrate remote changes before re-running this publisher." >&2
  exit 1
fi
files=(README.md RELEASE-0.8.3.md VERSION MANIFEST.sha256 station/web.py static/index.html static/app.js scripts/check-release-version.sh scripts/publish-0.8.3.sh tests/test_messages_compact_ui.py tests/test_reply_mention_083.cjs)
for f in "${files[@]}"; do [[ -f "$f" ]] || { echo "Missing $f" >&2; exit 1; }; done
git add -- "${files[@]}"
if git diff --cached --name-only | grep -Eq '(^|/)(runtime|backups|\.env)(/|$)'; then echo "ERROR: secrets staged" >&2; exit 1; fi
git diff --cached --check
git diff --cached --stat
read -r -p 'Commit and push MeshCore Station 0.8.3 to origin/main? Type yes: ' answer
[[ "$answer" == yes ]] || { echo 'Publish cancelled'; exit 1; }
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.3 channel reply mention hotfix'; else echo 'No new changes to commit'; fi
git push origin main
remote="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
local="$(git rev-parse HEAD)"
[[ "$remote" == "$local" ]] || { echo "Remote mismatch after push" >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.3 >/dev/null; then
  [[ "$(git rev-list -n 1 v0.8.3)" == "$local" ]] || { echo "v0.8.3 tag points to a different commit" >&2; exit 1; }
else git tag -a v0.8.3 -m 'MeshCore Station 0.8.3'; fi
git push origin v0.8.3
printf 'Published %s (v0.8.3)\n' "$local"
