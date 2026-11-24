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
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, case
from station.config import (USERNAME, HASH_SALT, PASSWORD_HASH, SESSION_SECRET,
                            COOKIE_SECURE, SPOOL_DIR, RADIO_POWER_SOURCE)
from station.geo import advertised_location, contact_role
from station.health import packet_detail, delta, seconds_old
from station.radio_diagnostics import sample_window, evidence_label
from station.radio_trends import trend
from station.node_adverts import coords_ok, advertise_wait
from station.secure import seal_key
from station.db import (initialize, Session, Contact, NodeLocation, Message, Sample, Alert, AddressEntry, RxActivity, TxEvidence,
                        Command, RadioEvent, StationStatus, utcnow)
from station.db import DigestSettings, DigestDelivery
from station.digest import (settings as get_digest_settings, public_settings, public_run,
                            validate_configuration, validate_mail_ready, validate_addresses,
                            encrypt_password, latest_due, next_due, lookback, report, aware_utc)
from typing import Literal


if not (HASH_SALT and PASSWORD_HASH and SESSION_SECRET and len(SESSION_SECRET) >= 32):
    raise RuntimeError('Run scripts/configure.sh first; authentication secrets are missing')

@asynccontextmanager
async def station_lifespan(_app: FastAPI):
    # Use the supported FastAPI lifespan hook, preserving the old startup work.
    initialize()
    for name in ('jobs', 'packages', 'states', 'logs'):
        (SPOOL_DIR / name).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title='MeshCore Station 0.8.8', docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=station_lifespan)
BASE = Path(__file__).resolve().parent.parent
app.mount('/assets', StaticFiles(directory=BASE / 'static'), name='assets')
signer = URLSafeTimedSerializer(SESSION_SECRET, salt='meshcore-station-auth')
login_failures = {}

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

def grafana_public_url():
    """Return only a safe, administrator-configured Grafana link."""
    raw = os.getenv('GRAFANA_PUBLIC_URL', '').strip()
    if not raw or any(char.isspace() for char in raw):
        return None
    try:
        url = urlsplit(raw)
        if (url.scheme not in ('http', 'https') or not url.hostname
                or url.username or url.password or url.query or url.fragment):
            return None
        if url.port is not None and url.port < 1:
            return None
    except ValueError:
        return None
    return raw.rstrip('/') + '/'


@app.get('/api/me')
def me(session=Depends(user_session)):
    return {'username': session['u'], 'csrf': session['csrf'],
            'grafana_port': int(os.getenv('GRAFANA_PORT', 3300)),
            'grafana_url': grafana_public_url()}

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
            'radio_config': data.get('radio_config', {}).get('value', {}),
            'last_stats': data.get('last_stats', {}).get('value', {})}

@app.get('/api/version')
def version(session=Depends(user_session)):
    return {'version': '0.8.8', 'release': 'Consistent overview channel names'}

@app.get('/api/radio/diagnostics')
def radio_diagnostics(hours: int = 24, session=Depends(user_session)):
    """Historical counter changes plus evidence; never claim RF delivery from counters."""
    hours = min(max(hours, 1), 168)
    now = utcnow()
    cutoff = now - timedelta(hours=hours)
    with Session() as db:
        samples = list(db.scalars(select(Sample).where(Sample.ts >= cutoff)
                      .order_by(Sample.ts.desc()).limit(3000)).all())
        messages = list(db.scalars(select(Message).where(Message.direction == 'out')
                       .order_by(Message.ts.desc()).limit(30)).all())
        ids = [m.id for m in messages]
        evidence = list(db.scalars(select(TxEvidence).where(TxEvidence.message_id.in_(ids))
                       .order_by(TxEvidence.ts)).all()) if ids else []
        status_rows = {r.key:r for r in db.scalars(select(StationStatus).where(
            StationStatus.key.in_(['radio','worker_heartbeat','routing_policy','routing_observed','contact_sync','radio_config']))).all()}
    related = {}
    for row in evidence:
        related.setdefault(row.message_id, []).append(row)
    timeline = []
    for msg in messages:
        proof = related.get(msg.id, [])
        timeline.append({'id': msg.id, 'ts': msg.ts.isoformat(), 'kind': msg.kind,
                         'destination': msg.target, 'sender': msg.sender,
                         'status': msg.status, 'text_preview': msg.body[:120],
                         'evidence': [{'ts':p.ts.isoformat(), 'kind':p.kind,
                                       'label':evidence_label(p.kind, msg.kind)} for p in proof]})
    heartbeat = status_rows.get('worker_heartbeat')
    age = seconds_old(heartbeat.updated, now) if heartbeat else None
    reported = (status_rows.get('radio').value or {}) if status_rows.get('radio') else {}
    def val(key):
        row = status_rows.get(key)
        return (row.value or {}) if row else {}
    return {'version': '0.8.8', 'window_hours': hours,
            'collector_online': bool(age is not None and age < 35 and reported.get('connected')),
            'heartbeat_age_secs': age, 'traffic': sample_window(samples, now),
            'routing': {'observed': val('routing_observed'),
                        'managed_policy': {k:val('routing_policy').get(k) for k in ('default_scope','scope_configured','channel_scopes')}},
            'contact_sync': val('contact_sync'), 'radio_config': val('radio_config'),
            'transmissions': timeline,
            'limitations': ['Packet counters include non-chat traffic.',
                'Counter reset intervals are not added to packet totals.',
                'Radio acceptance is not proof of reception.',
                'A matching channel copy is not an acknowledgment from a recipient.',
                'Missing evidence may reflect firmware visibility limits.']}

@app.get('/api/contacts')
def contacts(session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(Contact).where(~Contact.public_key.in_(['a1'*32, 'b2'*32])).order_by(Contact.last_seen.desc()).limit(2000)).all()
        return [{'key': c.public_key, 'name': c.name, 'role': c.role,
                 'first_seen': c.first_seen.isoformat(), 'last_seen': c.last_seen.isoformat(),
                 'detail': c.detail} for c in rows]

def iso_message_time(value):
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def serialize_messages(db, rows):
    """A single safe message representation for overview and history views."""
    ids = [m.id for m in rows if m.direction == 'out']
    evidence = {}
    if ids:
        for event in db.scalars(select(TxEvidence).where(TxEvidence.message_id.in_(ids))
                                .order_by(TxEvidence.id)).all():
            evidence.setdefault(event.message_id, []).append({
                'kind': event.kind, 'ts': iso_message_time(event.ts),
                'detail': event.detail if event.kind == 'channel_echo' else {}})
    return [{'id': m.id, 'ts': iso_message_time(m.ts), 'direction': m.direction,
             'kind': m.kind, 'target': m.target, 'sender': m.sender,
             'text': m.body, 'status': m.status,
             'tx_evidence': evidence.get(m.id, [])} for m in rows]


@app.get('/api/messages')
def messages(limit: int = 200, session=Depends(user_session)):
    """Keep the original endpoint contract for existing pages/integrations."""
    with Session() as db:
        rows = db.scalars(select(Message).order_by(Message.ts.desc(), Message.id.desc())
                          .limit(min(max(limit, 1), 2000))).all()
        return serialize_messages(db, rows)


# Slots 0–7 sort numerically; direct and unknown targets stay in a separate bucket.
# The bucket is part of the keyset cursor, so "load older" works across channels.
HISTORY_CHANNEL_SLOTS = tuple(str(n) for n in range(8))
HISTORY_SORTS = Literal['newest', 'oldest', 'channel_asc', 'channel_desc']


@app.get('/api/messages/history')
def message_history(limit: int = 50, direction: Literal['all', 'in', 'out'] = 'all',
                    destination: str = 'all', q: str = '', sort: HISTORY_SORTS = 'newest',
                    before_ts: datetime | None = None, before_id: int | None = None,
                    before_channel: str | None = None, session=Depends(user_session)):
    """Filtered, globally sorted history using stable timestamp/id/channel cursors.

    Channel names remain client-side: the database stores stable slot numbers and
    the browser resolves current radio names, including after channel renames.
    """
    if not 1 <= limit <= 100:
        raise HTTPException(400, 'Page size must be between 1 and 100')
    if len(q) > 120:
        raise HTTPException(400, 'Search is limited to 120 characters')
    if (before_ts is None) != (before_id is None) or (before_id is not None and before_id < 1):
        raise HTTPException(400, 'Invalid history cursor')
    if before_ts is not None and before_ts.tzinfo is None:
        raise HTTPException(400, 'History cursor must include a timezone')
    by_channel = sort.startswith('channel_')
    terminal_bucket = '8' if sort == 'channel_asc' else '-1'
    if by_channel:
        allowed = set(HISTORY_CHANNEL_SLOTS) | {terminal_bucket}
        if (before_ts is None) != (before_channel is None) or (before_channel is not None and before_channel not in allowed):
            raise HTTPException(400, 'Invalid channel sort cursor')
    elif before_channel is not None:
        raise HTTPException(400, 'Unexpected channel cursor')

    filters = []
    if direction != 'all':
        filters.append(Message.direction == direction)
    if destination == 'direct':
        filters.append(Message.kind == 'direct')
    elif destination != 'all':
        if not re.fullmatch(r'channel:[0-7]', destination):
            raise HTTPException(400, 'Invalid destination filter')
        filters.extend([Message.kind == 'channel', Message.target == destination.split(':')[1]])
    if q.strip():
        # Escape SQL LIKE wildcards so text searches cannot turn into patterns.
        term = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = '%' + term + '%'
        filters.append(or_(Message.body.ilike(pattern, escape='\\'),
                           Message.sender.ilike(pattern, escape='\\'),
                           Message.target.ilike(pattern, escape='\\')))

    time_ascending = sort == 'oldest'
    time_sort = [Message.ts.asc(), Message.id.asc()] if time_ascending else [Message.ts.desc(), Message.id.desc()]
    bucket = None
    order = time_sort
    if by_channel:
        bucket = case((and_(Message.kind == 'channel', Message.target.in_(HISTORY_CHANNEL_SLOTS)),
                       Message.target), else_=terminal_bucket)
        order = [bucket.asc() if sort == 'channel_asc' else bucket.desc(), *time_sort]

    with Session() as db:
        total = db.scalar(select(func.count(Message.id)).where(*filters)) or 0
        cursor_filter = []
        if before_ts is not None:
            older = or_(Message.ts > before_ts if time_ascending else Message.ts < before_ts,
                        and_(Message.ts == before_ts,
                             Message.id > before_id if time_ascending else Message.id < before_id))
            if by_channel:
                next_bucket = bucket > before_channel if sort == 'channel_asc' else bucket < before_channel
                cursor_filter.append(or_(next_bucket, and_(bucket == before_channel, older)))
            else:
                cursor_filter.append(older)
        rows = db.scalars(select(Message).where(*filters, *cursor_filter)
                          .order_by(*order).limit(limit + 1)).all()
        has_more = len(rows) > limit
        page = rows[:limit]
        last = page[-1] if page else None
        cursor = None
        if has_more and last is not None:
            cursor = {'before_ts': iso_message_time(last.ts), 'before_id': last.id}
            if by_channel:
                cursor['before_channel'] = (last.target if last.kind == 'channel'
                                             and last.target in HISTORY_CHANNEL_SLOTS else terminal_bucket)
        return {'items': serialize_messages(db, page), 'total': total,
                'has_more': has_more, 'next_cursor': cursor}


@app.get('/api/tx/diagnostics')
def tx_diagnostics(session=Depends(user_session)):
    # Authentication required; information limited to saved TX evidence and safe aggregate stats.
    with Session() as db:
        rows = db.scalars(select(Message).where(Message.direction == 'out')
                          .order_by(Message.ts.desc()).limit(100)).all()
        ids = [m.id for m in rows]
        events = db.scalars(select(TxEvidence).where(TxEvidence.message_id.in_(ids))
                            .order_by(TxEvidence.id.desc())).all() if ids else []
        linked = {}
        for e in events:
            linked.setdefault(e.message_id, []).append(e.kind)
        return {'recent_messages': len(rows),
                'accepted': sum('radio_accepted' in linked.get(m.id, []) for m in rows),
                'direct_acknowledged': sum(m.kind == 'direct' and 'direct_ack' in linked.get(m.id, []) for m in rows),
                'channel_echo_observed': sum(m.kind == 'channel' and 'channel_echo' in linked.get(m.id, []) for m in rows),
                'unconfirmed': sum(m.status == 'sent_unconfirmed' and 'channel_echo' not in linked.get(m.id, []) for m in rows),
                'note': 'A radio send response is not delivery. A matching channel echo is forwarding evidence, not recipient acknowledgment.'}

# Address book is distinct from the radio contact table and survives radio resets.
PUBLIC_KEY_RE = re.compile(r'^[0-9a-fA-F]{64}$')

class AddressInput(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    public_key: str | None = None
    notes: str = Field(default='', max_length=4000)
    tags: str = Field(default='', max_length=240)
    favorite: bool = False

def normalize_address(body: AddressInput):
    key = (body.public_key or '').strip().lower() or None
    if key is not None and not PUBLIC_KEY_RE.fullmatch(key):
        raise HTTPException(422, 'Public key must be a complete 64-character hexadecimal MeshCore public key')
    name = body.nickname.strip()
    if not name: raise HTTPException(422, 'Nickname required')
    return dict(public_key=key, nickname=name, notes=body.notes.strip(),
                tags=body.tags.strip(), favorite=body.favorite)

def address_dict(a, contact=None):
    return {'id': a.id, 'public_key': a.public_key, 'nickname': a.nickname,
            'notes': a.notes, 'tags': a.tags, 'favorite': a.favorite,
            'updated': a.updated.isoformat() if a.updated else None,
            'radio_contact': bool(contact), 'radio_name': contact.name if contact else None,
            'role': contact.role if contact else 'unknown'}

@app.get('/api/address-book')
def address_book(session=Depends(user_session)):
    with Session() as db:
        rows = db.scalars(select(AddressEntry).order_by(AddressEntry.favorite.desc(),
                          AddressEntry.nickname.asc()).limit(2000)).all()
        keys = [x.public_key for x in rows if x.public_key]
        known = {c.public_key: c for c in db.scalars(select(Contact).where(Contact.public_key.in_(keys))).all()} if keys else {}
        return [address_dict(a, known.get(a.public_key)) for a in rows]

@app.post('/api/address-book', status_code=201)
def add_address(body: AddressInput, session=Depends(require_csrf)):
    from sqlalchemy.exc import IntegrityError
    data = normalize_address(body)
    try:
        with Session.begin() as db:
            row = AddressEntry(**data, updated=utcnow()); db.add(row); db.flush()
            result = address_dict(row)
    except IntegrityError:
        raise HTTPException(409, 'That public key is already saved in the address book')
    return result

@app.put('/api/address-book/{entry_id}')
def edit_address(entry_id: int, body: AddressInput, session=Depends(require_csrf)):
    from sqlalchemy.exc import IntegrityError
    data = normalize_address(body)
    try:
        with Session.begin() as db:
            row = db.get(AddressEntry, entry_id)
            if row is None: raise HTTPException(404, 'Address entry not found')
            for key, value in data.items(): setattr(row, key, value)
            row.updated = utcnow(); db.flush()
            result = address_dict(row)
    except IntegrityError:
        raise HTTPException(409, 'That public key is already saved in another entry')
    return result

@app.delete('/api/address-book/{entry_id}')
def delete_address(entry_id: int, session=Depends(require_csrf)):
    with Session.begin() as db:
        row = db.get(AddressEntry, entry_id)
        if row is None: raise HTTPException(404, 'Address entry not found')
        db.delete(row)
    return {'ok': True}

@app.get('/api/radio/rx-log')
def rx_log(limit: int = 100, kind: str = '', session=Depends(user_session)):
    with Session() as db:
        q = select(RxActivity)
        if kind: q = q.where(RxActivity.kind == kind[:48])
        records = db.scalars(q.order_by(RxActivity.ts.desc()).limit(min(max(limit, 1), 500))).all()
        return [{'id': r.id, 'ts': r.ts.isoformat(), 'kind': r.kind,
                 'summary': r.summary, 'source': r.source,
                 'channel': r.channel, 'rssi': r.rssi, 'snr': r.snr,
                 'count': r.count, 'errors': r.errors, 'detail': r.detail} for r in records]

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


@app.get('/api/radio/trends')
def radio_trends(hours: int = 24, session=Depends(user_session)):
    hours = min(max(hours, 1), 168)
    with Session() as db:
        samples = list(db.scalars(select(Sample).where(
            Sample.ts >= utcnow() - timedelta(hours=hours))
            .order_by(Sample.ts.desc()).limit(11000)).all())
    return trend(samples, hours)


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
    if body.kind not in ('send', 'contacts'): raise HTTPException(400, 'Use the dedicated advertisement controls')
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

def csv_safe_cell(value):
    """Avoid spreadsheet formula execution in exported untrusted mesh text."""
    text = str(value if value is not None else '')
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


@app.get('/api/export/messages.csv')
def export_messages(session=Depends(user_session)):
    """Stream the complete message archive, not an arbitrary first-10k truncation."""
    def rows():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['timestamp_utc', 'direction', 'kind', 'target', 'sender', 'text', 'status'])
        yield output.getvalue()
        with Session() as db:
            query = (select(Message).order_by(Message.ts.desc(), Message.id.desc())
                     .execution_options(yield_per=500))
            for m in db.scalars(query):
                output.seek(0)
                output.truncate(0)
                writer.writerow([iso_message_time(m.ts), m.direction, m.kind,
                                 csv_safe_cell(m.target), csv_safe_cell(m.sender),
                                 csv_safe_cell(m.body), csv_safe_cell(m.status)])
                yield output.getvalue()
    return StreamingResponse(rows(), media_type='text/csv',
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

# Companion routing controls: no repeater region ACL commands are issued here.
# The SDK exposes a read command for path hashes, but not a reliable readback
# for the companion flood scope. Never present a locally saved scope as verified.
from station.routing import validate_region, validate_catalog, normalize_scope, normalize_channel_scopes

class RoutingSettings(BaseModel):
    path_hash_bytes: Literal[1, 2, 3] | None = None
    default_scope: str | None = None
    apply_scope: bool = False
    channel_scopes: dict[str, str] | None = None
    catalog: list[str] | None = None
    confirm: str

@app.get('/api/routing')
def routing_get(session=Depends(user_session)):
    with Session() as db:
        row = db.get(StationStatus, 'routing_policy')
        local = dict(row.value or {}) if row else {}
        observed = db.get(StationStatus, 'routing_observed')
    return {'catalog': local.get('catalog', []),
            'default_scope': local.get('default_scope') if local.get('scope_configured') else None,
            'scope_configured': bool(local.get('scope_configured')),
            'scope_verified': False,
            'channel_scopes': local.get('channel_scopes', {}),
            'path_hash_bytes': (observed.value or {}).get('path_hash_bytes') if observed else None,
            'path_hash_checked_at': observed.updated.isoformat() if observed else None,
            'note': 'Scope is managed by Station, not read back from firmware. No region restrictions are applied unless explicitly saved.'}

@app.post('/api/routing/read')
def routing_read(session=Depends(require_csrf)):
    with Session.begin() as db:
        cmd = Command(kind='read_routing', args={}, state='pending')
        db.add(cmd); db.flush()
        return {'id': cmd.id, 'state': 'pending'}

@app.put('/api/routing')
def routing_update(body: RoutingSettings, session=Depends(require_csrf)):
    if body.confirm != 'APPLY ROUTING':
        raise HTTPException(422, 'Type APPLY ROUTING to confirm')
    if body.path_hash_bytes is None and not body.apply_scope and body.channel_scopes is None and body.catalog is None:
        raise HTTPException(422, 'No routing changes provided')
    with Session() as db:
        row = db.get(StationStatus, 'routing_policy')
        current = dict(row.value or {}) if row else {}
    try:
        catalog = validate_catalog(body.catalog) if body.catalog is not None else current.get('catalog', [])
        scope = normalize_scope(body.default_scope) if body.apply_scope else current.get('default_scope', '')
        overrides = (normalize_channel_scopes(body.channel_scopes) if body.channel_scopes is not None
                     else current.get('channel_scopes', {}))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if overrides and not (body.apply_scope or current.get('scope_configured')):
        raise HTTPException(422, 'Apply a default scope (Unscoped is valid) before channel overrides')
    # Persist only once the radio has accepted the requested hardware settings.
    with Session.begin() as db:
        cmd = Command(kind='configure_routing', args={
            'path_hash_bytes': body.path_hash_bytes,
            'apply_scope': body.apply_scope,
            'default_scope': scope,
            'catalog': catalog,
            'channel_scopes': overrides,
        }, state='pending')
        db.add(cmd); db.flush()
        return {'id': cmd.id, 'state': 'pending'}

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

# The local map location is private until the user separately applies radio changes.
class OwnLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    description: str = Field(default='', max_length=160)
    elevation_m: float | None = Field(default=None, ge=-500, le=9000)

class OwnLocationApply(BaseModel):
    mode: Literal['share', 'private', 'hide']
    confirm: str

class AdvertRequest(BaseModel):
    flood: bool = False
    confirm: str

@app.get('/api/node/location')
def own_location_get(session=Depends(user_session)):
    with Session() as db:
        saved = db.get(StationStatus, 'own_location')
        radio = db.get(StationStatus, 'radio_location_observed')
        config = db.get(StationStatus, 'radio_config')
    return {'private': saved.value if saved else None,
            'radio': radio.value if radio else None,
            'radio_checked_at': radio.updated.isoformat() if radio else None,
            'node_name': (config.value or {}).get('name', 'Local node') if config else 'Local node',
            'note': 'Saving locally does not write to or advertise from the T114. Radio policy readback may be unavailable.'}

@app.put('/api/node/location')
def own_location_save(body: OwnLocation, session=Depends(require_csrf)):
    if not coords_ok(body.latitude, body.longitude):
        raise HTTPException(422, 'Enter valid latitude/longitude, not 0,0')
    data = {'latitude': body.latitude, 'longitude': body.longitude,
            'description': body.description.strip(), 'elevation_m': body.elevation_m}
    with Session.begin() as db:
        row = db.get(StationStatus, 'own_location')
        if row: row.value, row.updated = data, utcnow()
        else: db.add(StationStatus(key='own_location', value=data, updated=utcnow()))
    return {'saved': True, 'radio_changed': False}

@app.post('/api/node/location/apply')
def own_location_apply(body: OwnLocationApply, session=Depends(require_csrf)):
    expected = {'share': 'SHARE LOCATION', 'private': 'APPLY PRIVATE', 'hide': 'HIDE LOCATION'}[body.mode]
    if body.confirm != expected: raise HTTPException(422, f'Type {expected} to confirm')
    with Session.begin() as db:
        row = db.get(StationStatus, 'own_location')
        saved = dict(row.value or {}) if row else {}
        if body.mode in ('private','share') and not coords_ok(saved.get('latitude'), saved.get('longitude')):
            raise HTTPException(422, 'Save your location locally before applying it to the T114')
        cmd = Command(kind='node_location', args={'mode': body.mode,
                          'latitude': saved.get('latitude') if body.mode != 'hide' else None,
                          'longitude': saved.get('longitude') if body.mode != 'hide' else None}, state='pending')
        db.add(cmd);db.flush()
        return {'id': cmd.id, 'state': cmd.state}

@app.get('/api/node/adverts')
def advert_history(session=Depends(user_session)):
    with Session() as db:
        last = db.get(StationStatus, 'advert_last_sent')
        history = list(db.scalars(select(RadioEvent).where(RadioEvent.kind.in_(
            ['outgoing_advert_accepted','outgoing_advert_failed']))
            .order_by(RadioEvent.ts.desc()).limit(30)).all())
        pending = list(db.scalars(select(Command).where(Command.kind == 'advert',
                Command.state.in_(['pending','running'])).limit(10)).all())
    stored = last.value if last else {}
    now = utcnow()
    return {'last_accepted': stored, 'cooldown_local_secs': advertise_wait(stored, False, now),
            'cooldown_flood_secs': advertise_wait(stored, True, now),
            'pending': [{'id': c.id, 'mode': 'flood' if (c.args or {}).get('flood') else 'local'} for c in pending],
            'events': [{'ts': e.ts.isoformat(), 'kind': e.kind, 'mode': (e.detail or {}).get('mode')} for e in history],
            'note': 'Accepted only means the radio accepted the command; no other station is confirmed to have heard it.'}

@app.post('/api/node/adverts')
def advert_send(body: AdvertRequest, session=Depends(require_csrf)):
    expected = 'FLOOD ADVERT' if body.flood else 'LOCAL ADVERT'
    if body.confirm != expected: raise HTTPException(422, f'Type {expected} to confirm')
    with Session.begin() as db:
        last = db.get(StationStatus, 'advert_last_sent')
        wait = advertise_wait(last.value if last else {}, body.flood, utcnow())
        if wait: raise HTTPException(429, f'Advertisement cooldown: {wait} seconds remaining')
        existing = db.scalars(select(Command).where(Command.kind == 'advert',
                      Command.state.in_(['pending','running'])).limit(1)).first()
        if existing: raise HTTPException(409, 'An advertisement is already queued')
        cmd = Command(kind='advert', args={'flood': body.flood}, state='pending')
        db.add(cmd); db.flush()
        return {'id': cmd.id, 'state': cmd.state}

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
        own = db.get(StationStatus, 'own_location')
        rc = db.get(StationStatus, 'radio_config')
        if own and isinstance(own.value, dict) and coords_ok(own.value.get('latitude'), own.value.get('longitude')):
            nodes.append({'key':'self', 'name':(rc.value or {}).get('name','My Station') if rc else 'My Station',
                          'role':'self', 'last_seen':utcnow().isoformat(),
                          'location':{'lat':own.value['latitude'],'lon':own.value['longitude'],'source':'private'}})
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

# All digest endpoints are authenticated. Write actions require the same CSRF check as
# radio administration. SMTP credentials never appear in API responses or logs.
class DigestInput(BaseModel):
    enabled: bool = False
    frequency: Literal['daily','twice_daily','weekly'] = 'daily'
    send_time: str = Field(default='08:00', min_length=5, max_length=5)
    weekday: int = Field(default=0, ge=0, le=6)
    timezone: str = Field(default='America/Los_Angeles', max_length=80)
    include_received: bool = True
    include_sent: bool = False
    include_radio: bool = True
    include_alerts: bool = True
    include_nodes: bool = True
    include_rx: bool = False
    message_limit: int = Field(default=100, ge=5, le=250)
    smtp_host: str = Field(default='', max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal['starttls','ssl','none'] = 'starttls'
    smtp_username: str = Field(default='', max_length=255)
    smtp_password: str | None = Field(default=None, max_length=2048)
    clear_password: bool = False
    mail_from: str = Field(default='', max_length=255)
    mail_to: str = Field(default='', max_length=2000)


@app.get('/api/digest/settings')
def digest_settings_read(session=Depends(user_session)):
    with Session.begin() as db:
        cfg = get_digest_settings(db)
        item = public_settings(cfg)
        nxt = next_due(cfg, utcnow()) if cfg.enabled else None
        item['next_due'] = nxt.isoformat() if nxt else None
        heartbeat = db.get(StationStatus, 'digest_worker_heartbeat')
        item['worker_online'] = bool(heartbeat and (utcnow() - aware_utc(heartbeat.updated)).total_seconds() < 120)
        return item


@app.put('/api/digest/settings')
def digest_settings_save(body: DigestInput, session=Depends(require_csrf)):
    with Session.begin() as db:
        cfg = get_digest_settings(db)
        previous_schedule = (cfg.enabled, cfg.frequency, cfg.send_time, cfg.weekday, cfg.timezone)
        updates = body.model_dump(exclude={'smtp_password', 'clear_password'})
        for key, value in updates.items():
            setattr(cfg, key, value.strip() if isinstance(value, str) else value)
        if body.clear_password:
            cfg.smtp_password_enc = ''
        elif body.smtp_password:
            try:
                cfg.smtp_password_enc = encrypt_password(body.smtp_password)
            except ValueError as exc:
                raise HTTPException(503, str(exc)) from None
        if cfg.mail_to:
            try:
                cfg.mail_to = ', '.join(validate_addresses(cfg.mail_to))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        try:
            validate_configuration(cfg)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if (cfg.enabled, cfg.frequency, cfg.send_time, cfg.weekday, cfg.timezone) != previous_schedule:
            # Enabling/changing the schedule must never immediately email an old period.
            cfg.schedule_anchor = utcnow()
        cfg.updated_at = utcnow()
        db.flush()
        return {'ok': True, 'settings': public_settings(cfg),
                'next_due': next_due(cfg, utcnow()).isoformat() if cfg.enabled else None}


@app.get('/api/digest/preview')
def digest_preview(session=Depends(user_session)):
    with Session.begin() as db:
        cfg = get_digest_settings(db)
        end = utcnow()
        content = report(cfg, end - lookback(cfg), end, db=db)
        # Only the authenticated admin sees message content; never embed secrets.
        return {'subject': content['subject'], 'text': content['text'],
                'message_count': content['message_count'], 'sections': content['sections']}


def enqueue_digest(kind):
    with Session.begin() as db:
        cfg = get_digest_settings(db)
        try:
            validate_mail_ready(cfg)
            validate_configuration(cfg)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        end = utcnow()
        run = DigestDelivery(kind=kind, status='queued',
                             period_start=end - lookback(cfg), period_end=end)
        db.add(run)
        db.flush()
        return {'id': run.id, 'status': run.status}


@app.post('/api/digest/probe-smtp')
def digest_probe_smtp(session=Depends(require_csrf)):
    # The digest worker owns the network connection, not the API container.
    # The probe uses saved settings and sends no email.
    return enqueue_digest('probe')


@app.post('/api/digest/send-test')
def digest_send_test(session=Depends(require_csrf)):
    return enqueue_digest('test')


@app.post('/api/digest/send-now')
def digest_send_now(session=Depends(require_csrf)):
    return enqueue_digest('manual')


@app.get('/api/digest/history')
def digest_history(session=Depends(user_session)):
    with Session() as db:
        runs = db.scalars(select(DigestDelivery).order_by(DigestDelivery.id.desc()).limit(30)).all()
        return [public_run(x) for x in runs]


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
