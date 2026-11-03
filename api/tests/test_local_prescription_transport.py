"""Authenticated upload/restoration transport; no provider requests."""
from api.tests.test_local_auth import local,signup,login,PREFIX
from api.tests.test_prescriptions import upload,post,reviewed


def test_rejected_offline_upload_is_json_and_preserves_current_review(local):
    c,app=local
    assert signup(c).status_code==200
    assert c.post(PREFIX+'/logout').status_code==200
    assert login(c).status_code==200
    assert c.get('/api/prescriptions/current').json()['detail']['category']=='no_current_prescription'
    from api.demo_fixture import PRESCRIPTION,STRIP
    data=post(c,upload(c,PRESCRIPTION),'analyze').json()
    assert data['status']=='succeeded'
    data=reviewed(c,data).json()
    data=post(c,data,'confirm').json()
    assert data['confirmed']
    # Readable PNG, but deliberately not the registered prescription fixture.
    rejected=c.post('/api/prescriptions',content=STRIP,headers={'Content-Type':'image/png'})
    assert rejected.status_code==422
    assert rejected.headers['content-type']=='application/json'
    assert rejected.json()['detail']['category']=='image_validation_error'
    assert 'registered demo images' in rejected.json()['detail']['message']
    restored=c.get('/api/prescriptions/current').json()
    assert restored['analysis_id']==data['analysis_id']
    assert restored['revision']==data['revision'] and restored['confirmed']
    assert c.get('/api/prescriptions/current/image',params={k:data[k] for k in ('analysis_id','revision')}).content==PRESCRIPTION


def test_invalid_image_returns_json_without_creating_analysis(local):
    c,app=local;signup(c)
    r=c.post('/api/prescriptions',content=b'not an image',headers={'Content-Type':'image/png'})
    assert r.status_code==422 and r.json()['detail']['category']=='image_validation_error'
    assert c.get('/api/prescriptions/current').status_code==404
