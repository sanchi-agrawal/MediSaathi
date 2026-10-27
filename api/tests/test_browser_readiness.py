"""Presence-only health and fictional browser-shaped requests; all offline."""
from fastapi.testclient import TestClient
from api.dependencies import reader
from api.main import create_app
from api.tests.test_downstream import setup, associate, save, approve
from api.tests.test_prescriptions import HEADERS

def test_readiness_reports_loaded_contract_and_configuration_presence_only(monkeypatch):
    marker='FICTIONAL-CONFIGURATION-NOT-A-REAL-KEY'
    monkeypatch.setattr(reader,'_configuration',lambda:(marker,'fictional-model'))
    client=TestClient(create_app(),base_url='https://localhost',headers=HEADERS)
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.json()['api_contract']=='medisaathi-14d'
    assert response.json()['scheduling_contract']=='review-approve-v1'
    assert response.json()['gemini_configured'] is True
    assert marker not in response.text and 'fictional-model' not in response.text

def test_missing_gemini_configuration_does_not_disable_offline_scheduling(monkeypatch):
    def absent():raise reader.ReaderConfigurationError('Missing configuration')
    monkeypatch.setattr(reader,'_configuration',absent)
    client,_,_,_=setup()  # both fictional sections pass their real review/confirm endpoints
    assert client.get('/api/health').json()['gemini_configured'] is False
    result=approve(client,save(client,associate(client)))
    assert result.status_code==200
    assert result.json()['result']['payload']['total_units']==6
    assert result.json()['result']['payload']['end_date']=='2026-10-29'

def test_sessionless_current_route_has_structured_safe_error():
    client=TestClient(create_app(),base_url='https://localhost',headers=HEADERS)
    response=client.get('/api/scheduling/current')
    assert response.status_code==401
    assert response.json()['detail']['category']=='session_expired'

def test_guarded_capabilities_are_not_reported_as_scheduling_ready():
    client=TestClient(create_app(enabled_sections=('medicines',)),base_url='https://localhost',headers=HEADERS)
    assert client.get('/api/health').json()['scheduling_contract'] is None
    assert client.get('/api/scheduling/current').status_code==503
