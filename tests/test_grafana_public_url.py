"""Keep the Grafana address configurable without trusting browser-supplied origins."""
import os

os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/meshcore-grafana-url-test.sqlite')
os.environ.setdefault('ADMIN_PASSWORD_SALT', '01' * 16)
os.environ.setdefault('ADMIN_PASSWORD_HASH', '02' * 32)
os.environ.setdefault('SESSION_SECRET', 'test-secret-grafana-' * 4)

import pytest
from station.web import grafana_public_url


@pytest.mark.parametrize('value, expected', [
    ('', None),
    (' https://grafana.example.net ', 'https://grafana.example.net/'),
    ('https://grafana.example.net/metrics/', 'https://grafana.example.net/metrics/'),
    ('http://192.0.2.2:3300/', 'http://192.0.2.2:3300/'),
    ('javascript:alert(1)', None),
    ('//grafana.example.net', None),
    ('https://admin:secret@grafana.example.net/', None),
    ('https://grafana.example.net/?session=secret', None),
    ('https://grafana.example.net/#fragment', None),
    ('https://grafana.example.net:abc/', None),
    ('https://grafana.example.net:0/', None),
    ('https://grafana.example.net/\nheader: injected', None),
])
def test_grafana_public_url(monkeypatch, value, expected):
    monkeypatch.setenv('GRAFANA_PUBLIC_URL', value)
    assert grafana_public_url() == expected
