"""Real route flow with a temporary local account DB and mocked SDK only."""
import copy
import json
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest
import uvicorn
from io import BytesIO
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from api.dependencies import reader
from api.local_auth import create_local_app,PREFIX
from api.tests.test_local_auth import HEADERS,DETAILS
from api.tests.test_numeric_and_strip_integration import fixture
LOCAL_CONNECT=socket.create_connection

@pytest.fixture
def setup(tmp_path,monkeypatch,request):
    meds,items,image=fixture()
    for i,slots in enumerate(getattr(request,'param',('morning and night','night','morning'))):
        unit='capsule' if i==2 else 'tablet'
        text=f"SYNTHETIC {meds[i]['name']} {meds[i]['salt']} {meds[i]['strength']} take 1 {unit} {slots} After food x {meds[i]['duration_days']} days"
        meds[i].update(raw_text=text,form=unit,frequency_pattern=slots)
        items[i].update(raw_text=text,dose_unit_raw=unit,frequency_raw=meds[i]['frequency_pattern'],timing_raw=slots+' After food')
    canvas=Image.new('RGB',(1800,650),'white');draw=ImageDraw.Draw(canvas)
    draw.text((20,20),'SYNTHETIC TEST ONLY - NOT MEDICAL ADVICE',fill='black')
    for index,med in enumerate(meds):draw.text((20,130+index*130),med['raw_text'],fill='black')
    output=BytesIO();canvas.save(output,format='PNG');image=output.getvalue()
    sdk=MagicMock();sdk.__enter__.return_value=sdk
    sdk.models.generate_content.side_effect=[SimpleNamespace(text=json.dumps(meds)),SimpleNamespace(text=json.dumps({'instructions':[{k:v for k,v in i.items() if k not in ('instruction_id','confirmation_required')} for i in items],'issues':[]}))]
    monkeypatch.setattr(reader.genai,'Client',MagicMock(return_value=sdk));monkeypatch.setattr(reader,'_configuration',lambda:('offline-mocked-key','gemini-3.1-flash-lite'))
    return create_local_app(tmp_path/'isolated.sqlite3',offline=False),sdk,image

def prepare_review(c,image):
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    assert c.post('/api/session').status_code==200
    r=c.post('/api/prescriptions',content=image,headers={'Content-Type':'image/png'});assert r.status_code==200,r.text
    s=r.json();r=c.post(f"/api/prescriptions/{s['analysis_id']}/analyze",json={'revision':s['revision']});assert r.status_code==200,r.text
    ins=c.get(f"/api/prescriptions/{s['analysis_id']}/sections/instructions").json()
    r=c.post(f"/api/prescriptions/{s['analysis_id']}/sections/instructions/analyze",json={'revision':ins['revision']});assert r.status_code==200,r.text
    review=c.get('/api/prescription-review/current').json()
    body={k:review[k] for k in ('medicine_revision','instruction_revision','records','instructions')}
    body.update(pairs=[{k:p[k] for k in ('medicine_ref','instruction_id','slots')} for p in review['pairs']],resolved_records=[],resolved_instructions=[i['instruction_id'] for i in review['instructions']['instructions'] if i['needs_review']],acknowledge=True)
    return review,body

def confirm(c,review,body):
    r=c.post(f"/api/prescriptions/{review['analysis_id']}/review/confirm-all",json=body)
    assert r.status_code==200,r.text
    return r.json()

def assert_course(c,saved):
    assert all(not m['issues'] for m in saved['medicines']),saved
    assert [m['confirmed_slots'] for m in saved['medicines']]==[['morning','night'],['night'],['morning']]
    # Navigation/refresh is GET-only and retains the exact confirmed snapshot.
    assert c.get('/api/confirmed-prescription/current').json()['snapshot']==saved
    r=c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'});assert r.status_code==200,r.text
    course=r.json();assert len(course['results'])==3
    assert [v['result']['end_date'] for v in course['results']]==['2026-11-09','2026-11-07','2026-11-11']
    assert course['results'][2]['result']['unit']=='capsule'
    assert course['results'][0]['result']['doses_by_slot']==dict(morning=1,noon=0,night=1,bedtime=0)
    return course

def test_single_review_then_date_only_generation_and_invalidation(setup,monkeypatch):
    app,sdk,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image);saved=confirm(c,review,body)
        # No numeric parser or proposal is used after the final review.
        import confirmed_frequency as freq
        import schedule
        monkeypatch.setattr(freq,'three_slots',lambda *_:(_ for _ in ()).throw(AssertionError('reparse')))
        monkeypatch.setattr(schedule,'parse_pattern',lambda *_:(_ for _ in ()).throw(AssertionError('reparse')))
        course=assert_course(c,saved)
        assert c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'}).json()==course
        r=c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-06'});assert r.json()['results'][0]['result']['end_date']=='2026-11-10'
        ins=c.get(f"/api/prescriptions/{review['analysis_id']}/sections/instructions").json()
        assert c.post(f"/api/prescriptions/{review['analysis_id']}/sections/instructions/invalidate",json={'revision':ins['revision']}).status_code==200
        assert c.get('/api/confirmed-prescription/current').json()=={'snapshot':None,'course':None}
        assert c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'}).status_code==409
        assert sdk.models.generate_content.call_count==2

@pytest.mark.parametrize('change',['missing_dose','missing_duration','unresolved_flag','missing_link','unconfirmed_timing','instruction_flag'])
def test_missing_information_stays_blocked(setup,change):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        body['resolved_instructions']=body['resolved_instructions'][1:]
        if change=='missing_dose':body['instructions']['instructions'][0]['dose_quantity_raw']=None
        if change=='missing_duration':body['instructions']['instructions'][0]['duration_raw']=None
        if change=='unresolved_flag':body['records'][0]['needs_review']=True
        if change=='missing_link':body['pairs']=body['pairs'][1:]
        if change=='unconfirmed_timing':body['pairs'][0]['slots']=[]
        if change=='instruction_flag':body['instructions']['instructions'][0]['needs_review']=True
        saved=confirm(c,review,body)
        assert saved['medicines'][0]['issues']
        result=c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'})
        assert result.status_code==200,result.text
        assert len(result.json()['results'])==2 and len(result.json()['blocked'])==1

def test_stale_cross_session_forged_and_invalid_date(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image);saved=confirm(c,review,body)
        assert c.post(f"/api/prescriptions/{review['analysis_id']}/review/confirm-all",json=body).status_code==409
        assert c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-02-31'}).status_code==422
        with TestClient(app,base_url='http://localhost',headers=HEADERS) as other:
            other.post(PREFIX+'/signup',json={**DETAILS,'email':'other@example.test'})
            assert other.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'}).status_code in (401,404,409)

@pytest.mark.parametrize('setup',[('evening and bedtime','night','morning')],indirect=True)
def test_evening_is_distinct_from_night_and_bedtime(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image);saved=confirm(c,review,body)
        assert saved['medicines'][0]['confirmed_slots']==['evening','bedtime']
        assert not saved['medicines'][0]['issues'],saved['medicines'][0]
        r=c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'})
        assert r.status_code==200,r.text
        assert r.json()['results'][0]['result']['doses_by_slot']==dict(morning=0,noon=0,evening=1,night=0,bedtime=1)

def test_explicit_timing_does_not_require_redundant_frequency_text(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        body['instructions']['instructions'][0]['frequency_raw']=None
        assert_course(c,confirm(c,review,body))

@pytest.mark.parametrize('forgery',['acknowledgement','extra_medical_field','duplicate_pair','forged_slots'])
def test_forged_or_inconsistent_review_is_rejected(setup,forgery):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        if forgery=='acknowledgement':body['acknowledge']=1
        if forgery=='extra_medical_field':body['records'][0]['dose']=1
        if forgery=='duplicate_pair':body['pairs'].append(copy.deepcopy(body['pairs'][0]))
        if forgery=='forged_slots':body['pairs'][0]['slots']=['bedtime']
        assert c.post(f"/api/prescriptions/{review['analysis_id']}/review/confirm-all",json=body).status_code==422
        assert c.get('/api/confirmed-prescription/current').json()['snapshot'] is None

def test_explicit_supported_medicine_flag_resolution_keeps_original_ocr(setup):
    app,sdk,image=setup
    responses=list(sdk.models.generate_content.side_effect)
    original=json.loads(responses[0].text);original[0]['needs_review']=True
    responses[0]=SimpleNamespace(text=json.dumps(original));sdk.models.generate_content.side_effect=responses
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        assert review['review_requirements'][0]['can_resolve']
        body['records'][0]['needs_review']=False;body['resolved_records']=[0]
        assert_course(c,confirm(c,review,body))
        restored=c.get('/api/prescriptions/current').json()
        assert restored['original_records'][0]['needs_review'] is True
        assert restored['records'][0]['needs_review'] is False

@pytest.mark.parametrize('failure',['exception','invalid_output'])
def test_scheduler_failure_does_not_publish_a_course(setup,failure):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image);saved=confirm(c,review,body)
        session=next(iter(app.state.sessions.sessions.values()))
        def broken(_):
            if failure=='exception':raise RuntimeError('private diagnostic must not be exposed')
            return {'status':'ok','name':'forged'}
        session.ai._downstream['schedule']=broken
        r=c.post('/api/confirmed-prescription/generate',json={'snapshot_id':saved['snapshot_id'],'start_date':'2026-11-05'})
        assert r.status_code==502 and r.headers['content-type'].startswith('application/json')
        assert 'private diagnostic' not in r.text
        assert c.get('/api/confirmed-prescription/current').json()['course'] is None
        assert session.scheduling_state['course_results']==[]

def test_instruction_resolution_cannot_clear_missing_clinical_information(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        body['instructions']['instructions'][0]['dose_quantity_raw']=None
        r=c.post(f"/api/prescriptions/{review['analysis_id']}/review/confirm-all",json=body)
        assert r.status_code==422 and r.json()['detail']['category']=='unresolved_review'
        assert c.get('/api/confirmed-prescription/current').json()['snapshot'] is None

def test_instruction_review_flags_cannot_be_cleared_directly_by_json(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image)
        body['instructions']['instructions'][0]['needs_review']=False
        r=c.post(f"/api/prescriptions/{review['analysis_id']}/review/confirm-all",json=body)
        assert r.status_code==422 and r.json()['detail']['category']=='unresolved_review'
        state=c.get('/api/prescription-review/current').json()
        assert state['instructions']['instructions'][0]['needs_review'] is True

def test_source_warning_is_preserved_after_explicit_supported_resolution(setup):
    app,_,image=setup
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review,body=prepare_review(c,image);assert_course(c,confirm(c,review,body))
        state=c.get(f"/api/prescriptions/{review['analysis_id']}/sections/instructions").json()
        assert state['original_payload']['instructions'][0]['needs_review'] is True
        assert state['payload']['instructions'][0]['needs_review'] is False
        assert state['original_payload']['instructions'][0]['route_raw'] is None
        assert state['payload']['instructions'][0]['route_raw'] is None
        assert state['payload']['instructions'][0]['uncertainty_reasons']==['missing_information']

def test_actual_loopback_http_complete_workflow(setup,monkeypatch):
    app,sdk,image=setup
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def local_only(address,*args,**kwargs):
        assert address==('127.0.0.1',port),'External network remains forbidden'
        return LOCAL_CONNECT(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',local_only)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS) as c:
            review,body=prepare_review(c,image);assert_course(c,confirm(c,review,body))
            assert sdk.models.generate_content.call_count==2
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()
