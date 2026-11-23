"""0.8.7 UI integration contract without requiring a browser or radio."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()
CSS = (ROOT / "static/style.css").read_text()


def test_message_rows_are_collapsible_and_compact():
    assert '<details class="message-row ' in APP
    assert '<summary class="message-row-summary"' in APP
    assert 'message-row-preview' in APP
    assert 'message-row:not([open]) .message-row-expanded{display:none}' in CSS
    assert 'min-height:38px' in CSS
    assert 'min-height:44px' in CSS
    assert 'data-reply-message=' in APP


def test_reply_is_in_existing_composer_and_guards_direct_recipients():
    assert 'resolveDirectSender082(m.sender)' in APP
    assert 'matches.length===1?matches[0]:null' in APP
    assert "dest='channel:'+channel" in APP
    assert "body='@'+sender+' '" in APP
    assert "if(composed.length>input.maxLength)" in APP
    assert 'id="reply-context"' in HTML
    assert 'id="reply-cancel"' in HTML


def test_original_search_pagination_and_escape_retained():
    for token in ('/api/messages/history', 'loadOlderMessages081', 'history-search', 'history-direction', 'history-destination', 'tx_evidence'):
        assert token in APP + HTML
    assert '${H(m.text)}' in APP
    assert 'radio_accepted' in APP


def test_version_metadata():
    assert (ROOT/'VERSION').read_text().strip() == '0.8.8'
    assert '# MeshCore Station 0.8.8' in (ROOT/'README.md').read_text()
    assert 'MeshCore 0.8.8 · USB Companion' in HTML
    assert "'version': '0.8.8'" in (ROOT/'station/web.py').read_text()
