"""Real local-account factory and document conversion; provider is always mocked."""
import json
from io import BytesIO
from zipfile import ZipFile
from urllib.parse import quote
import pytest
import pymupdf
from api.prescription_documents import prepare,DocumentError,docx_text
from api.tests.test_local_real_ocr import setup_client
from api.tests.test_prescriptions import post,reviewed,RECORD

TEXT='DEMO Dolo 650 — सुबह 1 tablet, 5 दिन तक'
def docx():
    out=BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('[Content_Types].xml','<Types><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('word/document.xml',f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DEMO</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>{TEXT}</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    return out.getvalue()
def pdf(pages=1,password=None):
    with pymupdf.open() as d:
        for n in range(pages):d.new_page().insert_text((50,50),f'DEMO page {n+1} Dolo 650')
        return d.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw=password,user_pw=password) if password else d.tobytes()

@pytest.mark.parametrize('kind',['txt','docx','pdf','multipdf'])
def test_document_upload_analyze_review_local_account(tmp_path,monkeypatch,kind):
    data=TEXT.encode() if kind=='txt' else docx() if kind=='docx' else pdf(2 if kind=='multipdf' else 1)
    extension='pdf' if kind=='multipdf' else kind
    mime={'txt':'text/plain','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','pdf':'application/pdf'}[extension]
    c,sdk=setup_client(tmp_path,monkeypatch,{**RECORD,'raw_text':TEXT})
    r=c.post('/api/prescriptions',content=data,headers={'Content-Type':mime,'X-MediSaathi-Filename':quote('test.'+extension)})
    assert r.status_code==200,r.text
    assert sdk.models.generate_content.call_count==0
    assert r.json()['source_document']['kind']==mime
    result=post(c,r.json(),'analyze').json()
    assert result['status']=='succeeded' and not result['confirmed']
    assert result['records'][0]['raw_text']==TEXT and len(result['records'][0])==10
    args=sdk.models.generate_content.call_args.kwargs['contents']
    if extension in ('txt','docx'):assert TEXT in args[1]
    else:assert sum(hasattr(a,'inline_data') and a.inline_data is not None for a in args)==(2 if kind=='multipdf' else 1)
    assert sdk.models.generate_content.call_count==1
    result=reviewed(c,result).json()
    assert post(c,result,'confirm').json()['confirmed']
    assert c.get('/api/planner/prescription').status_code==200

def test_document_limits_and_invalid_contents():
    for data,mime,name in [(b'', 'text/plain','a.txt'),(b'\xff','text/plain','a.txt'),(b' \n','text/plain','a.txt'),(b'a'*262145,'text/plain','a.txt'),(b'not pdf','application/pdf','a.pdf'),(b'PK\x03\x04broken','application/vnd.openxmlformats-officedocument.wordprocessingml.document','a.docx'),(TEXT.encode(),'text/plain','a.exe')]:
        with pytest.raises(DocumentError):prepare(data,mime,name)
    for data in (pdf(4),pdf(password='synthetic')):
        with pytest.raises(DocumentError):prepare(data,'application/pdf','a.pdf')
    assert docx_text(docx())=='DEMO\n'+TEXT

def test_document_failure_never_returns_fake_records(tmp_path,monkeypatch):
    c,sdk=setup_client(tmp_path,monkeypatch,error=TimeoutError('sensitive provider message'))
    uploaded=c.post('/api/prescriptions',content=TEXT.encode(),headers={'Content-Type':'text/plain','X-MediSaathi-Filename':'a.txt'}).json()
    result=post(c,uploaded,'analyze').json()
    assert result['status']=='failed' and result['error']['category']=='extraction_timeout'
    assert not result['records'] and not result['confirmed']
    assert 'sensitive' not in json.dumps(result)
    assert sdk.models.generate_content.call_count==1

def test_docx_instructions_use_literal_source_and_session_isolation(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from api.tests.test_local_auth import HEADERS,DETAILS,PREFIX
    from medisaathi.tests.test_medication_instructions import response,instruction
    c,sdk=setup_client(tmp_path,monkeypatch)
    uploaded=c.post('/api/prescriptions',content=docx(),headers={'Content-Type':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','X-MediSaathi-Filename':'a.docx'}).json()
    sdk.models.generate_content.return_value=SimpleNamespace(text=json.dumps(response(instruction(raw_text=TEXT)),ensure_ascii=False))
    path=f'/api/prescriptions/{uploaded["analysis_id"]}/sections/instructions'
    state=c.get(path).json()
    result=c.post(path+'/analyze',json={'revision':state['revision']}).json()
    assert result['status']=='succeeded' and result['payload']['instructions'][0]['raw_text']==TEXT
    assert TEXT in sdk.models.generate_content.call_args.kwargs['contents'][1]
    assert sdk.models.generate_content.call_count==1
    other=TestClient(c.app,base_url='http://localhost',headers=HEADERS)
    assert other.post(PREFIX+'/signup',json={**DETAILS,'email':'other@example.test'}).status_code==200
    assert other.get(f'/api/prescriptions/{uploaded["analysis_id"]}').status_code in (401,409)
    assert other.get('/api/prescriptions/current').status_code==404

def test_docx_rejects_macros_dtd_and_zip_bombs():
    for filename,content in [('word/vbaProject.bin',b'macro'),('word/embeddings/a.bin',b'embedded'),('word/document.xml',b'<!DOCTYPE x [<!ENTITY z "bad">]><x>&z;</x>')]:
        original=ZipFile(BytesIO(docx()));out=BytesIO()
        with ZipFile(out,'w') as z:
            for entry in original.infolist():
                if entry.filename!=filename:z.writestr(entry,original.read(entry.filename))
            z.writestr(filename,content)
        with pytest.raises(DocumentError):docx_text(out.getvalue())
    from zipfile import ZIP_DEFLATED
    out=BytesIO()
    with ZipFile(out,'w',compression=ZIP_DEFLATED) as z:z.writestr('huge.xml',b'x'*(9*1024*1024))
    with pytest.raises(DocumentError):docx_text(out.getvalue())

def test_pdf_timeout_is_safe(monkeypatch):
    import subprocess
    from unittest.mock import MagicMock
    process=MagicMock();process.communicate.side_effect=[subprocess.TimeoutExpired('renderer',15),(b'',b'')]
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:process)
    with pytest.raises(DocumentError,match='15-second'):prepare(pdf(),'application/pdf','a.pdf')
    process.kill.assert_called_once()
