"""Explicit fixture simulations, script metadata and preserved schedule safeguards."""
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from api.local_auth import create_local_app
from api.evaluation.evaluate import evaluate
from api.tests.test_prescriptions import upload,post,reviewed
from api.tests.test_sections import extract,confirm
from api.tests.test_downstream import associate

BASE=Path(__file__).parents[1]/'evaluation/fixtures'
def manifest():return json.loads((BASE/'manifest.json').read_text(encoding='utf-8-sig'))

@pytest.mark.parametrize('identifier',['english_printed','hindi_printed','mixed_printed','hindi_handwriting_like'])
def test_fixture_bytes_valid_and_honestly_described(identifier):
    f=next(f for f in manifest()['fixtures'] if f['id']==identifier);data=(BASE/f['file']).read_bytes()
    from api.dependencies import reader
    assert reader._validate_image(data)=='image/png'
    assert hashlib.sha256(data).hexdigest()==f['sha256'] and f['synthetic'] and not f['patient_data']
    with Image.open(BASE/f['file']) as image:assert image.width*image.height<=reader.MAX_IMAGE_PIXELS
    if 'handwriting' in identifier:assert f['not_human_handwriting'] and f['style']=='synthetic_handwriting_like'

def test_offline_hindi_review_confirmation_does_not_enable_hindi_scheduling(tmp_path,monkeypatch):
    from api.dependencies import reader
    from api.downstream import scheduling
    app=create_local_app(tmp_path/'local.sqlite3',offline=True)
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('No provider request authorized'))
    monkeypatch.setattr(scheduling.engine,'build_schedule',lambda *a,**kw:pytest.fail('Hindi source may not bypass the schedule gate'))
    c=TestClient(app,base_url='http://localhost',headers={'Origin':'http://localhost:5177','X-MediSaathi-Action':'review'})
    c.post('/api/local-auth/signup',json={'full_name':'Language Test','email':'language@example.test','password':'fixture-password'})
    caps=c.get('/api/recognition/capabilities').json()
    assert caps['mode']=='offline_fixture' and caps['ui_language_affects_extraction'] is False and caps['accuracy_evaluated'] is False
    f=next(f for f in manifest()['fixtures'] if f['id']=='hindi_printed')
    state=post(c,upload(c,(BASE/f['file']).read_bytes()),'analyze').json()
    assert len(state['records'][0])==10
    assert state['script_observation']['script']=='devanagari'
    assert state['records'][0]['strength']=='10 mg'
    assert '१० मि.ग्रा.' in state['records'][0]['raw_text']
    assert state['numeric_previews'][0]['digit_reading']
    state=post(c,reviewed(c,state).json(),'confirm').json()
    instruction=extract(c,state,'instructions');assert instruction['script_observation']['script']=='devanagari'
    confirm(c,instruction,'instructions')
    linked=associate(c)
    # Use the existing test helper for endpoint binding; never infer Hindi slots.
    from api.tests.test_downstream import save,approve,plan
    saved=save(c,linked,{**plan(),'duration_days':5})
    rejected=approve(c,saved)
    assert rejected.status_code==422 and rejected.json()['detail']['category']=='unsafe_schedule'
    assert c.get('/api/scheduling/current').json()['result'] is None
    assert c.get('/api/prescriptions/current').json()['confirmed']

def test_evaluation_never_calls_ocr_or_counts_surrogates_as_human_handwriting():
    m=manifest();report=evaluate(m)
    assert report['groups']['printed']['available_images']==3
    assert report['groups']['handwritten']['available_images']==0
    assert report['groups']['handwritten']['character_error_rate'] is None
    assert report['groups']['synthetic_handwriting_like']['available_images']==1
    assert not report['real_ocr_accuracy_verified']
    f=m['fixtures'][0]
    supplied={'mode':'mock','predictions':{f['id']:{'medicines':f['expected_medicines']}}}
    r=evaluate(m,supplied)
    assert r['groups']['printed']['character_error_rate']==0
    assert r['simulation_is_not_ocr'] and not r['real_ocr_accuracy_verified']
