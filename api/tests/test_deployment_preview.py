"""Offline HTTPS reverse-proxy boundary checks; no provider request."""
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from api.local_auth import create_local_app

ORIGIN='https://care.example.test'
HOST='api.example.test'
HEADERS={'Origin':ORIGIN,'X-MediSaathi-Action':'review'}

def configured(monkeypatch,tmp_path):
    monkeypatch.setenv('MEDISAATHI_DEPLOYMENT_MODE','preview')
    monkeypatch.setenv('MEDISAATHI_ORIGINS',ORIGIN)
    monkeypatch.setenv('MEDISAATHI_TRUSTED_HOSTS',HOST)
    monkeypatch.setenv('MEDISAATHI_LOCAL_DB',str(tmp_path/'preview.sqlite3'))

def test_preview_requires_explicit_https_origin_host_and_database(monkeypatch,tmp_path):
    monkeypatch.setenv('MEDISAATHI_DEPLOYMENT_MODE','preview')
    with pytest.raises(ValueError):create_local_app(offline=True)
    configured(monkeypatch,tmp_path)
    monkeypatch.setenv('MEDISAATHI_ORIGINS','http://care.example.test')
    with pytest.raises(ValueError):create_local_app(offline=True)
    monkeypatch.setenv('MEDISAATHI_ORIGINS',ORIGIN)
    monkeypatch.delenv('MEDISAATHI_TRUSTED_HOSTS')
    with pytest.raises(ValueError):create_local_app(offline=True)

def test_preview_secure_cookie_auth_workspace_and_origin_boundary(monkeypatch,tmp_path):
    configured(monkeypatch,tmp_path)
    app=create_local_app(offline=True)
    with TestClient(app,base_url='https://'+HOST,headers=HEADERS) as client:
        assert client.get('/api/health').status_code==200
        signup=client.post('/api/local-auth/signup',json={
            'full_name':'Preview Tester','email':'tester@example.test','password':'fictional-only'})
        assert signup.status_code==200,signup.text
        cookie=signup.headers['set-cookie'].lower()
        assert all(flag in cookie for flag in ('secure','httponly','samesite=strict','path=/api'))
        assert client.get('/api/local-auth/me').status_code==200
        assert client.post('/api/session').status_code==200
        from api.demo_fixture import PRESCRIPTION
        uploaded=client.post('/api/prescriptions',content=PRESCRIPTION,headers={
            'Content-Type':'image/png','X-MediSaathi-Filename':'fictional-prescription.png'})
        assert uploaded.status_code==200 and uploaded.headers['content-type'].startswith('application/json')
        analysis=client.post(f"/api/prescriptions/{uploaded.json()['analysis_id']}/analyze",json={
            'revision':uploaded.json()['revision']})
        assert analysis.status_code==200 and analysis.json()['status']=='succeeded'
        assert client.post('/api/local-auth/logout').status_code==200
        assert client.get('/api/local-auth/me').status_code==401
        rejected=client.post('/api/local-auth/login',headers={'Origin':'https://other.example.test'},json={
            'email':'tester@example.test','password':'fictional-only'})
        assert rejected.status_code==403 and rejected.json()['detail']['category']=='origin_rejected'
    with TestClient(app,base_url='https://untrusted.example.test',headers=HEADERS) as other:
        assert other.get('/api/health').status_code==400

def test_vercel_template_routes_api_before_spa_and_keeps_secrets_out():
    path=Path(__file__).parents[2]/'frontend'/'vercel.json.template'
    config=json.loads(path.read_text(encoding='utf8'))
    api,spa=config['rewrites']
    assert api['source']=='/api/:path*'
    assert api['destination'].endswith('/api/:path*')
    assert spa=={'source':'/(.*)','destination':'/index.html'}
    assert 'GEMINI_API_KEY' not in path.read_text(encoding='utf8')
