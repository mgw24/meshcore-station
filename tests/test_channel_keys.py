"""Regression checks for MeshCore key-free hashtag channels.

Never print key material in application logs or send it to the browser.
"""
import hashlib
import pytest

from station.channel_keys import select_channel_key


def test_hashtag_derivation_matches_meshcore_protocol():
    result, mode = select_channel_key('#test', {'name': '', 'channel_secret': bytes(16)})
    assert result.hex() == '9cd8fcf22a47333b591d96a2b848b73f'
    assert mode == 'hashtag_derived'


def test_hashtag_is_case_sensitive():
    low, _ = select_channel_key('#test', {})
    high, _ = select_channel_key('#Test', {})
    assert low != high


def test_blank_key_renames_existing_channel_without_rekeying():
    existing = bytes.fromhex('0102030405060708090a0b0c0d0e0f10')
    result, mode = select_channel_key('#renamed', {'channel_name': '#original', 'channel_secret': existing.hex()})
    assert result == existing
    assert mode == 'preserved'


def test_blank_key_on_new_private_channel_requires_explicit_key():
    with pytest.raises(ValueError, match='explicit shared key'):
        select_channel_key('Private group', {'channel_name': '', 'channel_secret': bytes(16)})


def test_existing_unreadable_key_is_not_silently_replaced():
    with pytest.raises(ValueError, match='unavailable'):
        select_channel_key('#test', {'channel_name': '#old', 'channel_secret': 'invalid'})


def test_empty_payload_accepts_hashtag():
    key, mode = select_channel_key('#test', {})
    assert key == hashlib.sha256(b'#test').digest()[:16]
    assert mode == 'hashtag_derived'
