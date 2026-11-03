"""Real workbook, real local-auth app, no Gemini or pharmacy network traffic."""
import copy
import importlib
import json
import socket
import threading
import time
import pytest
import httpx
import uvicorn
from fastapi.testclient import TestClient
from pricing_dataset import market
from api.tests.test_local_auth import HEADERS,DETAILS
from api.local_auth import PREFIX
LOCAL_CONNECT=socket.create_connection

def test_real_workbook_coverage_search_and_raw_integrity():
    data=market.load();s=market.summary(data)
    assert s['medicines']==30 and s['observations']==90 and s['rejected']==0 and s['provisional']==90
    assert sorted(s['platforms'].values())==[30,30,30]
    assert s['cities']=={'Gurgaon':9,'Delhi':81} and s['availability']=={'in_stock':89,'out_of_stock':1}
    for query in ('Dolo','DOLO 650','Paracetamol','Cetirizine','Pantoprazole','tablet'):
        assert market.search(data,query),query
    assert not market.search(data,'unknown medicine 123')
    assert all(o['verification_status']=='provisional' and o['pack_size'] is None and o['observed_at'] is None for o in data['observations'])
    assert sum('excel_numeric_precision_normalized' in o['warnings'] for o in data['observations'])==2

@pytest.mark.parametrize('change',[{'med_id':'missing'},{'selling_price_inr':'-1'},{'selling_price_inr':'NaN'},{'selling_price_inr':'1.234'},{'url':'https://evil.example/test'},{'url':'https://www.1mg.com@evil.example/test'}])
def test_invalid_rows_fail_closed(change):
    row={**market.load()['observations'][0]['raw'],**change}
    with pytest.raises(ValueError):market.observation(row,{'ms_med_0001'})

def test_duplicate_and_tampered_export_rejected(tmp_path):
    data=copy.deepcopy(market.load());data['observations'].append(data['observations'][0]);path=tmp_path/'bad.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):market.load(path)
    data=copy.deepcopy(market.load());data['observations'][0]['verification_status']='verified';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):market.load(path)

@pytest.fixture
def local_entrypoint(tmp_path,monkeypatch):
    monkeypatch.setenv('MEDISAATHI_LOCAL_DB',str(tmp_path/'test-accounts.sqlite3'))
    monkeypatch.setenv('MEDISAATHI_LOCAL_OFFLINE','1');monkeypatch.setenv('MEDISAATHI_LOCAL_HTTPS','0')
    from api.dependencies import reader
    monkeypatch.setattr(reader.genai,'Client',lambda *a,**kw:pytest.fail('No Gemini requests'))
    from api import local_server
    app=importlib.reload(local_server).app
    yield app

def workflow(c):
    assert c.get('/api/pricing/listings/catalogue').status_code==401
    assert c.post(PREFIX+'/signup',json=DETAILS).status_code==200
    assert c.post('/api/session').status_code==200
    r=c.get('/api/pricing/listings/catalogue');assert r.status_code==200,r.text
    data=r.json();assert len(data['items'])==30
    results=c.get('/api/pricing/listings/catalogue',params={'q':'Dolo 650'}).json()['items']
    assert len(results)==1 and results[0]['composition']=='Paracetamol'
    item=results[0];r=c.post('/api/pricing/listings/lookup',json={'item_id':item['item_id']});assert r.status_code==200,r.text
    found=r.json();assert len(found['observations'])==3 and found['comparisons_enabled'] is False
    assert {o['platform'] for o in found['observations']}=={'tata_1mg','apollo_247','pharmeasy'}
    assert all(o['item_id']==item['item_id'] and o['verification_status']=='provisional' for o in found['observations'])
    assert c.post('/api/pricing/listings/lookup',json={'item_id':'missing'}).json()['state']=='no_match'
    r=c.post('/api/pricing/listings/lookup',json={'item_id':item['item_id'],'verified':True});assert r.status_code==422 and r.headers['content-type'].startswith('application/json')
    # Catalogue/prices are public reference data, not private prescription state.
    assert 'analysis_id' not in found and 'records' not in found
    for m in data['items']:
        value=c.post('/api/pricing/listings/lookup',json={'item_id':m['item_id']}).json()
        assert value['state']=='listed' and len(value['observations'])==3

def test_actual_local_account_entrypoint_and_two_user_isolation(local_entrypoint):
    with TestClient(local_entrypoint,base_url='http://localhost',headers=HEADERS) as c:workflow(c)
    with TestClient(local_entrypoint,base_url='http://localhost',headers=HEADERS) as other:
        assert other.post(PREFIX+'/signup',json={**DETAILS,'email':'second@example.test','full_name':'Second User'}).status_code==200
        assert other.post('/api/session').status_code==200
        assert other.get('/api/pricing/listings/catalogue').status_code==200
        assert other.get('/api/prescriptions/current').json().get('analysis_id') is None
        assert other.get(PREFIX+'/me').json()['user']['full_name']=='Second User'

def test_authenticated_real_http_entrypoint(local_entrypoint,monkeypatch):
    connect=LOCAL_CONNECT;sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def only_local(address,*args,**kwargs):
        assert address==('127.0.0.1',port),'No external requests allowed'
        return connect(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',only_local)
    server=uvicorn.Server(uvicorn.Config(local_entrypoint,log_level='critical',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS) as c:workflow(c)
    finally:server.should_exit=True;thread.join(5);sock.close()
