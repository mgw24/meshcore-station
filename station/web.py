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
                            COOKIE_SECURE, SPOOL_DIR, SIMULATION)
from station.db import (initialize, Session, Contact, Message, Sample, Alert,
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
        counts = {'contacts': db.scalar(select(func.count()).select_from(Contact)),
                  'messages': db.scalar(select(func.count()).select_from(Message)),
                  'alerts': db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved == False))}
    hb = data.get('worker_heartbeat')
    try:
        from datetime import datetime, timezone
        fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(hb['value']['at'])).total_seconds() < 35 if hb else False
    except (ValueError, KeyError, TypeError): fresh = False
    radio = data.get('radio', {}).get('value', {})
    radio['connected'] = bool(fresh and radio.get('connected'))
    return {'radio': radio, 'counts': counts,
            'sample': {'ts': last.ts.isoformat(), 'battery_pct': last.battery_pct,
                       'noise_floor': last.noise_floor, 'uptime': last.uptime,
                       'rssi': last.rssi, 'snr': last.snr,
                       'packets_rx': last.packets_rx, 'packets_tx': last.packets_tx} if last else None,
            'heartbeat_fresh': fresh, 'simulation': radio.get('mode') == 'simulation',
            'channels': data.get('channels', {}).get('value', []),
            'last_stats': data.get('last_stats', {}).get('value', {})}

@app.get('/api/contacts')
def contacts(session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(Contact).order_by(Contact.last_seen.desc()).limit(2000)).all()
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
        return [{'ts': x.ts.isoformat(), 'battery': x.battery_pct, 'noise': x.noise_floor,
                 'uptime': x.uptime, 'rssi': x.rssi, 'snr': x.snr,
                 'packets_rx': x.packets_rx, 'packets_tx': x.packets_tx} for x in reversed(rows)]

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
    if SIMULATION: raise HTTPException(409, 'Switch to real USB serial mode before firmware flashing')
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

@app.get('/metrics')
def metrics():
    registry = CollectorRegistry()
    up = Gauge('meshcore_collector_connected', 'Radio collector connection status', registry=registry)
    total = Gauge('meshcore_messages_total_logged', 'Logged messages', registry=registry)
    nodes = Gauge('meshcore_contacts_known', 'Known MeshCore nodes', registry=registry)
    critical = Gauge('meshcore_unresolved_alerts', 'Unresolved alerts', registry=registry)
    with Session() as db:
        radio = db.get(StationStatus, 'radio')
        heartbeat = db.get(StationStatus, 'worker_heartbeat')
        fresh = heartbeat and heartbeat.updated >= utcnow() - timedelta(seconds=35)
        up.set(1 if (fresh and radio and radio.value.get('connected')) else 0)
        total.set(db.scalar(select(func.count()).select_from(Message)))
        nodes.set(db.scalar(select(func.count()).select_from(Contact)))
        critical.set(db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved == False)))
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
