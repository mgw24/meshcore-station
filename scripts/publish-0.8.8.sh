#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) -ne 0 ]] || { echo 'Publish as your normal Linux Git user, not sudo.' >&2; exit 1; }
[[ "$(git branch --show-current)" == main ]] || { echo 'Switch to local main before publishing.' >&2; exit 1; }
bash scripts/check-release-version.sh 0.8.8
[[ "$(git remote get-url origin)" == *github.com/mgw24/meshcore-station* ]] || { echo 'Unexpected Git remote.' >&2; exit 1; }
for path in .env runtime backups; do
 if git ls-files -- "$path" | grep -q .; then echo "Private path tracked in Git: $path" >&2; exit 1; fi
done
# 0.8.8 checks only files changed by this release. No historic release-note manifest needed.
sha256sum --check --status RELEASE-0.8.8.sha256 || { echo 'Release checksum mismatch. Stop.' >&2; exit 1; }
mapfile -t files < <(sed -n 's/^[0-9a-f]\{64\}  //p' RELEASE-0.8.8.sha256)
((${#files[@]})) || { echo 'Empty release file list.' >&2; exit 1; }
for file in "${files[@]}"; do
 [[ -f "$file" && "$file" != .env && "$file" != runtime/* && "$file" != backups/* ]] || { echo "Unsafe or missing release file: $file" >&2; exit 1; }
done
# Fetch, but do not change the VM's working tree.
git fetch origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || {
 echo 'Local main and origin/main differ. Stop and reconcile; never force-push.' >&2; exit 1;
}
remote_ver="$(git show origin/main:VERSION 2>/dev/null | tr -d '\r\n' || true)"
[[ "$remote_ver" == 0.8.7 || "$remote_ver" == 0.8.8 ]] || {
 echo "GitHub reports VERSION=${remote_ver:-missing}; expected 0.8.7/0.8.8." >&2; exit 1;
}
if git ls-remote --tags origin v0.8.8 | grep -q .; then
 echo 'Remote v0.8.8 tag already exists. Review before retrying; no tag overwrite.' >&2; exit 1
fi
if ! git diff --cached --quiet; then echo 'Pre-staged files found. Stop and review.' >&2; exit 1; fi
# Make sure a prior hotfix wasn't left as a working-tree edit outside the published release.
unknown="$(git status --porcelain --untracked-files=no | awk '{print $2}' | while read -r p; do
  keep=no;for f in "${files[@]}"; do [[ "$p" == "$f" ]] && keep=yes; done
  [[ "$keep" == yes ]] || printf '%s\n' "$p"
done)"
[[ -z "$unknown" ]] || { printf 'Unrelated tracked edits, review before publishing:\n%s\n' "$unknown" >&2; exit 1; }
git add -- "${files[@]}" RELEASE-0.8.8.sha256
if git diff --cached --name-only | grep -Eq '(^|/)(\.env$|runtime|backups)(/|$)'; then
 echo 'Private file staged. Stop.' >&2; exit 1
fi
git diff --cached --check
printf '\n0.8.8 staged changes:\n';git diff --cached --stat
read -r -p 'Publish MeshCore Station 0.8.8 to GitHub main and tag v0.8.8? Type yes: ' answer
[[ "$answer" == yes ]] || { echo 'Cancelled; nothing pushed.'; exit 0; }
if ! git diff --cached --quiet; then git commit -m 'MeshCore Station 0.8.8 quality release and channel history sort'; fi
git push origin main
remote_sha="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$remote_sha" == "$(git rev-parse HEAD)" ]] || { echo 'Remote main did not match local HEAD. Tag not pushed.' >&2; exit 1; }
if git rev-parse -q --verify refs/tags/v0.8.8 >/dev/null; then
 [[ "$(git rev-list -n 1 v0.8.8)" == "$(git rev-parse HEAD)" ]] || { echo 'Local tag differs. Stop.' >&2; exit 1; }
else
 git tag -a v0.8.8 -m 'MeshCore Station 0.8.8'
fi
git push origin v0.8.8
printf '\n0.8.8 published to GitHub main and tagged v0.8.8.\n'
