"""Local accounts, real Argon2/SQLite, fictional medical data; no providers."""
import time
import pytest
from fastapi.testclient import TestClient
from api.local_auth import create_local_app,COOKIE,PREFIX,digest

HEADERS={'Origin':'http://localhost:5177','X-MediSaathi-Action':'review'}
DETAILS={'email':'asha@example.test','full_name':'Asha Sharma','password':'Fictional-test-password-27'}

@pytest.fixture
def local(tmp_path,monkeypatch):
    from api.dependencies import reader
    from api.accounts.provider import SupabaseProvider
    monkeypatch.setattr(SupabaseProvider,'call',lambda *a,**kw:pytest.fail('Provider forbidden'))
    app=create_local_app(tmp_path/'accounts.sqlite3',offline=True)
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('Gemini forbidden'))
    return TestClient(app,base_url='http://localhost',headers=HEADERS),app

def signup(c,**changes):return c.post(PREFIX+'/signup',json={**DETAILS,**changes})
def login(c,**changes):return c.post(PREFIX+'/login',json={**{k:DETAILS[k] for k in ('email','password')},**changes})

def test_signup_hashes_and_cookie_restoration(local):
    c,app=local;r=signup(c,email='ASHA@example.test')
    assert r.status_code==200 and r.json()['user']['full_name']=='Asha Sharma'
    assert r.json()['user']['email']=='asha@example.test'
    cookie=r.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
    assert 'Secure' not in cookie  # Explicit loopback HTTP mode only.
    assert c.get(PREFIX+'/me').json()==r.json()
    with app.state.local_accounts.connect() as db:
        user=db.execute('SELECT * FROM users').fetchone()
        session=db.execute('SELECT * FROM sessions').fetchone()
        assert user['password_hash'].startswith('$argon2id$')
        assert DETAILS['password'] not in repr(dict(user))
        assert session['token_hash']==digest(c.cookies.get(COOKIE))
        assert session['token_hash']!=c.cookies.get(COOKIE)
        assert app.state.local_accounts.hasher.verify(user['password_hash'],DETAILS['password'])

def test_duplicates_credentials_logout_and_relogin(local):
    c,app=local;signup(c)
    assert signup(c,email='ASHA@example.test').status_code==409
    assert login(c,password='incorrect').status_code==401
    assert login(c,email='unknown@example.test').json()['detail']['category']=='invalid_credentials'
    assert login(c).status_code==200
    token=c.cookies.get(COOKIE)
    assert c.post(PREFIX+'/logout').json()['signed_out']
    c.cookies.set(COOKIE,token)
    assert c.get(PREFIX+'/me').status_code==401
    assert c.get('/api/prescriptions/current').status_code==401
    assert login(c).status_code==200

def test_restart_preserves_users_and_sessions_not_medical_data(local):
    c,app=local;signup(c);token=c.cookies.get(COOKIE)
    from api.demo_fixture import PRESCRIPTION
    from api.tests.test_prescriptions import upload,post
    post(c,upload(c,PRESCRIPTION),'analyze')
    restarted=create_local_app(app.state.local_accounts.path,offline=True)
    other=TestClient(restarted,base_url='http://localhost',headers=HEADERS)
    other.cookies.set(COOKIE,token)
    assert other.get(PREFIX+'/me').json()['user']['full_name']=='Asha Sharma'
    assert other.get('/api/prescriptions/current').status_code==404
    assert login(other).status_code==200

def test_expiry_csrf_and_no_legacy_authority(local):
    c,app=local;signup(c)
    with app.state.local_accounts.connect() as db:db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,))
    assert c.get(PREFIX+'/me').status_code==401
    assert c.get('/api/scheduling/current').status_code==401
    assert login(c).status_code==200
    assert c.post(PREFIX+'/logout',headers={'Origin':'https://evil.test'}).status_code==403
    assert c.post(PREFIX+'/logout',headers={'X-MediSaathi-Action':''}).status_code==403
    assert c.get(PREFIX+'/me').status_code==200
    assert c.post('/api/demo-access/login',json={'email':DETAILS['email']}).status_code==403
    assert c.get('/api/auth/status').status_code==403
    assert c.post(PREFIX+'/login',content='x'*5000).status_code==413
    c.cookies.set('medisaathi_account','obsolete-provider-cookie')
    assert login(c).status_code==200

def test_two_users_and_workflow_isolation(local):
    c,app=local;signup(c)
    other=TestClient(app,base_url='http://localhost',headers=HEADERS)
    signup(other,email='ravi@example.test',full_name='Ravi Kumar')
    a=c.get(PREFIX+'/me').json()['user'];b=other.get(PREFIX+'/me').json()['user']
    assert a['id']!=b['id'] and b['full_name']=='Ravi Kumar'
    assert c.get(PREFIX+'/me',params={'user_id':b['id']}).json()['user']['id']==a['id']
    from api.demo_fixture import PRESCRIPTION,STRIP
    from api.tests.test_prescriptions import upload,post,reviewed
    from api.tests.test_sections import extract,confirm
    from api.tests.test_downstream import associate,save,approve
    from api.tests.test_strip_api import action,save as save_strip
    data=post(c,upload(c,PRESCRIPTION),'analyze').json()
    data=post(c,reviewed(c,data).json(),'confirm').json()
    for scope in ('instructions','investigations'):confirm(c,extract(c,data,scope),scope)
    assert other.get('/api/prescriptions/current').status_code==404
    assert post(other,data,'confirm').status_code==409
    assert approve(c,save(c,associate(c))).json()['status']=='succeeded'
    assert post(c,data,'explanation',language='hi').status_code==200
    assert post(c,data,'matching').status_code==200
    strip=c.post('/api/strips',content=STRIP,headers={'Content-Type':'image/png'}).json()
    strip=action(c,strip,'analyze').json();strip=save_strip(c,strip).json()
    assert action(c,strip,'confirm').json()['confirmed']
    assert post(c,data,'invalidate').status_code==200
    assert c.get('/api/scheduling/current').json()['result'] is None
    assert c.post(PREFIX+'/logout').status_code==200
    assert other.get(PREFIX+'/me').json()['user']==b
    assert login(c).status_code==200
    assert c.get('/api/prescriptions/current').status_code==404

def test_https_cookie_and_rate_limit(tmp_path):
    app=create_local_app(tmp_path/'db.sqlite3',offline=True,secure=True)
    c=TestClient(app,base_url='https://localhost',headers=HEADERS)
    assert 'Secure' in signup(c).headers['set-cookie']
    assert c.get(PREFIX+'/me').status_code==200
    for _ in range(29):app.state.local_accounts.throttle('testclient')
    assert login(c).status_code==429

@pytest.mark.parametrize('changes',[{'full_name':' '},{'full_name':'123'},{'email':'invalid'},{'password':'short'},{'verified':True}])
def test_invalid_signup_is_safe_json(local,changes):
    c,app=local;r=signup(c,**changes)
    assert r.status_code==422 and r.json()['detail']['category']=='invalid_input'
    assert DETAILS['password'] not in r.text
