"""Fictional observations; unchanged strip normalizer and no external OCR."""
import copy
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import threading

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from api.dependencies import AIIntegration,reader
from api.main import create_app
from api.tests.test_prescriptions import HEADERS,RECORD,upload as prescription_upload,post,reviewed
import strip


def image(fmt='PNG'):
    out=BytesIO();Image.new('RGB',(5,5),'white').save(out,format=fmt);return out.getvalue()


def transcription(dates=('08/2027',),label='EXP'):
    return {'medicine_name':'Fictional strip','batch_number':'DEMO-001','product_association':'single_product',
        'date_observations':[{'raw_label':label,'raw_date_text':value,'raw_text':label+' '+value,
            'association':'same_product','confidence':0.95,'uncertain':False} for value in dates],
        'quality_issues':[],'confidence':0.95,'uncertain':False}


def setup(data=None,extractor=None,enabled=None):
    calls=[]
    def run(raw):
        calls.append(raw)
        return extractor(raw) if extractor else strip.normalize_strip_response(copy.deepcopy(data or transcription()))
    app=create_app(factory=lambda:AIIntegration(extractors={'strip':run,'medicines':lambda _:[copy.deepcopy(RECORD)]}),
                   **({'enabled_sections':enabled} if enabled else {}))
    client=TestClient(app,base_url='https://localhost',headers=HEADERS);client.post('/api/session')
    return client,app,calls


def upload(client,data=None,mime='image/png'):
    response=client.post('/api/strips',content=data if data is not None else image(),headers={'Content-Type':mime})
    assert response.status_code==200,response.text
    return response.json()


def action(client,state,operation,**fields):
    return client.post('/api/strips/'+state['analysis_id']+'/'+operation,json={'revision':state['revision'],**fields})


def extract(client):
    return action(client,upload(client),'analyze').json()


def edits(state):
    payload=state['payload']
    return {k:payload[k] for k in ('medicine_name','batch_number','product_association')}|{
        'date_observations':[{k:o[k] for k in ('raw_label','raw_date_text','raw_text','association')} for o in payload['date_observations']]}


def save(client,state,changes=None):
    return client.put('/api/strips/'+state['analysis_id']+'/review',json={'revision':state['revision'],**(changes if changes is not None else edits(state))})


def confirmed(client,state=None):
    state=state or extract(client)
    saved=save(client,state);assert saved.status_code==200,saved.text
    result=action(client,saved.json(),'confirm');assert result.status_code==200,result.text
    return result.json()


def test_readable_month_precision_requires_explicit_scope_confirmation():
    client,app,calls=setup();state=upload(client)
    client.get('/api/strips/'+state['analysis_id'])
    assert calls==[]
    state=action(client,state,'analyze').json()
    assert state['payload']['expiry']=={'year':2027,'month':8,'day':None,'precision':'month','iso':'2027-08'}
    assert action(client,state,'confirm').status_code==409
    state=confirmed(client,state)
    assert state['confirmed'] and len(calls)==1
    session=next(iter(app.state.sessions.sessions.values()))
    assert session.ai.snapshot()['confirmed_scopes']==['strip']
    assert session.ai.snapshot()['associations']=={} and session.ai.snapshot()['derived']=={}
    assert 'safe_to_take' not in state['payload'] and 'expiry_status' not in state['payload']


@pytest.mark.parametrize('source,issue',[
    (transcription(('08/2027','09/2027')),'conflicting_expiry_dates'),
    (transcription(('06/07/2027',)),'ambiguous_date_order'),
    (transcription((),),'no_explicit_expiry'),
    (transcription(('08/2027',),'MFG'),'no_explicit_expiry'),
    (transcription(('08/2027',),'USE BEFORE'),'use_before_requires_clarification'),
])
def test_ambiguous_missing_conflicting_and_non_expiry_labels_stay_unknown(source,issue):
    client,_,_=setup(source);state=extract(client)
    assert state['status']=='succeeded' and state['error'] is None
    assert state['payload']['expiry'] is None and issue in state['payload']['issues']
    assert len(state['payload']['date_observations'])==len(source['date_observations'])
    assert confirmed(client,state)['payload']['expiry'] is None


def test_edit_runs_original_parser_offline_and_invalidates_current_confirmation():
    client,_,calls=setup();first=confirmed(client)
    dirty=action(client,first,'invalidate').json()
    assert not dirty['confirmed'] and not dirty['reviewed']
    assert action(client,first,'confirm').status_code==409
    changed=edits(dirty)
    changed['date_observations'][0].update(raw_date_text='06/07/2027',raw_text='EXP 06/07/2027')
    saved=save(client,dirty,changed).json()
    assert saved['payload']['expiry'] is None
    assert 'ambiguous_date_order' in saved['payload']['issues']
    assert saved['original_payload']['expiry']['iso']=='2027-08'
    assert not saved['confirmed'] and len(calls)==1
    assert action(client,saved,'confirm').json()['confirmed']


def test_forged_derived_dates_and_removed_conflicts_rejected():
    client,_,_=setup(transcription(('08/2027','09/2027')));state=extract(client)
    forged=edits(state)|{'expiry':{'year':2099,'month':1,'day':1,'precision':'day','iso':'2099-01-01'}}
    assert save(client,state,forged).status_code==422
    assert action(client,state,'confirm',acknowledged=True).status_code==422
    missing=edits(state);missing['date_observations'].pop()
    assert save(client,state,missing).status_code==422


def test_strip_and_prescription_images_replacements_and_clear_are_independent():
    client,_,_=setup()
    medicine=post(client,prescription_upload(client),'analyze').json()
    medicine=post(client,reviewed(client,medicine).json(),'confirm').json()
    strip_state=confirmed(client)
    assert strip_state['analysis_id']!=medicine['analysis_id']
    assert client.get('/api/prescriptions/'+medicine['analysis_id']).json()['confirmed']
    newer=upload(client)
    assert action(client,strip_state,'confirm').status_code==409
    assert client.get('/api/prescriptions/'+medicine['analysis_id']).json()['confirmed']
    new_strip=confirmed(client,action(client,newer,'analyze').json())
    client.delete('/api/prescriptions/current')
    assert client.get('/api/strips/'+new_strip['analysis_id']).json()['confirmed']
    assert post(client,medicine,'confirm').status_code==409
    medicine2=post(client,prescription_upload(client),'analyze').json()
    medicine2=post(client,reviewed(client,medicine2).json(),'confirm').json()
    client.delete('/api/strips/current')
    assert action(client,new_strip,'confirm').status_code==409
    assert client.get('/api/prescriptions/'+medicine2['analysis_id']).json()['confirmed']


def test_cross_session_and_stale_revision_rejected():
    client,app,_=setup();state=confirmed(client)
    other=TestClient(app,base_url='https://localhost',headers=HEADERS);other.post('/api/session')
    assert other.get('/api/strips/'+state['analysis_id']).status_code==409
    assert action(other,state,'confirm').status_code==409
    fresh=save(client,state).json()
    assert action(client,state,'confirm').status_code==409
    assert not fresh['confirmed']


@pytest.mark.parametrize('data,mime,status',[(b'corrupt','image/png',422),(b'','image/jpeg',422),
    (b'gif','image/png',422),(b'x'*(reader.MAX_IMAGE_BYTES+1),'image/png',413),(b'x','text/plain',415)],
    ids=['corrupt','empty','gif','oversized','wrong-mime'])
def test_invalid_images(data,mime,status):
    client,_,calls=setup()
    assert client.post('/api/strips',content=data,headers={'Content-Type':mime}).status_code==status
    assert calls==[]


def test_jpeg_multiframe_and_pixel_limits_are_existing_rules():
    client,_,calls=setup();assert upload(client,image('JPEG'),'image/jpeg')['status']=='not_requested'
    out=BytesIO();Image.new('RGB',(4001,2000)).save(out,format='PNG')
    assert client.post('/api/strips',content=out.getvalue(),headers={'Content-Type':'image/png'}).status_code==422
    out=BytesIO();Image.new('RGB',(3,3)).save(out,format='PNG',save_all=True,append_images=[Image.new('RGB',(3,3),'red')])
    assert client.post('/api/strips',content=out.getvalue(),headers={'Content-Type':'image/png'}).status_code==422
    assert calls==[]


def test_failure_is_distinct_from_unknown_and_retry_only_on_explicit_post():
    calls=[]
    def failure(_):
        calls.append(1);raise strip.StripNetworkError()
    client,_,_=setup(extractor=failure);state=extract(client)
    assert state['status']=='failed' and state['payload'] is None and state['error']['category']=='network_error'
    client.get('/api/strips/'+state['analysis_id']);assert len(calls)==1
    assert action(client,state,'confirm').status_code==409


def test_duplicate_and_late_strip_jobs_cannot_attach():
    entered=threading.Event();release=threading.Event()
    def slow(_):
        entered.set();assert release.wait(5);return strip.normalize_strip_response(transcription())
    client,_,calls=setup(extractor=slow);state=upload(client)
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(action,client,state,'analyze');assert entered.wait(5)
        assert action(client,state,'analyze').status_code==409
        replacement=upload(client);release.set()
        assert first.result(timeout=5).status_code==409
    assert len(calls)==1 and client.get('/api/strips/'+replacement['analysis_id']).json()['payload'] is None


def test_old_diagnostic_scope_cannot_gain_strip_calls():
    client,_,calls=setup(enabled=('medicines',))
    assert client.post('/api/strips',content=image(),headers={'Content-Type':'image/png'}).status_code==404
    assert calls==[]
