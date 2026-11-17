"""Read-only, reset-aware radio diagnostics. No guessed packet deliveries."""
from datetime import timezone
from station.health import packet_detail, delta, seconds_old

COUNTERS = ('rx','tx','rx_errors','flood_rx','direct_rx','flood_tx','direct_tx')

def sample_window(samples, now):
    """Newest-first telemetry; counters are boot-relative, never lifetime monotonic."""
    ordered = sorted(samples, key=lambda s: s.ts)
    valid = [s for s in ordered if not (s.stats or {}).get('simulated')]
    if not valid: return {'samples': 0, 'intervals': [], 'totals': None, 'resets': 0, 'latest_age_secs': None}
    intervals = []
    totals = {c: 0 for c in COUNTERS}
    resets = 0
    previous = valid[0]
    for current in valid[1:]:
        old, new = packet_detail(previous), packet_detail(current)
        a, b = old.get('uptime_secs'), new.get('uptime_secs')
        reset = (a is not None and b is not None and b < a) or any(
            old.get(k) is not None and new.get(k) is not None and new[k] < old[k] for k in COUNTERS)
        if reset:
            resets += 1
            intervals.append({'ts': current.ts.isoformat(), 'reset': True, 'seconds': None,
                              'counts': {k: None for k in COUNTERS}})
        else:
            seconds = max(0, (current.ts - previous.ts).total_seconds())
            changes = {k: delta(new.get(k), old.get(k), b, a) for k in COUNTERS}
            intervals.append({'ts': current.ts.isoformat(), 'reset': False,
                              'seconds': round(seconds, 2), 'counts': changes})
            for k, value in changes.items():
                if value is not None: totals[k] += int(value)
        previous = current
    return {'samples': len(valid), 'intervals': intervals[-120:], 'totals': totals if len(valid)>1 else None,
            'resets': resets, 'latest_age_secs': seconds_old(valid[-1].ts, now),
            'latest': packet_detail(valid[-1]), 'first_ts': valid[0].ts.isoformat(),
            'last_ts': valid[-1].ts.isoformat()}

def evidence_label(kind, message_kind):
    if kind == 'direct_ack' and message_kind == 'direct': return 'Direct ACK received'
    if kind == 'channel_echo' and message_kind == 'channel': return 'Matching channel copy heard; recipient unconfirmed'
    if kind == 'radio_accepted': return 'Radio accepted send request; delivery unconfirmed'
    return 'Unclassified evidence'
