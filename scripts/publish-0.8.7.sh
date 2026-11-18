#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) -ne 0 ]] || { echo 'Publish as your normal Linux Git user, not sudo.' >&2; exit 1; }
[[ "$(git branch --show-current)" == 'main' ]] || { echo 'Switch to local main before publishing.' >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.7
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo 'Unexpected Git remote; review before publishing.' >&2; exit 1; }
for file in station/worker.py station/tx_tracking.py station/radio_trends.py station/node_adverts.py; do
  [[ -s "$file" ]] || { echo "Required source dependency absent: $file" >&2; exit 1; }
done
for path in .env runtime backups; do
  if git ls-files -- "$path" | grep -q .; then echo "Private path already tracked: $path" >&2; exit 1; fi
done
# Unlike earlier versions, stage only 0.8.7 release files; don't require historical
# notes which a prior incremental installer may legitimately not have installed.
sha256sum --check --status RELEASE-0.8.7.sha256 || { echo '0.8.7 release file checksum mismatch. Stop.' >&2; exit 1; }
mapfile -t files < <(sed -n 's/^[0-9a-f]\{64\}  //p' RELEASE-0.8.7.sha256)
((${#files[@]})) || { echo 'Empty 0.8.7 publish list.' >&2; exit 1; }
for f in "${files[@]}"; do
  [[ "$f" != .env && "$f" != runtime/* && "$f" != backups/* ]] || { echo 'Private path in release list.' >&2; exit 1; }
done
# Fetch only; don't rewrite or overwrite the user's working tree.
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then
  echo 'GitHub main contains commits not present locally. Stop and reconcile without force-pushing.' >&2; exit 1
fi
remote_ver="$(git show origin/main:VERSION 2>/dev/null | tr -d '\r\n' || true)"
if [[ "$remote_ver" != '0.8.6' && "$remote_ver" != '0.8.7' ]]; then
  echo "GitHub main reports VERSION=${remote_ver:-missing}, expected 0.8.6 or 0.8.7. Publish/reconcile 0.8.6 first." >&2; exit 1
fi
# Don't accidentally bundle an unrelated pre-staged commit.
if ! git diff --cached --quiet; then
  echo 'Existing staged changes found. Review or unstage before publishing 0.8.7.' >&2; exit 1
fi
git add -- "${files[@]}" RELEASE-0.8.7.sha256 MANIFEST.sha256
if git diff --cached --name-only | grep -Eq '(^|/)(\.env$|runtime|backups)(/|$)'; then
  echo 'Private content staged: unstage it before publishing.' >&2; exit 1
fi
git diff --cached --check
printf '\nFiles staged for 0.8.7:\n'; git diff --cached --stat
printf '\nRepository status:\n'; git status --short
read -r -p 'Publish MeshCore Station 0.8.7 to GitHub main and tag v0.8.7? Type yes: ' answer
[[ "$answer" == yes ]] || { echo 'Cancelled; nothing pushed.'; exit 0; }
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.7 consistent channel names on Overview'; fi
remote_tag="$(git ls-remote origin 'refs/tags/v0.8.7^{}' | awk '{print $1}')"
if [[ -z "$remote_tag" ]]; then remote_tag="$(git ls-remote origin refs/tags/v0.8.7 | awk '{print $1}')"; fi
if [[ -n "$remote_tag" && "$remote_tag" != "$(git rev-parse HEAD)" ]]; then
  echo 'GitHub v0.8.7 tag points elsewhere. Stop; do not overwrite.' >&2; exit 1
fi
git push origin main
remote_sha="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$(git rev-parse HEAD)" == "$remote_sha" ]] || { echo 'Remote main does not match local HEAD; tag not pushed.' >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.7 >/dev/null; then
  [[ "$(git rev-list -n 1 v0.8.7)" == "$(git rev-parse HEAD)" ]] || { echo 'Local v0.8.7 tag points elsewhere.' >&2; exit 1; }
else
  git tag -a v0.8.7 -m 'MeshCore Station 0.8.7'
fi
git push origin v0.8.7
printf '\n0.8.7 published to GitHub main and tagged v0.8.7.\n'
