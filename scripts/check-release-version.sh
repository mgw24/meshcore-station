#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
EXPECTED="${1:-0.8.9}"
ACTUAL="$(tr -d '\r\n' < VERSION)"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "VERSION is $ACTUAL, expected $EXPECTED" >&2; exit 1; }
[[ -f "RELEASE-$EXPECTED.md" ]] || { echo 'Release notes missing' >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" README.md || { echo 'README version mismatch' >&2; exit 1; }
grep -Fq "# MeshCore Station $EXPECTED" "RELEASE-$EXPECTED.md" || { echo 'Release notes version mismatch' >&2; exit 1; }
grep -Fq "MeshCore $EXPECTED · USB Companion" static/index.html || { echo 'UI version mismatch' >&2; exit 1; }
grep -Fq "MeshCore Station $EXPECTED" station/web.py || { echo 'API title mismatch' >&2; exit 1; }
grep -Fq "'version': '$EXPECTED'" station/web.py || { echo 'API version mismatch' >&2; exit 1; }
grep -Fq '?v=089' static/index.html || { echo 'Static asset cache version mismatch' >&2; exit 1; }
for file in station/worker.py station/tx_tracking.py station/radio_trends.py station/node_adverts.py; do
 [[ -s "$file" ]] || { echo "Missing required collector source: $file" >&2; exit 1; }
done
grep -Fq 'id="history-sort"' static/index.html || { echo 'Archive sort missing' >&2; exit 1; }
grep -Fq 'id="history-destination" aria-label="Filter messages by channel"' static/index.html || { echo 'Channel filter missing' >&2; exit 1; }
grep -Fq 'HISTORY_SORTS' station/web.py || { echo 'Server-side sorting missing' >&2; exit 1; }
grep -Fq "before_channel" station/web.py || { echo 'Grouped history cursor missing' >&2; exit 1; }
grep -Fq 'function archiveCompare088' static/app.js || { echo 'Archive refresh sort missing' >&2; exit 1; }
grep -Fq 'function messageDisplaySender086(m)' static/app.js || { echo 'Shared sender resolver missing' >&2; exit 1; }
grep -Fq 'data-view="monitor"' static/index.html || { echo 'Radio Monitor nav missing' >&2; exit 1; }
if grep -Eq 'data-view="(health|diagnostics|telemetry)"' static/index.html; then echo 'Legacy monitor nav detected' >&2; exit 1; fi
echo "Release consistency: $EXPECTED OK"
