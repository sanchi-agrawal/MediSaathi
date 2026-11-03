"""Real local factory and reader path, with SDK mocked: never external calls."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from api.local_auth import create_local_app
from api.dependencies import reader
from api.tests.test_local_auth import HEADERS,DETAILS,PREFIX
from api.tests.test_prescriptions import image_bytes,post,reviewed,RECORD


def setup_client(tmp_path,monkeypatch,response=None,error=None):
    sdk=MagicMock();sdk.__enter__.return_value=sdk
    sdk.models.generate_content.return_value=SimpleNamespace(text=json.dumps([response or RECORD],ensure_ascii=False))
    if error:sdk.models.generate_content.side_effect=error
    monkeypatch.setattr(reader.genai,'Client',MagicMock(return_value=sdk))
    monkeypatch.setattr(reader,'_configuration',lambda:('mock-only-key','gemini-3.1-flash-lite'))
    app=create_local_app(tmp_path/'accounts.sqlite3',offline=False)
    c=TestClient(app,base_url='http://localhost',headers=HEADERS)
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    return c,sdk


@pytest.mark.parametrize('fmt,mime',[('PNG','image/png'),('JPEG','image/jpeg')])
def test_arbitrary_image_reaches_existing_gemini_reader(tmp_path,monkeypatch,fmt,mime):
    record={**RECORD,'raw_text':'DEMO सुबह १ गोली ५ दिन तक','name':'DEMO','frequency_pattern':None,'duration_days':5,'timing':'सुबह'}
    c,sdk=setup_client(tmp_path,monkeypatch,record)
    assert c.get('/api/recognition/capabilities').json()['mode']=='gemini'
    r=c.post('/api/prescriptions',content=image_bytes(fmt,(17,19)),headers={'Content-Type':mime})
    assert r.status_code==200 and sdk.models.generate_content.call_count==0
    data=post(c,r.json(),'analyze').json()
    assert data['status']=='succeeded' and not data['confirmed']
    assert data['records'][0]['raw_text']==record['raw_text']
    assert len(data['records'][0])==10 and data['records'][0]['needs_review']
    assert sdk.models.generate_content.call_count==1
    assert sdk.models.generate_content.call_args.kwargs['model']=='gemini-3.1-flash-lite'
    assert post(c,data,'confirm').status_code==409
    data=reviewed(c,data).json()
    assert post(c,data,'confirm').json()['confirmed']


def test_provider_failure_is_not_fixture_success(tmp_path,monkeypatch):
    c,sdk=setup_client(tmp_path,monkeypatch,error=ConnectionError('mock unavailable'))
    data=c.post('/api/prescriptions',content=image_bytes(),headers={'Content-Type':'image/png'}).json()
    result=post(c,data,'analyze')
    assert result.headers['content-type']=='application/json'
    result=result.json()
    assert result['status']=='failed' and result['error']['category']=='network_error'
    assert not result['confirmed'] and not result['records']
    assert sdk.models.generate_content.call_count==1


def test_real_mode_rejects_invalid_and_oversized_without_provider(tmp_path,monkeypatch):
    c,sdk=setup_client(tmp_path,monkeypatch)
    for data in (b'invalid',b'x'*(reader.MAX_IMAGE_BYTES+1)):
        r=c.post('/api/prescriptions',content=data,headers={'Content-Type':'image/png'})
        assert r.status_code in (413,422) and r.json()['detail']['category']=='image_validation_error'
    assert sdk.models.generate_content.call_count==0
