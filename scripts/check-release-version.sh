#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
EXPECTED="${1:-0.8.4}"
ACTUAL="$(tr -d '\r\n' < VERSION)"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "VERSION is $ACTUAL, expected $EXPECTED" >&2; exit 1; }
[[ -f "RELEASE-$EXPECTED.md" ]] || { echo "Missing release notes" >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" README.md || { echo "README version mismatch" >&2; exit 1; }
grep -Fq "MeshCore $EXPECTED · USB Companion" static/index.html || { echo "UI version mismatch" >&2; exit 1; }
grep -Fq "MeshCore Station $EXPECTED" station/web.py || { echo "API title mismatch" >&2; exit 1; }
grep -Fq "'version': '$EXPECTED'" station/web.py || { echo "API version mismatch" >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" "RELEASE-$EXPECTED.md" || { echo "Release notes mismatch" >&2; exit 1; }
echo "Release version consistency: $EXPECTED ✓"
