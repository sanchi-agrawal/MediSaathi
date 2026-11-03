"""Real provider flows, protected encrypted history, and fresh unconfirmed resume."""
import base64,copy,json,hashlib
from datetime import datetime,timezone
from http.cookies import SimpleCookie
from typing import Literal
from uuid import UUID
from fastapi import Request,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from starlette.concurrency import run_in_threadpool
from .provider import reject
from .service import AccountServices,COOKIE,MAX_AGE,identity
from ..sessions import COOKIE as DEMO_COOKIE
from ..section_routes import metadata
from ..dependencies import reader,IntegrationError

class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class Email(Strict):email:str=Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$',max_length=254)
class Login(Email):password:str=Field(min_length=1,max_length=128)
class Signup(Login):
    password:str=Field(min_length=12,max_length=128)
    name:str=Field(min_length=2,max_length=100)
class Verify(Email):code:str=Field(pattern=r'^\d{6,10}$')
class Reset(Verify):password:str=Field(min_length=12,max_length=128)
class Save(Strict):
    analysis_id:str=Field(min_length=1,max_length=128)
    revision:str=Field(min_length=1,max_length=128)
    section_revisions:dict[str,str]
    scheduling_revision:str=Field(min_length=1,max_length=128)
    consent:Literal[True]
    save_image:bool=False
class Resume(Strict):
    version:str=Field(min_length=1,max_length=128)
    acknowledge_reconfirmation:Literal[True]
    image_base64:str|None=Field(default=None,max_length=14*1024*1024)

class AccountBoundary:
    def __init__(self,app,service,store):self.app=app;self.service=service;self.store=store
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        path=scope['path'];headers=list(scope['headers']);jar=SimpleCookie()
        for key,value in headers:
            if key.lower()==b'cookie':jar.load(value.decode('latin1'))
        handle=jar[COOKIE].value if COOKIE in jar else None
        if path.startswith('/api/') and not path.startswith(('/api/auth/','/api/account/')) and path not in ('/api/health','/api/demo-info') and scope['method']!='OPTIONS' and (self.service or handle):
            try:
                if not self.service:reject(503,'auth_unavailable')
                account=await run_in_threadpool(self.service.authenticate,handle)
                await run_in_threadpool(self.service.workspace,account,self.store)
                # Ignore all anonymous workspace authority in account mode.
                jar[DEMO_COOKIE]=account.workspace
                headers=[(k,v) for k,v in headers if k.lower()!=b'cookie']
                headers.append((b'cookie',jar.output(header='',sep=';').strip().encode('latin1')))
                scope={**scope,'headers':headers}
            except HTTPException as e:
                return await JSONResponse({'detail':e.detail},e.status_code,headers={'Cache-Control':'no-store'})(scope,receive,send)
        if path.startswith(('/api/auth/','/api/account/')) and scope['method'] in ('POST','PUT'):
            limit=16*1024 if path.startswith('/api/auth/') else 16*1024*1024
            chunks=[];total=0
            while True:
                message=await receive()
                if message['type']!='http.request':return
                total+=len(message.get('body',b''))
                if total>limit:
                    return await JSONResponse({'detail':{'category':'request_too_large','message':'Request is too large.'}},413)(scope,receive,send)
                chunks.append(message.get('body',b''))
                if not message.get('more_body',False):break
            body=b''.join(chunks);used=False
            async def replay():
                nonlocal used
                if not used:used=True;return {'type':'http.request','body':body,'more_body':False}
                return await receive()
            return await self.app(scope,replay,send)
        return await self.app(scope,receive,send)

def register_accounts(app,store,enabled,services=None):
    service=AccountServices.from_env() if services is None else None if services is False else services
    app.state.accounts=service
    app.add_middleware(AccountBoundary,service=service,store=store)
    def configured():
        if service is None:reject(503,'auth_unavailable')
        return service
    def user(request):return configured().authenticate(request.cookies.get(COOKIE))
    def limited(request,email):configured().limited(request.client.host if request.client else 'unknown',email)
    def repository():
        if not configured().repository:reject(503,'storage_unavailable')
        return service.repository
    def workspace(record):return configured().workspace(record,store)
    def live(record):
        if record.revoked:reject(401,'session_expired')
    def bindings(session):
        snap=session.ai.snapshot();root=snap['prescription']
        if not session.prescription_active or root is None:reject(404,'not_found')
        return {'analysis_id':root['analysis_id'],'revision':session.revision,
            'section_revisions':{s:metadata(session,root,s)['revision'] for s in ('instructions','investigations') if s in enabled},
            'scheduling_revision':session.scheduling_revision}

    @app.get('/api/auth/status')
    def status():return {'configured':service is not None,'storage_configured':bool(service and service.repository),'provider':'supabase' if service else None,'demo_only':service is None}
    @app.get('/api/auth/me')
    def me(request:Request):return {'user':user(request).user}
    @app.post('/api/auth/signup')
    def signup(body:Signup,request:Request):
        limited(request,body.email)
        try:service.provider.sign_up(body.email,body.password,body.name)
        except HTTPException as e:
            if e.status_code!=401:raise
        return {'next':'verify_email','message':'If registration is eligible, check your email for a verification code.'}
    @app.post('/api/auth/login')
    def login(body:Login,request:Request):
        limited(request,body.email)
        service.revoke(request.cookies.get(COOKIE),store)
        handle,principal=service.establish(service.provider.sign_in(body.email,body.password))
        response=JSONResponse({'user':principal})
        response.set_cookie(COOKIE,handle,max_age=MAX_AGE,secure=True,httponly=True,samesite='strict',path='/api')
        return response
    @app.post('/api/auth/logout')
    def logout(request:Request):
        if service:service.revoke(request.cookies.get(COOKIE),store)
        response=JSONResponse({'signed_out':True})
        for name in (COOKIE,DEMO_COOKIE):response.delete_cookie(name,path='/api',secure=True,httponly=True,samesite='strict')
        return response
    @app.post('/api/auth/verify')
    def verify(body:Verify,request:Request):
        limited(request,body.email)
        try:
            tokens=service.provider.verify(body.email,body.code,'signup')
            if tokens.get('access_token'):service.provider.logout(tokens['access_token'])
        except HTTPException as e:
            if e.status_code==401:reject(401,'verification_failed')
            raise
        return {'verified':True,'next':'login'}
    @app.post('/api/auth/forgot-password')
    def forgot(body:Email,request:Request):
        limited(request,body.email)
        try:service.provider.recover(body.email)
        except HTTPException as e:
            if e.status_code!=401:raise
        return {'message':'If the account is eligible, a recovery code has been sent.'}
    @app.post('/api/auth/reset-password')
    def reset(body:Reset,request:Request):
        limited(request,body.email)
        tokens=service.provider.verify(body.email,body.code,'recovery')
        access=tokens.get('access_token')
        if not access:reject(401,'verification_failed')
        principal=identity(service.provider.user(access))
        service.provider.password(access,body.password)
        # Revoke every local BFF handle for this provider user after a reset.
        principal_id=principal['id']
        if principal_id:
            with service.lock:handles=[r for r in service.sessions.values() if r.user['id']==principal_id]
            for r in handles:
                with r.lock:
                    r.revoked=True
                    if r.workspace:
                        with store.lock:store.sessions.pop(r.workspace,None)
        try:service.provider.logout(access,scope='global')
        except HTTPException:pass # local handles already revoked; password change succeeded
        return {'reset':True,'next':'login'}
    @app.get('/api/account/workspace')
    def current(request:Request):
        record=user(request)
        with record.lock:
            live(record);session=workspace(record)
            with session.lock:return bindings(session)
    @app.get('/api/account/prescriptions')
    def history(request:Request):
        record=user(request)
        with record.lock:live(record);return {'records':repository().list(record)}
    @app.post('/api/account/prescriptions')
    def save(body:Save,request:Request):
        record=user(request)
        with record.lock:
            live(record);session=workspace(record)
            with session.lock:
                expected=bindings(session)
                if any(getattr(body,k)!=v for k,v in expected.items()):reject(409,'stale_result')
                if not session.reviewed:reject(409,'review_required')
                snap=session.ai.snapshot()
                payload={'schema_version':'account-archive-v1','owner_id':record.user['id'],'captured_at':datetime.now(timezone.utc).isoformat(),
                    'binding':expected,'prescription':snap['prescription'],'confirmed_scopes':snap['confirmed_scopes'],
                    'medicine_reviewed':session.reviewed,'medicine_confirmed_revision':session.confirmed_revision,
                    'section_states':session.section_states,'associations':snap['associations'],'scheduling_state':session.scheduling_state,
                    'matching_state':session.matching_state,'image_base64':base64.b64encode(session.prescription_image).decode() if body.save_image and session.prescription_image else None}
                return repository().save(record,payload)
    @app.get('/api/account/prescriptions/{archive_id}')
    def view(archive_id:str,request:Request):
        record=user(request)
        with record.lock:
            live(record);meta,payload=repository().get(record,archive_id)
            image=payload.pop('image_base64',None)
            return {**meta,'payload':payload,'image_saved':image is not None,'approval_authority_restored':False}
    @app.delete('/api/account/prescriptions/{archive_id}')
    def delete(archive_id:str,request:Request):
        record=user(request)
        with record.lock:live(record);return repository().delete(record,archive_id)
    @app.post('/api/account/prescriptions/{archive_id}/continue')
    def resume(archive_id:str,body:Resume,request:Request):
        record=user(request)
        with record.lock:
            live(record);meta,payload=repository().get(record,archive_id)
            if meta['version']!=body.version:reject(409,'stale_result')
            encoded=body.image_base64 or payload.get('image_base64')
            if not encoded:reject(422,'original_image_required')
            try:
                image=base64.b64decode(encoded,validate=True)
                reader._validate_image(image)
                if hashlib.sha256(image).hexdigest()!=payload['prescription']['source_image_sha256']:raise ValueError
            except (ValueError,reader.ImageInputError):reject(422,'image_validation_error')
            def replay(ai):
                root=ai.start_prescription(image)
                for scope,section in payload['prescription']['sections'].items():
                    if scope not in enabled or scope=='strip' or section['status']!='succeeded':continue
                    job=ai.begin_section(scope,analysis_id=root['analysis_id'])
                    restored=ai.complete_section(job,payload=section['payload'])
                    if restored['status']!='succeeded':reject(422,'invalid_archive')
                    if section['reviewed'] is not None:ai.review(scope,section['reviewed'])
                return root
            try:
                replay(store.factory()) # validate before altering the live workspace
                session=workspace(record)
                with session.lock:
                    session.invalidate();session.section_states={};root=replay(session.ai)
                    session.prescription_active=True;session.prescription_image=image
                    session.prescription_mime='image/png' if image.startswith(b'\x89PNG') else 'image/jpeg'
                    session.reviewed=payload.get('medicine_reviewed',False)
                    for scope in ('instructions','investigations'):
                        if scope in enabled:metadata(session,root,scope)['reviewed']=bool(payload.get('section_states',{}).get(scope,{}).get('reviewed'))
                    session.performance={};session.explanation=None
                    return {**bindings(session),'reconfirmation_required':True}
            except (IntegrationError,KeyError,TypeError,ValueError):reject(422,'invalid_archive')
