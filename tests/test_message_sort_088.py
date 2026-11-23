"""0.8.8: deterministic global channel ordering, filters, and keyset cursors."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/meshcore-088-test-bootstrap.sqlite')
os.environ.setdefault('ADMIN_PASSWORD_SALT', '01' * 16)
os.environ.setdefault('ADMIN_PASSWORD_HASH', '02' * 32)
os.environ.setdefault('SESSION_SECRET', 'test-secret-088-' * 4)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import station.web as web
from station.db import Base, Message


@pytest.fixture
def history_api(monkeypatch, tmp_path):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(web, 'Session', session)
    monkeypatch.setattr(web, 'initialize', lambda: None)
    monkeypatch.setattr(web, 'SPOOL_DIR', tmp_path)
    web.app.dependency_overrides.clear()
    now = datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)
    cases = [
        (1, 'channel', '5', 'in', 'Channel five recent', now),
        (2, 'channel', '0', 'in', 'Public recent', now),
        (3, 'direct', 'friend', 'in', 'Private hello', now),
        (4, 'channel', '2', 'out', 'Channel two sent', now),
        (5, 'channel', '5', 'out', 'Channel five older', now - timedelta(minutes=10)),
        (6, 'channel', '7', 'in', 'Channel seven', now),
        (7, 'channel', '0', 'out', 'Public older', now - timedelta(minutes=10)),
        (8, 'channel', '1', 'in', 'Channel one', now),
        (9, 'direct', 'other', 'out', 'Private later', now - timedelta(minutes=2)),
        (10, 'channel', '5', 'in', 'Channel five same time', now),
    ]
    with session.begin() as db:
        db.add_all(Message(id=i, kind=k, target=t, direction=d, body=text, sender='Test',
                           status='received', ts=ts) for i, k, t, d, text, ts in cases)
    with TestClient(web.app) as client:
        web.app.dependency_overrides[web.user_session] = lambda: {'u': 'tester'}
        yield client, session
    web.app.dependency_overrides.clear()
    engine.dispose()


def ids(data):
    return [m['id'] for m in data['items']]


def test_global_sort_modes(history_api):
    c, _ = history_api
    assert ids(c.get('/api/messages/history?sort=newest').json()) == [10, 8, 6, 4, 3, 2, 1, 9, 7, 5]
    assert ids(c.get('/api/messages/history?sort=oldest').json()) == [5, 7, 9, 1, 2, 3, 4, 6, 8, 10]
    assert ids(c.get('/api/messages/history?sort=channel_asc').json()) == [2, 7, 8, 4, 10, 1, 5, 6, 3, 9]
    assert ids(c.get('/api/messages/history?sort=channel_desc').json()) == [6, 10, 1, 5, 4, 8, 2, 7, 3, 9]


@pytest.mark.parametrize('sort', ['newest', 'oldest', 'channel_asc', 'channel_desc'])
def test_cursor_paging_returns_all_ids_once(history_api, sort):
    client, _ = history_api
    expected = ids(client.get('/api/messages/history', params={'sort': sort}).json())
    seen = []
    cursor = {}
    for i in range(12):
        response = client.get('/api/messages/history', params={'sort': sort, 'limit': 2, **cursor})
        assert response.status_code == 200, response.text
        data = response.json()
        seen.extend(ids(data))
        if not data['has_more']:
            assert data['next_cursor'] is None
            break
        cursor = data['next_cursor']
        assert ('before_channel' in cursor) == sort.startswith('channel_')
    else:
        pytest.fail('Pagination did not terminate')
    assert seen == expected
    assert len(seen) == len(set(seen))


def test_channel_direction_search_combine_server_side(history_api):
    c, _ = history_api
    data = c.get('/api/messages/history', params={'destination': 'channel:5', 'direction': 'in',
                                                    'q': 'five', 'sort': 'oldest'}).json()
    assert ids(data) == [1, 10]
    assert data['total'] == 2
    assert ids(c.get('/api/messages/history', params={'destination':'direct', 'sort':'channel_asc'}).json()) == [3, 9]
    assert ids(c.get('/api/messages/history', params={'destination':'channel:0', 'sort':'channel_desc'}).json()) == [2, 7]


def test_new_message_before_cursor_does_not_duplicate(history_api):
    c, session = history_api
    first = c.get('/api/messages/history', params={'sort':'channel_asc', 'limit':3}).json()
    assert ids(first) == [2, 7, 8]
    with session.begin() as db:
        db.add(Message(id=11, ts=datetime(2026,11,22,21,0,tzinfo=timezone.utc),
                       direction='in', kind='channel', target='0', sender='Test', body='New public', status='received'))
    second = c.get('/api/messages/history', params={'sort':'channel_asc', 'limit':5, **first['next_cursor']}).json()
    assert 11 not in ids(second)
    assert set(ids(first)).isdisjoint(ids(second))
    assert ids(second) == [4, 10, 1, 5, 6]


def test_invalid_sort_and_channel_cursors_rejected(history_api):
    c, _ = history_api
    bad = [
        ({'sort':'channel_asc', 'before_channel':'0'}, 400),
        ({'sort':'newest', 'before_channel':'1'}, 400),
        ({'sort':'channel_desc', 'before_channel':'8', 'before_ts':'2026-11-22T20:00:00+00:00', 'before_id':2}, 400),
        ({'sort':'channel_asc', 'before_channel':'-1', 'before_ts':'2026-11-22T20:00:00+00:00', 'before_id':2}, 400),
        ({'sort':'timestamp'}, 422),
        ({'destination':'channel:8'}, 400),
    ]
    for params, status in bad:
        resp = c.get('/api/messages/history', params=params)
        assert resp.status_code == status, (params, resp.text)


def test_csv_export_escapes_spreadsheet_formulas(history_api):
    import csv
    import io
    c, session = history_api
    with session.begin() as db:
        db.add(Message(id=20, ts=datetime(2026,11,22,23,0,tzinfo=timezone.utc),
                       direction='in', kind='channel', target='@bad', sender='  =sender()',
                       body='\t+SUM(1,2)', status='received'))
    response = c.get('/api/export/messages.csv')
    assert response.status_code == 200
    assert 'text/csv' in response.headers['content-type']
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 11
    first = rows[0]
    assert first['target'] == "'@bad"
    assert first['sender'] == "'  =sender()"
    assert first['text'] == "'\t+SUM(1,2)"
    assert rows[-1]['text'] == 'Channel five older'


def test_csv_export_is_not_capped_to_page_size(history_api):
    c, session = history_api
    with session.begin() as db:
        db.add_all(Message(id=i, ts=datetime(2026,11,22,20,0,tzinfo=timezone.utc),
                           direction='in', kind='channel', target='0', sender='A',
                           body=f'msg-{i}', status='received') for i in range(100, 760))
    response = c.get('/api/export/messages.csv')
    assert response.status_code == 200
    # More than the 50-message interactive page limit and 300-message Overview limit.
    assert len(response.text.splitlines()) == 671
