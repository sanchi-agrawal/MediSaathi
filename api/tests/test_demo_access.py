"""Temporary fictional access, not verified identities. No external calls."""
import time
import pytest
from fastapi.testclient import TestClient
from api.sessions import TTL_SECONDS
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import associate,save,approve
from api.tests.test_strip_api import action,save as save_strip

@pytest.fixture
def demo(monkeypatch):
    from api import hackathon_demo as d
    from api.dependencies import reader
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('Gemini forbidden'))
    from api.accounts.provider import SupabaseProvider
    monkeypatch.setattr(SupabaseProvider,'call',lambda *a,**kw:pytest.fail('Supabase forbidden'))
    with d.store.lock:d.store.sessions.clear()
    c=TestClient(d.app,base_url='https://localhost',headers={'Origin':'http://localhost:5177','X-MediSaathi-Action':'review'})
    return c,d
def login(c,email='visitor@example.test'):return c.post('/api/demo-access/login',json={'email':email})

def test_signup_name_refresh_logout_and_new_session(demo):
    c,d=demo
    r=c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':'  Asha   Sharma '})
    assert r.status_code==200 and r.json()['display_name']=='Asha Sharma'
    handle=c.cookies.get(d.COOKIE)
    assert c.get('/api/demo-access/status').json()['display_name']=='Asha Sharma'
    other=TestClient(d.app,base_url='https://localhost',headers=c.headers)
    login(other)
    assert other.get('/api/demo-access/status').json()['display_name'] is None
    assert c.get('/api/demo-access/status').json()['display_name']=='Asha Sharma'
    assert c.post('/api/demo-access/logout').status_code==200
    assert d.store.get(handle) is None
    assert c.get('/api/demo-access/status').json()['display_name'] is None
    login(c)
    assert c.get('/api/demo-access/status').json()['display_name'] is None

def test_signup_name_expires_and_direct_login_rotates(demo):
    c,d=demo
    details={'email':'visitor@example.test','display_name':'आशा शर्मा'}
    assert c.post('/api/demo-access/signup',json=details).json()['display_name']=='आशा शर्मा'
    handle=c.cookies.get(d.COOKIE)
    d.store.get(handle).created=time.monotonic()-TTL_SECONDS-1
    assert c.get('/api/demo-access/status').json()['display_name'] is None
    c.post('/api/demo-access/signup',json=details)
    login(c)
    assert c.get('/api/demo-access/status').json()['display_name'] is None

@pytest.mark.parametrize('name',[' ', 'A','123','x'*101])
def test_signup_rejects_invalid_names(demo,name):
    c,d=demo
    assert c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':name}).status_code==422
    assert not d.store.sessions

def test_signup_rejects_passwords_and_oversized_requests(demo):
    c,d=demo
    assert c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':'Asha Sharma','password':'not-allowed'}).status_code==422
    assert c.post('/api/demo-access/signup',content='x'*3000).status_code==413
    assert not d.store.sessions

def test_signup_name_refresh_logout_and_new_session(demo):
    c,d=demo
    r=c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':'  Asha   Sharma '})
    assert r.status_code==200 and r.json()['display_name']=='Asha Sharma'
    handle=c.cookies.get(d.COOKIE)
    assert c.get('/api/demo-access/status').json()['display_name']=='Asha Sharma'
    other=TestClient(d.app,base_url='https://localhost',headers=c.headers)
    login(other)
    assert other.get('/api/demo-access/status').json()['display_name'] is None
    assert c.get('/api/demo-access/status').json()['display_name']=='Asha Sharma'
    assert c.post('/api/demo-access/logout').status_code==200
    assert d.store.get(handle) is None
    assert c.get('/api/demo-access/status').json()['display_name'] is None
    login(c)
    assert c.get('/api/demo-access/status').json()['display_name'] is None

def test_signup_name_expires_and_direct_login_rotates(demo):
    c,d=demo
    details={'email':'visitor@example.test','display_name':'आशा शर्मा'}
    assert c.post('/api/demo-access/signup',json=details).json()['display_name']=='आशा शर्मा'
    handle=c.cookies.get(d.COOKIE)
    d.store.get(handle).created=time.monotonic()-TTL_SECONDS-1
    assert c.get('/api/demo-access/status').json()['display_name'] is None
    c.post('/api/demo-access/signup',json=details)
    login(c)
    assert c.get('/api/demo-access/status').json()['display_name'] is None

@pytest.mark.parametrize('name',[' ', 'A','123','x'*101])
def test_signup_rejects_invalid_names(demo,name):
    c,d=demo
    assert c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':name}).status_code==422
    assert not d.store.sessions

def test_signup_rejects_passwords_and_oversized_requests(demo):
    c,d=demo
    assert c.post('/api/demo-access/signup',json={'email':'visitor@example.test','display_name':'Asha Sharma','password':'not-allowed'}).status_code==422
    assert c.post('/api/demo-access/signup',content='x'*3000).status_code==413
    assert not d.store.sessions

def test_demo_login_cookie_and_refresh(demo):
    c,d=demo
    assert c.get('/api/demo-access/status').json()['active'] is False
    assert c.get('/api/prescriptions/current').status_code==401
    r=login(c);assert r.status_code==200
    assert r.json()['email_verified'] is False and r.json()['account_authentication'] is False
    cookie=r.headers['set-cookie'];assert cookie.startswith(d.COOKIE+'=') and all(x in cookie for x in ['HttpOnly','Secure','SameSite=strict','Path=/api'])
    for _ in range(3):assert c.get('/api/demo-access/status').json()['active']
    assert 'visitor@example.test' not in repr(d.store.sessions)
    assert len(d.store.sessions)==1

def test_logout_erases_workspace_and_old_cookie_cannot_replay(demo):
    c,d=demo;login(c);handle=c.cookies.get(d.COOKIE)
    from api.demo_fixture import PRESCRIPTION
    post(c,upload(c,PRESCRIPTION),'analyze')
    assert c.post('/api/demo-access/logout').json()['signed_out']
    assert d.store.get(handle) is None
    c.cookies.set(d.COOKIE,handle)
    assert c.get('/api/demo-access/status').json()['active'] is False
    assert c.get('/api/prescriptions/current').status_code==401

def test_expiry_rotation_and_other_demo_cookies_do_not_grant_access(demo):
    c,d=demo;login(c);old=c.cookies.get(d.COOKIE)
    assert login(c,'another@example.test').status_code==200 and d.store.get(old) is None
    handle=c.cookies.get(d.COOKIE);d.store.get(handle).created=time.monotonic()-TTL_SECONDS-1
    assert not c.get('/api/demo-access/status').json()['active']
    assert c.post('/api/session').status_code==401
    c.cookies.clear();c.cookies.set('medisaathi_demo',handle);c.cookies.set('medisaathi_team16c',handle)
    assert c.get('/api/prescriptions/current').status_code==401

@pytest.mark.parametrize('body',[{}, {'email':'bad'}, {'email':'visitor@example.test','password':'must-not-be-sent'}, {'email':'visitor@example.test','verified':True}])
def test_invalid_demo_login_has_no_session(demo,body):
    c,d=demo;r=c.post('/api/demo-access/login',json=body)
    assert r.status_code==422 and not d.store.sessions

def test_csrf_capacity_body_limit_and_accounts_disabled(demo):
    c,d=demo
    assert c.post('/api/demo-access/login',json={'email':'visitor@example.test'},headers={'Origin':'https://evil.example'}).status_code==403
    assert c.post('/api/demo-access/login',content='x'*3000).status_code==413
    d.store.limit=0
    try:assert login(c).status_code==503
    finally:d.store.limit=64
    assert c.get('/api/auth/status').status_code==403
    assert c.get('/api/account/prescriptions').status_code==403

def test_independent_demo_workspaces_and_full_fictional_flow(demo):
    from api.demo_fixture import PRESCRIPTION,STRIP
    c,d=demo;login(c)
    original=post(c,upload(c,PRESCRIPTION),'analyze').json()
    state=post(c,reviewed(c,original).json(),'confirm').json()
    for scope in ['instructions','investigations']:confirm(c,extract(c,state,scope),scope)
    assert post(c,state,'explanation',language='hi').status_code==200
    assert post(c,state,'matching').status_code==200
    assert post(c,state,'matching/selection',medicine_ref='medicine_001',candidate_id='person2:catalogue:MED001').status_code==200
    schedule=approve(c,save(c,associate(c))).json();assert schedule['status']=='succeeded'
    strip=c.post('/api/strips',content=STRIP,headers={'Content-Type':'image/png'}).json()
    strip=action(c,strip,'analyze').json();strip=save_strip(c,strip).json();assert action(c,strip,'confirm').json()['confirmed']
    other=TestClient(d.app,base_url='https://localhost',headers=c.headers);login(other)
    assert post(other,state,'confirm').status_code==409
    assert c.get('/api/prescriptions/current').json()['analysis_id']==state['analysis_id']
    assert post(c,state,'invalidate').status_code==200
    assert c.get('/api/scheduling/current').json()['result'] is None
    assert not c.get('/api/prescriptions/current').json()['confirmed']
