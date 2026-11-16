"""Only this process owns /dev/meshcore. Web requests arrive through a DB queue."""
import asyncio
import json
import logging
import os
import smtplib
from email.message import EmailMessage
from datetime import timedelta
from sqlalchemy import select
from station.config import RADIO_DEVICE, RADIO_POWER_SOURCE
from station.geo import contact_role
from station.secure import unseal_key
from station.db import (initialize, Session, Contact, Message, Sample, Alert, Command,
                        RadioEvent, StationStatus, status_set, record_event, utcnow)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('station.worker')

def jsonsafe(value):
    if isinstance(value, bytes): return value.hex()
    if isinstance(value, dict): return {str(jsonsafe(k)): jsonsafe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)): return [jsonsafe(v) for v in value]
    if isinstance(value, (int, float, str, type(None), bool)): return value
    return str(value)

def record_contact(key, contact, observed=False):
    obj = jsonsafe(contact) if isinstance(contact, dict) else {}
    pk = str(jsonsafe(obj.get('public_key') or key)).lower()
    if not pk or pk == 'none': return
    with Session.begin() as db:
        row = db.get(Contact, pk)
        if row is None:
            row = Contact(public_key=pk, first_seen=utcnow())
            db.add(row)
        row.name = str(obj.get('adv_name') or obj.get('name') or pk[:12])[:200]
        row.role = contact_role(obj)[:80]
        if observed:
            row.last_seen = utcnow()
        row.detail = obj

class Collector:
    def __init__(self):
        self.mesh = None
        self.mode = 'serial'
        self.last_alert = None

    async def handle(self, kind, event):
        data = jsonsafe(getattr(event, 'payload', {}))
        # Intentionally do not dump private key material or device secrets into the DB.
        if kind == 'direct':
            with Session.begin() as db:
                db.add(Message(direction='in', kind='direct', target='',
                               sender=str(data.get('pubkey_prefix', 'unknown')),
                               body=str(data.get('text', '')), meta=data))
        elif kind == 'channel':
            with Session.begin() as db:
                db.add(Message(direction='in', kind='channel',
                               target=str(data.get('channel_idx', '0')),
                               sender=str(data.get('pubkey_prefix', 'channel')),
                               body=str(data.get('text', '')), meta=data))
        elif kind == 'ack':
            code = str(data.get('code', '')).lower() if isinstance(data, dict) else ''
            if code:
                with Session.begin() as db:
                    rows = db.scalars(select(Message).where(
                        Message.direction == 'out', Message.status == 'sent_unconfirmed'
                    ).order_by(Message.id.desc()).limit(100)).all()
                    for row in rows:
                        if str((row.meta or {}).get('expected_ack', '')).lower() == code:
                            row.status = 'acknowledged'
                            break
        elif kind in ('advert', 'new_contact'):
            safe = {k: v for k, v in data.items() if not any(t in k.lower() for t in ('secret', 'private_key', 'password'))} if isinstance(data, dict) else {}
            record_event(kind, safe)
            if kind == 'advert' and isinstance(data, dict) and isinstance(data.get('public_key'), (str, bytes)):
                record_contact(data['public_key'], data, observed=True)
            if kind == 'new_contact':
                try: await self.refresh_contacts()
                except Exception as exc: log.warning('Contact refresh: %s', exc)
        else:
            record_event(kind, data)

    async def connect(self):
        from meshcore import MeshCore, EventType
        self.mesh = await MeshCore.create_serial(RADIO_DEVICE, 115200)
        if self.mesh is None or not getattr(self.mesh, 'is_connected', True):
            raise RuntimeError('Serial MeshCore connection not established')
        for etype, kind in [('CONTACT_MSG_RECV', 'direct'), ('CHANNEL_MSG_RECV', 'channel'),
                            ('ACK', 'ack'), ('ADVERTISEMENT', 'advert'),
                            ('NEW_CONTACT', 'new_contact'), ('PATH_UPDATE', 'path')]:
            if hasattr(EventType, etype):
                async def callback(event, capture=kind):
                    try: await self.handle(capture, event)
                    except Exception: log.exception('Failed processing radio event %s', capture)
                self.mesh.subscribe(getattr(EventType, etype), callback)
        await self.mesh.start_auto_message_fetching()
        status_set('radio', {'connected': True, 'mode': 'serial', 'device': RADIO_DEVICE})
        with Session.begin() as db:
            for alert in db.scalars(select(Alert).where(Alert.resolved == False, Alert.message.like('Collector offline:%'))).all():
                alert.resolved = True
        record_event('connected', {'mode': 'serial', 'device': RADIO_DEVICE})
        await self.refresh_contacts()
        await self.refresh_channels()
        await self.poll_radio()

    async def close(self):
        if self.mesh:
            try: await self.mesh.stop_auto_message_fetching()
            except Exception: pass
            try: await self.mesh.disconnect()
            except Exception: pass
            self.mesh = None
        status_set('radio', {'connected': False, 'mode': self.mode, 'device': RADIO_DEVICE})

    async def refresh_contacts(self):
        from meshcore import EventType
        result = await self.mesh.commands.get_contacts()
        if result.type == EventType.ERROR: raise RuntimeError(str(result.payload))
        payload = result.payload or {}
        if isinstance(payload, dict) and isinstance(payload.get('contacts'), (dict, list)):
            payload = payload['contacts']
        if isinstance(payload, dict):
            entries = list(payload.items())
        elif isinstance(payload, list):
            entries = [(item.get('public_key') or item.get('pubkey') or '', item)
                       for item in payload if isinstance(item, dict)]
        else:
            raise RuntimeError('Unknown contact-list response')
        with Session() as db:
            before = set(db.scalars(select(Contact.public_key)).all())
        discovered = 0
        for key, item in entries:
            if isinstance(item, dict):
                pk = str(jsonsafe(item.get('public_key') or key)).lower()
                if pk and pk not in before:
                    discovered += 1
                    before.add(pk)
                record_contact(key, item)
        info = {'radio_contacts': len(entries), 'new_in_sync': discovered,
                'sync_at': utcnow().isoformat()}
        status_set('contact_sync', info)
        record_event('contacts_refreshed', info)
        return info

    async def refresh_channels(self):
        from meshcore import EventType
        channels = []
        for index in range(8):
            entry = {'index': index, 'name': '', 'configured': False}
            try:
                result = await asyncio.wait_for(self.mesh.commands.get_channel(index), timeout=5)
                if result.type != EventType.ERROR and isinstance(result.payload, dict):
                    name = str(result.payload.get('channel_name') or result.payload.get('name') or '')[:50]
                    entry.update(name=name, configured=bool(name))
            except Exception as exc:
                log.debug('Channel %d unavailable: %s', index, exc)
            channels.append(entry)
        status_set('channels', channels)

    async def poll_radio(self):
        from meshcore import EventType
        captured = {}
        for name, method in ([('battery', 'get_bat')] if RADIO_POWER_SOURCE != 'usb' else []) + [('core', 'get_stats_core'),
                             ('radio', 'get_stats_radio'), ('packets', 'get_stats_packets')]:
            try:
                result = await asyncio.wait_for(getattr(self.mesh.commands, method)(), timeout=12)
                if result.type != EventType.ERROR: captured[name] = jsonsafe(result.payload)
            except Exception as exc: log.warning('%s sample failed: %s', name, exc)
        def number(data, *names):
            if not isinstance(data, dict): return None
            for key in names:
                if key in data and isinstance(data[key], (int, float)):
                    return float(data[key])
            return None
        with Session.begin() as db:
            db.add(Sample(battery_pct=None if RADIO_POWER_SOURCE == 'usb' else number(captured.get('battery'), 'battery_pct'),
                          noise_floor=number(captured.get('radio'), 'noise_floor', 'noise_floor_dbm'),
                          uptime=number(captured.get('core'), 'uptime', 'uptime_seconds'),
                          rssi=number(captured.get('radio'), 'last_rssi', 'rssi', 'last_rssi_dbm'),
                          snr=number(captured.get('radio'), 'last_snr', 'snr', 'last_snr_db'),
                          packets_rx=number(captured.get('packets'), 'recv', 'rx', 'rx_count', 'num_recv'),
                          packets_tx=number(captured.get('packets'), 'sent', 'tx', 'tx_count', 'num_sent'),
                          stats=captured))
        status_set('last_stats', captured)

    async def execute(self, cmd):
        args = cmd.args or {}
        if cmd.kind == 'contacts': return await self.refresh_contacts()
        if cmd.kind == 'advert':
            from meshcore import EventType
            result = await self.mesh.commands.send_advert(flood=bool(args.get('flood', False)))
            if result.type == EventType.ERROR: raise RuntimeError(str(result.payload))
            return {'accepted': True}
        if cmd.kind == 'send':
            kind = args.get('kind')
            dest = str(args.get('destination', ''))
            body = str(args.get('text', ''))
            if len(body) > 180 or not body.strip(): raise ValueError('Message length must be 1-180 characters')
            if kind not in ('direct', 'channel'): raise ValueError('Invalid message kind')
            if kind == 'direct':
                with Session() as db:
                    contact = db.get(Contact, dest)
                    if contact is None: raise ValueError('Choose a known contact')
                result = await self.mesh.commands.send_msg(dest, body)
            else:
                if not dest.isdecimal() or not 0 <= int(dest) <= 7:
                    raise ValueError('Invalid channel index 0-7')
                result = await self.mesh.commands.send_chan_msg(int(dest), body)
            from meshcore import EventType
            if result.type == EventType.ERROR: raise RuntimeError(str(result.payload))
            data = jsonsafe(result.payload)
            with Session.begin() as db:
                db.add(Message(direction='out', kind=kind, target=dest, sender='local', body=body,
                               status='sent_unconfirmed' if kind == 'direct' else 'sent',
                               meta=data if isinstance(data, dict) else {'response': data}))
            record_event('outgoing_command_accepted', {'kind': kind, 'destination': dest})
            return {'accepted': True, 'radio_response': data}
        if cmd.kind == 'read_radio':
            from meshcore import EventType
            info = await self.mesh.commands.send_appstart()
            if info.type == EventType.ERROR: raise RuntimeError(str(info.payload))
            safe = jsonsafe(info.payload or {})
            permitted = ('name','radio_freq','radio_bw','radio_sf','radio_cr','tx_power','adv_lat','adv_lon')
            result = {k: safe[k] for k in permitted if k in safe}
            status_set('radio_config', result)
            return result
        if cmd.kind == 'configure_radio':
            updates = args.get('updates') or {}
            from meshcore import EventType
            result_data = {}
            if 'name' in updates:
                response = await self.mesh.commands.set_name(updates['name'])
                if response.type == EventType.ERROR: raise RuntimeError('Unable to set node name')
                result_data['name'] = updates['name']
            if 'tx_power' in updates:
                response = await self.mesh.commands.set_tx_power(updates['tx_power'])
                if response.type == EventType.ERROR: raise RuntimeError('Unable to set TX power')
                result_data['tx_power'] = updates['tx_power']
            if 'radio_freq' in updates:
                response = await self.mesh.commands.set_radio(updates['radio_freq'], updates['radio_bw'], updates['radio_sf'], updates['radio_cr'])
                if response.type == EventType.ERROR: raise RuntimeError('Unable to apply radio preset')
                result_data.update({k: updates[k] for k in ('radio_freq','radio_bw','radio_sf','radio_cr')})
            record_event('radio_configuration_changed', {'fields': sorted(updates)})
            return {'accepted': True, 'updated': result_data}
        if cmd.kind == 'channels':
            await self.refresh_channels()
            return {'channels': 'refreshed'}
        if cmd.kind in ('set_channel', 'delete_channel'):
            from meshcore import EventType
            idx = int(args['index'])
            if not 0 <= idx <= 7: raise ValueError('Invalid channel slot')
            if cmd.kind == 'delete_channel':
                response = await self.mesh.commands.set_channel(idx, '', bytes(16))
                if response.type == EventType.ERROR: raise RuntimeError('Radio rejected channel removal')
                record_event('channel_deleted', {'index': idx})
            else:
                name = args['name']
                sealed = args.get('sealed_key')
                if sealed:
                    secret = unseal_key(sealed)
                else:
                    old = await self.mesh.commands.get_channel(idx)
                    if old.type == EventType.ERROR: raise RuntimeError('Cannot read existing channel key; supply key')
                    old_payload = old.payload if isinstance(old.payload, dict) else {}
                    secret = old_payload.get('channel_secret', old_payload.get('secret'))
                    if isinstance(secret, str): secret = bytes.fromhex(secret)
                    if not isinstance(secret, bytes) or len(secret) != 16 or secret == bytes(16):
                        raise ValueError('Cannot rename empty channel without a 16-byte shared key')
                if len(secret) != 16: raise ValueError('Channel secret must be exactly 16 bytes')
                response = await self.mesh.commands.set_channel(idx, name, secret)
                if response.type == EventType.ERROR: raise RuntimeError('Radio rejected channel update')
                record_event('channel_updated', {'index': idx, 'name': name})
            await self.refresh_channels()
            return {'accepted': True, 'index': idx}
        raise ValueError('Unsupported command')

    async def drain_commands(self):
        with Session.begin() as db:
            cmd = db.scalars(select(Command).where(Command.state == 'pending')
                             .order_by(Command.id).with_for_update(skip_locked=True).limit(1)).first()
            if cmd is None: return False
            ident = cmd.id
            cmd.state = 'running'
        try:
            result = await asyncio.wait_for(self.execute(cmd), timeout=45)
        except Exception as exc:
            log.exception('Command %s failed', ident)
            with Session.begin() as db:
                row = db.get(Command, ident)
                row.state, row.error, row.finished = 'failed', ('Channel update failed; check collector logs' if cmd.kind in ('set_channel','delete_channel') else str(exc)[:1000]), utcnow()
                if cmd.kind in ('set_channel','delete_channel'): row.args = {}
        else:
            with Session.begin() as db:
                row = db.get(Command, ident)
                row.state, row.result, row.finished = 'complete', result, utcnow()
                if cmd.kind in ('set_channel','delete_channel'): row.args = {}
        return True

    async def run_session(self):
        await self.connect()
        last_contacts = last_stats = asyncio.get_running_loop().time()
        while True:
            if self.mesh and not getattr(self.mesh, 'is_connected', True):
                raise RuntimeError('Radio disconnected')
            drained = await self.drain_commands()
            now = asyncio.get_running_loop().time()
            if now - last_stats > 60:
                await self.poll_radio()
                last_stats = now
            if now - last_contacts > 300:
                await self.refresh_contacts()
                last_contacts = now
            status_set('worker_heartbeat', {'at': utcnow().isoformat(), 'mode': self.mode})
            if not drained: await asyncio.sleep(2)

    def alert_failure(self, reason):
        now = utcnow()
        if self.last_alert and now - self.last_alert < timedelta(minutes=15): return
        self.last_alert = now
        with Session.begin() as db:
            db.add(Alert(severity='critical', message=f'Collector offline: {reason}'[:400]))
        smtp_host = os.getenv('SMTP_HOST', '')
        recipient = os.getenv('ALERT_EMAIL', '')
        sender = os.getenv('SMTP_FROM', '')
        if smtp_host and recipient and sender:
            try:
                mail = EmailMessage()
                mail['Subject'] = 'MeshCore Station: radio collector offline'
                mail['From'] = sender
                mail['To'] = recipient
                mail.set_content(f'Collector offline at {now.isoformat()} UTC\n\nReason: {reason}\n')
                port = int(os.getenv('SMTP_PORT', '587'))
                with smtplib.SMTP(smtp_host, port, timeout=12) as smtp:
                    smtp.starttls()
                    if os.getenv('SMTP_USER'):
                        smtp.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD', ''))
                    smtp.send_message(mail)
            except Exception as exc:
                log.warning('SMTP alert delivery failed: %s', exc)

async def main():
    initialize()
    with Session.begin() as db:
        # Crash recovery for queued work; never replay a send (could duplicate RF messages).
        for cmd in db.scalars(select(Command).where(Command.state == 'running')).all():
            cmd.state, cmd.error, cmd.finished = 'failed', 'Collector restarted; not retried', utcnow()
            if cmd.kind in ('set_channel', 'delete_channel'): cmd.args = {}
    worker = Collector()
    while True:
        try:
            await worker.run_session()
        except asyncio.CancelledError:
            await worker.close()
            raise
        except Exception as exc:
            log.exception('Collector session failed')
            await worker.close()
            status_set('radio', {'connected': False, 'mode': worker.mode, 'error': str(exc)[:300]})
            worker.alert_failure(str(exc))
            await asyncio.sleep(10)

if __name__ == '__main__': asyncio.run(main())
