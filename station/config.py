import os
from pathlib import Path

DB_URL = os.getenv('DATABASE_URL', 'sqlite:////tmp/meshcore-station-test.sqlite')
SIMULATION = os.getenv('SIMULATION', 'false').lower() == 'true'
RADIO_DEVICE = os.getenv('RADIO_DEVICE_IN_CONTAINER', '/dev/meshcore')
SPOOL_DIR = Path(os.getenv('SPOOL_DIR', '/spool'))
USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
HASH_SALT = os.getenv('ADMIN_PASSWORD_SALT', '')
PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', '')
SESSION_SECRET = os.getenv('SESSION_SECRET', '')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
