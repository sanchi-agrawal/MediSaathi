import copy
import pytest
from api.tests.test_numeric_and_strip_integration import configured
from api.tests.test_prescriptions import post
from api.tests.test_downstream import current,binding,linked,route,save,approve
from api.downstream import scheduling
import confirmed_frequency

def test_three_medicines_use_confirmed_names_without_any_frequency_parser_after_review(tmp_path,monkeypatch):
    c,sdk,med=configured(tmp_path,monkeypatch)
    expected=[['morning','night'],['night'],['morning']]
    for i,slots in enumerate(expected,1):
        s=current(c);s=c.post(route(s,'/associations'),json={**binding(s),'medicine_ref':f'medicine_{i:03}','instruction_id':f'instruction_{i:03}'}).json()
        entry=s['automatic'][i-1];assert entry['proposed_slots']==slots and entry['confirmed_slots']==[] and entry['template'] is None
        bad=c.post(route(s,'/schedule/slots/confirm'),json={**linked(s),'slots':['bedtime']});assert bad.status_code==422
        response=c.post(route(s,'/schedule/slots/confirm'),json={**linked(s),'slots':slots});assert response.status_code==200,response.text
        assert response.json()['automatic'][i-1]['confirmed_slots']==slots
    assert current(c)['timing_contract']=='confirmed-named-slots-v1'
    # A successful generation may not reinterpret notation anywhere downstream.
    monkeypatch.setattr(confirmed_frequency,'three_slots',lambda *a:pytest.fail('Frequency reparsed after slot confirmation'))
    monkeypatch.setattr(scheduling.engine,'parse_pattern',lambda *a:pytest.fail('Engine reparsed a frequency string'))
    calls=[];original=scheduling.engine.build_schedule
    def engine(medicine,start,confirmed_slots=None):
        calls.append(copy.deepcopy(confirmed_slots));return original(medicine,start,confirmed_slots)
    monkeypatch.setattr(scheduling.engine,'build_schedule',engine)
    for entry in current(c)['automatic']:
        s={**current(c),'association':entry['association']}
        result=approve(c,save(c,s,{**entry['template'],'start_date':'2026-11-05'}));assert result.status_code==200,result.text
    assert calls==expected
    results=current(c)['course_results'];assert len(results)==3
    assert [r['result']['payload']['duration_days'] for r in results]==[5,3,7]
    assert [r['result']['payload']['end_date'] for r in results]==['2026-11-09','2026-11-07','2026-11-11']
    assert sdk.models.generate_content.call_count==2
    state=c.get(f"/api/prescriptions/{med['analysis_id']}/sections/instructions").json()
    assert c.post(f"/api/prescriptions/{med['analysis_id']}/sections/instructions/invalidate",json={'revision':state['revision']}).status_code==200
    now=current(c);assert not now['ready'] and now['course_results']==[] and now['associations']==[]

def test_named_engine_does_not_infer_dose_or_clear_review_flags():
    from datetime import date
    from api.tests.test_downstream import medicine
    med=medicine();med.update(confirmed=True,frequency_pattern='DO NOT PARSE',dose_quantity=2,dose_unit='tablet')
    result=scheduling.engine.build_schedule(med,date(2026,11,5),['afternoon'])
    assert result['status']=='ok' and result['doses_by_slot']['noon']==2 and result['doses_by_slot']['morning']==0
    med['needs_review']=True;assert scheduling.engine.build_schedule(med,date(2026,11,5),['morning'])['status']=='needs_input'
    med['needs_review']=False;med.pop('dose_quantity');assert scheduling.engine.build_schedule(med,date(2026,11,5),['morning'])['status']=='needs_input'

@pytest.mark.parametrize('slots',[[],['noon'],['morning','morning'],['dawn'],['morning',1]])
def test_engine_rejects_invalid_named_slots(slots):
    from datetime import date
    from api.tests.test_downstream import medicine
    med=medicine();med.update(confirmed=True,dose_quantity=1,dose_unit='tablet')
    assert scheduling.engine.build_schedule(med,date(2026,11,5),slots)['status']=='needs_input'
