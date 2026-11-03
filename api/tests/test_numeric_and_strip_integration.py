import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import date
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from api.dependencies import reader
from api.local_auth import create_local_app,PREFIX
from api.tests.test_local_auth import HEADERS,DETAILS
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import current,binding,linked,route,save,approve
from api.tests.test_strip_api import action,save as save_strip,transcription
from api.expiry_status import expiry_status
from confirmed_frequency import three_slots

def fixture():
    meds=[];instructions=[]
    for i,(name,salt,strength,pattern,days) in enumerate([('Dolo','Paracetamol','650 mg','1-0-1',5),('Cetirizine','Cetirizine','10 mg','0-0-1',3),('Omeprazole','Omeprazole','20 mg','1-0-0',7)],1):
        raw=f'FICTIONAL {name} {salt} {strength} take 1 tablet {pattern} x {days} days After food'
        meds.append(dict(raw_text=raw,name=name,salt=salt,strength=strength,form='tablet',frequency_pattern=pattern,duration_days=days,timing='After food',confidence=.9,needs_review=False))
        instructions.append(dict(instruction_id=f'instruction_{i:03}',medicine_name_raw=name,raw_text=raw,dose_quantity_raw='1',dose_unit_raw='tablet',frequency_raw=pattern,duration_raw=f'{days} days',timing_raw='After food',route_raw=None,uncertainty_reasons=[],needs_review=False,confirmation_required=True))
    image=Image.new('RGB',(1600,550),'white');draw=ImageDraw.Draw(image)
    draw.text((25,20),'SYNTHETIC TEST ONLY - NOT MEDICAL ADVICE',fill='black')
    for i,m in enumerate(meds):draw.text((25,100+i*110),m['raw_text'],fill='black')
    output=BytesIO();image.save(output,format='PNG')
    return meds,instructions,output.getvalue()

def configured(tmp_path,monkeypatch):
    meds,instructions,image=fixture();sdk=MagicMock();sdk.__enter__.return_value=sdk
    raw_instructions=[{k:v for k,v in i.items() if k not in ('instruction_id','confirmation_required')} for i in instructions]
    sdk.models.generate_content.side_effect=[SimpleNamespace(text=json.dumps(meds)),SimpleNamespace(text=json.dumps({'instructions':raw_instructions,'issues':[]})),SimpleNamespace(text=json.dumps(transcription(('08/2099',))))]
    monkeypatch.setattr(reader.genai,'Client',MagicMock(return_value=sdk));monkeypatch.setattr(reader,'_configuration',lambda:('mock-only-key','gemini-3.1-flash-lite'))
    app=create_local_app(tmp_path/'accounts.sqlite3',offline=False);c=TestClient(app,base_url='http://localhost',headers=HEADERS)
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    data=post(c,upload(c,image),'analyze').json();assert data['status']=='succeeded'
    data=post(c,reviewed(c,data).json(),'confirm').json();confirm(c,extract(c,data,'instructions'),'instructions')
    return c,sdk,data

def test_mocked_gemini_to_three_numeric_schedules_and_independent_strip(tmp_path,monkeypatch):
    c,sdk,data=configured(tmp_path,monkeypatch)
    for i in range(1,4):
        s=current(c);s=c.post(route(s,'/associations'),json={**binding(s),'medicine_ref':f'medicine_{i:03}','instruction_id':f'instruction_{i:03}'}).json()
        assert 'notation_confirmation_required' in s['automatic'][i-1]['issues']
        response=c.post(route(s,'/schedule/notation/confirm'),json=linked(s));assert response.status_code==200,response.text
        assert response.json()['automatic'][i-1]['template'] is not None
    assert len(current(c)['associations'])==3 and sdk.models.generate_content.call_count==2
    for entry in current(c)['automatic']:
        s={**current(c),'association':entry['association']};response=approve(c,save(c,s,{**entry['template'],'start_date':'2026-11-05'}));assert response.status_code==200,response.text
    s=current(c);results=s['course_results'];assert len(results)==3
    assert [r['result']['payload']['end_date'] for r in results]==['2026-11-09','2026-11-07','2026-11-11']
    assert [r['result']['payload']['doses_by_slot'] for r in results]==[three_slots('1-0-1'),three_slots('0-0-1'),three_slots('1-0-0')]
    before=s['associations'];buffer=BytesIO();Image.new('RGB',(31,29),'white').save(buffer,format='JPEG')
    uploaded=c.post('/api/strips',content=buffer.getvalue(),headers={'Content-Type':'image/jpeg'});assert uploaded.status_code==200
    strip=action(c,uploaded.json(),'analyze').json();assert strip['status']=='succeeded' and strip['recognition_mode']=='gemini'
    assert strip['expiry_status']['state']=='unclear'
    strip=save_strip(c,strip).json();strip=action(c,strip,'confirm').json()
    assert strip['confirmed'] and strip['expiry_status']['state']=='not_expired_by_date'
    assert current(c)['associations']==before and len(current(c)['course_results'])==3
    assert sdk.models.generate_content.call_count==3

@pytest.mark.parametrize('pattern',['1-0-0','0-1-0','0-0-1','1-0-1','1-1-0','0-1-1','1-1-1'])
def test_exact_three_slot_mapping(pattern):
    assert list(three_slots(pattern).values())==[int(x) for x in pattern.split('-')]+[0]

@pytest.mark.parametrize('pattern',['0-0-0','2-0-1','1/2-0-1','1-0-1-0','1—0—1','OD','1-0-1 then 0-0-1'])
def test_ambiguous_patterns_have_no_mapping(pattern):assert three_slots(pattern) is None

def test_month_and_day_date_rules_without_inventing_a_day():
    import strip
    now=date(2026,11,5)
    for text,expected in [('10/2026','expired'),('12/2026','not_expired_by_date'),('11/2026','unclear')]:
        payload=strip.normalize_strip_response(transcription((text,)))
        assert expiry_status(payload,True,now)['state']==expected
        assert expiry_status(payload,False,now)['state']=='unclear'
    assert expiry_status(None,True,now)['state']=='unclear'

@pytest.mark.parametrize('pattern',['1-0-0','0-1-0','0-0-1','1-0-1','1-1-0','0-1-1','1-1-1'])
def test_every_pattern_requires_current_human_notation_confirmation(tmp_path,monkeypatch,pattern):
    from api.tests.test_downstream import setup,medicine,associate,plan
    med=medicine();raw=f'Fictional-A take 2 tablet {pattern} After food for 5 days'
    med.update(raw_text=raw,frequency_pattern=pattern,timing='After food',duration_days=5)
    c,_,_,_=setup(med,lambda i:i.update(raw_text=raw,frequency_raw=pattern,dose_quantity_raw='2',timing_raw='After food',duration_raw='5 days'))
    state=associate(c);p={**plan(),'dose_quantity':2,'duration_days':5,'administrations_by_slot':three_slots(pattern)}
    denied=approve(c,save(c,state,p));assert denied.status_code==422
    state=current(c);r=c.post(route(state,'/schedule/notation/confirm'),json=linked(state));assert r.status_code==200,r.text
    state=r.json();result=approve(c,save(c,state,p));assert result.status_code==200,result.text
    payload=result.json()['result']['payload'];assert payload['status']=='ok'
    assert payload['doses_by_slot']=={s:2*v for s,v in three_slots(pattern).items()}
    # A consumed earlier revision cannot approve notation for a newer plan.
    assert c.post(route(state,'/schedule/notation/confirm'),json=linked(state)).status_code==409
