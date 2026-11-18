"""Conservative correlation of MeshCore send responses and subsequent radio events.

A radio's command success is not recipient delivery. Direct ACKs use an exact
expected checksum. Channel repeat candidates require a matching channel, text,
original sender timestamp, and nonzero route length; they indicate a heard
retransmission, not proof of reader delivery.
"""
from datetime import datetime, timezone
import re

HEX8 = re.compile(r'^[a-f0-9]{8}$')


def ack_code(value):
    """Normalize a 4-byte checksum; refuse ambiguous/unrecognized values."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex() if len(value) == 4 else None
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**32:
        return value.to_bytes(4, 'little').hex()
    if isinstance(value, str):
        value = value.lower().strip().removeprefix('0x').replace(':', '').replace(' ', '')
        return value if HEX8.fullmatch(value) else None
    return None


def expected_ack(payload):
    if not isinstance(payload, dict): return None
    for field in ('expected_ack', 'expected_ack_code', 'ack_code', 'ack'):
        result = ack_code(payload.get(field))
        if result is not None: return result
    return None


def received_ack(payload):
    if not isinstance(payload, dict): return None
    return expected_ack(payload) or ack_code(payload.get('code')) or ack_code(payload.get('checksum'))


def match_channel_echo(payload, *, channel, body, send_ts):
    """Require sufficient fields to reject accidental message-text collisions.

    This confirms a matching decoded inbound channel copy; identification of a
    specific repeater is not possible from this evidence alone.
    """
    if not isinstance(payload, dict): return False
    try:
        idx = int(payload.get('channel_idx'))
        when = int(payload.get('timestamp'))
        hops = int(payload.get('path_len'))
    except (ValueError, TypeError, OverflowError):
        return False
    if idx != int(channel) or hops < 1 or payload.get('text') != body:
        return False
    if not isinstance(send_ts, datetime): return False
    if send_ts.tzinfo is None: send_ts = send_ts.replace(tzinfo=timezone.utc)
    return abs(when - int(send_ts.timestamp())) <= 15
