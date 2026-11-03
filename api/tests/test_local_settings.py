"""Local prototype settings, password policy, revocation and deletion isolation."""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from api.local_auth import create_local_app,PREFIX,COOKIE,digest

HEADERS={'Origin':'http://localhost:5177','X-MediSaathi-Action':'review'}
DETAILS={'full_name':'Asha Sharma','email':'asha@example.test','password':'Original-strong-passphrase'}
@pytest.fixture
def local(tmp_path,monkeypatch):
    from api.dependencies import reader
    from api.accounts.provider import SupabaseProvider
    app=create_local_app(tmp_path/'settings.sqlite3',offline=True)
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('Provider forbidden'))
    monkeypatch.setattr(SupabaseProvider,'call',lambda *a,**kw:pytest.fail('Provider forbidden'))
    return TestClient(app,base_url='http://localhost',headers=HEADERS),app
def signup(c,**kw):return c.post(PREFIX+'/signup',json={**DETAILS,**kw})
def login(c,password=DETAILS['password']):return c.post(PREFIX+'/login',json={'email':DETAILS['email'],'password':password})
def other(app):return TestClient(app,base_url='http://localhost',headers=HEADERS)

@pytest.mark.parametrize('length,status',[(5,422),(6,200),(7,200),(8,200),(128,200),(129,422)])
def test_new_password_boundaries(local,length,status):
    c,app=local;r=signup(c,password='a'*length)
    assert r.status_code==status
    if status==200:
        assert c.post(PREFIX+'/logout').status_code==200
        assert login(c,'a'*length).status_code==200
        with app.state.local_accounts.connect() as db:
            row=db.execute('SELECT password_hash FROM users').fetchone()
            assert row['password_hash'].startswith('$argon2id$')

def test_profile_updates_only_own_name(local):
    a,app=local;uid=signup(a).json()['user']['id'];b=other(app);signup(b,email='ravi@example.test',full_name='Ravi Kumar')
    assert a.post(PREFIX+'/profile',json={'full_name':'Asha Updated','id':'forged'}).status_code==422
    assert a.post(PREFIX+'/profile',json={'full_name':'Asha Updated','email':'ravi@example.test'}).status_code==422
    r=a.post(PREFIX+'/profile',json={'full_name':' Asha   Updated '});assert r.status_code==200
    assert r.json()['user']['id']==uid and r.json()['user']['email']==DETAILS['email']
    assert r.json()['user']['full_name']=='Asha Updated'
    assert b.get(PREFIX+'/me').json()['user']['full_name']=='Ravi Kumar'

def test_password_change_checks_current_and_revokes_all_sessions(local):
    a,app=local;signup(a);second=other(app);login(second)
    assert a.post(PREFIX+'/change-password',json={'current_password':'wrong','new_password':'new123'}).status_code==403
    assert a.post(PREFIX+'/change-password',json={'current_password':DETAILS['password'],'new_password':'short'}).status_code==422
    assert a.get(PREFIX+'/me').status_code==200
    r=a.post(PREFIX+'/change-password',json={'current_password':DETAILS['password'],'new_password':'new123'})
    assert r.status_code==200 and r.json()['signed_out']
    assert 'Max-Age=0' in r.headers['set-cookie']
    assert a.get(PREFIX+'/me').status_code==401 and second.get(PREFIX+'/me').status_code==401
    assert login(a).status_code==401
    assert login(a,'new123').status_code==200
    restarted=create_local_app(app.state.local_accounts.path,offline=True)
    assert login(other(restarted),'new123').status_code==200

@pytest.mark.parametrize('body',[{}, {'current_password':DETAILS['password']},{'current_password':DETAILS['password'],'confirm':False},{'current_password':DETAILS['password'],'confirm':1},{'current_password':DETAILS['password'],'confirm':True,'user_id':'someone-else'}])
def test_delete_requires_explicit_valid_consent(local,body):
    c,app=local;signup(c)
    assert c.post(PREFIX+'/delete-account',json=body).status_code==422
    assert c.get(PREFIX+'/me').status_code==200

def test_delete_requires_authentication_current_password_and_origin(local):
    c,app=local;body={'current_password':DETAILS['password'],'confirm':True}
    assert c.post(PREFIX+'/delete-account',json=body).status_code==401
    signup(c)
    assert c.post(PREFIX+'/delete-account',json=body,headers={'Origin':'https://evil.test'}).status_code==403
    assert c.post(PREFIX+'/delete-account',json={**body,'current_password':'incorrect'}).status_code==403
    assert c.get(PREFIX+'/me').status_code==200

def test_delete_is_atomic_scoped_and_revokes_every_account_session(local):
    a,app=local;uid=signup(a).json()['user']['id'];a2=other(app);login(a2)
    b=other(app);bid=signup(b,email='ravi@example.test',full_name='Ravi Kumar').json()['user']['id']
    for c in (a,a2,b):assert c.post('/api/session').status_code==200
    with app.state.local_accounts.connect() as db:
        keys=[r['token_hash'] for r in db.execute('SELECT token_hash FROM sessions WHERE user_id=?',(uid,))]
    handles=[app.state.local_accounts.workspaces[k] for k in keys]
    bhandle=app.state.local_accounts.workspaces[digest(b.cookies.get(COOKIE))]
    r=a.post(PREFIX+'/delete-account',json={'current_password':DETAILS['password'],'confirm':True})
    assert r.status_code==200 and r.json()['account_deleted'] and r.json()['medical_archives_deleted'] is False
    assert 'Max-Age=0' in r.headers['set-cookie']
    assert a.get(PREFIX+'/me').status_code==401 and a2.get(PREFIX+'/me').status_code==401
    assert a2.get('/api/prescriptions/current').status_code==401
    assert login(a).status_code==401
    assert b.get(PREFIX+'/me').json()['user']['id']==bid
    assert app.state.sessions.get(bhandle) is not None
    assert all(app.state.sessions.get(h) is None for h in handles)
    with app.state.local_accounts.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM sessions WHERE user_id=?',(uid,)).fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM users WHERE id=?',(uid,)).fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM users WHERE id=?',(bid,)).fetchone()[0]==1

def test_failed_delete_rolls_back_account_sessions_and_workspace(local):
    c,app=local;signup(c);c.post('/api/session');token=c.cookies.get(COOKIE)
    handle=app.state.local_accounts.workspaces[digest(token)]
    with app.state.local_accounts.connect() as db:
        db.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON users BEGIN SELECT RAISE(ABORT,'offline test'); END")
    r=c.post(PREFIX+'/delete-account',json={'current_password':DETAILS['password'],'confirm':True})
    assert r.status_code==503 and r.json()['detail']['category']=='storage_unavailable'
    assert 'set-cookie' not in r.headers
    assert c.get(PREFIX+'/me').status_code==200
    assert app.state.sessions.get(handle) is not None

def test_clear_workspace_keeps_accounts_and_other_sessions(local):
    a,app=local;signup(a);b=other(app);signup(b,email='ravi@example.test')
    a.post('/api/session');b.post('/api/session')
    old=app.state.local_accounts.workspaces[digest(a.cookies.get(COOKIE))]
    bh=app.state.local_accounts.workspaces[digest(b.cookies.get(COOKIE))]
    assert a.post(PREFIX+'/clear-workspace',json={'confirm':False}).status_code==422
    assert a.post(PREFIX+'/clear-workspace',json={'confirm':True}).json()['workspace_cleared']
    assert app.state.sessions.get(old) is None and app.state.sessions.get(bh) is not None
    assert a.get(PREFIX+'/me').status_code==200
    assert a.get('/api/prescriptions/current').status_code==404
