"""Provider failure classification and persistence without any network calls."""
import json
import httpx
import pytest
from google.genai import errors
from api.tests.test_local_real_ocr import setup_client
from api.tests.test_prescriptions import post,image_bytes
from api import extraction_diagnostics

@pytest.mark.parametrize('exception,category,status',[
 (errors.ClientError(429,{'message':'PRIVATE'}),'quota_exceeded',429),
 (errors.ClientError(401,{'message':'PRIVATE'}),'authentication_error',401),
 (errors.ClientError(403,{'message':'PRIVATE'}),'permission_denied',403),
 (errors.ClientError(404,{'message':'PRIVATE'}),'model_unavailable',404),
 (errors.ClientError(400,{'message':'PRIVATE'}),'provider_bad_request',400),
 (errors.ServerError(503,{'message':'PRIVATE'}),'provider_error',503),
 (httpx.ReadTimeout('PRIVATE'),'extraction_timeout',None),
 (httpx.ConnectError('PRIVATE'),'network_error',None),
])
def test_wrapped_provider_failure_persists_safe_status(tmp_path,monkeypatch,exception,category,status):
    path=tmp_path/'diagnostics.jsonl';monkeypatch.setattr(extraction_diagnostics,'PATH',path)
    c,sdk=setup_client(tmp_path,monkeypatch,error=exception)
    data=c.post('/api/prescriptions',content=image_bytes(),headers={'Content-Type':'image/png'}).json()
    result=post(c,data,'analyze').json()
    assert result['status']=='failed' and result['error']['category']==category
    assert result['records'] is None and not result['confirmed']
    assert sdk.models.generate_content.call_count==1
    assert post(c,data,'analyze').status_code==409 # old revision never retries
    entries=[json.loads(v) for v in path.read_text().splitlines()]
    assert len(entries)==1 and entries[0]['provider_http_status']==status
    assert 'PRIVATE' not in path.read_text() and 'PRIVATE' not in json.dumps(result)
    assert set(entries[0])=={'category','failure_stage','exception_type','upstream_exception_type','provider_http_status','provider_response_observed','section','timestamp','diagnostic_reference','runtime_kind'}
    assert entries[0]['runtime_kind']=='test'
    assert result['diagnostic_reference']==entries[0]['diagnostic_reference']
