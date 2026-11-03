"""Local SQLite identity and revocable opaque sessions; no medical persistence."""
import hashlib
import os
import secrets
import sqlite3
import time
from pathlib import Path
from threading import RLock
from uuid import uuid4
from http.cookies import SimpleCookie
from contextlib import contextmanager
from typing import Literal
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .main import create_app
from .sessions import COOKIE as WORKSPACE_COOKIE

COOKIE='medisaathi_local_auth'
PREFIX='/api/local-auth'
TTL=8*60*60
DEFAULT_DB=Path(__file__).parent/'runtime'/'local-accounts.sqlite3'
ORIGINS=('http://localhost:5177','http://127.0.0.1:5177','https://localhost:5177','https://127.0.0.1:5177')

def configured_origins(preview=False):
    setting=os.getenv('MEDISAATHI_ORIGINS','')
    if not setting:
        if preview:raise ValueError('Set MEDISAATHI_ORIGINS to the exact HTTPS frontend origin.')
        return ORIGINS
    origins=tuple(value.strip().rstrip('/') for value in setting.split(','))
    if not origins or any(not value or value=='*' for value in origins):raise ValueError('Explicit frontend origins are required.')
    for value in origins:
        parsed=urlsplit(value)
        if (parsed.scheme not in ('https',) if preview else parsed.scheme not in ('http','https')) or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('Use exact frontend origins without paths or credentials.')
    return origins

def reject(code,category,message):
    raise HTTPException(code,detail={'category':category,'message':message})

class Login(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    email:str=Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$',max_length=254)
    password:str=Field(min_length=1,max_length=128,repr=False)

class Signup(Login):
    password:str=Field(min_length=6,max_length=128,repr=False)
    full_name:str=Field(min_length=2,max_length=100)

    @field_validator('full_name')
    @classmethod
    def name(cls,value):
        value=' '.join(value.split())
        if len(value)<2 or not any(c.isalpha() for c in value) or not value.isprintable():
            raise ValueError('A valid full name is required.')
        return value

def digest(token):return hashlib.sha256(token.encode()).hexdigest()

class ProfileUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    full_name:str=Field(min_length=2,max_length=100)
    @field_validator('full_name')
    @classmethod
    def name(cls,value):return Signup.name(value)

class CurrentPassword(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    current_password:str=Field(min_length=1,max_length=128,repr=False)

class PasswordChange(CurrentPassword):
    new_password:str=Field(min_length=6,max_length=128,repr=False)

class Consent(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    confirm:Literal[True]
    @field_validator('confirm',mode='before')
    @classmethod
    def consent(cls,value):
        if value is not True:raise ValueError('Explicit confirmation required.')
        return value

class DeleteAccount(CurrentPassword,Consent):pass

class LocalAccounts:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.hasher=PasswordHasher()
        self.dummy=self.hasher.hash(secrets.token_urlsafe(32))
        self.lock=RLock();self.workspaces={}
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
            CREATE TABLE IF NOT EXISTS auth_limits (
                bucket TEXT PRIMARY KEY, started INTEGER NOT NULL, count INTEGER NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()

    def throttle(self,ip):
        # Persistent bounded window. Proxy headers are deliberately not trusted.
        now=int(time.time());key=digest(ip)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_limits WHERE started < ?',(now-900,))
            row=db.execute('SELECT count FROM auth_limits WHERE bucket=?',(key,)).fetchone()
            if row and row['count']>=30:reject(429,'rate_limited','Too many attempts. Try again later.')
            db.execute('INSERT INTO auth_limits VALUES (?,?,1) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(key,now))

    def signup(self,body):
        hashed=self.hasher.hash(body.password)
        try:
            with self.connect() as db:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?)',(str(uuid4()),body.full_name,body.email.casefold(),hashed,int(time.time())))
        except sqlite3.IntegrityError:
            reject(409,'email_exists','An account with this email already exists.')
        return self.login(body)

    def login(self,body):
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM users WHERE email=?',(body.email.casefold(),)).fetchone()
            try:self.hasher.verify(row['password_hash'] if row else self.dummy,body.password)
            except (VerificationError,InvalidHashError):reject(401,'invalid_credentials','Email or password is incorrect.')
            if row is None:reject(401,'invalid_credentials','Email or password is incorrect.')
            if self.hasher.check_needs_rehash(row['password_hash']):
                db.execute('UPDATE users SET password_hash=? WHERE id=?',(self.hasher.hash(body.password),row['id']))
            token=secrets.token_urlsafe(32);now=int(time.time())
            db.execute('DELETE FROM sessions WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(digest(token),row['id'],now,now+TTL))
        return token

    def identity(self,token):
        if not token or len(token)>128:return None
        with self.connect() as db:
            row=db.execute('''SELECT u.id,u.full_name,u.email,u.created_at,s.expires_at FROM sessions s
                JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?''',(digest(token),int(time.time()))).fetchone()
        return dict(row) if row else None

    def revoke(self,token,store):
        if not token:return
        key=digest(token)
        with self.lock:
            with self.connect() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(key,))
            handle=self.workspaces.pop(key,None)
            if handle:
                with store.lock:store.sessions.pop(handle,None)

    def require_identity(self,token):
        user=self.identity(token)
        if not user:reject(401,'session_expired','Please sign in again.')
        return user

    def update_profile(self,token,name):
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            user=self.require_identity(token)
            db.execute('UPDATE users SET full_name=? WHERE id=?',(name,user['id']))
        return self.require_identity(token)

    def clear_workspace(self,token,store):
        with self.lock:
            self.require_identity(token)
            handle=self.workspaces.pop(digest(token),None)
            if handle:
                with store.lock:store.sessions.pop(handle,None)

    def secured_change(self,token,password,store,*,new_password=None,delete=False):
        # Serialize against login and use a transaction: never revoke another
        # account or let old credentials create a session during a password change.
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            user=self.require_identity(token)
            row=db.execute('SELECT password_hash FROM users WHERE id=?',(user['id'],)).fetchone()
            try:self.hasher.verify(row['password_hash'],password)
            except (VerificationError,InvalidHashError):reject(403,'current_password_incorrect','Current password is incorrect.')
            keys=[r['token_hash'] for r in db.execute('SELECT token_hash FROM sessions WHERE user_id=?',(user['id'],))]
            if not delete:
                db.execute('UPDATE users SET password_hash=? WHERE id=?',(self.hasher.hash(new_password),user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
            if delete:db.execute('DELETE FROM users WHERE id=?',(user['id'],))
            # Complete durable changes before discarding temporary workspaces.
            db.commit()
            with store.lock:
                for key in keys:
                    handle=self.workspaces.pop(key,None)
                    if handle:store.sessions.pop(handle,None)

    def workspace(self,token,store):
        with self.lock:
            # Check inside the same lock as logout to prevent resurrection.
            if not self.identity(token):reject(401,'session_expired','Please sign in again.')
            key=digest(token);handle=self.workspaces.get(key)
            self.workspaces={k:v for k,v in self.workspaces.items() if store.get(v)}
            if not store.get(handle):
                created=store.create()
                if not created:reject(503,'capacity','Workspace unavailable. Try again later.')
                handle,_=created;self.workspaces[key]=handle
            return handle

class LocalBoundary:
    def __init__(self,app,service,store,origins):self.app=app;self.service=service;self.store=store;self.origins=origins
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        path=scope['path'];headers=scope['headers'];jar=SimpleCookie()
        if scope['method'] not in ('GET','HEAD','OPTIONS'):
            supplied={k.lower():v for k,v in headers}
            if supplied.get(b'origin') not in tuple(o.encode() for o in self.origins) or supplied.get(b'x-medisaathi-action')!=b'review':
                return await JSONResponse({'detail':{'category':'origin_rejected','message':'Use the configured local frontend.'}},403,headers={'Cache-Control':'no-store'})(scope,receive,send)
        for k,v in headers:
            if k.lower()==b'cookie':jar.load(v.decode('latin1'))
        token=jar[COOKIE].value if COOKIE in jar else None
        # Ignore legacy Supabase/demo cookies even on public local auth routes.
        headers=[(k,v) for k,v in headers if k.lower()!=b'cookie']
        if token:headers.append((b'cookie',(COOKIE+'='+token).encode('latin1')))
        scope={**scope,'headers':headers}
        if path.startswith(('/api/auth/','/api/account/','/api/demo-access/')):
            return await JSONResponse({'detail':{'category':'local_accounts','message':'Use local account endpoints. Medical history is temporary.'}},403,headers={'Cache-Control':'no-store'})(scope,receive,send)
        if path.startswith('/api/') and not path.startswith(PREFIX+'/') and path not in ('/api/health','/api/demo-info') and scope['method']!='OPTIONS':
            try:handle=await run_in_threadpool(self.service.workspace,token,self.store)
            except HTTPException as e:return await JSONResponse({'detail':e.detail},e.status_code,headers={'Cache-Control':'no-store'})(scope,receive,send)
            headers=[(k,v) for k,v in headers if k.lower()!=b'cookie']
            headers.append((b'cookie',(WORKSPACE_COOKIE+'='+handle).encode()))
            scope={**scope,'headers':headers}
        if path.startswith(PREFIX+'/') and scope['method']=='POST':
            chunks=[];total=0
            while True:
                m=await receive()
                if m['type']!='http.request':return
                total+=len(m.get('body',b''))
                if total>4096:return await JSONResponse({'detail':{'category':'invalid_input','message':'Request too large.'}},413)(scope,receive,send)
                chunks.append(m.get('body',b''))
                if not m.get('more_body'):break
            payload=b''.join(chunks);used=False;original=receive
            async def replay():
                nonlocal used
                if not used:used=True;return {'type':'http.request','body':payload,'more_body':False}
                return await original()
            receive=replay
        async def filtered(m):
            if m['type']=='http.response.start':
                m={**m,'headers':[(k,v) for k,v in m['headers'] if k.lower()!=b'set-cookie' or v.startswith(COOKIE.encode()+b'=')]}
            await send(m)
        await self.app(scope,receive,filtered)

def create_local_app(path=None,*,offline=False,secure=None):
    preview=os.getenv('MEDISAATHI_DEPLOYMENT_MODE')=='preview'
    origins=configured_origins(preview)
    if preview and (not os.getenv('MEDISAATHI_TRUSTED_HOSTS') or not (path or os.getenv('MEDISAATHI_LOCAL_DB'))):
        raise ValueError('Preview requires explicit trusted hosts and SQLite path; account data is not durable without a mounted disk.')
    options={}
    if offline:
        from .demo_fixture import factory,check
        options={'factory':factory,'upload_validator':check}
    app=create_app(accounts=False,origins=origins,recognition_mode='offline_fixture' if offline else 'gemini',**options)
    service=LocalAccounts(path or os.getenv('MEDISAATHI_LOCAL_DB',str(DEFAULT_DB)))
    app.state.local_accounts=service
    app.add_middleware(LocalBoundary,service=service,store=app.state.sessions,origins=origins)
    cookie_secure=preview or (secure if secure is not None else os.getenv('MEDISAATHI_LOCAL_HTTPS','0')=='1')
    @app.exception_handler(sqlite3.Error)
    async def database_error(request,error):
        return JSONResponse({'detail':{'category':'storage_unavailable','message':'Local account storage unavailable.'}},503,headers={'Cache-Control':'no-store'})
    def session_response(token,request):
        service.revoke(request.cookies.get(COOKIE),app.state.sessions)
        response=JSONResponse({'user':service.identity(token)})
        response.set_cookie(COOKIE,token,httponly=True,secure=cookie_secure or request.url.scheme=='https',samesite='strict',path='/api',max_age=TTL)
        return response
    @app.post(PREFIX+'/signup')
    def signup(body:Signup,request:Request):
        service.throttle(request.client.host)
        return session_response(service.signup(body),request)
    @app.post(PREFIX+'/login')
    def login(body:Login,request:Request):
        service.throttle(request.client.host)
        return session_response(service.login(body),request)
    @app.get(PREFIX+'/me')
    def me(request:Request):
        user=service.identity(request.cookies.get(COOKIE))
        if not user:reject(401,'session_expired','Please sign in again.')
        return {'user':user}
    @app.post(PREFIX+'/logout')
    def logout(request:Request):
        service.revoke(request.cookies.get(COOKIE),app.state.sessions)
        response=JSONResponse({'signed_out':True})
        response.delete_cookie(COOKIE,path='/api',httponly=True,secure=cookie_secure or request.url.scheme=='https',samesite='strict')
        return response
    def cleared_response(request,payload):
        response=JSONResponse(payload)
        response.delete_cookie(COOKIE,path='/api',httponly=True,secure=cookie_secure or request.url.scheme=='https',samesite='strict')
        return response
    @app.post(PREFIX+'/profile')
    def profile(body:ProfileUpdate,request:Request):
        return {'user':service.update_profile(request.cookies.get(COOKIE),body.full_name)}
    @app.post(PREFIX+'/change-password')
    def change_password(body:PasswordChange,request:Request):
        service.require_identity(request.cookies.get(COOKIE));service.throttle(request.client.host)
        service.secured_change(request.cookies.get(COOKIE),body.current_password,app.state.sessions,new_password=body.new_password)
        return cleared_response(request,{'password_changed':True,'signed_out':True})
    @app.post(PREFIX+'/clear-workspace')
    def clear_workspace(body:Consent,request:Request):
        service.clear_workspace(request.cookies.get(COOKIE),app.state.sessions)
        return {'workspace_cleared':True}
    @app.post(PREFIX+'/delete-account')
    def delete_account(body:DeleteAccount,request:Request):
        service.require_identity(request.cookies.get(COOKIE));service.throttle(request.client.host)
        service.secured_change(request.cookies.get(COOKIE),body.current_password,app.state.sessions,delete=True)
        return cleared_response(request,{'account_deleted':True,'signed_out':True,'medical_archives_deleted':False})
    @app.get('/api/local-info')
    def info():return {'authentication':'local-password','medical_storage':'temporary-session-memory','offline_ocr':offline,'email_verification':False,'notifications':False}
    return app
