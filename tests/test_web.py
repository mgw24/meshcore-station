import io
import json
import zipfile
from fastapi.testclient import TestClient
from station.web import app, validate_firmware
from station.db import Session, Contact


def login(client):
    r=client.post('/api/login',json={'username':'admin','password':'correct horse battery staple'})
    assert r.status_code==200, r.text
    return r.json()['csrf']

def test_auth_and_messages_queue():
    with TestClient(app) as c:
        assert c.get('/api/status').status_code==401
        assert c.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==401
        csrf=login(c)
        assert c.get('/api/status').status_code==200
        assert c.post('/api/commands',json={'kind':'contacts'}).status_code==403
        r=c.post('/api/commands',headers={'x-csrf-token':csrf},json={'kind':'contacts'})
        assert r.status_code==200
        assert r.json()['state']=='pending'
        r=c.post('/api/commands',headers={'x-csrf-token':csrf},json={'kind':'send','destination':'unknown','text':'hello'})
        assert r.status_code==422


def firmware_zip():
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as z:
        z.writestr('manifest.json',json.dumps({'manifest':{'application':{'bin_file':'app.bin','dat_file':'app.dat'}}}))
        z.writestr('app.bin',bytes(range(256))*4)
        z.writestr('app.dat',bytes(range(100)))
    return buffer.getvalue()


def test_firmware_validator():
    data=firmware_zip()
    assert len(validate_firmware('Heltec_t114_companion_radio_usb-v1.18.0.zip',data))==64
    for bad in ['Heltec_t114_repeater.zip','RAK4631_companion_radio_usb.zip','Heltec_t114_companion_radio_ble.zip']:
        try: validate_firmware(bad,data)
        except ValueError: pass
        else: assert False, f'Accepted forbidden filename: {bad}'


def test_firmware_queue_requires_confirmation(monkeypatch):
    import station.web as web
    monkeypatch.setattr(web, "SIMULATION", False)
    with TestClient(app) as c:
        csrf=login(c)
        zip_data=firmware_zip()
        def post(phrase):
            return c.post('/api/firmware/upload',headers={'x-csrf-token':csrf},
                          data={'confirmation':phrase},
                          files={'file':('Heltec_t114_companion_radio_usb-test.zip',zip_data,'application/zip')})
        assert post('no').status_code==422
        r=post('FLASH T114')
        assert r.status_code==200, r.text
        assert r.json()['status']=='queued'
        assert len(c.get('/api/firmware/jobs').json())>=1
