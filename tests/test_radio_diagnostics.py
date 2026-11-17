from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from station.radio_diagnostics import sample_window, evidence_label

T = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)

def sample(seconds, rx, tx, errors, uptime, flood=None):
    return SimpleNamespace(
        ts=T + timedelta(seconds=seconds), stats={
            'packets': {'recv':rx, 'sent':tx, 'recv_errors':errors,
                        'flood_tx':flood, 'direct_tx': 0},
            'core': {'uptime_secs':uptime}},
        packets_rx=rx, packets_tx=tx, uptime=uptime,
        noise_floor=-117, rssi=-90, snr=4.0)

def test_reset_aware_counter_changes():
    rows=[sample(0,10,4,1,100,3), sample(60,15,6,1,160,5),
          sample(120,1,0,0,5,0), sample(180,9,3,2,65,2)]
    result=sample_window(rows,T+timedelta(seconds=181))
    assert result['resets']==1
    assert result['totals']['rx']==13
    assert result['totals']['tx']==5
    assert result['totals']['rx_errors']==2
    assert result['totals']['flood_tx']==4
    assert result['intervals'][1]['reset'] is True

def test_missing_or_single_sample_not_zero_traffic():
    assert sample_window([],T)['totals'] is None
    assert sample_window([sample(0,0,0,0,1)],T)['totals'] is None

def test_confirmations_are_conservative():
    assert 'unconfirmed' in evidence_label('radio_accepted','channel')
    assert 'recipient unconfirmed' in evidence_label('channel_echo','channel')
    assert 'ACK' in evidence_label('direct_ack','direct')
    assert 'Unclassified' in evidence_label('direct_ack','channel')
