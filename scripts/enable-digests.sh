#!/usr/bin/env bash
# Safe, idempotent upgrade: creates a separate SMTP encryption key in .env.
set -euo pipefail
cd /opt/meshcore-station
[[ -f .env ]] || { echo 'Missing .env; run the normal installer first' >&2; exit 1; }
if ! grep -q '^DIGEST_ENCRYPTION_KEY=.' .env; then
  # An empty placeholder does not count as a configured key.
  sed -i '/^DIGEST_ENCRYPTION_KEY=$/d' .env
  KEY=$(python3 - <<'PY'
import os,base64
print(base64.urlsafe_b64encode(os.urandom(32)).decode('ascii'))
PY
)
  printf '\nDIGEST_ENCRYPTION_KEY=%s\n' "$KEY" >> .env
  echo 'New digest encryption key saved in .env.'
else
  echo 'Existing digest encryption key retained.'
fi
chmod 0600 .env
printf 'IMPORTANT: Back up .env securely; losing the key makes the stored SMTP password unrecoverable.\n'
