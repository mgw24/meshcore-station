"""Encrypt short-lived channel secrets in the database command queue.

Both API and collector have SESSION_SECRET through the private .env file.
Secrets never appear in API responses, Grafana metrics, or application logs.
"""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from station.config import SESSION_SECRET


def _fernet():
    if not SESSION_SECRET or len(SESSION_SECRET) < 32:
        raise RuntimeError('Station secret is not configured')
    key = hashlib.sha256(('meshcore-channel-queue-v1:' + SESSION_SECRET).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal_key(hex_value):
    raw = bytes.fromhex(hex_value)
    if len(raw) != 16:
        raise ValueError('Shared key must be 16 bytes')
    return _fernet().encrypt(raw).decode('ascii')


def unseal_key(value):
    try:
        raw = _fernet().decrypt(value.encode('ascii'))
    except (InvalidToken, ValueError):
        raise ValueError('Cannot decrypt channel key; verify current session secret') from None
    if len(raw) != 16:
        raise ValueError('Invalid decrypted channel key length')
    return raw
