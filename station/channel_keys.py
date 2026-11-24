"""MeshCore channel key selection; never log or return secret material."""
import hashlib
import secrets


def select_channel_key(name: str, radio_payload: dict, random_bytes=None):
    """Keep existing keys, derive standard #channels, or generate private keys.

    A named channel with an unreadable key is never silently rekeyed.
    Returns (16-byte key, non-secret mode label).
    """
    data = radio_payload if isinstance(radio_payload, dict) else {}
    existing_name = str(data.get('channel_name') or data.get('name') or '').strip()
    raw = data.get('channel_secret', data.get('secret'))
    if isinstance(raw, str):
        try:
            raw = bytes.fromhex(raw)
        except ValueError:
            raw = None
    if isinstance(raw, bytearray):
        raw = bytes(raw)
    if isinstance(raw, bytes) and len(raw) == 16 and raw != bytes(16):
        return raw, 'preserved'
    if existing_name:
        raise ValueError('Existing channel key unavailable. Provide its shared key to avoid replacing it.')
    if name.startswith('#'):
        return hashlib.sha256(name.encode('utf-8')).digest()[:16], 'hashtag_derived'
    key = (random_bytes or secrets.token_bytes)(16)
    if not isinstance(key, bytes) or len(key) != 16 or key == bytes(16):
        raise ValueError('Could not generate a valid private channel key')
    return key, 'random_private'
