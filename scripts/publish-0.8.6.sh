#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) -ne 0 ]] || { echo 'Publish as your normal Git user; do not use sudo.' >&2; exit 1; }
[[ $(git branch --show-current) == main ]] || { echo 'Switch to main before publishing.' >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.6
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo 'Unexpected origin: review Git remote.' >&2; exit 1; }
for file in station/worker.py station/tx_tracking.py station/radio_trends.py station/node_adverts.py; do
  [[ -s "$file" ]] || { echo "Required collector module missing: $file. Repair 0.8.4 first." >&2; exit 1; }
done
for path in .env runtime backups; do
  if git ls-files -- "$path" | grep -q .; then echo "Private path already tracked: $path. Aborting." >&2; exit 1; fi
done
# Refuse remote divergence. Fetch does not alter working files.
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then
  echo 'GitHub main contains work absent from local main. Stop and reconcile changes; never force-push.' >&2
  exit 1
fi
# Source-only whitelist built from this release's SHA-256 manifest; no runtime or private data.
mapfile -t files < <(sed -n 's/^[0-9a-f]\{64\}  //p' MANIFEST.sha256)
((${#files[@]})) || { echo 'Empty release manifest.' >&2; exit 1; }
for file in "${files[@]}"; do
  [[ -f "$file" ]] || { echo "Manifest file missing: $file" >&2; exit 1; }
  if [[ "$file" == .env || "$file" == runtime/* || "$file" == backups/* ]]; then
    echo "Private path in release manifest: $file" >&2; exit 1
  fi
done
sha256sum --check --status MANIFEST.sha256 || { echo 'Full-source manifest mismatch.' >&2; exit 1; }
git add -- "${files[@]}" MANIFEST.sha256
if git diff --cached --name-only | grep -Eq '(^|/)(\.env$|runtime|backups)(/|$)'; then
  echo 'Private content staged: unstage it before publishing.' >&2; exit 1
fi
git diff --cached --check
printf '\nFiles staged for 0.8.6:\n'; git diff --cached --stat
printf '\nRepository status:\n'; git status --short
read -r -p 'Publish MeshCore Station 0.8.6 to GitHub main and tag v0.8.6? Type yes: ' answer
[[ "$answer" == yes ]] || { echo 'Cancelled. Nothing pushed.'; exit 0; }
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.6 channel names in message history'; fi
# Before touching remote, reject an existing remote tag at a different commit.
remote_tag="$(git ls-remote origin 'refs/tags/v0.8.6^{}' | awk '{print $1}')"
if [[ -z "$remote_tag" ]]; then remote_tag="$(git ls-remote origin refs/tags/v0.8.6 | awk '{print $1}')"; fi
if [[ -n "$remote_tag" && "$remote_tag" != "$(git rev-parse HEAD)" ]]; then
  echo 'GitHub v0.8.6 tag exists at a different commit. Stop; do not overwrite tags.' >&2; exit 1
fi
git push origin main
remote_sha="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$(git rev-parse HEAD)" == "$remote_sha" ]] || { echo 'Remote main did not match pushed commit; no tag created.' >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.6 >/dev/null; then
  [[ "$(git rev-list -n 1 v0.8.6)" == "$(git rev-parse HEAD)" ]] || { echo 'Local v0.8.6 tag differs; no tag pushed.' >&2; exit 1; }
else
  git tag -a v0.8.6 -m 'MeshCore Station 0.8.6'
fi
git push origin v0.8.6
printf '\nMeshCore Station 0.8.6 published to origin/main and tagged v0.8.6.\n'
