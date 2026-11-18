#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
EXPECTED="${1:-0.8.7}"
ACTUAL="$(tr -d '\r\n' < VERSION)"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "VERSION is $ACTUAL, expected $EXPECTED" >&2; exit 1; }
[[ -f "RELEASE-$EXPECTED.md" ]] || { echo "Missing release notes" >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" README.md || { echo "README version mismatch" >&2; exit 1; }
grep -Fq "MeshCore $EXPECTED · USB Companion" static/index.html || { echo "UI version mismatch" >&2; exit 1; }
grep -Fq "MeshCore Station $EXPECTED" station/web.py || { echo "API title mismatch" >&2; exit 1; }
grep -Fq "'version': '$EXPECTED'" station/web.py || { echo "API version mismatch" >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" "RELEASE-$EXPECTED.md" || { echo "Release notes mismatch" >&2; exit 1; }
grep -Fq 'data-view="monitor"' static/index.html || { echo "Monitor nav missing" >&2; exit 1; }
if grep -Eq 'data-view="(health|diagnostics|telemetry)"' static/index.html; then echo 'Legacy monitor navigation still visible' >&2; exit 1; fi
for file in station/tx_tracking.py station/radio_trends.py station/node_adverts.py; do
  [[ -f "$file" ]] || { echo "Missing required 0.8.4 dependency: $file" >&2; exit 1; }
done
# Archive labels must resolve channel names from live status, never hard-code slot titles.
grep -Fq 'function channelName086(target)' static/app.js || { echo 'Channel name resolver missing' >&2; exit 1; }
grep -Fq 'const author=messageDisplaySender086(m)' static/app.js || { echo 'Shared channel sender resolver missing from archive' >&2; exit 1; }
grep -Fq 'function messageHeading(m){const node=messageDisplaySender086(m)' static/app.js || { echo 'Overview channel resolver missing' >&2; exit 1; }
grep -Fq 'function messageDisplaySender086(m)' static/app.js || { echo 'Shared Overview/archive label resolver missing' >&2; exit 1; }
grep -Fq '?v=087' static/index.html || { echo 'App cache-buster not bumped' >&2; exit 1; }
echo "Release consistency: $EXPECTED OK"
