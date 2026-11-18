from datetime import datetime, timezone
from station.tx_tracking import ack_code, received_ack, expected_ack, match_channel_echo


def test_direct_ack_checksum_normalized():
    assert ack_code(bytes.fromhex('1234abcd')) == '1234abcd'
    assert expected_ack({'expected_ack': '12:34:AB:CD'}) == '1234abcd'
    assert received_ack({'code': '1234abcd'}) == '1234abcd'
    assert ack_code('not-an-ack') is None
    assert ack_code(b'\x01\x02') is None


def test_channel_repeat_requires_full_match():
    t = datetime(2026,11,16,20,0,0,tzinfo=timezone.utc)
    p = {'channel_idx':0,'text':'test','timestamp':int(t.timestamp()),'path_len':2}
    assert match_channel_echo(p,channel='0',body='test',send_ts=t)
    for change in ({'channel_idx':1},{'text':'other'},{'path_len':0},
                   {'timestamp':int(t.timestamp())+16},{'timestamp':None}):
        assert not match_channel_echo({**p, **change},channel='0',body='test',send_ts=t)
    assert not match_channel_echo({'channel_idx':0,'text':'test'},channel='0',body='test',send_ts=t)
