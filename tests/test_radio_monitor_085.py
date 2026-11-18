"""0.8.5 monitor integration contract: no radio or browser required."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT/'static/index.html').read_text()
APP = (ROOT/'static/app.js').read_text()
CSS = (ROOT/'static/style.css').read_text()


def test_single_monitor_route_and_shared_window():
    assert HTML.count('data-view="monitor"') == 1
    assert 'id="view-monitor"' in HTML
    assert not re.search(r'id="view-(health|telemetry|diagnostics)"', HTML)
    assert not re.search(r'data-view="(health|telemetry|diagnostics)"', HTML)
    assert HTML.count('id="monitor-window"') == 1
    for value in (1, 6, 24, 168):
        assert f'<option value="{value}"' in HTML
    assert "request('/api/radio/trends?hours='+hours)" in APP
    assert "request('/api/radio/diagnostics?hours='+hours)" in APP
    assert 'const [trends,diagnostics]=await Promise.all' in APP


def test_monitor_has_unique_metric_sections_and_preserves_expert_data():
    for title in ('Signal &amp; Power','Packet Analysis &amp; Uptime','Transmission Evidence','Advanced Diagnostics'):
        assert title in HTML
    for target in ('trend-traffic','trend-paths','trend-errors','trend-rf','trend-snr','trend-uptime-chart',
                   'trend-reset-list','tx-confirmation-stats','diag-transmissions','diag-settings',
                   'health-rx-log','telemetry-info','battery-chart'):
        assert HTML.count(f'id="{target}"') == 1
    assert 'id="diag-traffic"' not in HTML
    assert 'id="health-rx-chart"' not in HTML
    assert 'id="health-error-chart"' not in HTML
    assert 'id="tx-confirmation-list"' not in HTML
    assert "if(st.power_source!=='usb')plot('battery-chart'" in APP


def test_no_broken_dom_references_in_runtime():
    required = set(re.findall(r"\$\('([\\w-]+)'\)", APP))
    actual = set(re.findall(r'\bid="([\\w-]+)"', HTML))
    # The direct ID references must all resolve in the assembled HTML.
    assert required <= actual, sorted(required-actual)
    assert 'monitor-view .chart{display:flex' in CSS


def test_history_endpoints_are_preserved():
    api=(ROOT/'station/web.py').read_text()
    assert '/api/radio/health' in api
    assert '/api/radio/trends' in api
    assert '/api/radio/diagnostics' in api
    assert '/api/radio/rx-log' in api
    assert 'MeshCore Station 0.8.6' in api
