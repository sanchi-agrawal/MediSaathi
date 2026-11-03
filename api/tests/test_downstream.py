"""Fictional offline schedule/association/API tests; no extractors call Gemini."""
import copy
import hashlib
import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from api.dependencies import AIIntegration
from api.main import create_app
from api.downstream.scheduling import schedule_handoff
from api.downstream import scheduling
from api.tests.test_prescriptions import HEADERS, image_bytes, upload, post, reviewed
from api.tests.test_sections import extract, confirm


def medicine():
    return dict(raw_text='Fictional-A take 1 tablet BD morning and night for 3 days', name='Fictional-A',
                salt=None, strength=None, form='tablet', frequency_pattern='BD', duration_days=3,
                timing='morning and night', confidence=None, needs_review=False)

def instruction(data, med):
    return dict(schema_version='medication-instructions-v1', source_image_sha256=hashlib.sha256(data).hexdigest(),
                instructions=[dict(instruction_id='instruction_001', medicine_name_raw='Fictional-A', raw_text=med['raw_text'],
                dose_quantity_raw='1', dose_unit_raw='tablet', frequency_raw='BD', route_raw=None,
                timing_raw='morning and night', duration_raw='3 days', uncertainty_reasons=[], needs_review=False,
                confirmation_required=True)], issues=[], confirmation_required=True)

def setup(med=None, ins_edit=None, callback=schedule_handoff):
    med=copy.deepcopy(med or medicine())
    def instructions(data):
        result=instruction(data,med)
        if ins_edit: ins_edit(result['instructions'][0])
        return result
    downstream={} if callback is None else {'schedule':callback}
    app=create_app(factory=lambda:AIIntegration(extractors={'medicines':lambda _:[copy.deepcopy(med)], 'instructions':instructions},downstream=downstream))
    client=TestClient(app,base_url='https://localhost',headers=HEADERS)
    client.post('/api/session')
    state=post(client,upload(client),'analyze').json()
    state=post(client,reviewed(client,state).json(),'confirm').json()
    ins=confirm(client,extract(client,state,'instructions'),'instructions')
    return client,app,state,ins

def current(client):
    response=client.get('/api/scheduling/current');assert response.status_code==200,response.text
    return response.json()

def binding(s):
    return {k:s[k] for k in ('medicine_revision','instruction_revision','scheduling_revision')}

def linked(s):
    return {**binding(s),'association_id':s['association']['association_id']}

def route(s,action):return '/api/prescriptions/'+s['analysis_id']+action

def associate(client):
    s=current(client)
    r=client.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001'})
    assert r.status_code==200,r.text
    return r.json()

def plan():
    return dict(dose_quantity=1,dose_unit='tablet',duration_days=3,administrations_by_slot=dict(morning=1,noon=0,night=1,bedtime=0),start_date='2026-10-27')

def save(client,s,p=None):
    r=client.put(route(s,'/schedule/review'),json={**linked(s),'plan':p or plan()})
    assert r.status_code==200,r.text
    return r.json()

def approve(client,s):return client.post(route(s,'/schedule/approve'),json=linked(s))

def test_complete_flow_uses_engine_only_after_separate_approval_and_preserves_source(monkeypatch):
    calls=[]; original=scheduling.engine.build_schedule
    monkeypatch.setattr(scheduling.engine,'build_schedule',lambda *args: calls.append(copy.deepcopy(args)) or original(*args))
    client,app,med,ins=setup()
    s=associate(client);assert s['plan'] is None and not calls
    assert approve(client,s).status_code==409
    s=save(client,s);assert s['status']=='reviewed' and not calls
    result=approve(client,s);assert result.status_code==200,result.text
    result=result.json();p=result['result']['payload']
    assert p['total_units']==6 and p['doses_by_slot']==dict(morning=1,noon=0,night=1,bedtime=0)
    assert p['start_date']=='2026-10-27' and p['end_date']=='2026-10-29' and p['refill_date'] is None
    assert len(calls)==1 and calls[0][0]['confirmed'] is True
    session=next(iter(app.state.sessions.sessions.values()))
    assert session.ai.snapshot()['prescription']['sections']['medicines']['reviewed']==[medicine()]
    assert len(session.ai.snapshot()['prescription']['sections']['medicines']['reviewed'][0])==10
    assert approve(client,s).status_code==409 # replay cannot call engine again

def test_ml_and_long_term_refill_boundary():
    med=medicine();med.update(form='syrup',duration_days=30,raw_text='Fictional-A 1 mL BD morning and night for 30 days')
    client,_,_,_=setup(med,lambda i:i.update(dose_unit_raw='mL',duration_raw='30 days'))
    p=plan();p.update(dose_unit='mL',duration_days=30)
    result=approve(client,save(client,associate(client),p));assert result.status_code==200,result.text
    payload=result.json()['result']['payload']
    assert payload['unit']=='mL' and payload['total_units']==60
    assert payload['end_date']=='2026-11-25' and payload['refill_date']=='2026-11-22'

@pytest.mark.parametrize('change',[
    {'dose_quantity_raw':None},{'dose_unit_raw':None},{'frequency_raw':'OD'},
    {'frequency_raw':'1-0-1'},{'frequency_raw':'PRN'},{'duration_raw':'5-7 days'},
    {'duration_raw':'2 weeks'},{'dose_quantity_raw':'1/2'},
    {'timing_raw':'08:00 and 20:00'},{'raw_text':'Fictional-A then taper'},
    {'uncertainty_reasons':['conflicting_instructions']},
])
def test_unsafe_sources_never_reach_engine(change,monkeypatch):
    calls=[];monkeypatch.setattr(scheduling.engine,'build_schedule',lambda *a:calls.append(a))
    client,_,_,_=setup(ins_edit=lambda i:i.update(change))
    s=save(client,associate(client));r=approve(client,s)
    assert r.status_code==422 and r.json()['detail']['category']=='unsafe_schedule'
    assert calls==[] and current(client)['result'] is None and current(client)['status']=='failed'

@pytest.mark.parametrize('change',[{'dose_quantity':2},{'dose_unit':'mL'},{'duration_days':4},
    {'administrations_by_slot':dict(morning=1,noon=1,night=0,bedtime=0)}])
def test_plan_cannot_disagree_with_source(change):
    client,_,_,_=setup();p=plan();p.update(change)
    assert approve(client,save(client,associate(client),p)).status_code==422

def test_explicit_named_slots_are_honored_without_abbreviation_reinterpretation():
    med=medicine();med.update(raw_text='Fictional-A 1 tablet BD noon and night for 3 days',timing='noon and night')
    client,_,_,_=setup(med,lambda i:i.update(timing_raw='noon and night'))
    p=plan();p['administrations_by_slot']=dict(morning=0,noon=1,night=1,bedtime=0)
    r=approve(client,save(client,associate(client),p))
    assert r.status_code==200 and r.json()['result']['payload']['doses_by_slot']==dict(morning=0,noon=1,night=1,bedtime=0)

@pytest.mark.parametrize('field,value',[('dose_quantity',True),('dose_quantity',0),('dose_quantity',-1),
    ('dose_quantity',1001),('dose_quantity','NaN'),('duration_days',True),('duration_days',366),
    ('administrations_by_slot',dict(morning=True,noon=0,night=1,bedtime=0))])
def test_strict_request_types_and_limits(field,value):
    client,_,_,_=setup();s=associate(client);p=plan();p[field]=value
    assert client.put(route(s,'/schedule/review'),json={**linked(s),'plan':p}).status_code==422

@pytest.mark.parametrize('number',['NaN','Infinity','-Infinity'])
def test_nonfinite_json_rejected(number):
    client,_,_,_=setup();s=associate(client)
    body=json.dumps({**linked(s),'plan':plan()}).replace('"dose_quantity": 1','"dose_quantity": '+number)
    assert client.put(route(s,'/schedule/review'),content=body,headers={'Content-Type':'application/json'}).status_code==422

def test_invalid_date_is_not_scheduled():
    client,_,_,_=setup();s=associate(client);p=plan();p['start_date']='2026-02-30'
    assert client.put(route(s,'/schedule/review'),json={**linked(s),'plan':p}).status_code==422
    assert current(client)['result'] is None

def test_unconfirmed_empty_stale_cross_session_and_forged_approvals():
    client,app,med,ins=setup();s=associate(client)
    for field in ('medicine_revision','instruction_revision','scheduling_revision'):
        body=linked(s);body[field]='stale'
        assert client.post(route(s,'/schedule/approve'),json=body).status_code==409
    assert client.post('/api/prescriptions/other/schedule/approve',json=linked(s)).status_code==409
    other=TestClient(app,base_url='https://localhost',headers=HEADERS);other.post('/api/session')
    assert other.post(route(s,'/schedule/approve'),json=linked(s)).status_code==409
    for extra in ({'approved':True},{'event':'forged'},{'plan':plan()}):
        assert client.post(route(s,'/schedule/approve'),json={**linked(s),**extra}).status_code==422
    dirty=post(client,med,'invalidate');assert dirty.status_code==200
    now=current(client);assert not now['ready'] and now['association'] is None
    assert client.post(route(now,'/associations'),json={**binding(now),'medicine_ref':'medicine_001','instruction_id':'instruction_001'}).status_code==409

@pytest.mark.parametrize('scope',['medicines','instructions'])
def test_dirty_api_scope_invalidates_internal_links_and_results_immediately(scope):
    client,app,med,ins=setup();s=approve(client,save(client,associate(client))).json()
    path='/invalidate' if scope=='medicines' else '/sections/instructions/invalidate'
    state=med if scope=='medicines' else ins
    assert client.post(route(s,path),json={'revision':state['revision']}).status_code==200
    now=current(client)
    assert not now['ready'] and now['result'] is None and now['association'] is None
    session=next(iter(app.state.sessions.sessions.values()))
    snap=session.ai.snapshot();assert not snap['associations'] and not snap['derived']
    assert approve(client,s).status_code==409

def test_plan_edit_association_change_and_clear_invalidate_results():
    client,_,_,_=setup();s=approve(client,save(client,associate(client))).json()
    old=s; s=client.post(route(s,'/schedule/invalidate'),json=linked(s)).json()
    assert s['result'] is None and s['plan'] is None and s['status']=='associated'
    assert approve(client,old).status_code==409
    s=approve(client,save(client,s)).json()
    duplicate=client.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001'})
    assert duplicate.status_code==409 and duplicate.json()['detail']['category']=='association_exists'
    assert current(client)['result'] is not None
    assert client.request('DELETE',route(s,'/associations'),json=binding(s)).status_code==200
    assert current(client)['association'] is None
    upload(client,image_bytes(size=(5,5)));assert not current(client)['ready']
    client.delete('/api/prescriptions/current');assert client.get('/api/scheduling/current').status_code==409

@pytest.mark.parametrize('damage',['extra','missing','nonfinite','slot','total','date','exception'])
def test_invalid_engine_output_and_exceptions_never_become_schedules(damage,monkeypatch):
    original=scheduling.engine.build_schedule
    def broken(*args):
        if damage=='exception':raise RuntimeError('never expose provider or patient detail')
        result=original(*args)
        if damage=='extra':result['safe_to_take']=True
        if damage=='missing':result.pop('unit')
        if damage=='nonfinite':result['total_units']=float('inf')
        if damage=='slot':result['doses_by_slot']['morning']=2
        if damage=='total':result['total_units']=99
        if damage=='date':result['end_date']+=timedelta(days=1)
        return result
    monkeypatch.setattr(scheduling.engine,'build_schedule',broken)
    client,_,_,_=setup();r=approve(client,save(client,associate(client)))
    assert r.status_code==502 and 'patient detail' not in r.text
    assert current(client)['result'] is None

def test_unavailable_is_explicit_and_clinical_review_does_not_erase_ocr_flag():
    client,_,_,_=setup(callback=None)
    assert approve(client,save(client,associate(client))).status_code==503
    med=medicine();med['needs_review']=True
    client,_,_,_=setup(med);r=approve(client,save(client,associate(client)))
    assert r.status_code==200 and r.json()['status']=='succeeded'
    assert r.json()['result']['payload']['status']=='ok'
    assert current(client)['medicines'][0]['needs_review'] is True

def test_concurrent_approvals_call_engine_once():
    calls=[]
    def callback(request):calls.append(1);return schedule_handoff(request)
    client,_,_,_=setup(callback=callback);s=save(client,associate(client))
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:approve(client,s),range(2)))
    assert sorted(r.status_code for r in results)==[200,409] and len(calls)==1

def test_guarded_diagnostic_capabilities_remain_unavailable():
    app=create_app(enabled_sections=('medicines',))
    client=TestClient(app,base_url='https://localhost',headers=HEADERS);client.post('/api/session')
    assert client.get('/api/scheduling/current').status_code==503

def test_schema_valid_but_inconsistent_injected_result_is_rejected():
    def callback(request):
        result=schedule_handoff(request);result['total_units']=999
        return result
    client,app,_,_=setup(callback=callback)
    r=approve(client,save(client,associate(client)))
    assert r.status_code==502 and r.json()['detail']['category']=='invalid_response'
    assert current(client)['result'] is None and current(client)['association'] is None
    assert not next(iter(app.state.sessions.sessions.values())).ai.snapshot()['derived']

def test_no_missing_association_ids_or_forged_medicine_records():
    client,_,_,_=setup();s=current(client)
    for body in ({**binding(s),'medicine_ref':'medicine_999','instruction_id':'instruction_001'},
                 {**binding(s),'medicine_ref':'medicine_001','instruction_id':'other-session'},
                 {**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001','medicine':medicine()}):
        r=client.post(route(s,'/associations'),json=body)
        assert r.status_code in (409,422)
        s=current(client)
    assert s['association'] is None and s['result'] is None

def test_empty_results_do_not_invent_scheduling_inputs():
    client,_,med,_=setup()
    fresh=client.put(route(med,'/review'),json={'revision':med['revision'],'records':[]}).json()
    post(client,fresh,'confirm')
    s=current(client)
    assert s['medicines']==[] and s['result'] is None
    assert client.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001'}).status_code==422

def test_unconfirmed_instruction_and_expired_session_block_schedule_access():
    client,app,_,ins=setup()
    client.post(route(ins,'/sections/instructions/invalidate'),json={'revision':ins['revision']})
    s=current(client)
    assert not s['ready']
    assert client.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001'}).status_code==409
    next(iter(app.state.sessions.sessions.values())).created-=1801
    assert client.get('/api/scheduling/current').status_code==401

def test_strip_and_investigation_changes_preserve_the_confirmed_schedule():
    client,_,_,_=setup();s=approve(client,save(client,associate(client))).json()
    inv=client.get(route(s,'/sections/investigations')).json()
    client.post(route(s,'/sections/investigations/invalidate'),json={'revision':inv['revision']})
    assert current(client)['result']==s['result']
    assert client.post('/api/strips',content=image_bytes(size=(6,6)),headers={'Content-Type':'image/png'}).status_code==200
    assert current(client)['result']==s['result']
