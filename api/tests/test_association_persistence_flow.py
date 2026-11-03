"""Fictional three-medicine local-account flow; no provider or notification calls."""
import copy,hashlib
import pytest
from fastapi.testclient import TestClient
from api.local_auth import create_local_app,PREFIX
from api.dependencies import AIIntegration,reader
from api.downstream.scheduling import schedule_handoff
from api.tests.test_local_auth import HEADERS,DETAILS
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import current,binding,linked,route,save,approve


def configured(tmp_path,monkeypatch,unsupported=False):
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**k:pytest.fail('Gemini forbidden'))
    names=['Dolo','Cetirizine','Omeprazole'];meds=[];instructions=[]
    for i,name in enumerate(names,1):
        frequency='1-0-1' if unsupported else 'BD';timing='After food' if unsupported else 'morning and night'
        raw=f'{name} {i} tablet {frequency} {timing} for {i+2} days'
        meds.append(dict(raw_text=raw,name=name,salt=None,strength=None,form='tablet',frequency_pattern=frequency,duration_days=i+2,timing=timing,confidence=None,needs_review=False))
        instructions.append(dict(instruction_id=f'instruction_{i:03}',medicine_name_raw=name,raw_text=raw,dose_quantity_raw=str(i),dose_unit_raw='tablet',frequency_raw=frequency,timing_raw=timing,duration_raw=f'{i+2} days',route_raw=None,uncertainty_reasons=[],needs_review=True,confirmation_required=True))
    def instruction_extractor(data):return dict(schema_version='medication-instructions-v1',source_image_sha256=hashlib.sha256(data).hexdigest(),instructions=copy.deepcopy(instructions),issues=[],confirmation_required=True)
    app=create_local_app(tmp_path/'accounts.sqlite3',offline=False)
    app.state.sessions.factory=lambda:AIIntegration(extractors={'medicines':lambda _:copy.deepcopy(meds),'instructions':instruction_extractor},downstream={'schedule':schedule_handoff})
    c=TestClient(app,base_url='http://localhost',headers=HEADERS)
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    c.post(PREFIX+'/logout');assert c.post(PREFIX+'/login',json={k:DETAILS[k] for k in ('email','password')}).status_code==200
    data=post(c,upload(c),'analyze').json();data=post(c,reviewed(c,data).json(),'confirm').json()
    ins=confirm(c,extract(c,data,'instructions'),'instructions')
    return c,data,ins


def link(c,number):
    s=current(c);r=c.post(route(s,'/associations'),json={**binding(s),'medicine_ref':f'medicine_{number:03}','instruction_id':f'instruction_{number:03}'})
    assert r.status_code==200,r.text
    return r.json()


def test_login_review_three_pairs_navigation_and_date_only_generation(tmp_path,monkeypatch):
    c,med,ins=configured(tmp_path,monkeypatch)
    for i,name in enumerate(['Dolo','Cetirizine','Omeprazole'],1):
        saved=link(c,i);fresh=current(c)
        assert len(fresh['associations'])==i and fresh['associations']==saved['associations']
        entry=fresh['automatic'][i-1]
        assert entry['template']['dose_quantity']==i and entry['template']['duration_days']==i+2
        assert fresh['medicines'][i-1]['name']==name
    for entry in current(c)['automatic']:
        state={**current(c),'association':entry['association']}
        result=approve(c,save(c,state,{**entry['template'],'start_date':'2026-11-05'}))
        assert result.status_code==200
    assert len(current(c)['course_results'])==3
    invalidated=c.post(f"/api/prescriptions/{med['analysis_id']}/sections/instructions/invalidate",json={'revision':ins['revision']})
    assert invalidated.status_code==200
    fresh=current(c);assert not fresh['ready'] and not fresh['associations'] and not fresh['course_results']
    assert c.get(PREFIX+'/me').status_code==200


def test_duplicate_conflict_and_stale_requests_cannot_replace_links(tmp_path,monkeypatch):
    c,_,_=configured(tmp_path,monkeypatch);old=current(c);state=link(c,1)
    for body,category in [
        ({**binding(state),'medicine_ref':'medicine_001','instruction_id':'instruction_001'},'association_exists'),
        ({**binding(state),'medicine_ref':'medicine_002','instruction_id':'instruction_001'},'association_conflict'),
        ({**binding(old),'medicine_ref':'medicine_002','instruction_id':'instruction_002'},'stale_result')]:
        response=c.post(route(state,'/associations'),json=body)
        assert response.status_code==409 and response.json()['detail']['category']==category
        assert current(c)['associations']==state['associations']


def test_numeric_pattern_link_saves_but_unsupported_schedule_stays_blocked(tmp_path,monkeypatch):
    c,_,_=configured(tmp_path,monkeypatch,unsupported=True);state=link(c,1)
    assert state['associations'] and current(c)['instructions'][0]['frequency_raw']=='1-0-1'
    assert state['automatic'][0]['template'] is None
    assert 'notation_confirmation_required' in state['automatic'][0]['issues']
