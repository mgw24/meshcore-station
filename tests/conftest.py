import hashlib
import os
import tempfile
from pathlib import Path

TEMP = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(TEMP.name) / 'test.sqlite')
os.environ['SPOOL_DIR'] = str(Path(TEMP.name) / 'spool')
os.environ['SIMULATION'] = 'true'
os.environ['SESSION_SECRET'] = 'a'*64
os.environ['ADMIN_PASSWORD_SALT'] = 'b'*32
os.environ['ADMIN_PASSWORD_HASH'] = hashlib.pbkdf2_hmac(
    'sha256', b'correct horse battery staple', bytes.fromhex('b'*32), 260000).hex()
