"""Read-only, reset-aware radio timeseries assembled from existing Samples.

Rates represent the average packets/minute between two successive polls, not
individual reception timestamps. Unknown data is None; never silently zero-fill.
"""
from datetime import timezone
from math import isfinite
from station.health import packet_detail

COUNTERS = ('rx', 'tx', 'rx_errors', 'flood_rx', 'direct_rx', 'flood_tx', 'direct_tx')
MAX_INTERVAL = 600  # larger gaps are outages; do not present average rate as live


def numeric(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v):
        return float(v)
    return None


def trend(samples, window_hours=24):
    ordered = sorted((s for s in samples if not (s.stats or {}).get('simulated')), key=lambda s: s.ts)
    points, resets = [], []
    previous = None
    for sample in ordered:
        d = packet_detail(sample)
        point = {'ts': sample.ts.isoformat(), 'uptime_secs': numeric(d.get('uptime_secs')),
                 'noise_floor_dbm': numeric(d.get('noise_floor')), 'rssi_dbm': numeric(d.get('rssi')),
                 'snr_db': numeric(d.get('snr')), 'rx_per_min': None, 'tx_per_min': None,
                 'errors_per_min': None, 'flood_rx_per_min': None, 'direct_rx_per_min': None,
                 'flood_tx_per_min': None, 'direct_tx_per_min': None, 'reset': False}
        if previous is not None:
            old = packet_detail(previous)
            secs = (sample.ts - previous.ts).total_seconds()
            old_uptime = numeric(old.get('uptime_secs'))
            new_uptime = point['uptime_secs']
            uptime_reset = (old_uptime is not None and new_uptime is not None and new_uptime < old_uptime)
            drops = [k for k in COUNTERS if numeric(d.get(k)) is not None and
                     numeric(old.get(k)) is not None and d[k] < old[k]]
            if uptime_reset or drops:
                point['reset'] = True
                resets.append({'ts': point['ts'], 'reason': 'uptime decreased' if uptime_reset else 'packet counter decreased',
                               'counter_names': drops})
            elif 0 < secs <= MAX_INTERVAL:
                for field in COUNTERS:
                    new, prior = numeric(d.get(field)), numeric(old.get(field))
                    if new is not None and prior is not None:
                        point[('errors' if field == 'rx_errors' else field) + '_per_min'] = round((new - prior) * 60 / secs, 3)
        points.append(point)
        previous = sample
    # We cap response size rather than downsampling reset evidence.
    if len(points) > 2500:
        step = (len(points) + 2499) // 2500
        points = points[::step] + ([points[-1]] if points[-1] != points[::step][-1] else [])
    last = points[-1] if points else None
    return {'window_hours': window_hours, 'samples': len(ordered), 'points': points,
            'resets': resets[-100:], 'reset_count': len(resets),
            'latest': last,
            'notes': ['Rates are averages between consecutive approximately 60-second samples.',
                      'A gap longer than 10 minutes is not treated as a valid rate interval.',
                      'Uptime decreases or counter rollbacks mark suspected radio resets.',
                      'RSSI/SNR represent the firmware latest-packet fields, not per-sample average signal strength.']}
