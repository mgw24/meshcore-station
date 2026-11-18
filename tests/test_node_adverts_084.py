from datetime import datetime, timezone, timedelta
from station.node_adverts import coords_ok, advertise_wait

NOW=datetime(2026,11,17,10,0,tzinfo=timezone.utc)

def test_coords_validation_and_local_nonprivacy_location():
    assert coords_ok(47.65,-117.42)
    assert not coords_ok(0,0)
    assert not coords_ok(float('nan'),0)
    assert not coords_ok(91,0)
    assert not coords_ok(20,181)

def test_advert_cooldown_per_mode():
    last={'local':(NOW-timedelta(minutes=3)).isoformat(), 'flood':(NOW-timedelta(hours=1)).isoformat()}
    assert advertise_wait(last,False,NOW)==120
    assert advertise_wait(last,True,NOW)==3600
    assert advertise_wait({},True,NOW)==0

def test_elapsed_and_invalid_time_are_safe():
    assert advertise_wait({'local':'not-a-date'},False,NOW)==0
    assert advertise_wait({'local':NOW.isoformat()},False,NOW)==300
