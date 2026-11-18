"""0.8.7 channel history name contract, without live T114 hardware."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'static/app.js').read_text()


def test_channel_names_come_from_live_status_not_database_rewrites():
    assert 'function channelName086(target)' in JS
    assert 'S.status?.channels' in JS
    assert 'S.channels?.slots' in JS
    assert "const author=messageDisplaySender086(m)" in JS
    assert 'const author=messageDisplaySender086(m)' in JS
    assert 'const dest=isChannel?`${channelName} (#${m.target})`' in JS


def test_channel_author_and_real_sender_are_distinct():
    assert 'const actualSender=genericChannelSender?' in JS
    assert 'channelReplySender082(m)' in JS
    assert '<dt>From</dt><dd>${H(actualSender)}</dd>' in JS
    assert "const sender=channelReplySender082(m)" in JS


def test_fallback_and_safe_output():
    assert 'Number.isInteger(index)' in JS
    assert 'return found?String(found.name).trim():`Channel ${index}`' in JS
    assert '<strong class="message-row-sender" title="${H(author)}">${H(author)}</strong>' in JS
    assert '<span class="message-row-target" title="${H(dest)}">${H(dest)}</span>' in JS


def test_version_migration_is_consistent():
    assert (ROOT / 'VERSION').read_text().strip() == '0.8.7'
    assert "'version': '0.8.7'" in (ROOT / 'station/web.py').read_text()
    assert 'MeshCore 0.8.7 · USB Companion' in (ROOT / 'static/index.html').read_text()
