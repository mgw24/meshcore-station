"""Location input validation and advert throttling helpers (no serial access)."""
from datetime import datetime, timezone, timedelta
from math import isfinite

LOCAL_COOLDOWN = timedelta(minutes=5)
FLOOD_COOLDOWN = timedelta(hours=2)


def coords_ok(lat, lon):
    return (isinstance(lat, (int, float)) and not isinstance(lat, bool) and isfinite(lat)
            and isinstance(lon, (int, float)) and not isinstance(lon, bool) and isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat != 0 or lon != 0))


def elapsed_since(last_iso, now):
    if not last_iso:
        return None
    try:
        then = datetime.fromisoformat(last_iso)
        if then.tzinfo is None: then = then.replace(tzinfo=timezone.utc)
        return max(0., (now - then).total_seconds())
    except (ValueError, TypeError):
        return None


def advertise_wait(last_sent, flood, now):
    """Per-mode cooldown, based on successful requests to firmware."""
    when = (last_sent or {}).get('flood' if flood else 'local')
    seconds = elapsed_since(when, now)
    window = (FLOOD_COOLDOWN if flood else LOCAL_COOLDOWN).total_seconds()
    return max(0, int(window - seconds + 0.999)) if seconds is not None else 0
