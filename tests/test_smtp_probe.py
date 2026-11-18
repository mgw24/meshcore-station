"""SMTP diagnostic checks without external networking or email delivery."""
from types import SimpleNamespace
import smtplib
import pytest
import station.digest as digest


def config(security='starttls', username=''):
    return SimpleNamespace(smtp_host='smtp.example.org', smtp_port=587,
                           smtp_security=security, smtp_username=username,
                           smtp_password_enc='enc' if username else '',
                           mail_from='station@example.org', mail_to='operator@example.org')


class FakeSMTP:
    sent = False
    started_tls = False
    did_login = False
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def ehlo(self): return (250, b'ok')
    def has_extn(self, name): return name == 'starttls'
    def starttls(self, **kwargs): self.started_tls = True
    def login(self, user, password): self.did_login = True
    def send_message(self, m): self.sent = True


def test_smtp_probe_does_not_send(monkeypatch):
    monkeypatch.setattr(digest.socket, 'getaddrinfo', lambda *a, **kw: [(0, 0, 0, '', ())])
    monkeypatch.setattr(digest.smtplib, 'SMTP', FakeSMTP)
    monkeypatch.setattr(digest, 'decrypt_password', lambda x: 'hidden')
    probe = config(username='operator')
    result = digest.probe_smtp(probe)
    assert 'no email was sent' in result
    assert FakeSMTP.sent is False


def test_smtp_probe_dns_failure_is_safe(monkeypatch):
    monkeypatch.setattr(digest.socket, 'getaddrinfo', lambda *a, **kw: (_ for _ in ()).throw(OSError('err')))
    with pytest.raises(digest.SMTPProbeError) as err:
        digest.probe_smtp(config())
    assert 'connection' in str(err.value).lower() or 'DNS' in str(err.value)
