"""Pure radio telemetry helpers; no serial access, database migrations, or radio writes."""
from datetime import timezone
import math


def metric(block, key):
    """Only report actual finite numeric measurements, never coerce absent data to zero."""
    value = (block or {}).get(key) if isinstance(block, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def packet_detail(sample):
    if sample is None:
        return {}
    stats = sample.stats if isinstance(sample.stats, dict) else {}
    packets = stats.get('packets') or {}
    radio = stats.get('radio') or {}
    core = stats.get('core') or {}
    return {
        'rx': metric(packets, 'recv') if metric(packets, 'recv') is not None else sample.packets_rx,
        'tx': metric(packets, 'sent') if metric(packets, 'sent') is not None else sample.packets_tx,
        'rx_errors': metric(packets, 'recv_errors'),
        'flood_rx': metric(packets, 'flood_rx'),
        'flood_tx': metric(packets, 'flood_tx'),
        'direct_tx': metric(packets, 'direct_tx'),
        'direct_rx': metric(packets, 'direct_rx'),
        'rx_air_secs': metric(radio, 'rx_air_secs'),
        'tx_air_secs': metric(radio, 'tx_air_secs'),
        'core_errors': metric(core, 'errors'),
        'uptime_secs': metric(core, 'uptime_secs') or sample.uptime,
        'noise_floor': sample.noise_floor,
        'rssi': sample.rssi,
        'snr': sample.snr,
    }


def delta(current, previous, current_uptime=None, previous_uptime=None):
    if current is None or previous is None: return None
    if (current_uptime is not None and previous_uptime is not None and
            current_uptime < previous_uptime):
        return None  # Counters may reset on radio reboot.
    if current < previous: return None
    return current - previous


def seconds_old(when, now):
    if when is None: return None
    if when.tzinfo is None: when = when.replace(tzinfo=timezone.utc)
    return max(0, round((now - when).total_seconds()))
