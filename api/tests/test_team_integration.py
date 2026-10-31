"""Fictional offline workflows: never instantiate a Gemini client or Telegram sender."""
import copy
from datetime import date,timedelta
from fastapi.testclient import TestClient
import pytest
from api.tests.test_downstream import setup,medicine,associate,save,approve,plan,current,linked,route
from api.tests.test_prescriptions import HEADERS,post,reviewed,upload
from api.team_matching import identify

def known():
    m=medicine();m.update(name='Dolo 650',salt='Paracetamol',strength='650 mg',form='tablet')
    return m
def match(client,state):return post(client,state,'matching')
def choose(client,state,candidate='person2:catalogue:MED001'):
    return post(client,state,'matching/selection',medicine_ref='medicine_001',candidate_id=candidate)

def test_confirmed_matching_selection_restoration_and_source_unchanged():
    client,app,state,_=setup(known())
    original=copy.deepcopy(state['records'])
    assert client.get('/api/matching/current').json()['state']=='not_requested'
    result=match(client,state);assert result.status_code==200,result.text
    row=result.json()['records'][0]
    assert row['state']=='review_required' and row['selected'] is None
    assert row['candidates'][0]['identity_verified'] is False
    assert row['candidates'][0]['review_reasons']==['release_type']
    assert choose(client,state,'MED001').status_code==409
    assert choose(client,state).json()['records'][0]['selected']=='person2:catalogue:MED001'
    assert client.get('/api/matching/current').json()['records'][0]['selected']=='person2:catalogue:MED001'
    assert client.get('/api/prescriptions/current').json()['records']==original
    assert len(original[0])==10
    assert match(client,state).json()['records'][0]['selected']=='person2:catalogue:MED001'

@pytest.mark.parametrize('field,value',[('salt','Different'),('strength','500 mg'),('form','capsule')])
def test_known_identity_conflicts_never_offered(field,value):
    m=known();m[field]=value
    row=dict(catalog_id='MED001',name='Dolo 650',salt='Paracetamol',strength='650 mg',form='tablet')
    assert identify(m,[row])['candidates']==[]

def test_missing_identity_and_release_conflicts():
    m=known();m['salt']=None
    row=dict(catalog_id='MED001',name='Dolo 650',salt='Paracetamol',strength='650 mg',form='tablet')
    result=identify(m,[row]);assert result['state']=='review_required'
    assert 'salt' in result['candidates'][0]['review_reasons']
    m['name']='Dolo 650 SR';row['name']='Dolo 650 IR'
    assert identify(m,[row])['candidates']==[]
    m['needs_review']=True;assert identify(m)['candidates']==[]

def test_matching_stale_cross_session_edits_and_replacement():
    client,app,state,_=setup(known());match(client,state);choose(client,state)
    other=TestClient(app,base_url='https://localhost',headers=HEADERS);other.post('/api/session')
    assert choose(other,state).status_code==409
    assert choose(client,{**state,'revision':'old'}).status_code==409
    dirty=post(client,state,'invalidate').json()
    assert client.get('/api/matching/current').status_code==409
    assert choose(client,state).status_code==409
    fresh=post(client,reviewed(client,dirty).json(),'confirm').json()
    assert client.get('/api/matching/current').json()['state']=='not_requested'
    assert choose(client,fresh).status_code==409
    upload(client);assert choose(client,fresh).status_code==409

def test_pricing_audited_zero_quotes_and_namespaces():
    client,_,_,_=setup()
    for kind in ['medicine','lab']:
        catalog=client.get('/api/pricing/catalogue',params={'kind':kind}).json()
        assert catalog['verified_delhi_quote_count']==0 and not catalog['comparisons_enabled']
        item=catalog['items'][0]
        r=client.post('/api/pricing/lookup',json={'kind':kind,'item_id':item['item_id']})
        assert r.status_code==200,r.text
        r=r.json();assert r['state']=='unavailable' and r['item']==item
        assert r['quotes']==r['comparisons']==[]
        assert r['message']=='No verified Delhi price available'
    assert client.post('/api/pricing/lookup',json={'kind':'medicine','item_id':'person2:catalogue:MED001'}).json()['state']=='no_match'
    assert client.post('/api/pricing/lookup',json={'kind':'medicine','name':'Dolo'}).json()['state']=='no_match'
    assert client.post('/api/pricing/lookup',json={'kind':'lab','name':'CBC','price':12}).status_code==422
    assert TestClient(client.app).get('/api/pricing/catalogue?kind=lab').status_code==401

def generated():
    client,app,state,ins=setup()
    p=plan();p['start_date']=(date.today()+timedelta(days=2)).isoformat()
    s=approve(client,save(client,associate(client),p)).json()
    assert s['status']=='succeeded'
    return client,app,state,s
def preview(client,s,**extra):
    return client.post(route(s,'/reminder-preview'),json={**linked(s),'clock_times':{'morning':'08:15','night':'20:30'},**extra})

def test_preview_only_current_approved_schedule_no_persistence_or_delivery(monkeypatch):
    from api.vendor.person3 import reminders
    def forbidden(*a,**kw):raise AssertionError('Persistence/delivery prohibited')
    for name in ['connect','load_schedule','sender_from_env','send_missed_alerts','make_sender']:
        monkeypatch.setattr(reminders,name,forbidden)
    client,app,state,s=generated()
    r=preview(client,s);assert r.status_code==200,r.text
    p=r.json();assert len(p['doses'])==6 and p['timezone']=='Asia/Kolkata'
    assert p['notifications_enabled'] is False
    assert p['doses'][0]['due_at'].endswith('08:15:00+05:30')
    assert all(d['amount']==1 and d['unit']=='tablet' for d in p['doses'])
    assert current(client)==s
    assert preview(client,{**s,'scheduling_revision':'stale'}).status_code==409
    assert preview(client,{**s,'association':{**s['association'],'association_id':'forged'}}).status_code==409
    other=TestClient(app,base_url='https://localhost',headers=HEADERS);other.post('/api/session')
    assert preview(other,s).status_code==409
    post(client,state,'invalidate')
    assert preview(client,s).status_code==409

@pytest.mark.parametrize('times',[{}, {'morning':'08:00'}, {'morning':'25:00','night':'20:00'}, {'morning':'08:00','night':'08:00'}, {'morning':'08:00','night':'20:00','noon':'12:00'}])
def test_preview_never_infers_clocks(times):
    client,_,_,s=generated();assert preview(client,s,clock_times=times).status_code==422

def test_preview_invalidated_on_plan_review_or_association_change():
    client,_,_,s=generated();assert preview(client,s).status_code==200
    client.post(route(s,'/schedule/invalidate'),json=linked(s))
    assert preview(client,s).status_code==409
    fresh=current(client);assert preview(client,fresh).status_code==409

def test_full_fictional_confirm_explain_match_schedule_preview_and_restore():
    client,_,state,s=generated()
    for language in ['en','hi','hinglish']:
        r=post(client,state,'explanation',language=language)
        assert r.status_code==200 and r.json()['payload']['language']==language
    assert match(client,state).status_code==200
    assert preview(client,s).status_code==200
    assert client.get('/api/prescriptions/current').json()['analysis_id']==state['analysis_id']
    assert current(client)['result']==s['result']

def test_offline_browser_fixture_all_scopes_and_cookie_namespace(monkeypatch):
    from api.dependencies import reader
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**k:pytest.fail('Provider forbidden'))
    from api import demo_fixture as demo
    from api.tests.test_sections import extract,confirm
    from api.tests.test_strip_api import action,save as strip_save
    client=TestClient(demo.app,base_url='https://localhost',headers={**HEADERS,'Origin':'http://localhost:5175'})
    cookie=client.post('/api/session').headers['set-cookie']
    assert cookie.startswith('medisaathi_team16c=') and 'Secure' in cookie and 'HttpOnly' in cookie
    state=upload(client,demo.PRESCRIPTION)
    state=post(client,state,'analyze').json();assert state['status']=='succeeded'
    state=post(client,reviewed(client,state).json(),'confirm').json()
    for scope in ['instructions','investigations']:
        section=extract(client,state,scope);assert section['status']=='succeeded',section.get('error')
        confirm(client,section,scope)
    candidates=match(client,state).json();assert candidates['records'][0]['candidates']
    assert choose(client,state).status_code==200
    p=plan();p['start_date']=(date.today()+timedelta(days=1)).isoformat()
    s=approve(client,save(client,associate(client),p)).json();assert s['status']=='succeeded'
    assert preview(client,s).status_code==200
    assert post(client,state,'explanation',language='hi').status_code==200
    strip=client.post('/api/strips',content=demo.STRIP,headers={'Content-Type':'image/png'}).json()
    strip=action(client,strip,'analyze').json();assert strip['status']=='succeeded',strip.get('error')
    strip=strip_save(client,strip).json();assert action(client,strip,'confirm').json()['confirmed']
    assert client.get('/api/prescriptions/current').json()['analysis_id']==state['analysis_id']
    assert client.get('/api/demo-info').json()['gemini_enabled'] is False

def test_pricing_ambiguous_and_error_are_not_unavailable_success(monkeypatch):
    import api.team_routes as routes
    client,_,_,_=setup()
    monkeypatch.setattr(routes,'lookup',lambda **kw:dict(state='error',error_code='dataset_invalid'))
    assert client.post('/api/pricing/lookup',json={'kind':'lab','item_id':'LAB001'}).status_code==503
    monkeypatch.setattr(routes,'lookup',lambda **kw:dict(state='ambiguous',error_code=None,item=None,candidates=[],quotes=[],comparisons=[],reasons=['multiple_exact_catalogue_matches']))
    assert client.post('/api/pricing/lookup',json={'kind':'lab','name':'Fictional'}).json()['state']=='ambiguous'
