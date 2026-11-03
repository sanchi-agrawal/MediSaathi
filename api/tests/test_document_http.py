"""Loopback HTTP against the local-account factory, isolated DB, mocked SDK."""
import json,socket,threading,time
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx,uvicorn
from api.local_auth import create_local_app
from api.dependencies import reader
from api.tests.test_local_auth import HEADERS,DETAILS,PREFIX
from api.tests.test_prescriptions import RECORD,reviewed,post
from api.tests.test_prescription_documents import TEXT,docx,pdf

def test_authenticated_loopback_document_workflow(tmp_path,monkeypatch):
    sdk=MagicMock();sdk.__enter__.return_value=sdk
    sdk.models.generate_content.return_value=SimpleNamespace(text=json.dumps([{**RECORD,'raw_text':TEXT}],ensure_ascii=False))
    monkeypatch.setattr(reader.genai,'Client',MagicMock(return_value=sdk))
    monkeypatch.setattr(reader,'_configuration',lambda:('mock-only','gemini-3.1-flash-lite'))
    app=create_local_app(tmp_path/'http-accounts.sqlite3',offline=False)
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    def loopback_only(address,timeout=None,source_address=None,**kwargs):
        assert address==('127.0.0.1',port), 'External network forbidden'
        connection=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        connection.settimeout(timeout)
        if source_address:connection.bind(source_address)
        connection.connect(address)
        return connection
    monkeypatch.setattr(socket,'create_connection',loopback_only)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    worker=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);worker.start()
    try:
        deadline=time.monotonic()+8
        while not server.started and worker.is_alive() and time.monotonic()<deadline:time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS,timeout=25) as client:
            assert client.post(PREFIX+'/signup',json=DETAILS).status_code==200
            for name,mime,source in [('a.txt','text/plain',TEXT.encode()),('a.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',docx()),('a.pdf','application/pdf',pdf(2))]:
                before=sdk.models.generate_content.call_count
                uploaded=client.post('/api/prescriptions',content=source,headers={'Content-Type':mime,'X-MediSaathi-Filename':name})
                assert uploaded.status_code==200,uploaded.text
                assert sdk.models.generate_content.call_count==before
                analyzed=post(client,uploaded.json(),'analyze').json()
                assert analyzed['status']=='succeeded' and analyzed['records'][0]['raw_text']==TEXT
                confirmed=post(client,reviewed(client,analyzed).json(),'confirm').json()
                assert confirmed['confirmed']
                assert client.get('/api/prescriptions/current').json()['analysis_id']==confirmed['analysis_id']
                assert client.get('/api/planner/prescription').status_code==200
                assert sdk.models.generate_content.call_count==before+1
            invalid=client.post('/api/prescriptions',content=b'not a PDF',headers={'Content-Type':'application/pdf','X-MediSaathi-Filename':'bad.pdf'})
            assert invalid.status_code==422 and invalid.headers['content-type'].startswith('application/json')
            assert client.get('/api/prescriptions/current').json()['confirmed'] # invalid replacement preserves current review
    finally:
        server.should_exit=True;worker.join(timeout=8);listener.close()
        assert not worker.is_alive()
