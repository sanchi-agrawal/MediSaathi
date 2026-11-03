"""Original OCR completeness must not override current confirmed prescribing data."""
import copy,json
from types import SimpleNamespace
import pytest
from api.tests.test_clock_scheduling import runtime,synthetic_image,clock_state,clock_body,send
from api.tests.test_clock_browser_handoff import client
from api.tests.test_local_auth import PREFIX,DETAILS
from api.tests.test_prescriptions import upload,post
from api.tests.test_sections import extract,confirm,route as section_route
from api.tests.test_downstream import current,binding,route

@pytest.mark.parametrize('transport',['asgi','tcp'])
@pytest.mark.parametrize('incomplete',[None,'dose','count'])
def test_original_flag_then_current_clinical_review(runtime,transport,monkeypatch,incomplete):
    app,sdk,_=runtime;responses=list(sdk.models.generate_content.side_effect)
    medicines=json.loads(responses[0].text);envelope=json.loads(responses[1].text)
    names=['Dolo 650','Cetirizine 10 mg','Omeprazole 20 mg'];durations=[5,3,7]
    frequencies=['twice per day','once per day','once per day']
    original_lines=[]
    for i,med in enumerate(medicines):
        form='capsule' if i==2 else 'tablet'
        # Medicine OCR line is incomplete and contains stale structured fields.
        # The separate instruction line is the prescribing source, not this text.
        med.update(name=names[i],salt=None,raw_text=f'{names[i]} {form}',
            form=form,duration_days=1,frequency_pattern='BD',timing='legacy OCR timing',
            needs_review=True,confidence=None)
        frequency='as directed' if incomplete=='count' and i==0 else frequencies[i]
        source=f'{names[i]} take 1 {form} {frequency} for {durations[i]} days'
        if i==0:source+=' After food'
        original_lines.append({'raw_text':source})
        envelope['instructions'][i].update(medicine_name_raw=names[i],raw_text=source,
            dose_quantity_raw=None if incomplete=='dose' and i==0 else '1',dose_unit_raw=form,
            duration_raw=f'{durations[i]} days',frequency_raw=frequency,
            timing_raw='After food' if i==0 else None,route_raw=None,
            uncertainty_reasons=[],needs_review=bool(incomplete and i==0))
    responses[:2]=[SimpleNamespace(text=json.dumps(medicines)),SimpleNamespace(text=json.dumps(envelope))]
    sdk.models.generate_content.side_effect=responses
    with client(app,transport,monkeypatch) as c:
        assert c.get('/api/health').json()['scheduling_eligibility_policy']=='confirmed-clinical-fields-v2'
        assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
        assert c.post('/api/session').status_code==200
        source=post(c,upload(c,synthetic_image(original_lines)),'analyze').json()
        original=copy.deepcopy(source['original_records']);records=copy.deepcopy(source['records'])
        for i,record in enumerate(records):record['duration_days']=durations[i]
        saved=c.put(f"/api/prescriptions/{source['analysis_id']}/review",json={'revision':source['revision'],'records':records})
        assert saved.status_code==200,saved.text
        source=post(c,saved.json(),'confirm').json();assert source['confirmed']
        instructions=confirm(c,extract(c,source,'instructions'),'instructions');assert instructions['confirmed']
        for index in range(1,4):
            fresh=current(c);r=c.post(route(fresh,'/associations'),json={**binding(fresh),'medicine_ref':f'medicine_{index:03}','instruction_id':f'instruction_{index:03}'})
            assert r.status_code==200,r.text
        state=clock_state(c)
        assert [m['administrations_per_day'] for m in state['medicines']]==([0,1,1] if incomplete else [2,1,1])
        assert [m['eligible'] for m in state['medicines']]==([False,True,True] if incomplete else [True,True,True])
        assert [m['duration_days'] for m in state['medicines']]==durations
        assert all(m['review_details']['flagged'] and 'salt' in m['review_details']['missing_fields'] for m in state['medicines'])
        body=clock_body(state)
        if incomplete:body['medicines']=body['medicines'][1:]
        generated=send(c,state,body);assert generated.status_code==200,generated.text
        course=generated.json()
        assert [len(m['days'])*len(m['clock_times']) for m in course['medicines']]==([3,7] if incomplete else [10,3,7])
        assert [m['result']['total_units'] for m in course['medicines']]==([3,7] if incomplete else [10,3,7])
        if incomplete:
            assert course['blocked'][0]['name']=='Dolo 650'
            assert ('dose_quantity_missing' if incomplete=='dose' else 'administration_count_unconfirmed') in course['blocked'][0]['issues']
        else:assert not course['blocked']
        fresh=c.get('/api/prescriptions/current').json()
        assert fresh['original_records']==original
        assert all(m['needs_review'] is True and m['salt'] is None for m in fresh['records'])
        assert [m['duration_days'] for m in fresh['records']]==durations
        assert fresh['revision']==source['revision']
        assert clock_state(c)['course']==course
        # A current instruction edit still revokes the course and confirmations.
        response=c.post(section_route(source,'instructions','/invalidate'),json={'revision':instructions['revision']})
        assert response.status_code==200,response.text
        assert clock_state(c)['course'] is None
        assert not any(m['eligible'] for m in clock_state(c)['medicines'])
        assert sdk.models.generate_content.call_count==2
