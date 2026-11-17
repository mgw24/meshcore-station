"""0.8.1 message history endpoint: auth, server filters, safe search, stable cursor."""
import os
from datetime import datetime, timezone, timedelta

# The tests never talk to the real PostgreSQL installation or USB device.
os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/meshcore-081-test-bootstrap.sqlite')
os.environ.setdefault('ADMIN_PASSWORD_SALT', '01' * 16)
os.environ.setdefault('ADMIN_PASSWORD_HASH', '02' * 32)
os.environ.setdefault('SESSION_SECRET', 'test-secret-081-' * 4)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import station.web as web
from station.db import Base, Message, TxEvidence


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(web, 'Session', db_session)
    monkeypatch.setattr(web, 'initialize', lambda: None)
    monkeypatch.setattr(web, 'SPOOL_DIR', tmp_path)
    web.app.dependency_overrides.clear()
    now = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)
    with db_session.begin() as db:
        db.add_all([
            Message(id=1, ts=now, direction='in', kind='channel', target='0', sender='HamHock', body='Received public message', status='received'),
            Message(id=2, ts=now, direction='out', kind='channel', target='0', sender='MCS-T114 LewID', body='TX test 100%', status='sent'),
            Message(id=3, ts=now - timedelta(minutes=1), direction='in', kind='direct', target='private', sender='Friend', body='Direct hello', status='received'),
            Message(id=4, ts=now - timedelta(minutes=2), direction='out', kind='channel', target='1', sender='MCS-T114 LewID', body='Other channel', status='sent_unconfirmed'),
            Message(id=5, ts=now - timedelta(minutes=3), direction='in', kind='channel', target='0', sender='HamHock', body='Older public message', status='received'),
        ])
        db.add(TxEvidence(message_id=2, ts=now, kind='radio_accepted', detail={'raw_secret':'not_exposed'}))
    with TestClient(web.app) as client:
        yield client, db_session
    web.app.dependency_overrides.clear()
    engine.dispose()


def test_history_requires_login(api):
    client, _ = api
    assert client.get('/api/messages/history').status_code == 401


def test_history_paging_and_new_arrival(api):
    client, db_session = api
    web.app.dependency_overrides[web.user_session] = lambda: {'u':'tester'}
    first = client.get('/api/messages/history?limit=2').json()
    assert [x['id'] for x in first['items']] == [2, 1]  # timestamp tie -> id DESC
    assert first['total'] == 5 and first['has_more']
    assert first['next_cursor']['before_ts'].endswith('+00:00')
    # A new message inserted between page requests must not cause skipped/duplicate older messages.
    with db_session.begin() as db:
        db.add(Message(id=6, ts=datetime(2026,11,17,21,0,tzinfo=timezone.utc), direction='in', kind='channel', target='0', sender='Fresh', body='New arrival', status='received'))
    second = client.get('/api/messages/history', params={'limit':2, **first['next_cursor']}).json()
    assert [x['id'] for x in second['items']] == [3, 4]
    assert len({x['id'] for x in first['items'] + second['items']}) == 4
    assert second['total'] == 6
    assert second['has_more']
    third = client.get('/api/messages/history', params={'limit':2, **second['next_cursor']}).json()
    assert [x['id'] for x in third['items']] == [5]
    assert not third['has_more'] and third['next_cursor'] is None


def test_history_filters_and_safe_evidence(api):
    client, _ = api
    web.app.dependency_overrides[web.user_session] = lambda: {'u':'tester'}
    assert [x['id'] for x in client.get('/api/messages/history?direction=in&destination=direct').json()['items']] == [3]
    assert [x['id'] for x in client.get('/api/messages/history?direction=out&destination=channel:0').json()['items']] == [2]
    assert [x['id'] for x in client.get('/api/messages/history?q=HamHock').json()['items']] == [1,5]
    assert [x['id'] for x in client.get('/api/messages/history?q=%25').json()['items']] == [2]
    assert [x['id'] for x in client.get('/api/messages/history?q=_').json()['items']] == []
    row = client.get('/api/messages/history?q=TX%20test').json()['items'][0]
    assert row['tx_evidence'][0]['kind'] == 'radio_accepted'
    assert 'raw_secret' not in str(row['tx_evidence'])
    # The pre-existing list endpoint remains backward compatible.
    assert isinstance(client.get('/api/messages').json(), list)


def test_history_rejects_bad_filters(api):
    client, _ = api
    web.app.dependency_overrides[web.user_session] = lambda: {'u':'tester'}
    for params in ({'destination':'channel:9'}, {'before_id':4}, {'limit':101}, {'q':'x'*121}):
        assert client.get('/api/messages/history', params=params).status_code == 400
