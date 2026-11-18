"""MeshCore email digest schedule, reporting and SMTP delivery (no serial access)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
import os
import re
import smtplib
import ssl
import socket
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, func
from station.db import (Session, DigestSettings, DigestDelivery, Message, Sample,
                        Alert, Contact, RadioEvent, RxActivity, StationStatus, utcnow)
from station.health import packet_detail, delta

ALLOWED_FREQUENCIES = ('twice_daily', 'daily', 'weekly')
ALLOWED_SECURITY = ('starttls', 'ssl', 'none')
DIGEST_SECTION_NAMES = ('received', 'sent', 'radio', 'alerts', 'nodes', 'rx')
EMAIL_RE = re.compile(r'^[^\s@,;<>\x00-\x1f]+@[^\s@,;<>\x00-\x1f]+$')
TIME_RE = re.compile(r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')


def aware_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite in local tests may return naive UTC values.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_addresses(value, limit=20):
    """Only simple mailbox addresses are accepted; no arbitrary mail header content."""
    result = []
    for item in re.split(r'[,;]', value or ''):
        addr = item.strip()
        if not addr:
            continue
        if not EMAIL_RE.fullmatch(addr) or addr.startswith('.') or addr.endswith('.'):
            raise ValueError('Use plain email addresses, separated by commas (no display names)')
        local, domain = addr.rsplit('@', 1)
        if not local or '.' not in domain or len(addr) > 254:
            raise ValueError('Invalid email address')
        result.append(addr)
    if len(result) > limit:
        raise ValueError(f'Maximum {limit} recipients')
    # Stable dedupe avoids sending duplicate mail to same recipient.
    return list(dict.fromkeys(result))


def validate_configuration(cfg):
    if cfg.frequency not in ALLOWED_FREQUENCIES:
        raise ValueError('Unsupported digest frequency')
    if not TIME_RE.fullmatch(cfg.send_time):
        raise ValueError('Send time must be HH:MM')
    if not 0 <= cfg.weekday <= 6:
        raise ValueError('Weekday must be 0 (Monday) through 6 (Sunday)')
    if not 1 <= cfg.smtp_port <= 65535:
        raise ValueError('Invalid SMTP port')
    if cfg.smtp_security not in ALLOWED_SECURITY:
        raise ValueError('Invalid SMTP security setting')
    try:
        ZoneInfo(cfg.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Choose a valid IANA timezone, such as America/Los_Angeles') from None
    if not 5 <= cfg.message_limit <= 250:
        raise ValueError('Message limit must be between 5 and 250')
    if not any(getattr(cfg, 'include_' + s) for s in DIGEST_SECTION_NAMES):
        raise ValueError('Select at least one digest content section')
    if cfg.smtp_security == 'none' and (cfg.smtp_username or cfg.smtp_password_enc):
        raise ValueError('SMTP login requires STARTTLS or SSL; plaintext authentication is prohibited')
    if cfg.smtp_username and not cfg.smtp_password_enc:
        raise ValueError('An SMTP username requires a password')
    if cfg.enabled:
        validate_mail_ready(cfg)


def validate_mail_ready(cfg):
    if not cfg.smtp_host.strip() or not cfg.mail_from.strip() or not cfg.mail_to.strip():
        raise ValueError('Configure an SMTP server, sender and recipient before enabling or sending')
    if not cfg.smtp_host.strip() or any(c.isspace() for c in cfg.smtp_host.strip()):
        raise ValueError('Invalid SMTP server hostname')
    if len(validate_addresses(cfg.mail_from, limit=1)) != 1:
        raise ValueError('A single sender address is required')
    if not validate_addresses(cfg.mail_to):
        raise ValueError('At least one recipient is required')
    if cfg.smtp_username and not cfg.smtp_password_enc:
        raise ValueError('SMTP password missing')
    if cfg.smtp_security == 'none' and (cfg.smtp_username or cfg.smtp_password_enc):
        raise ValueError('Plaintext SMTP authentication is not allowed')


def cipher():
    key = os.getenv('DIGEST_ENCRYPTION_KEY', '').strip()
    if not key:
        raise ValueError('DIGEST_ENCRYPTION_KEY missing. Run scripts/enable-digests.sh')
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, UnicodeError):
        raise ValueError('Invalid digest encryption key') from None


def encrypt_password(plain):
    return cipher().encrypt(plain.encode('utf-8')).decode('ascii')


def decrypt_password(token):
    if not token:
        return ''
    try:
        return cipher().decrypt(token.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError):
        raise ValueError('Cannot decrypt SMTP password. Restore the original DIGEST_ENCRYPTION_KEY') from None


def settings(db):
    row = db.get(DigestSettings, 1)
    if row is None:
        row = DigestSettings(id=1)
        db.add(row)
        db.flush()
    return row


def slots_near(cfg, reference):
    """Return local calendar slots near reference, including DST-offset transitions."""
    zone = ZoneInfo(cfg.timezone)
    local = aware_utc(reference).astimezone(zone)
    hour, minute = [int(x) for x in cfg.send_time.split(':')]
    slots = []
    for offset in range(-9, 10):
        day = local.date() + timedelta(days=offset)
        if cfg.frequency == 'weekly' and day.weekday() != cfg.weekday:
            continue
        first = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
        slots.append(first.astimezone(timezone.utc))
        if cfg.frequency == 'twice_daily':
            slots.append((first + timedelta(hours=12)).astimezone(timezone.utc))
    return sorted(set(slots))


def latest_due(cfg, now):
    choices = [t for t in slots_near(cfg, now) if t <= aware_utc(now)]
    return max(choices) if choices else None


def next_due(cfg, now):
    now = aware_utc(now)
    anchor = aware_utc(cfg.schedule_anchor) or now
    choices = [t for t in slots_near(cfg, max(now, anchor)) if t > now and t >= anchor]
    return min(choices) if choices else None


def prior_slot(cfg, slot):
    choices = [t for t in slots_near(cfg, slot - timedelta(days=1)) if t < slot]
    return max(choices) if choices else slot - timedelta(days=7 if cfg.frequency == 'weekly' else 1)


def lookback(cfg):
    return timedelta(days=7) if cfg.frequency == 'weekly' else timedelta(hours=12 if cfg.frequency == 'twice_daily' else 24)


def local_time(dt, tz):
    return aware_utc(dt).astimezone(ZoneInfo(tz)).strftime('%a %b %d %Y, %I:%M %p %Z')


def safe_text(s, limit=500):
    # Remove control characters other than newlines/tabs to prevent mail format weirdness.
    return ''.join(c for c in str(s or '') if c in '\n\t' or ord(c) >= 32)[:limit]


def report(cfg, start, end, db=None):
    """Render from PostgreSQL snapshots; no commands are sent to the radio."""
    start, end = aware_utc(start), aware_utc(end)
    own = db is None
    if own:
        db = Session()
    try:
        title = f'MeshCore Station digest · {local_time(end, cfg.timezone)}'
        lines = ['MESHCORE STATION', '================', title,
                 f'Period: {local_time(start, cfg.timezone)} to {local_time(end, cfg.timezone)}', '']
        message_count = 0
        section_counts = {}
        def section(label, items):
            lines.extend([label.upper(), '-' * len(label)])
            lines.extend(items if items else ['None recorded.'])
            lines.append('')
        for direction, enabled, label in (
                ('in', cfg.include_received, 'Received messages'),
                ('out', cfg.include_sent, 'Sent messages')):
            if not enabled:
                continue
            # Limit query and email size. Old simulated entries are never emailed.
            candidates = db.scalars(select(Message)
                .where(Message.direction == direction, Message.ts >= start, Message.ts < end)
                .order_by(Message.ts.desc()).limit(cfg.message_limit * 4)).all()
            selected = [m for m in candidates if not (isinstance(m.meta, dict) and m.meta.get('simulated'))]
            count = len(selected)
            section_counts[direction] = count
            selected = selected[:cfg.message_limit]
            message_count += len(selected)
            entries = [f'[{local_time(m.ts, cfg.timezone)}] {safe_text(m.sender, 100) or "Unknown"} '
                       f'({"Channel " + safe_text(m.target, 32) if m.kind == "channel" else "Direct"}):\n'
                       f'{safe_text(m.body, 500)}\n' for m in selected]
            if count > len(selected):
                entries.append(f'... additional messages omitted (limit {cfg.message_limit}).')
            section(label, entries)
        if cfg.include_radio:
            latest = db.scalar(select(Sample).where(Sample.ts < end)
                .order_by(Sample.ts.desc()).limit(1))
            first = db.scalar(select(Sample).where(Sample.ts >= start, Sample.ts < end)
                .order_by(Sample.ts.asc()).limit(1))
            radio = db.get(StationStatus, 'radio')
            heartbeat = db.get(StationStatus, 'worker_heartbeat')
            fresh = bool(heartbeat and (utcnow() - aware_utc(heartbeat.updated)).total_seconds() < 60)
            connected = bool(fresh and radio and (radio.value or {}).get('connected'))
            ritems = [f'Collector: {"Connected" if connected else "Offline / stale heartbeat"}',
                      'Power: USB (no battery installed)']
            if latest:
                age_seconds = int((utcnow() - aware_utc(latest.ts)).total_seconds())
                current = packet_detail(latest)
                previous = packet_detail(first) if first else {}
                rx_delta = delta(current.get('rx'), previous.get('rx'), current.get('uptime_secs'), previous.get('uptime_secs'))
                tx_delta = delta(current.get('tx'), previous.get('tx'), current.get('uptime_secs'), previous.get('uptime_secs'))
                def show(v, unit=''):
                    return ('unavailable' if v is None else f'{v:g}{unit}')
                ritems.extend([
                    f'Latest telemetry: {local_time(latest.ts, cfg.timezone)} (age {age_seconds} seconds)',
                    f'Noise floor: {show(latest.noise_floor, " dBm")}',
                    f'Last RSSI: {show(latest.rssi, " dBm")}',
                    f'RX packets (since radio boot): {show(current.get("rx"))}',
                    f'TX packets (since radio boot): {show(current.get("tx"))}',
                    f'RX errors (since boot): {show(current.get("rx_errors"))}',
                    f'RX delta in period: {show(rx_delta)} (unavailable if counters reset)',
                    f'TX delta in period: {show(tx_delta)} (unavailable if counters reset)',
                ])
                if age_seconds > 300:
                    ritems.append('ISSUE: telemetry is older than 5 minutes')
            else:
                ritems.append('ISSUE: no radio telemetry available')
            section('Radio status', ritems)
        if cfg.include_alerts:
            alerts = db.scalars(select(Alert).where(
                (Alert.ts >= start) | (Alert.resolved == False)).order_by(Alert.ts.desc()).limit(50)).all()
            section_counts['alerts'] = len(alerts)
            extra_issues = []
            heartbeat = db.get(StationStatus, 'worker_heartbeat')
            status = db.get(StationStatus, 'radio')
            if not heartbeat or (utcnow() - aware_utc(heartbeat.updated)).total_seconds() > 60 or not (status and (status.value or {}).get('connected')):
                extra_issues.append('ISSUE: Collector disconnected or heartbeat stale')
            last_sample = db.scalar(select(Sample).order_by(Sample.ts.desc()).limit(1))
            if not last_sample or (utcnow() - aware_utc(last_sample.ts)).total_seconds() > 300:
                extra_issues.append('ISSUE: Radio telemetry missing or more than five minutes old')
            alert_rows = extra_issues + [f'[{local_time(x.ts, cfg.timezone)}] {safe_text(x.severity, 40).upper()} '
                          f'{"(resolved) " if x.resolved else "(unresolved) "}{safe_text(x.message, 350)}'
                          for x in alerts]
            section('Issues and alerts', alert_rows)
        if cfg.include_nodes:
            # First-seen is contact inventory, not proof of over-the-air reception at this time.
            total = db.scalar(select(func.count()).select_from(Contact)) or 0
            added = db.scalars(select(Contact).where(Contact.first_seen >= start, Contact.first_seen < end)
                               .order_by(Contact.first_seen.desc()).limit(30)).all()
            section_counts['new_nodes'] = len(added)
            section('Known nodes', [f'Total saved radio contacts: {total}',
                    f'New entries this period: {len(added)}'] +
                    [f'  {safe_text(c.name, 80)} ({safe_text(c.role, 40)})' for c in added])
        if cfg.include_rx:
            rx_rows = db.scalars(select(RxActivity).where(RxActivity.ts >= start, RxActivity.ts < end)
                                .order_by(RxActivity.ts.desc()).limit(30)).all()
            section_counts['rx_events'] = len(rx_rows)
            section('RX activity', [f'[{local_time(x.ts, cfg.timezone)}] '
                       f'{safe_text(x.kind, 40)}: {safe_text(x.summary, 160)}'
                       f'{f" (+{x.count} RF packets)" if x.kind == "counter_delta" else ""}'
                       for x in rx_rows])
        lines.extend(['--', 'Generated by MeshCore Station. Times are in ' + cfg.timezone + '.',
                      'RF transmission/packet counters do not prove remote delivery.'])
        text_body = '\n'.join(lines)
        # HTML alternative is fully escaped; no external images, tracking pixels or URLs.
        html_body = ('<html><body style="background:#f6f9fa;color:#172a34;font-family:system-ui,Arial,sans-serif;'
                     'padding:20px"><div style="max-width:720px;margin:auto;background:white;border-radius:12px;'
                     'padding:28px;border:1px solid #dae3e8"><h2 style="color:#117a75">MeshCore Station</h2>'
                     '<pre style="white-space:pre-wrap;font-family:system-ui,Arial,sans-serif;line-height:1.55;'
                     'overflow-wrap:anywhere">'+escape(text_body)+'</pre></div></body></html>')
        return {'subject': title, 'text': text_body, 'html': html_body,
                'message_count': message_count, 'sections': section_counts}
    finally:
        if own:
            db.close()


def send_email(cfg, subject, text_body, html_body=None):
    validate_mail_ready(cfg)
    recipients = validate_addresses(cfg.mail_to)
    sender = validate_addresses(cfg.mail_from, limit=1)[0]
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = ', '.join(recipients)
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')
    context = ssl.create_default_context()
    if cfg.smtp_security == 'ssl':
        smtp = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=20, context=context)
    else:
        smtp = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=20)
    with smtp:
        smtp.ehlo()
        if cfg.smtp_security == 'starttls':
            smtp.starttls(context=context)
            smtp.ehlo()
        if cfg.smtp_username:
            if cfg.smtp_security == 'none':
                raise ValueError('Refusing to authenticate over plaintext SMTP')
            smtp.login(cfg.smtp_username, decrypt_password(cfg.smtp_password_enc))
        smtp.send_message(message)
    return len(recipients)



class SMTPProbeError(ValueError):
    """Safe, step-specific mail diagnostic with no server reply disclosure."""


def probe_smtp(cfg):
    """Check DNS, TCP, TLS, and optional auth. Does NOT send a message."""
    validate_mail_ready(cfg)
    host, port = cfg.smtp_host.strip(), cfg.smtp_port
    stage = 'DNS lookup'
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        stage = 'TCP connection / SMTP greeting'
        context = ssl.create_default_context()
        if cfg.smtp_security == 'ssl':
            smtp = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        else:
            smtp = smtplib.SMTP(host, port, timeout=15)
        with smtp:
            smtp.ehlo()
            if cfg.smtp_security == 'starttls':
                stage = 'STARTTLS negotiation'
                if not smtp.has_extn('starttls'):
                    raise SMTPProbeError('STARTTLS negotiation: server does not advertise STARTTLS')
                smtp.starttls(context=context)
                smtp.ehlo()
            if cfg.smtp_username:
                stage = 'SMTP authentication'
                smtp.login(cfg.smtp_username, decrypt_password(cfg.smtp_password_enc))
    except SMTPProbeError:
        raise
    except socket.gaierror:
        raise SMTPProbeError('DNS lookup failed. Check the SMTP hostname and DNS on the VM.') from None
    except smtplib.SMTPAuthenticationError:
        raise SMTPProbeError('SMTP authentication failed. Check username and app password.') from None
    except ssl.SSLError:
        raise SMTPProbeError(f'{stage} failed: TLS certificate or handshake problem.') from None
    except (TimeoutError, OSError, smtplib.SMTPException) as exc:
        raise SMTPProbeError(f'{stage} failed: {safe_smtp_error(exc)}') from None
    return 'DNS, SMTP connection, TLS, and configured authentication succeeded; no email was sent.'


def safe_smtp_error(exc):
    # Do not leak SMTP server error bodies, credentials, or message content into logs/API.
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return 'SMTP authentication rejected. Check username and app password.'
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return 'SMTP connection/TLS failed. Verify hostname, port, TLS mode and network access.'
    if isinstance(exc, smtplib.SMTPException):
        return 'SMTP server rejected the operation. Verify sender and recipients.'
    if isinstance(exc, ValueError):
        return safe_text(str(exc), 250)
    return 'Unexpected digest delivery error. Check the digest worker service.'


def public_settings(cfg):
    return {k: getattr(cfg, k) for k in (
        'enabled', 'frequency', 'send_time', 'weekday', 'timezone',
        *(f'include_{s}' for s in DIGEST_SECTION_NAMES), 'message_limit',
        'smtp_host', 'smtp_port', 'smtp_security', 'smtp_username',
        'mail_from', 'mail_to')} | {'password_configured': bool(cfg.smtp_password_enc),
                                    'updated_at': aware_utc(cfg.updated_at).isoformat() if cfg.updated_at else None}


def public_run(run):
    return {'id': run.id, 'kind': run.kind, 'status': run.status,
            'created_at': aware_utc(run.created_at).isoformat() if run.created_at else None,
            'started_at': aware_utc(run.started_at).isoformat() if run.started_at else None,
            'finished_at': aware_utc(run.finished_at).isoformat() if run.finished_at else None,
            'message_count': run.message_count, 'recipient_count': run.recipient_count,
            'error': run.error}
