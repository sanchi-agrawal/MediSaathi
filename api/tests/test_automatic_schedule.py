import copy
import pytest
from api.tests.test_downstream import setup,associate,current,save,approve,binding,route
from api.tests.test_prescriptions import post


def test_date_only_preparation_generation_and_new_dates():
    c,app,med,ins=setup();state=associate(c)
    entry=state['automatic'][0]
    assert not entry['issues'] and 'start_date' not in entry['template']
    assert entry['template']['dose_quantity']==1 and entry['template']['duration_days']==3
    for start,end in [('2026-11-03','2026-11-05'),('2026-11-09','2026-11-11')]:
        state=save(c,current(c),{**entry['template'],'start_date':start})
        state=approve(c,state).json()
        assert state['result']['payload']['end_date']==end
        assert len(state['course_results'])==1
    assert post(c,med,'invalidate').status_code==200
    state=current(c)
    assert not state['ready'] and not state['course_results'] and not state['associations']


@pytest.mark.parametrize('change,reason',[
    ({'dose_quantity_raw':None},'dose_quantity_missing'),({'dose_unit_raw':None},'dose_unit_missing'),
    ({'duration_raw':None},'duration_missing'),({'frequency_raw':'OD'},'frequency_unsupported'),
    ({'timing_raw':None},'timing_missing'),({'dose_quantity_raw':'1/2'},'quantity_unsupported'),
    ({'duration_raw':'3-5 days'},'duration_unsupported'),
    ({'timing_raw':'morning'},'source_requires_clarification'),
])
def test_missing_or_ambiguous_source_never_prepares_plan(change,reason):
    c,_,_,_=setup(ins_edit=lambda i:i.update(change));entry=associate(c)['automatic'][0]
    assert entry['template'] is None and reason in entry['issues']


def test_missing_association_blocks_without_automatic_matching():
    c,_,_,_=setup();entry=current(c)['automatic'][0]
    assert entry['template'] is None and entry['issues']==['association_required']


def test_multiple_explicit_pairs_keep_separate_plans_and_results():
    from api.dependencies import AIIntegration
    from api.main import create_app
    from api.downstream.scheduling import schedule_handoff
    from api.tests.test_downstream import medicine,instruction
    from api.tests.test_prescriptions import HEADERS,upload,post,reviewed
    from api.tests.test_sections import extract,confirm
    from fastapi.testclient import TestClient
    a=medicine();b={**a,'name':'Fictional-B','raw_text':'Fictional-B take 2 tablet BD morning and night for 5 days','duration_days':5}
    def instructions(data):
        env=instruction(data,a);second=copy.deepcopy(env['instructions'][0]);second.update(instruction_id='instruction_002',medicine_name_raw='Fictional-B',raw_text=b['raw_text'],dose_quantity_raw='2',duration_raw='5 days');env['instructions'].append(second);return env
    app=create_app(factory=lambda:AIIntegration(extractors={'medicines':lambda _:[a,b],'instructions':instructions},downstream={'schedule':schedule_handoff}))
    c=TestClient(app,base_url='https://localhost',headers=HEADERS);c.post('/api/session')
    state=post(c,upload(c),'analyze').json();state=post(c,reviewed(c,state).json(),'confirm').json();confirm(c,extract(c,state,'instructions'),'instructions')
    s=associate(c)
    s=c.post(route(s,'/associations'),json={**binding(s),'medicine_ref':'medicine_002','instruction_id':'instruction_002'}).json()
    assert len(s['associations'])==2 and all(e['template'] for e in s['automatic'])
    for e in s['automatic']:
        active={**current(c),'association':e['association']}
        active=save(c,active,{**e['template'],'start_date':'2026-11-03'})
        assert approve(c,active).status_code==200
    results=current(c)['course_results'];assert len(results)==2
    assert [r['result']['payload']['total_units'] for r in results]==[6,20]
