"""Temporary DEMO access, not email/password authentication. No provider calls."""
import time
from http.cookies import SimpleCookie
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .demo_fixture import factory,check
from .main import create_app
from .sessions import COOKIE as WORKSPACE_COOKIE,TTL_SECONDS

COOKIE='medisaathi_hackathon'
inner=create_app(factory=factory,upload_validator=check,accounts=False,recognition_mode='offline_fixture',
    origins=('http://localhost:5177','http://127.0.0.1:5177'))
store=inner.state.sessions

class DemoDetails(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    # Used only for format validation; never saved or treated as an identity.
    email:str=Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$',max_length=254)

class DemoSignup(DemoDetails):
    display_name: str = Field(min_length=2,max_length=100)

    @field_validator('display_name')
    @classmethod
    def validate_name(cls,value):
        value=' '.join(value.split())
        if len(value)<2 or not any(c.isalpha() for c in value) or any(not c.isprintable() for c in value):
            raise ValueError('Enter a display name.')
        return value

def state(session):
    remaining=max(0,int(TTL_SECONDS-(time.monotonic()-session.created))) if session else 0
    return {'mode':'demo-access','active':session is not None,'expires_in':remaining,
            'email_verified':False,'account_authentication':False,
            'display_name':session.display_name if session else None}

def discard(handle):
    session=store.get(handle)
    if session:
        with session.lock:
            session.prescription_active=False;session.strip_active=False;session.invalidate()
            with store.lock:store.sessions.pop(handle,None)

@inner.get('/api/demo-access/status')
def status(request:Request):return state(store.get(request.cookies.get(COOKIE)))

@inner.post('/api/demo-access/login')
def login(body:DemoDetails,request:Request):
    return start_session(request)

@inner.post('/api/demo-access/signup')
def signup(body:DemoSignup,request:Request):
    return start_session(request,body.display_name)

def start_session(request,display_name=None):
    discard(request.cookies.get(COOKIE))
    created=store.create()
    if created is None:
        return JSONResponse({'detail':{'category':'capacity','message':'Demo capacity reached. Try again later.'}},503)
    handle,session=created
    session.display_name=display_name
    response=JSONResponse(state(session))
    response.set_cookie(COOKIE,handle,max_age=TTL_SECONDS,secure=True,httponly=True,samesite='strict',path='/api')
    return response

@inner.post('/api/demo-access/logout')
def logout(request:Request):
    discard(request.cookies.get(COOKIE))
    response=JSONResponse({'signed_out':True,'mode':'demo-access'})
    response.delete_cookie(COOKIE,path='/api',secure=True,httponly=True,samesite='strict')
    return response

@inner.get('/api/demo-info')
def info():return {'mode':'hackathon-demo-access','gemini_enabled':False,'notifications_enabled':False,'account_authentication':False}

class DemoBoundary:
    """Separate cookie namespace; only a live temporary session may use workflows."""
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        path=scope['path'];jar=SimpleCookie()
        for key,value in scope['headers']:
            if key.lower()==b'cookie':jar.load(value.decode('latin1'))
        handle=jar[COOKIE].value if COOKIE in jar else None
        session=store.get(handle)
        public=path.startswith('/api/demo-access/') or path in ('/api/health','/api/demo-info')
        if path.startswith('/api/account/') or path.startswith('/api/auth/'):
            return await JSONResponse({'detail':{'category':'demo_only','message':'Account authentication and saved medical history are unavailable in demo access.'}},403,headers={'Cache-Control':'no-store'})(scope,receive,send)
        if path.startswith('/api/') and not public and scope['method']!='OPTIONS' and session is None:
            return await JSONResponse({'detail':{'category':'demo_session_expired','message':'Start a new temporary demo session.'}},401,headers={'Cache-Control':'no-store'})(scope,receive,send)
        headers=[(k,v) for k,v in scope['headers'] if k.lower()!=b'cookie']
        # Neither account cookies nor other demos can supply workflow authority.
        cookies=[]
        if handle:cookies.append(COOKIE+'='+handle)
        if session:cookies.append(WORKSPACE_COOKIE+'='+handle)
        if cookies:headers.append((b'cookie','; '.join(cookies).encode('latin1')))
        scope={**scope,'headers':headers}
        if path in ('/api/demo-access/login','/api/demo-access/signup') and scope['method']=='POST':
            chunks=[];total=0
            while True:
                message=await receive()
                if message['type']!='http.request':return
                total+=len(message.get('body',b''))
                if total>2048:return await JSONResponse({'detail':{'category':'invalid_input','message':'Demo form too large.'}},413)(scope,receive,send)
                chunks.append(message.get('body',b''))
                if not message.get('more_body',False):break
            payload=b''.join(chunks);used=False
            original=receive
            async def bounded():
                nonlocal used
                if not used:used=True;return {'type':'http.request','body':payload,'more_body':False}
                return await original()
            receive=bounded
        async def reply(message):
            if message['type']=='http.response.start':
                message={**message,'headers':[(k,v) for k,v in message['headers'] if k.lower()!=b'set-cookie' or v.startswith(COOKIE.encode()+b'=')]}
            await send(message)
        await self.app(scope,receive,reply)

app=DemoBoundary(inner)
