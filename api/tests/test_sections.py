"""Three independent prescription scopes; all extractors fictional/offline."""
import copy
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from api.dependencies import AIIntegration
from api.main import create_app
from api.tests.test_prescriptions import HEADERS,RECORD,upload,post,reviewed
import medication_instructions as medication
import investigations


def payload(scope,data):
    if scope=='instructions':
        record={k:None for k in medication.TEXT_FIELDS}
        record.update(instruction_id='instruction-001',medicine_name_raw='Fictional-A',
            raw_text='Fictional-A: instruction unclear',uncertainty_reasons=['ambiguous_dose'],
            needs_review=True,confirmation_required=True)
        version=medication.SCHEMA_VERSION
    else:
        record={k:None for k in investigations.TEXT_FIELDS}
        record.update(investigation_id='investigation-001',test_name_raw='Fictional test',
            raw_text='Fictional test ordered',order_context_raw='ordered',
            uncertainty_reasons=['variant_unclear'],needs_review=True,confirmation_required=True)
        version=investigations.SCHEMA_VERSION
    return {'schema_version':version,'source_image_sha256':hashlib.sha256(data).hexdigest(),
            scope:[record],'issues':[],'confirmation_required':True}


def setup(extra=None,enabled=None):
    calls={s:0 for s in ['medicines','instructions','investigations']}
    def extractor(scope):
        def run(data):
            calls[scope]+=1
            if extra and scope in extra:return extra[scope](data)
            return [copy.deepcopy(RECORD)] if scope=='medicines' else payload(scope,data)
        return run
    app=create_app(factory=lambda:AIIntegration(extractors={s:extractor(s) for s in calls}),
                   **({'enabled_sections':enabled} if enabled else {}))
    client=TestClient(app,base_url='https://localhost',headers=HEADERS)
    assert client.post('/api/session').status_code==200
    return client,app,calls


def route(state,scope,action=''):
    return f'/api/prescriptions/{state["analysis_id"]}/sections/{scope}'+action


def extract(client,state,scope):
    current=client.get(route(state,scope)).json()
    response=client.post(route(state,scope,'/analyze'),json={'revision':current['revision']})
    assert response.status_code==200,response.text
    return response.json()


def confirm(client,state,scope):
    saved=client.put(route(state,scope,'/review'),json={'revision':state['revision'],'payload':state['payload']})
    assert saved.status_code==200,saved.text
    response=client.post(route(state,scope,'/confirm'),json={'revision':saved.json()['revision']})
    assert response.status_code==200,response.text
    return response.json()


def test_independent_extraction_confirmation_and_no_association():
    client,app,calls=setup()
    state=upload(client)
    assert calls=={'medicines':0,'instructions':0,'investigations':0}
    ins=extract(client,state,'instructions')
    assert ins['payload']['instructions'][0]['dose_quantity_raw'] is None
    assert ins['payload']['instructions'][0]['needs_review'] is True
    assert ins['payload']['instructions'][0]['uncertainty_reasons']==['ambiguous_dose']
    assert client.post(route(ins,'instructions','/confirm'),json={'revision':ins['revision']}).status_code==409
    ins=confirm(client,ins,'instructions')
    assert ins['confirmed'] and not client.get(f'/api/prescriptions/{state["analysis_id"]}').json()['confirmed']
    inv=confirm(client,extract(client,state,'investigations'),'investigations')
    med=post(client,state,'analyze').json()
    med=post(client,reviewed(client,med).json(),'confirm').json()
    assert med['confirmed'] and med['sections']['instructions']['confirmed'] and med['sections']['investigations']['confirmed']
    assert set(med['records'][0])==set(RECORD)
    session=next(iter(app.state.sessions.sessions.values()))
    assert session.ai.snapshot()['confirmed_scopes']==['instructions','investigations','medicines']
    assert session.ai.snapshot()['associations']=={} and session.ai.snapshot()['derived']=={}
    assert calls=={'medicines':1,'instructions':1,'investigations':1}
    assert inv['payload']['investigations'][0]['variant_raw'] is None


def test_edit_invalidates_only_affected_section_and_rejects_stale_revision():
    client,_,_=setup();state=upload(client)
    ins=confirm(client,extract(client,state,'instructions'),'instructions')
    inv=confirm(client,extract(client,state,'investigations'),'investigations')
    dirty=client.post(route(ins,'instructions','/invalidate'),json={'revision':ins['revision']}).json()
    assert not dirty['confirmed'] and not dirty['reviewed']
    assert client.post(route(ins,'instructions','/confirm'),json={'revision':ins['revision']}).status_code==409
    corrected=copy.deepcopy(dirty['payload']);corrected['instructions'][0]['medicine_name_raw']='Corrected fictional name'
    saved=client.put(route(dirty,'instructions','/review'),json={'revision':dirty['revision'],'payload':corrected}).json()
    assert not saved['confirmed']
    assert saved['original_payload']['instructions'][0]['medicine_name_raw']=='Fictional-A'
    assert saved['payload']['instructions'][0]['dose_quantity_raw'] is None
    assert client.get(route(inv,'investigations')).json()['confirmed']


def test_partial_failure_and_explicit_retry_preserve_completed_sections():
    count=[]
    def intermittent(data):
        count.append(1)
        if len(count)==1:raise investigations.InvestigationNetworkError()
        return payload('investigations',data)
    client,_,calls=setup({'investigations':intermittent});state=upload(client)
    ins=confirm(client,extract(client,state,'instructions'),'instructions')
    failed=extract(client,state,'investigations')
    assert failed['status']=='failed' and failed['payload'] is None and failed['error']['category']=='network_error'
    before=client.get(route(ins,'instructions')).json()
    client.get(route(failed,'investigations'))
    assert calls['investigations']==1
    result=extract(client,state,'investigations')
    assert result['status']=='succeeded' and calls['investigations']==2
    assert client.get(route(ins,'instructions')).json()==before


def test_replacement_and_cross_session_reject_old_analysis():
    client,app,_=setup();state=upload(client)
    ins=confirm(client,extract(client,state,'instructions'),'instructions')
    other=TestClient(app,base_url='https://localhost',headers=HEADERS);other.post('/api/session')
    assert other.get(route(ins,'instructions')).status_code==409
    assert other.post(route(ins,'instructions','/confirm'),json={'revision':ins['revision']}).status_code==409
    new=upload(client)
    assert client.post(route(ins,'instructions','/confirm'),json={'revision':ins['revision']}).status_code==409
    for scope in ['instructions','investigations']:
        fresh=client.get(route(new,scope)).json()
        assert fresh['status']=='not_requested' and not fresh['confirmed'] and fresh['payload'] is None


def test_forged_fields_and_cross_scope_payloads_rejected():
    client,_,_=setup();state=upload(client);ins=extract(client,state,'instructions')
    forged=copy.deepcopy(ins['payload']);forged['instructions'][0]['dose_quantity']=12
    assert client.put(route(ins,'instructions','/review'),json={'revision':ins['revision'],'payload':forged}).status_code==422
    ins=client.get(route(ins,'instructions')).json()
    assert client.put(route(ins,'instructions','/review'),json={'revision':ins['revision'],'payload':payload('investigations',b'other')}).status_code==422
    assert client.post(route(ins,'instructions','/confirm'),json={'revision':ins['revision'],'acknowledged':True}).status_code==422


def test_duplicate_section_analyze_calls_only_once():
    entered=threading.Event();release=threading.Event()
    def slow(data):
        entered.set();assert release.wait(5);return payload('instructions',data)
    client,_,calls=setup({'instructions':slow});state=upload(client)
    initial=client.get(route(state,'instructions')).json()
    def run():return client.post(route(state,'instructions','/analyze'),json={'revision':initial['revision']})
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(run);assert entered.wait(5)
        assert run().status_code==409
        release.set();assert first.result(timeout=5).json()['status']=='succeeded'
    assert calls['instructions']==1


def test_diagnostic_capabilities_do_not_expand_with_new_routes():
    client,_,calls=setup(enabled=('medicines',));state=upload(client)
    assert client.get('/api/health').json()['scopes']==['medicines']
    assert client.get(route(state,'instructions')).status_code==404
    assert client.get(route(state,'investigations')).status_code==404
    assert calls=={'medicines':0,'instructions':0,'investigations':0}


def test_empty_section_is_success_not_failure_and_needs_own_confirmation():
    def empty(data):
        result=payload('investigations',data);result['investigations']=[];return result
    client,_,_=setup({'investigations':empty});state=upload(client)
    inv=extract(client,state,'investigations')
    assert inv['status']=='succeeded' and inv['payload']['investigations']==[] and inv['error'] is None
    inv=confirm(client,inv,'investigations')
    assert inv['confirmed']


def test_replacing_image_during_section_extraction_rejects_late_result():
    entered=threading.Event();release=threading.Event()
    def slow(data):
        entered.set();assert release.wait(5);return payload('instructions',data)
    client,_,_=setup({'instructions':slow});state=upload(client)
    current=client.get(route(state,'instructions')).json()
    def run():return client.post(route(state,'instructions','/analyze'),json={'revision':current['revision']})
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(run);assert entered.wait(5)
        new=upload(client);release.set()
        assert first.result(timeout=5).status_code==409
    fresh=client.get(route(new,'instructions')).json()
    assert fresh['status']=='not_requested' and fresh['payload'] is None
