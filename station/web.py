"""VPN-facing web UI and command queue. No serial access or Docker socket here."""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from station.config import (USERNAME, HASH_SALT, PASSWORD_HASH, SESSION_SECRET,
                            COOKIE_SECURE, SPOOL_DIR, RADIO_POWER_SOURCE)
from station.geo import advertised_location, contact_role
from station.health import packet_detail, delta, seconds_old
from station.secure import seal_key
from station.db import (initialize, Session, Contact, NodeLocation, Message, Sample, Alert,
                        Command, RadioEvent, StationStatus, utcnow)

if not (HASH_SALT and PASSWORD_HASH and SESSION_SECRET and len(SESSION_SECRET) >= 32):
    raise RuntimeError('Run scripts/configure.sh first; authentication secrets are missing')

app = FastAPI(title='MeshCore Station', docs_url=None, redoc_url=None, openapi_url=None)
BASE = Path(__file__).resolve().parent.parent
app.mount('/assets', StaticFiles(directory=BASE / 'static'), name='assets')
signer = URLSafeTimedSerializer(SESSION_SECRET, salt='meshcore-station-auth')
login_failures = {}

@app.on_event('startup')
def startup():
    initialize()
    for name in ('jobs', 'packages', 'states', 'logs'):
        (SPOOL_DIR / name).mkdir(parents=True, exist_ok=True)

@app.get('/')
def index(): return FileResponse(BASE / 'static' / 'index.html')

@app.get('/healthz')
def healthz(): return {'ok': True}

def user_session(request: Request):
    token = request.cookies.get('meshcore_session')
    try:
        data = signer.loads(token or '', max_age=12 * 3600)
        if data.get('u') != USERNAME: raise BadSignature('wrong user')
        return data
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail='Login required')

def require_csrf(request: Request, session=Depends(user_session)):
    supplied = request.headers.get('x-csrf-token', '')
    if not supplied or not hmac.compare_digest(supplied, session.get('csrf', '')):
        raise HTTPException(status_code=403, detail='Invalid CSRF token')
    return session

class Login(BaseModel):
    username: str
    password: str

@app.post('/api/login')
def login(body: Login, request: Request, response: Response):
    client = request.client.host if request.client else 'unknown'
    failed, started = login_failures.get(client, (0, time.monotonic()))
    if time.monotonic() - started > 900: failed, started = 0, time.monotonic()
    if failed >= 10:
        raise HTTPException(429, 'Too many login attempts. Retry later.')
    try:
        computed = hashlib.pbkdf2_hmac('sha256', body.password.encode(), bytes.fromhex(HASH_SALT), 260000).hex()
    except ValueError:
        raise HTTPException(500, 'Invalid configured authentication salt')
    if not (hmac.compare_digest(body.username, USERNAME) and hmac.compare_digest(computed, PASSWORD_HASH)):
        login_failures[client] = (failed + 1, started)
        raise HTTPException(401, 'Invalid credentials')
    login_failures.pop(client, None)
    csrf = secrets.token_urlsafe(32)
    response.set_cookie('meshcore_session', signer.dumps({'u': USERNAME, 'csrf': csrf}),
                        max_age=12*3600, httponly=True, secure=COOKIE_SECURE,
                        samesite='strict', path='/')
    return {'username': USERNAME, 'csrf': csrf}

@app.get('/api/me')
def me(session=Depends(user_session)):
    return {'username': session['u'], 'csrf': session['csrf'],
            'grafana_port': int(os.getenv('GRAFANA_PORT', 3300))}

@app.post('/api/logout')
def logout(response: Response, session=Depends(require_csrf)):
    response.delete_cookie('meshcore_session', path='/')
    return {'ok': True}

@app.get('/api/status')
def status(session=Depends(user_session)):
    with Session() as db:
        data = {row.key: {'value': row.value, 'updated': row.updated.isoformat()}
                for row in db.scalars(select(StationStatus)).all()}
        last = db.scalars(select(Sample).order_by(Sample.ts.desc()).limit(1)).first()
        counts = {'contacts': db.scalar(select(func.count()).select_from(Contact).where(~Contact.public_key.in_(['a1'*32, 'b2'*32]))),
                  'messages': db.scalar(select(func.count()).select_from(Message)),
                  'alerts': db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved == False))}
    hb = data.get('worker_heartbeat')
    try:
        from datetime import datetime, timezone
        fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(hb['value']['at'])).total_seconds() < 35 if hb else False
    except (ValueError, KeyError, TypeError): fresh = False
    radio = data.get('radio', {}).get('value', {})
    radio['connected'] = bool(fresh and radio.get('connected'))
    return {'radio': radio, 'power_source': RADIO_POWER_SOURCE, 'counts': counts,
            'sample': {'ts': last.ts.isoformat(), 'battery_pct': None if RADIO_POWER_SOURCE == 'usb' else last.battery_pct,
                       'noise_floor': last.noise_floor, 'uptime': last.uptime,
                       'rssi': last.rssi, 'snr': last.snr,
                       'packets_rx': last.packets_rx, 'packets_tx': last.packets_tx} if last else None,
            'heartbeat_fresh': fresh, 'contact_sync': data.get('contact_sync', {}).get('value', {}),
            'channels': data.get('channels', {}).get('value', []),
            'last_stats': data.get('last_stats', {}).get('value', {})}

@app.get('/api/contacts')
def contacts(session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(Contact).where(~Contact.public_key.in_(['a1'*32, 'b2'*32])).order_by(Contact.last_seen.desc()).limit(2000)).all()
        return [{'key': c.public_key, 'name': c.name, 'role': c.role,
                 'first_seen': c.first_seen.isoformat(), 'last_seen': c.last_seen.isoformat(),
                 'detail': c.detail} for c in rows]

@app.get('/api/messages')
def messages(limit: int = 200, session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(Message).order_by(Message.ts.desc()).limit(min(max(limit, 1), 2000))).all()
        return [{'id': m.id, 'ts': m.ts.isoformat(), 'direction': m.direction, 'kind': m.kind,
                 'target': m.target, 'sender': m.sender, 'text': m.body, 'status': m.status}
                for m in rows]

@app.get('/api/events')
def events(limit: int = 100, session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(RadioEvent).order_by(RadioEvent.ts.desc()).limit(min(max(limit, 1), 500))).all()
        return [{'ts': r.ts.isoformat(), 'kind': r.kind, 'detail': r.detail} for r in rows]

@app.get('/api/alerts')
def alerts(session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(Alert).order_by(Alert.ts.desc()).limit(200)).all()
        return [{'id': x.id, 'ts': x.ts.isoformat(), 'severity': x.severity,
                 'message': x.message, 'resolved': x.resolved} for x in rows]

@app.post('/api/alerts/{alert_id}/resolve')
def resolve_alert(alert_id: int, session=Depends(require_csrf)):
    with Session.begin() as db:
        item = db.get(Alert, alert_id)
        if not item: raise HTTPException(404, 'No such alert')
        item.resolved = True
    return {'ok': True}

@app.get('/api/history')
def history(hours: int = 24, session=Depends(user_session)):
    hours = max(1, min(hours, 24 * 30))
    with Session() as db:
        rows = db.scalars(select(Sample).where(Sample.ts >= utcnow() - timedelta(hours=hours))
                          .order_by(Sample.ts.desc()).limit(1000)).all()
        rows = [x for x in rows if not (x.stats or {}).get('simulated')]
        result = []
        for x in reversed(rows):
            p = packet_detail(x)
            result.append({'ts': x.ts.isoformat(), 'battery': None if RADIO_POWER_SOURCE == 'usb' else x.battery_pct,
                           'noise': x.noise_floor, 'uptime': x.uptime, 'rssi': x.rssi, 'snr': x.snr,
                           'packets_rx': x.packets_rx, 'packets_tx': x.packets_tx,
                           'rx_errors': p['rx_errors'], 'flood_rx': p['flood_rx'], 'direct_rx': p['direct_rx'],
                           'rx_air_secs': p['rx_air_secs'], 'tx_air_secs': p['tx_air_secs'],
                           'core_errors': p['core_errors'],
                           'simulated': False})
        return result


@app.get('/api/radio/health')
def radio_health(session=Depends(user_session)):
    now = utcnow()
    with Session() as db:
        samples = [x for x in db.scalars(select(Sample).order_by(Sample.ts.desc()).limit(40)).all() if not (x.stats or {}).get('simulated')][:2]
        radio_status = db.get(StationStatus, 'radio')
        heartbeat = db.get(StationStatus, 'worker_heartbeat')
        fresh_heartbeat = (seconds_old(heartbeat.updated, now) < 35) if heartbeat else False
        connected = bool(fresh_heartbeat and radio_status and radio_status.value.get('connected'))
    current, previous = (samples[0] if samples else None), (samples[1] if len(samples) > 1 else None)
    latest = packet_detail(current)
    prior = packet_detail(previous)
    uptime = latest.get('uptime_secs')
    old_uptime = prior.get('uptime_secs')
    counters = ('rx', 'tx', 'rx_errors', 'flood_rx', 'direct_rx')
    return {'connected': connected,
            'power_source': RADIO_POWER_SOURCE,
            'sample_ts': current.ts.isoformat() if current else None,
            'sample_age_secs': seconds_old(current.ts, now) if current else None,
            'sample_fresh': bool(current and seconds_old(current.ts, now) <= 150),
            'heartbeat_age_secs': seconds_old(heartbeat.updated, now) if heartbeat else None,

            'measurements': latest,
            'deltas': {field: delta(latest.get(field), prior.get(field), uptime, old_uptime) for field in counters},
            'delta_interval_secs': round((current.ts - previous.ts).total_seconds()) if current and previous else None,
            'note': 'RF packet receive counts include non-chat traffic. No traffic alone does not establish a fault.'}


class CommandIn(BaseModel):
    kind: str
    destination: str = ''
    text: str = Field(default='', max_length=180)
    flood: bool = False

@app.post('/api/commands')
def queue_command(body: CommandIn, session=Depends(require_csrf)):
    if body.kind not in ('send', 'contacts', 'advert'): raise HTTPException(400, 'Unsupported command')
    if body.kind == 'send':
        kind, dest = ('channel', body.destination[8:]) if body.destination.startswith('channel:') else ('direct', body.destination)
        if not body.text.strip(): raise HTTPException(422, 'Message required')
        if kind == 'channel' and (not dest.isdecimal() or not 0 <= int(dest) <= 7):
            raise HTTPException(422, 'Channel index must be 0-7')
        if kind == 'direct':
            with Session() as db:
                if db.get(Contact, dest) is None: raise HTTPException(422, 'Choose a known contact')
        args = {'kind': kind, 'destination': dest, 'text': body.text.strip()}
    else: args = {'flood': body.flood}
    with Session.begin() as db:
        item = Command(kind=body.kind, args=args, state='pending')
        db.add(item)
        db.flush()
        identifier = item.id
    return {'id': identifier, 'state': 'pending'}

@app.get('/api/commands/{command_id}')
def command_status(command_id: int, session=Depends(user_session)):
    with Session() as db:
        c = db.get(Command, command_id)
        if not c: raise HTTPException(404, 'Unknown command')
        return {'id': c.id, 'kind': c.kind, 'state': c.state, 'error': c.error, 'result': c.result}

@app.get('/api/export/messages.csv')
def export_messages(session=Depends(user_session)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['timestamp_utc', 'direction', 'kind', 'target', 'sender', 'text', 'status'])
    with Session() as db:
        rows = db.scalars(select(Message).order_by(Message.ts.desc()).limit(10000)).all()
        for m in rows:
            writer.writerow([m.ts.isoformat(), m.direction, m.kind, m.target, m.sender,
                             "'" + m.body if m.body[:1] in ('=', '+', '-', '@') else m.body, m.status])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename="meshcore-messages.csv"'})

FIRMWARE_NAME = re.compile(r'^Heltec_t114(?:_without_display)?_companion_radio_usb[^/\\]*\.zip$', re.I)
MAX_ZIP = 8 * 1024 * 1024

def validate_firmware(filename: str, content: bytes):
    if not FIRMWARE_NAME.fullmatch(filename):
        raise ValueError('Use the official Heltec_t114_*companion_radio_usb*.zip (not BLE, repeater, UF2 or another board)')
    if len(content) > MAX_ZIP or len(content) < 500:
        raise ValueError('DFU ZIP must be between 500 bytes and 8 MiB')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(entry.file_size for entry in archive.infolist()) > 20 * 1024 * 1024:
            raise ValueError('Uncompressed firmware archive exceeds size limit')
        files = set(archive.namelist())
        if 'manifest.json' not in files: raise ValueError('Missing Nordic DFU manifest.json')
        manifest = json.loads(archive.read('manifest.json'))
        application = manifest.get('manifest', {}).get('application')
        if not application: raise ValueError('Archive has no Nordic DFU application section')
        for key in ('bin_file', 'dat_file'):
            path = application.get(key, '')
            if not isinstance(path, str) or path not in files or '/' in path or '\\' in path:
                raise ValueError(f'Invalid Nordic DFU {key}')
    return hashlib.sha256(content).hexdigest()

@app.post('/api/firmware/upload')
async def firmware_upload(request: Request, file: UploadFile = File(...), confirmation: str = Form(...),
                          session=Depends(require_csrf)):
    if confirmation != 'FLASH T114': raise HTTPException(422, 'Type FLASH T114 to confirm')
    if file.content_type not in ('application/zip', 'application/x-zip-compressed', 'application/octet-stream', None):
        raise HTTPException(422, 'Firmware must be a ZIP archive')
    content = await file.read(MAX_ZIP + 1)
    try: sha = validate_firmware(file.filename or '', content)
    except (ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f'Invalid firmware package: {exc}')
    if not SPOOL_DIR.is_dir(): raise HTTPException(503, 'Flashing agent spool unavailable')
    for state_path in (SPOOL_DIR / 'states').glob('*.json'):
        try:
            if json.loads(state_path.read_text()).get('status') in ('queued', 'flashing', 'stopping', 'restarting'):
                raise HTTPException(409, 'A flash is already pending or in progress')
        except json.JSONDecodeError: continue
    identifier = str(uuid.uuid4())
    pkg = SPOOL_DIR / 'packages' / f'{identifier}.zip'
    state = SPOOL_DIR / 'states' / f'{identifier}.json'
    job = SPOOL_DIR / 'jobs' / f'{identifier}.json'
    with pkg.open('xb') as out:
        os.chmod(pkg, 0o640)
        out.write(content)
    state.write_text(json.dumps({'id': identifier, 'status': 'queued', 'filename': file.filename,
                                 'sha256': sha, 'message': 'Waiting for host agent'}))
    job.write_text(json.dumps({'id': identifier, 'filename': file.filename, 'sha256': sha}))
    return {'id': identifier, 'status': 'queued', 'sha256': sha}

def firmware_states():
    base = SPOOL_DIR / 'states'
    if not base.exists(): return []
    jobs = []
    for p in base.glob('*.json'):
        try:
            d = json.loads(p.read_text())
            if re.fullmatch(r'[0-9a-f-]{36}', d.get('id', '')): jobs.append(d)
        except (OSError, json.JSONDecodeError): pass
    return sorted(jobs, key=lambda d: d['id'], reverse=True)[:30]

@app.get('/api/firmware/jobs')
def firmware_jobs(session=Depends(user_session)):
    return firmware_states()

@app.get('/api/firmware/jobs/{job_id}')
def firmware_job(job_id: str, session=Depends(user_session)):
    if not re.fullmatch(r'[0-9a-f-]{36}', job_id): raise HTTPException(400, 'Invalid job ID')
    state = SPOOL_DIR / 'states' / f'{job_id}.json'
    if not state.exists(): raise HTTPException(404, 'Job not found')
    try: payload = json.loads(state.read_text())
    except json.JSONDecodeError: raise HTTPException(503, 'Job state updating')
    log_file = SPOOL_DIR / 'logs' / f'{job_id}.log'
    payload['log'] = log_file.read_text(errors='replace')[-15000:] if log_file.exists() else ''
    return payload

class RadioSettings(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=31)
    tx_power: int | None = Field(default=None, ge=2, le=22)
    radio_freq: float | None = Field(default=None, ge=902, le=928)
    radio_bw: float | None = None
    radio_sf: int | None = Field(default=None, ge=7, le=12)
    radio_cr: int | None = Field(default=None, ge=5, le=8)
    confirm: str

@app.get('/api/radio/config')
def radio_config(session=Depends(user_session)):
    with Session() as db:
        state = db.get(StationStatus, 'radio_config')
        return state.value if state else {}

@app.post('/api/radio/read')
def radio_read(session=Depends(require_csrf)):
    with Session.begin() as db:
        cmd = Command(kind='read_radio', args={}, state='pending')
        db.add(cmd); db.flush()
        return {'id': cmd.id, 'state': cmd.state}

@app.post('/api/radio/settings')
def radio_settings(body: RadioSettings, session=Depends(require_csrf)):
    if body.confirm != 'APPLY RADIO': raise HTTPException(422, 'Type APPLY RADIO to confirm')
    updates = body.model_dump(exclude_none=True, exclude={'confirm'})
    keys = set(updates)
    radio_keys = {'radio_freq','radio_bw','radio_sf','radio_cr'}
    if keys & radio_keys:
        if not radio_keys.issubset(keys):
            raise HTTPException(422, 'Submit all four radio parameters together')
        if updates['radio_bw'] not in (62.5, 125.0, 250.0, 500.0):
            raise HTTPException(422, 'Unsupported bandwidth')
    if not updates: raise HTTPException(422, 'No changes supplied')
    with Session.begin() as db:
        cmd = Command(kind='configure_radio', args={'updates': updates}, state='pending')
        db.add(cmd); db.flush()
        return {'id': cmd.id, 'state': cmd.state}

# Public API never returns keys, including channel secrets. They live temporarily in
# the command queue and are scrubbed by the collector after processing.
class ChannelUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=31)
    secret_hex: str | None = None
    confirm: str

class ChannelDelete(BaseModel):
    confirm: str

@app.get('/api/channels')
def channel_list(session=Depends(user_session)):
    with Session() as db:
        value = db.get(StationStatus, 'channels')
        items = value.value if value and isinstance(value.value, list) else []
    indexed = {x.get('index'): x for x in items if isinstance(x, dict)}
    return {'slots': [{'index': i, 'name': str(indexed.get(i, {}).get('name') or ''),
                       'configured': bool(indexed.get(i, {}).get('name'))} for i in range(8)],
            'source': 'T114 cached channel listing, secrets hidden'}

@app.post('/api/channels/refresh')
def channel_refresh(session=Depends(require_csrf)):
    with Session.begin() as db:
        item = Command(kind='channels', args={}, state='pending')
        db.add(item); db.flush()
        return {'id': item.id, 'state': item.state}

@app.put('/api/channels/{index}')
def channel_update(index: int, body: ChannelUpdate, session=Depends(require_csrf)):
    if not 0 <= index <= 7: raise HTTPException(422, 'Channel index must be 0-7')
    if body.confirm != 'SAVE CHANNEL': raise HTTPException(422, 'Type SAVE CHANNEL to confirm')
    name = body.name.strip()
    if not name: raise HTTPException(422, 'Channel name must not be blank')
    secret = body.secret_hex.strip() if body.secret_hex is not None else None
    if secret is not None and not re.fullmatch(r'[0-9a-fA-F]{32}', secret):
        raise HTTPException(422, 'Shared key must be exactly 32 hexadecimal characters (16 bytes)')
    args = {'index': index, 'name': name}
    if secret is not None: args['sealed_key'] = seal_key(secret.lower())
    with Session.begin() as db:
        item = Command(kind='set_channel', args=args, state='pending')
        db.add(item); db.flush()
        return {'id': item.id, 'state': item.state}

@app.delete('/api/channels/{index}')
def channel_delete(index: int, body: ChannelDelete, session=Depends(require_csrf)):
    if not 0 <= index <= 7: raise HTTPException(422, 'Channel index must be 0-7')
    if body.confirm != f'DELETE CHANNEL {index}':
        raise HTTPException(422, f'Type DELETE CHANNEL {index} to confirm')
    with Session.begin() as db:
        item = Command(kind='delete_channel', args={'index': index}, state='pending')
        db.add(item); db.flush()
        return {'id': item.id, 'state': item.state}

class LocationInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

@app.get('/api/map/nodes')
def map_nodes(session=Depends(user_session)):
    with Session() as db:
        manual = {x.public_key: x for x in db.scalars(select(NodeLocation)).all()}
        rows = db.scalars(select(Contact).where(~Contact.public_key.in_(['a1'*32, 'b2'*32])).order_by(Contact.name)).all()
        nodes=[]
        for c in rows:
            location = advertised_location(c.detail or {})
            if c.public_key in manual:
                o = manual[c.public_key]
                location={'lat': o.latitude, 'lon': o.longitude, 'source': 'manual'}
            nodes.append({'key': c.public_key, 'name': c.name,
                          'role': (contact_role(c.detail or {}) if contact_role(c.detail or {}) != 'unknown' else c.role),
                          'last_seen': c.last_seen.isoformat(), 'location': location})
    return nodes

@app.put('/api/map/nodes/{public_key}/location')
def set_node_location(public_key: str, body: LocationInput, session=Depends(require_csrf)):
    if body.latitude == 0 and body.longitude == 0: raise HTTPException(422, 'Unknown location (0,0) is not allowed')
    with Session.begin() as db:
        if db.get(Contact, public_key) is None: raise HTTPException(404, 'Unknown contact')
        loc = db.get(NodeLocation, public_key)
        if loc is None:
            loc=NodeLocation(public_key=public_key); db.add(loc)
        loc.latitude, loc.longitude, loc.updated = body.latitude, body.longitude, utcnow()
    return {'ok': True, 'source': 'manual'}

@app.delete('/api/map/nodes/{public_key}/location')
def clear_node_location(public_key: str, session=Depends(require_csrf)):
    with Session.begin() as db:
        loc = db.get(NodeLocation, public_key)
        if loc: db.delete(loc)
    return {'ok': True}

@app.get('/metrics')
def metrics():
    registry = CollectorRegistry()
    up = Gauge('meshcore_collector_connected', 'Radio collector connection status', registry=registry)
    total = Gauge('meshcore_messages_total_logged', 'Logged messages', registry=registry)
    nodes = Gauge('meshcore_contacts_known', 'Known MeshCore nodes', registry=registry)
    critical = Gauge('meshcore_unresolved_alerts', 'Unresolved alerts', registry=registry)
    rf_gauges = {key: Gauge('meshcore_radio_'+key, 'Latest MeshCore radio '+key.replace('_',' '), registry=registry)
                 for key in ('rx_packets','tx_packets','rx_errors','flood_rx','direct_rx','noise_floor_dbm','uptime_seconds','telemetry_age_seconds')}
    synced = Gauge('meshcore_radio_contacts_returned', 'Contacts returned by last radio sync', registry=registry)
    with Session() as db:
        radio = db.get(StationStatus, 'radio')
        heartbeat = db.get(StationStatus, 'worker_heartbeat')
        fresh = heartbeat and heartbeat.updated >= utcnow() - timedelta(seconds=35)
        up.set(1 if (fresh and radio and radio.value.get('connected')) else 0)
        total.set(db.scalar(select(func.count()).select_from(Message)))
        nodes.set(db.scalar(select(func.count()).select_from(Contact)))
        critical.set(db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved == False)))
        sample = db.scalar(select(Sample).order_by(Sample.ts.desc()).limit(1))
        contact_info = db.get(StationStatus, 'contact_sync')
        if contact_info and isinstance(contact_info.value, dict):
            synced.set(contact_info.value.get('radio_contacts', 0))
        if sample is not None:
            d = packet_detail(sample)
            for prometheus_key, detail_key in [('rx_packets','rx'),('tx_packets','tx'),('rx_errors','rx_errors'),('flood_rx','flood_rx'),('direct_rx','direct_rx'),('noise_floor_dbm','noise_floor'),('uptime_seconds','uptime_secs')]:
                if d.get(detail_key) is not None: rf_gauges[prometheus_key].set(d[detail_key])
            rf_gauges['telemetry_age_seconds'].set(seconds_old(sample.ts, utcnow()))
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
