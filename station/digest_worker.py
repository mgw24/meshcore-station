"""Single-instance, PostgreSQL-backed digest delivery scheduler.

This container never opens USB serial. A scheduled slot is queued at most once,
and an interrupted 'sending' operation is NOT retried automatically (SMTP may
have accepted the email before a crash). Admin can manually resend.
"""
from datetime import timedelta
import logging
import os
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from station.db import (initialize, Session, DigestSettings, DigestDelivery, utcnow,
                        status_set)
from station.digest import (settings, validate_mail_ready, latest_due, prior_slot,
                            aware_utc, lookback, report, send_email, safe_smtp_error, probe_smtp)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('meshcore.digest')
POLL = max(10, min(120, int(os.getenv('DIGEST_POLL_SECONDS', '30'))))


def queue_scheduled(now=None):
    now = now or utcnow()
    with Session.begin() as db:
        cfg = settings(db)
        if not cfg.enabled:
            return None
        try:
            validate_mail_ready(cfg)
            due = latest_due(cfg, now)
        except ValueError:
            log.warning('Digest configuration incomplete; scheduled send not queued')
            return None
        if due is None or due < aware_utc(cfg.schedule_anchor):
            return None
        key = 'slot:' + due.isoformat()
        found = db.scalar(select(DigestDelivery.id).where(DigestDelivery.slot_key == key))
        if found:
            return None
        prior = db.scalar(select(DigestDelivery).where(
            DigestDelivery.kind == 'scheduled', DigestDelivery.status == 'sent',
            DigestDelivery.period_end <= due).order_by(DigestDelivery.period_end.desc()).limit(1))
        start = aware_utc(prior.period_end) if prior else prior_slot(cfg, due)
        # Catch up a bounded period if the station was offline for many days.
        start = max(start, due - timedelta(days=30))
        db.add(DigestDelivery(slot_key=key, kind='scheduled', status='queued',
                              period_start=start, period_end=due))
        try:
            db.flush()
        except IntegrityError:
            # With two workers the unique key prevents duplicate sends.
            db.rollback()
            return None
        log.info('Queued scheduled digest for %s', due.isoformat())
        return key


def claim_next():
    with Session.begin() as db:
        job = db.scalar(select(DigestDelivery).where(DigestDelivery.status == 'queued')
                        .order_by(DigestDelivery.created_at, DigestDelivery.id)
                        .with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        job.status = 'sending'
        job.started_at = utcnow()
        db.flush()
        return job.id


def deliver(job_id):
    with Session() as db:
        job = db.get(DigestDelivery, job_id)
        if not job or job.status != 'sending':
            return
        cfg = db.get(DigestSettings, 1)
        kind = job.kind
        start = aware_utc(job.period_start)
        end = aware_utc(job.period_end)
        if not cfg:
            error = 'Digest settings missing'
        elif kind == 'scheduled' and not cfg.enabled:
            with Session.begin() as update_db:
                rec = update_db.get(DigestDelivery, job_id)
                rec.status = 'skipped'
                rec.finished_at = utcnow()
                rec.error = 'Digests disabled before delivery'
            return
        else:
            error = None
        try:
            if error:
                raise ValueError(error)
            if kind == 'probe':
                detail = probe_smtp(cfg)
                with Session.begin() as update_db:
                    rec = update_db.get(DigestDelivery, job_id)
                    rec.status = 'passed'
                    rec.finished_at = utcnow()
                    rec.error = detail
                log.info('SMTP diagnostic job %s passed', job_id)
                return
            if kind == 'test':
                subject = 'MeshCore Station · SMTP test'
                text_body = ('This is a test email from your MeshCore Station.\n'
                             'SMTP connectivity and authentication succeeded.\n'
                             'No mesh messages or channel secrets are included.\n')
                html_body = None
                count = 0
            else:
                content = report(cfg, start, end, db=db)
                subject, text_body, html_body = content['subject'], content['text'], content['html']
                count = content['message_count']
            recipients = send_email(cfg, subject, text_body, html_body)
        except Exception as exc:
            sanitized = safe_smtp_error(exc)
            log.warning('Digest job %s (%s) failed (%s): %s', job_id, kind, type(exc).__name__, sanitized)
            with Session.begin() as update_db:
                rec = update_db.get(DigestDelivery, job_id)
                rec.status = 'failed'
                rec.error = sanitized
                rec.finished_at = utcnow()
            return
    with Session.begin() as db:
        rec = db.get(DigestDelivery, job_id)
        rec.status = 'sent'
        rec.finished_at = utcnow()
        rec.message_count = count
        rec.recipient_count = recipients
        rec.error = ''
    log.info('Digest job %s delivered (%s, %s recipients, %s messages)',
             job_id, kind, recipients, count)


def tick():
    status_set('digest_worker_heartbeat', {'at': utcnow().isoformat()})
    queue_scheduled()
    for _ in range(10):  # Drain limited queue; old jobs do not block new ones indefinitely.
        job_id = claim_next()
        if job_id is None:
            break
        deliver(job_id)


def recover_interrupted_jobs():
    # A worker crash may have happened after SMTP accepted a message. Do not
    # blindly retry: operators can explicitly use Send Now if needed.
    with Session.begin() as db:
        interrupted = db.scalars(select(DigestDelivery).where(DigestDelivery.status == 'sending')).all()
        for job in interrupted:
            job.status = 'unknown'
            job.finished_at = utcnow()
            job.error = 'Worker restarted during SMTP delivery; delivery uncertain. No automatic retry.'
        if interrupted:
            log.warning('%s interrupted digest jobs marked delivery-uncertain', len(interrupted))


def main():
    initialize()
    recover_interrupted_jobs()
    log.info('Email digest worker started; poll=%ds', POLL)
    while True:
        try:
            tick()
        except Exception as exc:
            log.error('Digest scheduler loop failed: %s', type(exc).__name__)
        time.sleep(POLL)

if __name__ == '__main__':
    main()
