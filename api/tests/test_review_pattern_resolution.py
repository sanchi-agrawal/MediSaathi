import copy
import pytest
from api.tests import test_numeric_and_strip_integration as integration
from api.tests.test_prescriptions import post
from api.tests.test_downstream import current,binding,linked,route,save,approve
from api.medicine_review import VERIFY_FIELDS
from confirmed_frequency import three_slots,canonical_pattern,remove_verified_pattern


@pytest.mark.parametrize('pattern',['1-0-1','1 - 0 - 1','1 – 0 – 1'])
def test_real_reader_review_resolution_and_confirmed_format_generate(tmp_path,monkeypatch,pattern):
    meds,ins,image=integration.fixture()
    meds[0].update(needs_review=True,frequency_pattern=pattern,raw_text=meds[0]['raw_text'].replace('1-0-1',pattern))
    ins[0].update(frequency_raw=pattern,raw_text=ins[0]['raw_text'].replace('1-0-1',pattern),dose_unit_raw='tab')
    ins[0]['raw_text']=ins[0]['raw_text'].replace('1 tablet','1 tab')
    # Source and structured fields may use different harmless separators/spaces.
    meds[0]['raw_text']=meds[0]['raw_text'].replace(pattern,'1 – 0 – 1')
    ins[0]['raw_text']=ins[0]['raw_text'].replace(pattern,'1 - 0 - 1')
    # Distinct literal spellings are retained in each independently reviewed scope.
    monkeypatch.setattr(integration,'fixture',lambda:(meds,ins,image))
    c,sdk,state=integration.configured(tmp_path,monkeypatch)
    assert state['original_records'][0]['needs_review'] is True
    req=state['review_requirements'][0];assert req['flagged'] and req['can_resolve']
    response=c.post(f"/api/prescriptions/{state['analysis_id']}/review/resolve",json={'revision':state['revision'],'record_index':0,'verified_fields':list(VERIFY_FIELDS),'acknowledge':True})
    assert response.status_code==200,response.text
    state=response.json();assert state['original_records'][0]['needs_review'] is True and state['records'][0]['needs_review'] is False
    assert not state['confirmed'];state=post(c,state,'confirm').json()
    s=current(c);s=c.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_001','instruction_id':'instruction_001'}).json()
    assert 'notation_confirmation_required' in s['automatic'][0]['issues']
    # No pattern approval is inferred from generic medicine/instruction confirmation.
    assert s['automatic'][0]['template'] is None
    s=c.post(route(s,'/schedule/notation/confirm'),json=linked(s)).json()
    template=s['automatic'][0]['template'];assert template['dose_unit']=='tablet'
    result=approve(c,save(c,s,{**template,'start_date':'2026-11-05'}));assert result.status_code==200,result.text
    assert result.json()['result']['payload']['doses_by_slot']=={'morning':1,'noon':0,'night':1,'bedtime':0}
    assert current(c)['associations']==s['associations']
    assert sdk.models.generate_content.call_count==2


@pytest.mark.parametrize('change,field',[({'salt':None},'salt'),({'confidence':None},'confidence'),({'confidence':.5},None)])
def test_unknown_or_low_confidence_review_stays_unresolved(tmp_path,monkeypatch,change,field):
    meds,ins,image=integration.fixture();meds[0].update(change);monkeypatch.setattr(integration,'fixture',lambda:(meds,ins,image))
    c,_,state=integration.configured(tmp_path,monkeypatch);details=state['review_requirements'][0]
    assert not details['can_resolve'] and details['flagged']
    if field:assert field in details['missing_fields']
    response=c.post(f"/api/prescriptions/{state['analysis_id']}/review/resolve",json={'revision':state['revision'],'record_index':0,'verified_fields':list(VERIFY_FIELDS),'acknowledge':True})
    assert response.status_code==422
    assert c.get('/api/prescriptions/current').json()['records'][0]['needs_review'] is True


def test_missing_ocr_value_can_only_be_resolved_after_source_supported_edit(tmp_path,monkeypatch):
    meds,ins,image=integration.fixture();meds[0]['salt']=None;monkeypatch.setattr(integration,'fixture',lambda:(meds,ins,image))
    c,_,state=integration.configured(tmp_path,monkeypatch)
    forged=copy.deepcopy(state['records']);forged[0]['needs_review']=False
    denied=c.put(f"/api/prescriptions/{state['analysis_id']}/review",json={'revision':state['revision'],'records':forged});assert denied.status_code==422
    state=c.get('/api/prescriptions/current').json();records=copy.deepcopy(state['records']);records[0]['salt']='Paracetamol'
    # This ingredient was explicitly present in the synthetic source, not inferred.
    response=c.put(f"/api/prescriptions/{state['analysis_id']}/review",json={'revision':state['revision'],'records':records});assert response.status_code==200
    state=response.json();assert state['review_requirements'][0]['can_resolve']
    stale_revision=state['revision'];body={'revision':stale_revision,'record_index':0,'verified_fields':list(VERIFY_FIELDS),'acknowledge':True}
    assert c.post(f"/api/prescriptions/{state['analysis_id']}/review/resolve",json={**body,'verified_fields':['name']}).status_code==422
    assert c.post(f"/api/prescriptions/{state['analysis_id']}/review/resolve",json=body).status_code==200
    assert c.post(f"/api/prescriptions/{state['analysis_id']}/review/resolve",json=body).status_code==409


def test_only_verified_pattern_token_is_removed_from_range_checks():
    assert canonical_pattern('1 – 0 – 1')=='1-0-1'
    assert three_slots('1 - 0 - 1')==three_slots('1-0-1')
    assert '5-7 days' in remove_verified_pattern('1 – 0 – 1 for 5-7 days','1-0-1')
    assert canonical_pattern('1 - 0 - 1 then 0-0-1') is None
