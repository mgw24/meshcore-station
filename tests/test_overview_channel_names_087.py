"""Regression checks for Overview and Messages channel labels."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'static/app.js').read_text()


def test_overview_and_archive_share_the_same_resolver():
    assert 'function messageDisplaySender086(m)' in JS
    assert 'function messageHeading(m){const node=messageDisplaySender086(m)' in JS
    assert 'const author=messageDisplaySender086(m);' in JS
    assert 'rec.map(m=>item(messageHeading(m),m.text,m.ts,m.direction))' in JS


def test_channel_names_from_live_status_with_fallback():
    assert 'function channelName086(target)' in JS
    assert 'S.status?.channels' in JS
    assert 'S.channels?.slots' in JS
    assert 'Channel ${index}' in JS
    assert 'H(title)' in JS  # Overview stream HTML escaping
