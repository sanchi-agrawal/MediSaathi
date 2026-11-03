"""Offline Supabase REST simulation, encrypted durable test DB; not hosted RLS verification."""
import copy,json,sqlite3,time,threading
from datetime import datetime,timezone
from uuid import uuid4
import httpx,pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from api.accounts.provider import SupabaseProvider
from api.accounts.service import AccountServices,COOKIE
from api.accounts.storage import ArchiveRepository
from api.main import create_app
from api.dependencies import AIIntegration,reader
from api.downstream.scheduling import schedule_handoff
from api.tests.test_prescriptions import HEADERS,upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import medicine,instruction,associate,save,approve

UIDS=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222']
PASSWORD='fictional-password-16E'
class HostedFake:
    def __init__(self,path):
        self.db=sqlite3.connect(path,check_same_thread=False);self.db.execute('create table if not exists archives (id text primary key, owner text, row text)');self.db.commit()
        self.lock=threading.RLock();self.calls=[];self.tokens={};self.refreshes={}
        self.users={f'user{i}@example.test':{'id':uid,'email':f'user{i}@example.test','password':PASSWORD,'email_confirmed_at':'2026-10-31T00:00:00Z','user_metadata':{'full_name':'Fictional user '+str(i)}} for i,uid in enumerate(UIDS)}
    def tokens_for(self,email):
        access='fictional-access-'+str(uuid4());refresh='fictional-refresh-'+str(uuid4());self.tokens[access]=email;self.refreshes[refresh]=email
        return {'access_token':access,'refresh_token':refresh,'expires_in':3600,'user':self.public(self.users[email])}
    def public(self,user):return {k:v for k,v in user.items() if k!='password'}
    def handle(self,request):
        with self.lock:return self._handle(request)
    def _handle(self,request):
        self.calls.append((request.method,request.url.path))
        path=request.url.path;body=json.loads(request.content) if request.content else {};token=request.headers.get('authorization','').removeprefix('Bearer ')
        email=self.tokens.get(token);user=self.users.get(email)
        def response(value,status=200):return httpx.Response(status,json=value)
        if path=='/auth/v1/token':
            if request.url.params.get('grant_type')=='refresh_token':
                email=self.refreshes.get(body['refresh_token'])
            else:
                email=body.get('email');u=self.users.get(email)
                if not u or body.get('password')!=u['password']:email=None
            return response(self.tokens_for(email)) if email else response({'error':'PRIVATE PROVIDER BODY MUST NOT LEAK'},400)
        if path=='/auth/v1/signup':
            email=body['email']
            if email not in self.users:self.users[email]={'id':str(uuid4()),'email':email,'password':body['password'],'email_confirmed_at':None,'user_metadata':body['data']}
            return response({'user':self.public(self.users[email])})
        if path=='/auth/v1/verify':
            email=body['email']
            if body['token']!='123456' or email not in self.users:return response({'error':'private-otp'},400)
            self.users[email]['email_confirmed_at']='2026-10-31T00:00:00Z';return response(self.tokens_for(email))
        if path=='/auth/v1/recover':return response({})
        if path=='/auth/v1/user':
            if not user:return response({'error':'private-token'},401)
            if request.method=='PUT':user['password']=body['password']
            return response(self.public(user))
        if path=='/auth/v1/logout':return response({})
        if path=='/rest/v1/prescription_archives':
            if not user:return response({},401)
            # Simulate RLS under caller JWT; real PostgreSQL policies still require a live test.
            if request.method=='POST':
                if body['owner_id']!=user['id']:return response({},403)
                row={**body,'created_at':datetime.now(timezone.utc).isoformat()}
                self.db.execute('insert into archives values (?,?,?)',(row['id'],row['owner_id'],json.dumps(row)));self.db.commit();return response([row])
            owner=request.url.params.get('owner_id','').removeprefix('eq.')
            if owner!=user['id']:return response([])
            rows=[json.loads(r[0]) for r in self.db.execute('select row from archives where owner=?',(owner,))]
            wanted=request.url.params.get('id','').removeprefix('eq.')
            if wanted:rows=[r for r in rows if r['id']==wanted]
            if request.method=='DELETE':
                for row in rows:self.db.execute('delete from archives where id=? and owner=?',(row['id'],owner))
                self.db.commit()
            return response(rows)
        return response({'error':'unexpected'},404)

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('Gemini forbidden'))
    host=HostedFake(tmp_path/'durable-test.sqlite');key=Fernet.generate_key();extract_calls=[]
    provider=SupabaseProvider('https://fictional.supabase.co','sb_publishable_fictional',transport=httpx.MockTransport(host.handle))
    def build():
        service=AccountServices(provider,key)
        def factory():
            def med(data):extract_calls.append('medicines');return [medicine()]
            def ins(data):extract_calls.append('instructions');return instruction(data,medicine())
            return AIIntegration(extractors={'medicines':med,'instructions':ins},downstream={'schedule':schedule_handoff})
        app=create_app(factory=factory,accounts=service)
        client=TestClient(app,base_url='https://localhost',headers=HEADERS)
        return client,app,service
    return host,build,extract_calls
def login(client,index=0,password=PASSWORD):return client.post('/api/auth/login',json={'email':f'user{index}@example.test','password':password})
def workspace(client):
    client.post('/api/session');s=post(client,upload(client),'analyze').json();s=reviewed(client,s).json();return post(client,s,'confirm').json()
def archive(client,save_image=True):
    binding=client.get('/api/account/workspace').json()
    r=client.post('/api/account/prescriptions',json={**binding,'consent':True,'save_image':save_image})
    assert r.status_code==200,r.text
    return r.json()

def test_missing_configuration_has_no_fake_auth():
    client=TestClient(create_app(accounts=False),base_url='https://localhost',headers=HEADERS)
    assert client.get('/api/auth/status').json()['configured'] is False
    assert client.post('/api/auth/login',json={'email':'test@example.test','password':PASSWORD}).status_code==503
    assert client.get('/api/account/prescriptions').status_code==503

def test_login_cookie_verified_identity_invalid_credentials_and_protected_routes(setup):
    host,build,_=setup;client,app,service=build()
    assert client.get('/api/prescriptions/current').status_code==401
    assert client.get('/api/account/prescriptions').status_code==401
    bad=login(client,password='wrong');assert bad.status_code==401 and 'PRIVATE' not in bad.text
    response=login(client);assert response.status_code==200
    assert 'access_token' not in response.text and 'refresh_token' not in response.text
    cookie=response.headers['set-cookie'];assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
    assert client.get('/api/auth/me').json()['user']['id']==UIDS[0]
    assert client.get('/api/auth/me').json()['user']['id']==UIDS[0]
    assert sum(p=='/auth/v1/user' for _,p in host.calls)>=3
    assert login(client).headers['set-cookie']!=cookie

def test_signup_email_verification_and_recovery(setup):
    _,build,_=setup;client,_,_=build();email='new@example.test'
    r=client.post('/api/auth/signup',json={'email':email,'password':PASSWORD,'name':'Fictional new'})
    assert r.status_code==200 and 'set-cookie' not in r.headers
    assert client.post('/api/auth/login',json={'email':email,'password':PASSWORD}).status_code==401
    assert client.post('/api/auth/verify',json={'email':email,'code':'000000'}).status_code==401
    assert client.post('/api/auth/verify',json={'email':email,'code':'123456'}).json()['verified']
    assert client.post('/api/auth/login',json={'email':email,'password':PASSWORD}).status_code==200
    assert client.post('/api/auth/forgot-password',json={'email':email}).status_code==200
    assert client.post('/api/auth/reset-password',json={'email':email,'code':'123456','password':'new-fictional-password'}).json()['reset']
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'email':email,'password':'new-fictional-password'}).status_code==200

def test_logout_revokes_workspace_and_cookie_replay(setup):
    _,build,_=setup;client,app,service=build();login(client);workspace(client)
    handle=client.cookies.get(COOKIE);record=service.find(handle);assert record.workspace
    response=client.post('/api/auth/logout');assert response.json()['signed_out']
    assert record.workspace not in app.state.sessions.sessions
    client.cookies.set(COOKIE,handle)
    assert client.get('/api/auth/me').status_code==401
    assert client.get('/api/prescriptions/current').status_code==401

def test_refresh_session_expiry_csrf_rate_limit_and_extra_claims(setup):
    host,build,_=setup;client,_,service=build();login(client)
    record=service.find(client.cookies.get(COOKIE));record.expires=time.time()-1
    assert client.get('/api/auth/me').status_code==200
    assert ('POST','/auth/v1/token') in host.calls
    record.until=time.time()-1;assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',headers={'Origin':'https://evil.example'},json={'email':'user0@example.test','password':PASSWORD}).status_code==403
    assert client.post('/api/auth/login',json={'email':'user0@example.test','password':PASSWORD,'user_id':UIDS[1]}).status_code==422
    service.attempts={}
    for _ in range(8):login(client,password='wrong')
    assert login(client,password='wrong').status_code==429

def test_account_workspace_ignores_anonymous_cookie_and_other_user(setup):
    _,build,_=setup;a,app,service=build();login(a);sa=workspace(a)
    b=TestClient(app,base_url='https://localhost',headers=HEADERS);login(b,1);sb=workspace(b)
    assert sa['analysis_id']!=sb['analysis_id']
    a.cookies.set('medisaathi_demo',service.find(b.cookies.get(COOKIE)).workspace)
    assert a.get('/api/prescriptions/current').json()['analysis_id']==sa['analysis_id']
    assert post(a,sb,'confirm').status_code==409

def test_encrypted_history_restart_and_owner_isolation(setup):
    host,build,_=setup;a,app,_=build();login(a);s=workspace(a);saved=archive(a)
    assert b'Fictional-A' not in json.dumps(host.db.execute('select row from archives').fetchall()).encode()
    view=a.get('/api/account/prescriptions/'+saved['id']).json()
    assert view['payload']['prescription']['sections']['medicines']['payload']==[medicine()]
    assert view['approval_authority_restored'] is False and 'image_base64' not in view['payload']
    b=TestClient(app,base_url='https://localhost',headers=HEADERS);login(b,1)
    assert b.get('/api/account/prescriptions').json()['records']==[]
    for method in ['get','delete']:
        assert getattr(b,method)('/api/account/prescriptions/'+saved['id']).status_code==404
    assert b.post('/api/account/prescriptions/'+saved['id']+'/continue',json={'version':saved['version'],'acknowledge_reconfirmation':True}).status_code==404
    restarted,_,_=build();assert restarted.get('/api/auth/me').status_code==401
    login(restarted);assert restarted.get('/api/account/prescriptions').json()['records'][0]['id']==saved['id']
    assert restarted.delete('/api/account/prescriptions/'+saved['id']).json()['deleted']
    assert restarted.get('/api/account/prescriptions').json()['records']==[]

def test_resume_replays_only_validated_data_without_old_confirmation_or_ocr(setup):
    _,build,calls=setup;client,_,_=build();login(client);s=workspace(client);confirm(client,extract(client,s,'instructions'),'instructions')
    schedule=approve(client,save(client,associate(client))).json();assert schedule['status']=='succeeded'
    saved=archive(client);before=list(calls)
    url='/api/account/prescriptions/'+saved['id']+'/continue'
    assert client.post(url,json={'version':str(uuid4()),'acknowledge_reconfirmation':True}).status_code==409
    r=client.post(url,json={'version':saved['version'],'acknowledge_reconfirmation':True});assert r.status_code==200,r.text
    current=client.get('/api/prescriptions/current').json()
    assert current['analysis_id']!=s['analysis_id'] and not current['confirmed']
    assert not current['sections']['instructions']['confirmed']
    assert client.get('/api/scheduling/current').json()['result'] is None
    assert post(client,s,'confirm').status_code==409
    assert post(client,current,'explanation',language='hi').status_code==409
    assert current['records']==[medicine()] and calls==before
    assert post(client,current,'confirm').status_code==200

def test_save_rejects_stale_snapshot_forged_records_and_optional_image(setup):
    _,build,_=setup;client,_,_=build();login(client);s=workspace(client)
    binding=client.get('/api/account/workspace').json()
    assert client.post('/api/account/prescriptions',json={**binding,'consent':True,'records':[]}).status_code==422
    post(client,s,'invalidate')
    assert client.post('/api/account/prescriptions',json={**binding,'consent':True}).status_code==409
    s=client.get('/api/prescriptions/current').json();reviewed(client,s)
    saved=archive(client,False)
    assert client.post('/api/account/prescriptions/'+saved['id']+'/continue',json={'version':saved['version'],'acknowledge_reconfirmation':True}).status_code==422

def test_privileged_key_and_untrusted_provider_identity_rejected(setup):
    import base64
    key='e30.'+base64.urlsafe_b64encode(b'{"role":"service_role"}').decode()+'.fake'
    with pytest.raises(ValueError):SupabaseProvider('https://fictional.supabase.co',key)
    _,build,_=setup;client,_,service=build();login(client)
    record=service.find(client.cookies.get(COOKIE))
    service.provider.user=lambda token:{'id':UIDS[1],'email':'user1@example.test','email_confirmed_at':'2026-10-31'}
    assert client.get('/api/auth/me').status_code==401 and record.revoked

def test_resume_requires_matching_original_image_and_ciphertext_integrity(setup):
    import base64
    from api.tests.test_prescriptions import image_bytes
    host,build,_=setup;client,_,_=build();login(client);state=workspace(client);saved=archive(client,False)
    url='/api/account/prescriptions/'+saved['id']+'/continue'
    body={'version':saved['version'],'acknowledge_reconfirmation':True}
    assert client.post(url,json={**body,'image_base64':base64.b64encode(image_bytes(size=(5,5))).decode()}).status_code==422
    assert client.get('/api/prescriptions/current').json()['analysis_id']==state['analysis_id']
    assert client.post(url,json={**body,'image_base64':base64.b64encode(image_bytes()).decode()}).status_code==200
    raw=json.loads(host.db.execute('select row from archives').fetchone()[0]);raw['payload_ciphertext']='not-a-valid-ciphertext'
    host.db.execute('update archives set row=? where id=?',(json.dumps(raw),saved['id']));host.db.commit()
    assert client.get('/api/account/prescriptions/'+saved['id']).status_code==503

def test_missing_storage_does_not_fabricate_persistence(setup):
    _,build,_=setup;client,_,service=build();service.repository=None
    assert client.get('/api/auth/status').json()['storage_configured'] is False
    login(client)
    assert client.get('/api/account/prescriptions').status_code==503
    assert client.get('/api/auth/me').status_code==200

def test_auth_body_bound_and_generic_recovery_responses(setup):
    _,build,_=setup;client,_,_=build()
    a=client.post('/api/auth/forgot-password',json={'email':'user0@example.test'}).json()
    b=client.post('/api/auth/forgot-password',json={'email':'missing@example.test'}).json()
    assert a==b
    assert client.post('/api/auth/login',json={'email':'user0@example.test','password':'x'*20000}).status_code==413
