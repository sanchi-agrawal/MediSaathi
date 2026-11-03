"""Opaque BFF sessions. No passwords or provider tokens are persisted."""
import secrets,hashlib,time,os
from dataclasses import dataclass,field
from threading import RLock
from uuid import UUID
from fastapi import HTTPException
from .provider import configured_provider,reject
COOKIE='medisaathi_account'
MAX_AGE=8*60*60
@dataclass
class AccountSession:
    access:str
    refresh:str
    expires:float
    until:float
    user:dict
    workspace:str|None=None
    revoked:bool=False
    lock:RLock=field(default_factory=RLock)
def identity(user):
    try:
        uid=str(UUID(user['id']))
        if not user.get('email_confirmed_at') or user.get('is_anonymous'):raise ValueError
        email=user['email'];name=(user.get('user_metadata') or {}).get('full_name')
        if not isinstance(email,str):raise ValueError
        return {'id':uid,'email':email,'name':name[:100] if isinstance(name,str) else None}
    except (KeyError,TypeError,ValueError):reject(401,'invalid_credentials')
class AccountServices:
    def __init__(self,provider,archive_key=None,repository=None):
        self.provider=provider;self.sessions={};self.lock=RLock();self.attempts={}
        from .storage import ArchiveRepository
        self.repository=repository or (ArchiveRepository(provider,archive_key) if archive_key else None)
    @classmethod
    def from_env(cls):
        provider=configured_provider()
        if not provider:return None
        try:return cls(provider,os.getenv('MEDISAATHI_ARCHIVE_KEY'))
        except ValueError:return cls(provider)
    def limited(self,ip,email=''):
        now=time.monotonic();key=hashlib.sha256((ip+'|'+email.casefold()).encode()).hexdigest()
        with self.lock:
            self.attempts={k:v for k,v in self.attempts.items() if v[0]>now-60}
            for k,limit in [('ip:'+hashlib.sha256(ip.encode()).hexdigest(),30),(key,8)]:
                start,count=self.attempts.get(k,(now,0))
                if count>=limit or len(self.attempts)>=10000:reject(429,'rate_limited')
                self.attempts[k]=(start,count+1)
    def establish(self,tokens):
        try:
            access=tokens['access_token'];refresh=tokens['refresh_token'];ttl=int(tokens['expires_in'])
            if not isinstance(access,str) or not isinstance(refresh,str) or ttl<1:raise ValueError
        except (KeyError,ValueError,TypeError):reject(503,'auth_unavailable')
        user=identity(self.provider.user(access));handle=secrets.token_urlsafe(48);now=time.time()
        with self.lock:
            self.sessions={k:v for k,v in self.sessions.items() if v.until>now and not v.revoked}
            if len(self.sessions)>=512:reject(503,'auth_unavailable')
            self.sessions[hashlib.sha256(handle.encode()).hexdigest()]=AccountSession(access,refresh,now+ttl,now+MAX_AGE,user)
        return handle,user
    def find(self,handle):
        if not handle:return None
        with self.lock:return self.sessions.get(hashlib.sha256(handle.encode()).hexdigest())
    def authenticate(self,handle):
        record=self.find(handle)
        if record is None:reject(401,'session_expired')
        with record.lock:
            if record.revoked or record.until<=time.time():reject(401,'session_expired')
            if record.expires<=time.time()+30:
                try:
                    data=self.provider.refresh(record.refresh)
                    record.access=data['access_token'];record.refresh=data['refresh_token'];record.expires=time.time()+int(data['expires_in'])
                except (KeyError,TypeError,ValueError,HTTPException):record.revoked=True;reject(401,'session_expired')
            user=identity(self.provider.user(record.access))
            if user['id']!=record.user['id']:record.revoked=True;reject(401,'session_expired')
            record.user=user
            return record
    def workspace(self,record,store):
        with record.lock:
            if record.revoked:reject(401,'session_expired')
            if record.workspace and store.get(record.workspace):return store.get(record.workspace)
            created=store.create()
            if created is None:reject(503,'auth_unavailable')
            record.workspace,session=created
            return session
    def revoke(self,handle,store):
        record=self.find(handle)
        if record:
            with record.lock:
                record.revoked=True
                if record.workspace:
                    with store.lock:store.sessions.pop(record.workspace,None)
                try:self.provider.logout(record.access)
                except HTTPException:pass
            with self.lock:self.sessions.pop(hashlib.sha256(handle.encode()).hexdigest(),None)
