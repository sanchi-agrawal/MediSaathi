"""Ordinary review/confirm → confirmed links → user clock preferences, offline."""
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
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import current,binding,linked,route
from api.tests.test_strip_api import transcription

LOCAL_CONNECT=socket.create_connection

def synthetic_image(medicines):
    canvas=Image.new('RGB',(1800,650),'white');draw=ImageDraw.Draw(canvas)
    draw.text((20,20),'SYNTHETIC TEST ONLY - NOT MEDICAL ADVICE',fill='black')
    for index,medicine in enumerate(medicines):draw.text((20,130+index*130),medicine['raw_text'],fill='black')
    output=BytesIO();canvas.save(output,format='PNG');return output.getvalue()

@pytest.fixture
def runtime(tmp_path,monkeypatch):
    meds,items,image=fixture()
    # Explicitly different source doses/forms and course lengths.
    for index in (0,):
        meds[index]['raw_text']=meds[index]['raw_text'].replace('take 1 tablet','take 2 tablet')
        items[index].update(raw_text=meds[index]['raw_text'],dose_quantity_raw='2')
    meds[2].update(raw_text=meds[2]['raw_text'].replace('tablet','capsule'),form='capsule')
    items[2].update(raw_text=meds[2]['raw_text'],dose_unit_raw='capsule')
    image=synthetic_image(meds)
    sdk=MagicMock();sdk.__enter__.return_value=sdk
    sdk.models.generate_content.side_effect=[SimpleNamespace(text=json.dumps(meds)),SimpleNamespace(text=json.dumps({'instructions':[{k:v for k,v in i.items() if k not in ('instruction_id','confirmation_required')} for i in items],'issues':[]})),SimpleNamespace(text=json.dumps(transcription(('08/2099',))))]
    monkeypatch.setattr(reader.genai,'Client',MagicMock(return_value=sdk));monkeypatch.setattr(reader,'_configuration',lambda:('mock-only-secret','gemini-3.1-flash-lite'))
    return create_local_app(tmp_path/'isolated.sqlite3',offline=False),sdk,image

def ordinary_review(c,image,slots=True):
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    assert c.post('/api/session').status_code==200
    s=post(c,upload(c,image),'analyze').json();assert s['status']=='succeeded'
    s=reviewed(c,s).json();s=post(c,s,'confirm').json();assert s['confirmed']
    instructions=confirm(c,extract(c,s,'instructions'),'instructions');assert instructions['confirmed']
    for index,named in enumerate((['morning','night'],['night'],['morning']),1):
        state=current(c)
        r=c.post(route(state,'/associations'),json={**binding(state),'medicine_ref':f'medicine_{index:03}','instruction_id':f'instruction_{index:03}'})
        assert r.status_code==200,r.text
        if slots:
            state=r.json();r=c.post(route(state,'/schedule/slots/confirm'),json={**linked(state),'slots':named})
            assert r.status_code==200,r.text
    return s

def clock_state(c):
    r=c.get('/api/clock-scheduling/current');assert r.status_code==200,r.text
    return r.json()

def clock_body(state):
    return {**{k:state[k] for k in ('medicine_revision','instruction_revision','scheduling_revision')},'start_date':'2026-11-05','medicines':[
        {'medicine_ref':'medicine_001','clock_times':['08:15','20:30']},
        {'medicine_ref':'medicine_002','clock_times':['21:45']},
        {'medicine_ref':'medicine_003','clock_times':['07:10']}]}

def send(c,state,body):return c.post(f"/api/prescriptions/{state['analysis_id']}/schedule/clock-generate",json=body)

def assert_calendar(c,state):
    assert all(m['eligible'] for m in state['medicines']),state
    assert [m['administrations_per_day'] for m in state['medicines']]==[2,1,1]
    assert [m['dose_quantity'] for m in state['medicines']]==['2','1','1']
    assert [m['duration_days'] for m in state['medicines']]==[5,3,7]
    response=send(c,state,clock_body(state));assert response.status_code==200,response.text
    course=response.json();assert course['timezone']=='Asia/Kolkata'
    assert [m['result']['end_date'] for m in course['medicines']]==['2026-11-09','2026-11-07','2026-11-11']
    assert [len(m['days']) for m in course['medicines']]==[5,3,7]
    assert course['medicines'][0]['days'][0]['administrations']==[
        dict(slot='morning',time='08:15',quantity=2.0,unit='tablet',at='2026-11-05T08:15:00+05:30'),
        dict(slot='night',time='20:30',quantity=2.0,unit='tablet',at='2026-11-05T20:30:00+05:30')]
    assert course['medicines'][2]['result']['unit']=='capsule'
    assert clock_state(c)['course']==course
    return course

def test_ordinary_review_then_clock_schedule_no_frequency_reparse(runtime,monkeypatch):
    app,sdk,image=runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        source=ordinary_review(c,image)
        import confirmed_frequency
        import schedule
        monkeypatch.setattr(confirmed_frequency,'three_slots',lambda *_:pytest.fail('Frequency notation reparsed in Scheduling'))
        monkeypatch.setattr(schedule,'parse_pattern',lambda *_:pytest.fail('Engine reparsed frequency'))
        state=clock_state(c);assert_calendar(c,state)
        body=clock_body(state);body['start_date']='2026-11-06';body['medicines'][0]['clock_times']=['09:00','21:00']
        response=send(c,state,body);assert response.status_code==200,response.text
        assert response.json()['medicines'][0]['days'][0]['administrations'][0]['at']=='2026-11-06T09:00:00+05:30'
        assert c.get('/api/prescriptions/current').json()['revision']==source['revision']
        assert sdk.models.generate_content.call_count==2

def test_literal_twice_daily_uses_two_user_times_without_inventing_named_slots(runtime,monkeypatch):
    app,sdk,image=runtime
    responses=list(sdk.models.generate_content.side_effect);meds=json.loads(responses[0].text);envelope=json.loads(responses[1].text)
    for index,(pattern,frequency) in enumerate((('1-0-1','twice daily'),('0-0-1','once daily'),('1-0-0','once daily'))):
        meds[index]['raw_text']=meds[index]['raw_text'].replace(pattern,frequency);meds[index]['frequency_pattern']=frequency
        envelope['instructions'][index].update(raw_text=meds[index]['raw_text'],frequency_raw=frequency)
    responses[:2]=[SimpleNamespace(text=json.dumps(meds)),SimpleNamespace(text=json.dumps(envelope))];sdk.models.generate_content.side_effect=responses
    image=synthetic_image(meds)
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image,slots=False)
        import confirmed_count
        import schedule
        monkeypatch.setattr(confirmed_count,'literal_count',lambda *_:pytest.fail('Daily count parsed again during generation'))
        monkeypatch.setattr(schedule,'parse_pattern',lambda *_:pytest.fail('Frequency parsed in engine'))
        state=clock_state(c)
        assert [m['administrations_per_day'] for m in state['medicines']]==[2,1,1]
        assert all(m['eligible'] and m['slots']==[] for m in state['medicines'])
        r=send(c,state,clock_body(state));assert r.status_code==200,r.text
        first=r.json()['medicines'][0]
        assert first['result']['total_units']==20
        assert [a['time'] for a in first['days'][0]['administrations']]==['08:15','20:30']
        assert all(a['slot'] is None for a in first['days'][0]['administrations'])
        legacy=c.get('/api/scheduling/current').json()
        assert legacy['plan'] is None and legacy['result'] is None
        assert len(legacy['associations'])==3
        assert sdk.models.generate_content.call_count==2

@pytest.mark.parametrize('case',['extra_dose','too_few','duplicate','invalid','reverse','duplicate_medicine','forged_dose','date','stale'])
def test_invalid_preferences_and_stale_revisions(runtime,case):
    app,_,image=runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image);state=clock_state(c);body=clock_body(state)
        if case=='extra_dose':body['medicines'][0]['clock_times'].append('22:00')
        if case=='too_few':body['medicines'][0]['clock_times']=['08:00']
        if case=='duplicate':body['medicines'][0]['clock_times']=['08:00','08:00']
        if case=='invalid':body['medicines'][0]['clock_times']=['25:00','26:00']
        if case=='reverse':body['medicines'][0]['clock_times']=['21:00','08:00']
        if case=='duplicate_medicine':body['medicines'].append(copy.deepcopy(body['medicines'][0]))
        if case=='forged_dose':body['medicines'][0]['dose_quantity']=100
        if case=='date':body['start_date']='2026-02-31'
        if case=='stale':body['instruction_revision']='stale'
        r=send(c,state,body);assert r.status_code==(409 if case=='stale' else 422),r.text
        assert clock_state(c)['course'] is None

def test_unknown_count_stays_blocked_without_trying_numeric_parser(runtime,monkeypatch):
    app,_,image=runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image,slots=False)
        import confirmed_frequency
        monkeypatch.setattr(confirmed_frequency,'three_slots',lambda *_:pytest.fail('Unconfirmed notation parsed in Scheduling'))
        state=clock_state(c);assert all(not m['eligible'] for m in state['medicines'])
        assert all('administration_count_unconfirmed' in m['issues'] for m in state['medicines'])
        assert send(c,state,clock_body(state)).status_code==409

def test_edits_logout_and_cross_account_access(runtime):
    app,_,image=runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        ordinary_review(c,image);state=clock_state(c);assert_calendar(c,state)
        with TestClient(app,base_url='http://localhost',headers=HEADERS) as b:
            b.post(PREFIX+'/signup',json={**DETAILS,'email':'second@example.test'});b.post('/api/session')
            assert send(b,state,clock_body(state)).status_code in (401,409)
        ins=c.get(f"/api/prescriptions/{state['analysis_id']}/sections/instructions").json()
        assert c.post(f"/api/prescriptions/{state['analysis_id']}/sections/instructions/invalidate",json={'revision':ins['revision']}).status_code==200
        assert clock_state(c)['course'] is None
        assert send(c,state,clock_body(state)).status_code==409
        c.post(PREFIX+'/logout');assert c.get('/api/clock-scheduling/current').status_code==401

def test_actual_http_ordinary_reviews_user_clock_times_and_strip(runtime,monkeypatch):
    app,sdk,image=runtime;sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
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
            ordinary_review(c,image);state=clock_state(c);course=assert_calendar(c,state)
            assert sdk.models.generate_content.call_count==2
            assert c.get('/api/prescriptions/current').json()['confirmed'] is True
            # Independent strip upload cannot erase the prescription clock course.
            r=c.post('/api/strips',content=image,headers={'Content-Type':'image/png'});assert r.status_code==200
            assert clock_state(c)['course']==course
            assert c.post(PREFIX+'/logout').status_code==200
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()
