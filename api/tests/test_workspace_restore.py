"""Session restoration and multilingual summaries, using fictional extractors."""
import copy
import pytest
from fastapi.testclient import TestClient
from api.main import create_app
from api.sessions import COOKIE
from api.tests.test_downstream import setup, associate, save, approve, current as scheduling_current
from api.tests.test_prescriptions import HEADERS, image_bytes, post, reviewed

def image_route(s):return '/api/prescriptions/current/image?analysis_id='+s['analysis_id']+'&revision='+s['revision']

def test_current_static_route_restores_confirmations_and_image_without_new_analysis_or_extraction():
    client,app,med,ins=setup()
    before=next(iter(app.state.sessions.sessions.values())).ai.snapshot()
    health=client.get('/api/health').json()
    assert health['storage']=='session-memory' and health['authentication']=='demo-only'
    for _ in range(3):
        r=client.get('/api/prescriptions/current');assert r.status_code==200,r.text
        s=r.json();assert s['analysis_id']==med['analysis_id'] and s['revision']==med['revision']
        assert s['confirmed'] and s['sections']['instructions']['confirmed']
        image=client.get(image_route(s))
        assert image.status_code==200 and image.content==image_bytes()
        assert image.headers['content-type']=='image/png' and image.headers['cache-control']=='no-store'
        assert scheduling_current(client)['ready']
    after=next(iter(app.state.sessions.sessions.values())).ai.snapshot()
    assert before==after

def test_navigation_reads_preserve_approved_schedule_and_source_revisions():
    client,_,med,_=setup();approved=approve(client,save(client,associate(client))).json()
    for _ in range(3):
        restored=client.get('/api/prescriptions/current').json()
        assert restored['analysis_id']==med['analysis_id'] and restored['confirmed']
        assert scheduling_current(client)['result']==approved['result']

def test_current_and_image_are_isolated_between_sessions_and_cookie_attributes_preserved():
    client,app,med,_=setup()
    stranger=TestClient(app,base_url='https://localhost',headers=HEADERS)
    assert stranger.get('/api/prescriptions/current').status_code==401
    response=stranger.post('/api/session')
    cookie=response.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
    assert stranger.get('/api/prescriptions/current').status_code==404
    assert stranger.get('/api/prescriptions/'+med['analysis_id']).status_code==409
    assert stranger.get(image_route(med)).status_code==409
    assert client.get(image_route(med)).status_code==200

def test_current_image_rejects_stale_id_or_revision_and_clear_revokes_restoration():
    client,_,med,_=setup()
    assert client.get(image_route({**med,'analysis_id':'stale'})).status_code==409
    assert client.get(image_route({**med,'revision':'stale'})).status_code==409
    assert client.delete('/api/prescriptions/current').status_code==200
    assert client.get('/api/prescriptions/current').status_code==404
    assert client.get(image_route(med)).status_code==409

def test_expiry_or_server_restart_does_not_falsely_restore_anonymous_history():
    client,app,med,_=setup()
    token=client.cookies.get(COOKIE)
    app.state.sessions.get(token).created-=1801
    assert client.get('/api/prescriptions/current').status_code==401
    restarted=TestClient(create_app(),base_url='https://localhost',headers=HEADERS)
    restarted.cookies.set(COOKIE,token)
    assert restarted.get('/api/prescriptions/current').status_code==401

def test_dirty_source_restores_unconfirmed_and_old_schedule_is_inaccessible():
    client,_,med,_=setup();approve(client,save(client,associate(client)))
    post(client,med,'invalidate')
    s=client.get('/api/prescriptions/current').json()
    assert not s['confirmed'] and not s['reviewed']
    assert scheduling_current(client)['result'] is None
    assert post(client,s,'explanation',language='hi').status_code==409

def test_real_controlled_language_content_changes_and_raw_records_do_not():
    client,_,med,_=setup();responses={}
    for language in ('en','hi','hinglish'):
        response=post(client,med,'explanation',language=language)
        assert response.status_code==200,response.text
        body=response.json();responses[language]=body
        assert body['payload']['language']==language and body['summary']['language']==language
        assert body['payload']['medicines'][0]['record']==med['records'][0]
        ins=body['summary']['sections']['instructions']
        assert ins['confirmed'] and ins['records'][0]['original_text']==med['records'][0]['raw_text']
        values={f['field']:f['value'] for f in ins['records'][0]['fields']}
        assert values['dose_quantity_raw']=='1' and values['dose_unit_raw']=='tablet' and values['duration_raw']=='3 days'
        assert values['route_raw'] is None
        assert not body['summary']['sections']['investigations']['confirmed']
        assert body['summary']['sections']['investigations']['records']==[]
    assert len({r['payload']['notice'] for r in responses.values()})==3
    assert len({r['summary']['title'] for r in responses.values()})==3
    assert 'दवा' in responses['hi']['payload']['medicines'][0]['fields'][1]['text']
    assert 'Dawa' in responses['hinglish']['payload']['medicines'][0]['fields'][1]['text']
    assert client.get('/api/prescriptions/current').json()['records']==med['records']

def test_unconfirmed_instructions_never_enter_summary_even_if_extraction_succeeded():
    client,_,med,ins=setup()
    client.post('/api/prescriptions/'+med['analysis_id']+'/sections/instructions/invalidate',json={'revision':ins['revision']})
    body=post(client,med,'explanation',language='hi').json()
    assert not body['summary']['sections']['instructions']['confirmed']
    assert body['summary']['sections']['instructions']['records']==[]

@pytest.mark.parametrize('language',['en','hi','hinglish'])
def test_unknown_values_and_ten_field_contract_survive_explanation(language):
    client,_,med,_=setup()
    fields=post(client,med,'explanation',language=language).json()['payload']['medicines'][0]['fields']
    assert {f['field'] for f in fields}==set(med['records'][0])
    salt=next(f for f in fields if f['field']=='salt')
    assert salt['value'] is None and salt['is_unknown'] is True

def test_confirmed_investigations_preserve_raw_names_unknown_variant_and_warnings():
    from api.tests.test_sections import setup as section_setup, extract, confirm
    from api.tests.test_prescriptions import upload
    client,_,_=section_setup()
    med=post(client,upload(client),'analyze').json()
    med=post(client,reviewed(client,med).json(),'confirm').json()
    confirm(client,extract(client,med,'investigations'),'investigations')
    body=post(client,med,'explanation',language='hi').json()
    inv=body['summary']['sections']['investigations']
    assert inv['confirmed']
    values={field['field']:field['value'] for field in inv['records'][0]['fields']}
    assert values['test_name_raw']=='Fictional test' and values['variant_raw'] is None
    assert inv['records'][0]['uncertainty_reasons']==['variant_unclear']
