#!/usr/bin/env python3
"""Root-owned host helper; never exposes HTTP or a Docker socket to the web app.

The API can only enqueue a vetted T114 USB Companion ZIP. This agent independently
revalidates the package, stops the collector, flashes, and restarts the collector.
"""
import hashlib
import json
import os
import re
import select
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HOME = Path('/opt/meshcore-station')
SPOOL = HOME / 'runtime' / 'spool'
JOBS = SPOOL / 'jobs'
STATES = SPOOL / 'states'
LOGS = SPOOL / 'logs'
PACKAGES = SPOOL / 'packages'
COMPOSE = ['/usr/bin/docker', 'compose', '--profile', 'radio', '-f', str(HOME / 'compose.yaml')]
NRFUTIL = '/opt/meshcore-flasher-venv/bin/adafruit-nrfutil'
MAX_PACKAGE = 8 * 1024 * 1024
FILENAME = re.compile(r'^Heltec_t114(?:_without_display)?_companion_radio_usb[^/\\]*\.zip$', re.I)

def settings():
    result = {}
    for line in (HOME / '.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1)
            result[k.strip()]=v.strip().strip('"').strip("'")
    return result

def update(jid, status, message='', **extra):
    file = STATES / f'{jid}.json'
    try: obj = json.loads(file.read_text())
    except (FileNotFoundError, ValueError): obj = {'id': jid}
    obj.update({'status':status, 'message':message, 'updated':datetime.now(timezone.utc).isoformat(), **extra})
    temp = STATES / f'.{jid}.{uuid.uuid4().hex}.tmp'
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    os.fchmod(fd, 0o644)  # API container must read agent updates; spool directory limits access.
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(obj, out, indent=2)
        os.replace(temp, file)
    finally:
        if temp.exists(): temp.unlink()

def validate(job):
    jid = job.get('id','')
    if not str(uuid.UUID(jid)) == jid:
        raise ValueError('Invalid job ID')
    name=job.get('filename','')
    if not FILENAME.fullmatch(name): raise ValueError('Non-T114 USB Companion firmware rejected')
    package = PACKAGES / f'{jid}.zip'
    if package.is_symlink() or not package.is_file() or package.stat().st_size > MAX_PACKAGE:
        raise ValueError('Missing, oversized, or symlinked package')
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    if digest != job.get('sha256'): raise ValueError('Firmware checksum mismatch')
    with zipfile.ZipFile(package) as archive:
        if sum(x.file_size for x in archive.infolist()) > 20*1024*1024:
            raise ValueError('Archive exceeds uncompressed size limit')
        names=set(archive.namelist())
        manifest=json.loads(archive.read('manifest.json'))
        app=manifest.get('manifest',{}).get('application',{})
        for field in ('bin_file','dat_file'):
            if app.get(field) not in names or '/' in app[field] or '\\' in app[field]:
                raise ValueError('Malformed DFU application payload')
    return package, digest

def run(cmd, log):
    log.write('$ '+ ' '.join(str(a) for a in cmd)+'\n')
    log.flush()
    with subprocess.Popen(cmd, cwd=HOME, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, bufsize=0) as p:
        deadline = time.monotonic() + 300
        fd = p.stdout.fileno()
        while True:
            if time.monotonic() > deadline:
                p.kill()
                p.wait()
                raise TimeoutError('Firmware operation exceeded 5 minutes')
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                log.write(chunk.decode('utf-8', errors='replace'))
                log.flush()
            if p.poll() is not None and not ready:
                # Keep reading until EOF; p.poll() alone doesn't drain stdout.
                continue
        rc = p.wait(timeout=10)
        if rc:
            raise RuntimeError(f'Exit status {rc} from {cmd[0]}')

def process(jobpath):
    jid = jobpath.stem
    if not re.fullmatch(r'[0-9a-f-]{36}', jid): return
    logpath=LOGS / f'{jid}.log'
    if logpath.is_symlink():
        update(jid, 'failed', 'Unsafe log path: symlink not accepted')
        jobpath.unlink()
        return
    collector_stopped = False
    def open_log():
        fd = os.open(logpath, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
        os.fchmod(fd, 0o644)  # API container needs to show progress logs.
        return os.fdopen(fd, 'a', encoding='utf-8')
    try:
        job=json.loads(jobpath.read_text())
        if job.get('id') != jid: raise ValueError('Job identifier mismatch')
        package, digest=validate(job)
        cfg=settings()
        device=cfg.get('RADIO_DEVICE','')
        if not device.startswith('/dev/') or device == '/dev/' or not Path(device).exists():
            raise RuntimeError(f'Radio serial device not found: {device}')
        if not Path(NRFUTIL).is_file(): raise RuntimeError('Flasher not installed; rerun install.sh')
        with open_log() as log:
            log.write(f'Firmware package: {job["filename"]}\nVerified SHA-256: {digest}\n')
            update(jid,'stopping','Stopping radio collector to free the serial port')
            run(COMPOSE+['stop','collector'],log)
            collector_stopped=True
            time.sleep(2)
            update(jid,'flashing','Flashing Nordic DFU ZIP over USB')
            run([NRFUTIL,'--verbose','dfu','serial','--package',str(package),
                 '-p',device,'-b','115200','--singlebank','--touch','1200'],log)
            update(jid,'restarting','Flashed; restarting collector')
            run(COMPOSE+['up','-d','--force-recreate','--no-deps','collector'],log)
            collector_stopped=False
            update(jid,'complete','Flasher exited successfully; confirm radio reconnects in Overview')
    except Exception as exc:
        update(jid,'failed',f'{type(exc).__name__}: {exc}')
        with open_log() as log: log.write(f'ERROR: {type(exc).__name__}: {exc}\n')
    finally:
        if collector_stopped:
            try:
                with open_log() as log:
                    update(jid,'restarting','Update failed; attempting to restart collector')
                    run(COMPOSE+['up','-d','--force-recreate','--no-deps','collector'],log)
            except Exception as exc:
                with open_log() as log: log.write(f'Collector restart failed: {exc}\n')
            # Keep a failed state even if the collector could be restarted.
            update(jid,'failed','Flashing failed. Collector restart attempted; check the log and USB passthrough.')
        try: jobpath.unlink()
        except OSError: pass

def main():
    for path in (JOBS,STATES,LOGS,PACKAGES):path.mkdir(parents=True,exist_ok=True)
    print('MeshCore firmware agent ready',flush=True)
    while True:
        for jobpath in sorted(JOBS.glob('*.json')):
            if jobpath.is_symlink(): continue
            process(jobpath)
        time.sleep(3)

if __name__=='__main__':main()
