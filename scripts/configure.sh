#!/usr/bin/env bash
set -euo pipefail
cd /opt/meshcore-station
if [ -e .env ]; then echo 'Existing .env found; refusing to overwrite secrets.'; exit 1; fi
read -rp 'Ubuntu VM private IP reachable over your VPN [127.0.0.1]: ' BIND_IP
BIND_IP=${BIND_IP:-127.0.0.1}
if ! [[ "$BIND_IP" =~ ^[0-9.]+$ ]]; then echo 'Use an IPv4 address (not a hostname).'; exit 1; fi
read -rp 'T114 serial device [/dev/ttyACM0] (can change later): ' RADIO_DEVICE
RADIO_DEVICE=${RADIO_DEVICE:-/dev/ttyACM0}
if [[ "$RADIO_DEVICE" != /dev/* ]]; then echo 'Expected an absolute /dev/... path'; exit 1; fi
read -rp 'Web admin username [admin]: ' ADMIN_USERNAME
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
if ! [[ "$ADMIN_USERNAME" =~ ^[a-zA-Z0-9_-]{3,32}$ ]]; then echo 'Username must be 3-32 alphanumeric/_/- characters'; exit 1; fi
while true; do
  read -rsp 'Choose web admin password (at least 12 characters): ' PASSWORD; echo
  [ "${#PASSWORD}" -ge 12 ] && break
  echo 'Use at least 12 characters.'
done
export PASSWORD
python3 - "$BIND_IP" "$RADIO_DEVICE" "$ADMIN_USERNAME" <<'PY'
import os,sys,hashlib,secrets
ip,dev,user=sys.argv[1:]
pw=os.environ['PASSWORD']
salt=secrets.token_hex(16)
digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),260000).hex()
values={'POSTGRES_USER':'meshcore','POSTGRES_DB':'meshcore','POSTGRES_PASSWORD':secrets.token_hex(24),
'GRAFANA_DB_PASSWORD':secrets.token_hex(24),'GRAFANA_ADMIN_PASSWORD':secrets.token_urlsafe(24),
'ADMIN_USERNAME':user,'ADMIN_PASSWORD_SALT':salt,'ADMIN_PASSWORD_HASH':digest,
'SESSION_SECRET':secrets.token_hex(32),'BIND_IP':ip,'APP_PORT':'8088','GRAFANA_PORT':'3300',
'RADIO_DEVICE':dev,'RADIO_POWER_SOURCE':'usb','COOKIE_SECURE':'false','GRAFANA_PUBLIC_URL':'',
'SMTP_HOST':'','SMTP_PORT':'587','SMTP_USER':'','SMTP_PASSWORD':'','SMTP_FROM':'','ALERT_EMAIL':''}
with open('.env','x') as out:
    for k,v in values.items():out.write(f'{k}={v}\n')
os.chmod('.env',0o600)
print('Generated .env (mode: USB serial)')
print('Grafana admin password (store in password manager):',values['GRAFANA_ADMIN_PASSWORD'])
PY
unset PASSWORD
