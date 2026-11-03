"""Click-only, single-medicine provider calls; trusted facts and scoped caches."""
import json
import socket
import threading
import time
from types import SimpleNamespace
import pytest
import httpx
import uvicorn
from fastapi.testclient import TestClient
from api.tests.test_clock_scheduling import runtime,ordinary_review,clock_state,clock_body,send,synthetic_image
from api.tests.test_local_auth import HEADERS,DETAILS
from api.local_auth import PREFIX
from api.drug_information import FIELDS,identify
from api.dependencies import reader
from api.tests.test_clock_scheduling import LOCAL_CONNECT

@pytest.fixture
def patient_runtime(runtime):
    app,sdk,_=runtime;responses=list(sdk.models.generate_content.side_effect);meds=json.loads(responses[0].text);ins=json.loads(responses[1].text)
    frequencies=['twice daily','once at night','once in the morning']
    for i,frequency in enumerate(frequencies):
        pattern=meds[i]['frequency_pattern'];text=meds[i]['raw_text'].replace(pattern,frequency).replace('take 2 tablet','take 1 tablet')
        meds[i].update(raw_text=text,frequency_pattern=frequency)
        ins['instructions'][i].update(raw_text=text,frequency_raw=frequency,dose_quantity_raw='1')
    responses[:2]=[SimpleNamespace(text=json.dumps(meds)),SimpleNamespace(text=json.dumps(ins))];queue=iter(responses)
    def answer(**kwargs):
        if isinstance(kwargs.get('contents'),str):
            prompt=json.loads(kwargs['contents'])
            assert set(prompt)=={'ingredient','language','approved_facts'}
            return SimpleNamespace(text=json.dumps({'language':prompt['language'],'fact_ids':list(FIELDS)}))
        return next(queue)
    sdk.models.generate_content.side_effect=answer
    return app,sdk,synthetic_image(meds)

def explain(c,source,index=0,language='en'):
    return c.post(f"/api/prescriptions/{source['analysis_id']}/medicines/explain",json={'revision':source['revision'],'record_index':index,'language':language})

def test_exact_three_medicine_flow_normal_review_clocks_and_on_demand_information(patient_runtime):
    app,sdk,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image,slots=False)
        assert sdk.models.generate_content.call_count==2 # ONLY the two OCR extractors
        state=clock_state(c);assert [m['administrations_per_day'] for m in state['medicines']]==[2,1,1]
        assert all(m['eligible'] and m['dose_quantity']=='1' for m in state['medicines']),state
        body=clock_body(state);r=send(c,state,body);assert r.status_code==200,r.text
        assert [m['result']['total_units'] for m in r.json()['medicines']]==[10,3,7]
        assert sdk.models.generate_content.call_count==2
        for index,ingredient in enumerate(('paracetamol','cetirizine','omeprazole')):
            before=sdk.models.generate_content.call_count
            r=explain(c,source,index);assert r.status_code==200,r.text
            data=r.json();assert data['status']=='explained' and data['ingredient']==ingredient
            assert len(data['sections'])==len(FIELDS) and data['prescription']['confirmed_linked_instruction']
            assert {section['key'] for section in data['sections']}==set(FIELDS)
            assert sdk.models.generate_content.call_count==before+1
            assert json.loads(sdk.models.generate_content.call_args.kwargs['contents'])['ingredient']==ingredient
            assert explain(c,source,index).json()['cached'] is True
            assert sdk.models.generate_content.call_count==before+1
        english=explain(c,source,1).json();hindi=explain(c,source,1,'hi').json()
        assert english['sections']!=hindi['sections']
        assert all(any('\u0900'<=char<='\u097f' for char in s['text']) for s in hindi['sections'])
        before=sdk.models.generate_content.call_count
        c.get('/api/prescriptions/current');clock_state(c)
        assert sdk.models.generate_content.call_count==before

def test_cache_invalidates_on_source_edit_and_cross_account_access_is_rejected(patient_runtime):
    app,sdk,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image,slots=False);assert explain(c,source).status_code==200
        with TestClient(app,base_url='http://localhost',headers=HEADERS) as b:
            b.post(PREFIX+'/signup',json={**DETAILS,'email':'another@example.test'});b.post('/api/session')
            assert explain(b,source).status_code in (401,409)
        r=c.post(f"/api/prescriptions/{source['analysis_id']}/invalidate",json={'revision':source['revision']});assert r.status_code==200
        assert explain(c,source).status_code==409
        fresh=r.json();assert explain(c,fresh).status_code==409
        assert sdk.models.generate_content.call_count==3

@pytest.mark.parametrize('failure',['invalid_content','provider_failure','configuration'])
def test_failures_never_return_fabricated_information(patient_runtime,monkeypatch,failure):
    app,sdk,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image,slots=False)
        if failure=='invalid_content':sdk.models.generate_content.side_effect=lambda **_:SimpleNamespace(text=json.dumps({'language':'en','fact_ids':['invented_dose']}))
        if failure=='provider_failure':sdk.models.generate_content.side_effect=RuntimeError('private provider details')
        if failure=='configuration':
            def unavailable():raise reader.ReaderConfigurationError('not configured')
            monkeypatch.setattr(reader,'_configuration',unavailable)
        r=explain(c,source);assert r.status_code in (502,503),r.text
        assert 'sections' not in r.json() and 'private provider details' not in r.text
        assert sdk.models.generate_content.call_count==(2 if failure=='configuration' else 3)

def test_unknown_or_conflicting_identity_does_not_call_provider(patient_runtime):
    app,sdk,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image,slots=False)
        records=source['records'];records[0]['name']='Unknown Brand';records[0]['salt']=None
        r=c.put(f"/api/prescriptions/{source['analysis_id']}/review",json={'revision':source['revision'],'records':records});assert r.status_code==200
        fresh=r.json();fresh=c.post(f"/api/prescriptions/{source['analysis_id']}/confirm",json={'revision':fresh['revision']}).json()
        r=explain(c,fresh);assert r.status_code==200 and r.json()['status']=='identity_uncertain'
        assert r.json()['ingredient'] is None and r.json()['sections']==[] and sdk.models.generate_content.call_count==2

def test_drug_identity_requires_exact_supported_product():
    med=dict(name='Dolo',salt='paracetamol',strength='650 mg',form='tablet',needs_review=False)
    assert identify(med)=='paracetamol'
    assert identify({**med,'needs_review':True})=='paracetamol'
    assert identify({**med,'salt':None})=='paracetamol' # Exact documented 650 mg tablet product.
    for change in (dict(strength=None),dict(name='Dolo Cold'),dict(salt='paracetamol + caffeine')):
        assert identify({**med,**change}) is None


@pytest.mark.parametrize('name,strength,ingredient',[
    ('Omeprazole 20 mg','20 mg','omeprazole'),
    ('Cetirizine 10 mg','10 mg','cetirizine'),
    ('Paracetamol 650 mg','650 mg','paracetamol'),
    ('Omeprazole','20 mg','omeprazole'),
])
def test_confirmed_generic_identity_ignores_missing_printed_salt_and_old_ocr_flag(name,strength,ingredient):
    record=dict(name=name,salt=None,strength=strength,form=None,needs_review=True)
    assert identify(record)==ingredient
    assert identify({**record,'salt':'Unrelated ingredient'}) is None
    assert identify({**record,'name':name+' combination'}) is None
    if name.endswith('mg'):
        assert identify({**record,'strength':'40 mg'}) is None


def test_omeprazole_20_mg_confirmed_review_explains_without_scheduling_link(patient_runtime):
    app,sdk,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image,slots=False)
        records=source['records']
        records[2].update(name='Omeprazole 20 mg',salt=None,needs_review=True)
        saved=c.put(f"/api/prescriptions/{source['analysis_id']}/review",json={'revision':source['revision'],'records':records})
        assert saved.status_code==200,saved.text
        current=saved.json()
        current=c.post(f"/api/prescriptions/{source['analysis_id']}/confirm",json={'revision':current['revision']}).json()
        assert current['confirmed'] and current['records'][2]['needs_review'] is True
        session=next(iter(app.state.sessions.sessions.values()))
        session.ai.clear_associations()
        before=sdk.models.generate_content.call_count
        result=explain(c,current,2)
        assert result.status_code==200,result.text
        payload=result.json()
        assert payload['status']=='explained' and payload['ingredient']=='omeprazole'
        assert {s['key'] for s in payload['sections']}==set(FIELDS)
        assert any('acid' in s['text'].lower() for s in payload['sections'])
        assert payload['prescription']['confirmed_linked_instruction'] is None
        assert sdk.models.generate_content.call_count==before+1
        session.scheduling_revision='unrelated-schedule-change'
        again=explain(c,current,2).json()
        assert again['cached'] is True and sdk.models.generate_content.call_count==before+1
        hindi=explain(c,current,2,'hi').json()
        assert hindi['status']=='explained' and all(any('\u0900'<=ch<='\u097f' for ch in s['text']) for s in hindi['sections'])
        assert sdk.models.generate_content.call_count==before+2

def test_saved_associations_are_recovered_from_current_backend_receipts(patient_runtime):
    app,_,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image,slots=False)
        session=next(iter(app.state.sessions.sessions.values()))
        session.scheduling_state['associations']=[]
        state=clock_state(c);assert all(m['eligible'] for m in state['medicines'])
        assert len(session.scheduling_state['associations'])==3
        assert send(c,state,clock_body(state)).status_code==200

def test_known_count_preserves_unresolved_medicine_flag_and_other_courses(patient_runtime):
    app,sdk,image=patient_runtime
    original_answer=sdk.models.generate_content.side_effect
    first=True
    def flagged(**kwargs):
        nonlocal first
        answer=original_answer(**kwargs)
        if first:
            first=False;records=json.loads(answer.text);records[0]['needs_review']=True
            return SimpleNamespace(text=json.dumps(records))
        return answer
    sdk.models.generate_content.side_effect=flagged
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image,slots=False);state=clock_state(c)
        dolo=state['medicines'][0]
        assert dolo['administrations_per_day']==2 and dolo['eligible'] is True
        assert not dolo['issues'] and dolo['review_details']['flagged'] is True
        assert c.get('/api/prescriptions/current').json()['records'][0]['needs_review'] is True
        body=clock_body(state)
        r=send(c,state,body);assert r.status_code==200
        assert len(r.json()['medicines'])==3 and len(r.json()['blocked'])==0

def test_real_local_http_selected_explanations_and_generated_calendar(patient_runtime,monkeypatch):
    app,sdk,image=patient_runtime;sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def local_only(address,*args,**kwargs):
        assert address==('127.0.0.1',port),'External network remains forbidden'
        return LOCAL_CONNECT(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',local_only)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS) as c:
            source=ordinary_review(c,image,slots=False);state=clock_state(c)
            assert sdk.models.generate_content.call_count==2
            r=send(c,state,clock_body(state));assert r.status_code==200,r.text
            assert [m['result']['total_units'] for m in r.json()['medicines']]==[10,3,7]
            assert [m['result']['end_date'] for m in r.json()['medicines']]==['2026-11-09','2026-11-07','2026-11-11']
            assert [a['time'] for a in r.json()['medicines'][0]['days'][0]['administrations']]==['08:15','20:30']
            assert sdk.models.generate_content.call_count==2
            for index,language in ((0,'en'),(1,'hi'),(2,'en')):
                response=explain(c,source,index,language);assert response.status_code==200,response.text
            assert len(response.json()['sections'])==len(FIELDS)
            assert sdk.models.generate_content.call_count==5
            assert explain(c,source,1,'hi').json()['cached'] is True
            assert sdk.models.generate_content.call_count==5
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()


@pytest.mark.parametrize('blocker',['dose_quantity_missing','administration_count_unconfirmed'])
def test_authenticated_http_partial_course_excludes_flagged_medicine(patient_runtime,monkeypatch,blocker):
    app,sdk,image=patient_runtime
    original=sdk.models.generate_content.side_effect
    calls=0
    def answer(**kwargs):
        nonlocal calls
        value=original(**kwargs)
        calls+=1
        if blocker=='dose_quantity_missing' and calls==1:
            records=json.loads(value.text);records[0]['needs_review']=True
            return SimpleNamespace(text=json.dumps(records))
        if blocker=='dose_quantity_missing' and calls==2:
            payload=json.loads(value.text);payload['instructions'][0]['dose_quantity_raw']=None
            return SimpleNamespace(text=json.dumps(payload))
        if blocker=='administration_count_unconfirmed' and calls in (1,2):
            payload=json.loads(value.text);record=payload[0] if calls==1 else payload['instructions'][0]
            record['raw_text']=record['raw_text'].replace('twice daily','as directed')
            record['frequency_pattern' if calls==1 else 'frequency_raw']='as directed'
            return SimpleNamespace(text=json.dumps(payload))
        return value
    sdk.models.generate_content.side_effect=answer
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def local_only(address,*args,**kwargs):
        assert address==('127.0.0.1',port),'External network forbidden'
        return LOCAL_CONNECT(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',local_only)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS) as c:
            ordinary_review(c,image,slots=False);state=clock_state(c)
            assert [m['administrations_per_day'] for m in state['medicines']]==[0,1,1]
            assert [m['eligible'] for m in state['medicines']]==[False,True,True]
            body=clock_body(state);body['medicines']=body['medicines'][1:]
            response=send(c,state,body);assert response.status_code==200,response.text
            course=response.json()
            assert [m['result']['name'] for m in course['medicines']]==['Cetirizine','Omeprazole']
            assert [len(m['days']) for m in course['medicines']]==[3,7]
            assert course['blocked'][0]['name']=='Dolo'
            assert blocker in course['blocked'][0]['issues']
            invalid={**body,'medicines':[{'medicine_ref':'medicine_002','clock_times':[]}]}
            assert send(c,state,invalid).status_code==422
            assert clock_state(c)['course']==course
            assert sdk.models.generate_content.call_count==2
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()
