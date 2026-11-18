"""Reset-aware rate conversion; no serial or DB required."""
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from station.radio_trends import trend

T=datetime(2026,11,17,tzinfo=timezone.utc)

def sample(t, rx=None, tx=None, err=None, uptime=None, snr=None, flood=None, direct=None, simulated=False):
    packets={'recv':rx,'sent':tx,'recv_errors':err,'flood_rx':flood,'direct_rx':direct}
    return SimpleNamespace(ts=T+timedelta(seconds=t), stats={'packets':packets,'core':{'uptime_secs':uptime}, 'simulated':simulated},
                           packets_rx=rx,packets_tx=tx,uptime=uptime,noise_floor=-117,rssi=-88,snr=snr)

def test_per_minute_and_missing_snr():
    r=trend([sample(0,rx=20,tx=4,err=1,uptime=100,flood=19,direct=1),
             sample(60,rx=50,tx=6,err=3,uptime=160,flood=47,direct=3)],1)
    p=r['points'][1]
    assert p['rx_per_min']==30
    assert p['tx_per_min']==2
    assert p['errors_per_min']==2
    assert p['flood_rx_per_min']==28
    assert p['snr_db'] is None
    assert r['resets']==[]

def test_uptime_reset_not_counted_as_negative_or_positive_rate():
    r=trend([sample(0,rx=200,tx=10,uptime=3000),sample(60,rx=3,tx=1,uptime=15)],1)
    assert r['reset_count']==1
    assert r['points'][1]['reset']
    assert r['points'][1]['rx_per_min'] is None

def test_counter_drop_even_if_uptime_monotonic_is_reset():
    r=trend([sample(0,rx=200,tx=10,uptime=100),sample(60,rx=0,tx=11,uptime=160)],1)
    assert r['reset_count']==1
    assert r['resets'][0]['counter_names']==['rx']

def test_gap_and_simulation_not_converted_to_zero():
    r=trend([sample(0,rx=4,tx=2,uptime=100),sample(60,rx=900,tx=99,uptime=160,simulated=True),
             sample(720,rx=10,tx=4,uptime=820)],1)
    assert r['samples']==2
    assert r['points'][1]['rx_per_min'] is None

def test_snr_distinct_from_dbm():
    r=trend([sample(0,rx=4,tx=0,uptime=100,snr=8),sample(60,rx=5,tx=1,uptime=160,snr=-1)],1)
    assert r['points'][0]['snr_db']==8
    assert r['points'][1]['noise_floor_dbm']==-117
    assert r['points'][1]['snr_db']==-1
