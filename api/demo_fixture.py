"""Explicit offline-only fictional demo. All four provider paths are blocked.

python -m api.demo_fixture --write-fixtures
uvicorn api.demo_fixture:app --host 127.0.0.1 --port 8002 --no-access-log
"""
import copy,hashlib,sys
from io import BytesIO
from pathlib import Path
from http.cookies import SimpleCookie
from PIL import Image,ImageDraw
from .dependencies import AIIntegration,reader
from .main import create_app
from .downstream.scheduling import schedule_handoff
import strip
from .offline_languages import lookup as language_fixture,extract as language_extract

def forbidden(*a,**kw):raise RuntimeError('Provider access disabled in offline fictional demo')
reader.genai.Client=forbidden

def picture(lines):
    image=Image.new('RGB',(1100,500),'white');draw=ImageDraw.Draw(image)
    for i,line in enumerate(lines):draw.text((35,35+i*60),line,fill='black',font_size=25)
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()
PRESCRIPTION=picture(['FICTIONAL DEMO ONLY - NOT A PRESCRIPTION - NO PATIENT DATA',
    'Dolo 650 (Paracetamol 650 mg tablet)',
    'Take 1 tablet BD morning and night for 3 days.',
    'Investigation: CBC test. Specimen and variant not specified.',
    'Static mocked extraction. Do not use as medical advice.'])
STRIP=picture(['FICTIONAL DEMO STRIP ONLY - NOT A REAL PRODUCT','Demo product - Batch DEMO-001','EXP 08/2027'])
MED=dict(raw_text='FICTIONAL: Dolo 650 take 1 tablet BD morning and night for 3 days',name='Dolo 650',
    salt='Paracetamol',strength='650 mg',form='tablet',frequency_pattern='BD',duration_days=3,
    timing='morning and night',confidence=None,needs_review=False)
def check(data,expected=PRESCRIPTION):
    if hashlib.sha256(data).digest()!=hashlib.sha256(expected).digest():
        if expected is PRESCRIPTION and language_fixture(data) is not None:return
        raise reader.ImageInputError('Use the registered fictional fixture for the offline demo.')
def medicine(data):
    check(data)
    if language_fixture(data):return language_extract(data,'medicines')
    return [copy.deepcopy(MED)]
def instructions(data):
    check(data)
    if language_fixture(data):return language_extract(data,'instructions')
    return dict(schema_version='medication-instructions-v1',source_image_sha256=hashlib.sha256(data).hexdigest(),
        instructions=[dict(instruction_id='instruction_001',medicine_name_raw='Dolo 650',raw_text=MED['raw_text'],
            dose_quantity_raw='1',dose_unit_raw='tablet',frequency_raw='BD',route_raw=None,timing_raw='morning and night',
            duration_raw='3 days',uncertainty_reasons=[],needs_review=False,confirmation_required=True)],issues=[],confirmation_required=True)
def investigations(data):
    check(data)
    if language_fixture(data):return language_extract(data,'investigations')
    return dict(schema_version='prescribed-investigations-v1',source_image_sha256=hashlib.sha256(data).hexdigest(),
        investigations=[dict(investigation_id='investigation_001',raw_text='FICTIONAL: CBC test ordered',test_name_raw='CBC test',
            specimen_raw=None,variant_raw=None,timing_raw=None,order_context_raw='ordered',
            uncertainty_reasons=['specimen_unclear','variant_unclear'],needs_review=True,confirmation_required=True)],issues=[],confirmation_required=True)
def expiry(data):
    check(data,STRIP)
    return strip.normalize_strip_response(dict(medicine_name='Fictional strip',batch_number='DEMO-001',product_association='single_product',
        date_observations=[dict(raw_label='EXP',raw_date_text='08/2027',raw_text='EXP 08/2027',association='same_product',confidence=None,uncertain=False)],
        quality_issues=[],confidence=None,uncertain=False))
def factory():return AIIntegration(extractors={'medicines':medicine,'instructions':instructions,'investigations':investigations,'strip':expiry},downstream={'schedule':schedule_handoff})
inner=create_app(factory=factory,upload_validator=check,origins=('http://localhost:5175','http://127.0.0.1:5175'),accounts=False,recognition_mode='offline_fixture')
@inner.get('/api/demo-info')
def info():return {'mode':'offline-fictional','gemini_enabled':False,'notifications_enabled':False}

class FixtureCookies:
    """Ports share browser cookie scope. Keep normal demo sessions untouched."""
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=[]
        for key,value in scope['headers']:
            if key.lower()==b'cookie':
                jar=SimpleCookie();jar.load(value.decode('latin1'))
                if 'medisaathi_team16c' in jar:headers.append((b'cookie',('medisaathi_demo='+jar['medisaathi_team16c'].value).encode('latin1')))
            else:headers.append((key,value))
        async def reply(message):
            if message['type']=='http.response.start':
                message={**message,'headers':[(k,v.replace(b'medisaathi_demo=',b'medisaathi_team16c=',1) if k.lower()==b'set-cookie' else v) for k,v in message['headers']]}
            await send(message)
        await self.app({**scope,'headers':headers},receive,reply)
app=FixtureCookies(inner)
if __name__=='__main__' and '--write-fixtures' in sys.argv:
    destination=Path(__file__).parent/'.venv/demo16c';destination.mkdir(parents=True,exist_ok=True)
    (destination/'fictional-prescription.png').write_bytes(PRESCRIPTION)
    (destination/'fictional-strip.png').write_bytes(STRIP)
    print('Fictional fixtures written under api/.venv/demo16c. No external calls.')
