"""Geographical metadata from advertised MeshCore contact records.
No inferred geolocation based on signal/RSSI, path, name, or IP address.
"""
import math

ROLE_NAMES = {1: 'client', 2: 'repeater', 3: 'room_server', 4: 'sensor'}

def contact_role(detail):
    raw = detail.get('node_type_str') or detail.get('type') or detail.get('role')
    if isinstance(raw, int): return ROLE_NAMES.get(raw, 'unknown')
    value = str(raw or 'unknown').lower().strip().replace(' ', '_')
    if value.isdecimal(): return ROLE_NAMES.get(int(value), 'unknown')
    return {'chat': 'client', 'companion':'client', 'room':'room_server',
            'roomserver':'room_server'}.get(value, value)

def advertised_location(detail):
    """Return valid lat/lon or None. Firmware may return degrees or microdegrees."""
    if not isinstance(detail, dict): return None
    for lat_key, lon_key in [('latitude','longitude'), ('adv_lat','adv_lon'), ('lat','lon')]:
        if lat_key not in detail or lon_key not in detail: continue
        try:
            lat, lon = float(detail[lat_key]), float(detail[lon_key])
            if abs(lat) > 90 or abs(lon) > 180:
                lat, lon = lat / 1_000_000, lon / 1_000_000
            if not (math.isfinite(lat) and math.isfinite(lon)): continue
            if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0): continue
            return {'lat': lat, 'lon': lon, 'source': 'advertised'}
        except (ValueError, TypeError, OverflowError): continue
    return None
