import copy,json
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
import medication_instructions as medication
from api.tests.test_clock_scheduling import runtime,ordinary_review,synthetic_image
from api.tests.test_patient_explanations import patient_runtime
from api.tests.test_clock_browser_handoff import client
from api.tests.test_local_auth import HEADERS,DETAILS,PREFIX
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm,route

def prefill(c):
    r=c.get('/api/planner/prescription');assert r.status_code==200,r.text
    return r.json()

@pytest.mark.parametrize('transport',['asgi','tcp'])
def test_confirmed_associations_prefill_without_any_scheduling_action(patient_runtime,monkeypatch,transport):
    app,sdk,image=patient_runtime
    with client(app,transport,monkeypatch) as c:
        ordinary_review(c,image,slots=False)
        session=next(iter(app.state.sessions.sessions.values()));before=copy.deepcopy(session.ai.snapshot())
        monkeypatch.setattr(session.ai,'schedule',lambda *a,**k:pytest.fail('No approval or schedule generation permitted'))
        monkeypatch.setattr(session.ai,'associate',lambda *a,**k:pytest.fail('Prefill must never create associations'))
        value=prefill(c)
        assert [m['name'] for m in value['medicines']]==['Dolo','Cetirizine','Omeprazole']
        assert [m['quantity'] for m in value['medicines']]==[1,1,1]
        assert [m['days'] for m in value['medicines']]==[5,3,7]
        assert [m['administrations_per_day'] for m in value['medicines']]==[2,1,1]
        assert all(m['eligible'] and m['relationship']=='confirmed_link' for m in value['medicines'])
        assert session.ai.snapshot()==before and sdk.models.generate_content.call_count==2
        assert 'raw_text' not in json.dumps(value) and 'image' not in value

def review_without_links(c,image):
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    assert c.post('/api/session').status_code==200
    state=post(c,upload(c,image),'analyze').json()
    # Extraction alone is not a saved user review.
    initial=prefill(c);assert len(initial['medicines'])==3 and not any(m['eligible'] for m in initial['medicines'])
    state=post(c,reviewed(c,state).json(),'confirm').json()
    ins=confirm(c,extract(c,state,'instructions'),'instructions')
    return state,ins

def test_unique_reviewed_names_do_not_require_or_create_associations(patient_runtime):
    app,sdk,image=patient_runtime
    original=sdk.models.generate_content.side_effect
    first=True
    def flagged(**kwargs):
        nonlocal first
        response=original(**kwargs)
        if first:
            first=False;rows=json.loads(response.text)
            for row in rows:row.update(salt=None,needs_review=True,frequency_pattern='legacy metadata')
            return SimpleNamespace(text=json.dumps(rows))
        return response
    sdk.models.generate_content.side_effect=flagged
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        state,ins=review_without_links(c,image)
        session=next(iter(app.state.sessions.sessions.values()));assert session.ai.snapshot()['associations']=={}
        value=prefill(c);assert all(m['eligible'] and m['relationship']=='unique_reviewed_name' for m in value['medicines'])
        assert [m['administrations_per_day'] for m in value['medicines']]==[2,1,1]
        assert session.ai.snapshot()['associations']=={}
        assert all(m['needs_review'] and m['salt'] is None for m in c.get('/api/prescriptions/current').json()['records'])
        assert c.post(route(state,'instructions','/invalidate'),json={'revision':ins['revision']}).status_code==200
        assert not any(m['eligible'] for m in prefill(c)['medicines'])
        assert sdk.models.generate_content.call_count==2

def test_mocked_mixed_hindi_review_preserves_instructions_and_prefills_three_medicines(patient_runtime):
    app,sdk,image=patient_runtime
    medicines=[];instructions=[]
    rows=[
        ('Dolo','Dolo 650 mg गोली','650 mg','Dolo 650 mg १ गोली दिन में दो बार ५ दिन खाने के बाद','Dolo','गोली','दिन में दो बार','५ दिन','खाने के बाद'),
        ('Cetirizine','सेटिरिज़िन 10 मि.ग्रा. (Cetirizine 10 mg)','10 मि.ग्रा.','सेटिरिज़िन 10 मि.ग्रा. (Cetirizine 10 mg) १ गोली दिन में एक बार ३ दिन रात में','सेटिरिज़िन','गोली','दिन में एक बार','३ दिन','रात में'),
        ('Omeprazole','ओमेप्राज़ोल 20 मि.ग्रा. (Omeprazole 20 mg)','20 मि.ग्रा.','ओमेप्राज़ोल 20 मि.ग्रा. (Omeprazole 20 mg) १ कैप्सूल दिन में एक बार ७ दिन सुबह','ओमेप्राज़ोल','कैप्सूल','दिन में एक बार','७ दिन','सुबह'),
    ]
    for name,raw,strength,line,written,unit,frequency,duration,timing in rows:
        medicines.append(dict(raw_text=raw,name=raw if name!='Dolo' else name,salt=None,
            strength=strength,form='tablet' if name=='Dolo' else None,
            frequency_pattern=None,duration_days=None,timing=None,confidence=None,needs_review=True))
        item={field:None for field in medication.TEXT_FIELDS}
        item.update(medicine_name_raw=written,raw_text=line,dose_quantity_raw='१',
            dose_unit_raw=unit,frequency_raw=frequency,duration_raw=duration,timing_raw=timing)
        instructions.append({**item,'uncertainty_reasons':[],'needs_review':True})
    sdk.models.generate_content.side_effect=[SimpleNamespace(text=json.dumps(medicines,ensure_ascii=False)),
        SimpleNamespace(text=json.dumps({'instructions':instructions,'issues':[]},ensure_ascii=False))]
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        state,ins=review_without_links(c,image)
        assert [m['name'] for m in state['records']]==['Dolo','Cetirizine','Omeprazole']
        assert state['records'][1]['raw_text']==rows[1][1]
        assert state['records'][1]['strength']=='10 mg'
        assert ins['payload']['instructions'][1]['raw_text']==rows[1][3]
        value=prefill(c)
        assert [m['name'] for m in value['medicines']]==['Dolo','Cetirizine','Omeprazole']
        assert [m['quantity'] for m in value['medicines']]==[1,1,1]
        assert [m['unit'] for m in value['medicines']]==['tablet','tablet','capsule']
        assert [m['days'] for m in value['medicines']]==[5,3,7]
        assert [m['administrations_per_day'] for m in value['medicines']]==[2,1,1]
        assert all(m['eligible'] for m in value['medicines'])
        assert sdk.models.generate_content.call_count==2

@pytest.mark.parametrize('kind',['missing_dose','unknown_count','ambiguous_name'])
def test_incomplete_medicine_does_not_block_other_prefills(patient_runtime,kind):
    app,sdk,image=patient_runtime;original=sdk.models.generate_content.side_effect;calls=0
    def incomplete(**kwargs):
        nonlocal calls
        response=original(**kwargs);calls+=1
        if calls==2:
            payload=json.loads(response.text);row=payload['instructions'][0]
            if kind=='missing_dose':row['dose_quantity_raw']=None
            elif kind=='unknown_count':row['raw_text']=row['raw_text'].replace('twice daily','as directed');row['frequency_raw']='as directed'
            else:payload['instructions'].append({**row,'raw_text':row['raw_text']+' duplicate'})
            return SimpleNamespace(text=json.dumps(payload))
        return response
    sdk.models.generate_content.side_effect=incomplete
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review_without_links(c,image);value=prefill(c)
        assert [m['eligible'] for m in value['medicines']]==[False,True,True]
        assert value['medicines'][0]['missing']
        if kind=='missing_dose':assert value['medicines'][0]['quantity'] is None
        if kind=='unknown_count':assert value['medicines'][0]['administrations_per_day'] is None

def test_empty_workspace_and_two_account_isolation(patient_runtime):
    app,_,image=patient_runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as a:
        assert a.get('/api/planner/prescription').status_code==401
        review_without_links(a,image);assert len(prefill(a)['medicines'])==3
        with TestClient(app,base_url='http://localhost',headers=HEADERS) as b:
            assert b.post(PREFIX+'/signup',json={**DETAILS,'email':'planner-b@example.test'}).status_code==200
            assert prefill(b)['medicines']==[]
            assert prefill(a)['medicines']

def test_unverified_numeric_notation_never_becomes_a_default_count(runtime):
    app,_,image=runtime
    with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:
        review_without_links(c,image)
        value=prefill(c)
        assert all(not m['eligible'] and m['administrations_per_day'] is None for m in value['medicines'])
        assert all('administrations_per_day' in m['missing'] for m in value['medicines'])
