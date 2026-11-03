"""Supabase Auth REST transport. Provider error bodies never reach the UI."""
import os,json,base64
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException

def reject(status,category):
    messages={'auth_unavailable':'Account service unavailable. Check server configuration.',
        'invalid_credentials':'Sign-in failed. Check credentials and email verification.',
        'session_expired':'Sign in again to continue.', 'verification_failed':'Code invalid or expired.',
        'storage_unavailable':'Account storage unavailable. No record was changed.',
        'rate_limited':'Too many attempts. Please wait.', 'not_found':'Record not found.'}
    raise HTTPException(status,detail={'category':category,'message':messages.get(category,'The account request could not be completed.')})

class SupabaseProvider:
    def __init__(self,url,key,transport=None):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('Use an HTTPS Supabase project origin')
        if not key.startswith('sb_publishable_'):
            try:
                part=key.split('.')[1];claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
                if claims.get('role')!='anon':raise ValueError
            except Exception:raise ValueError('Use a publishable/anon key, never a privileged key') from None
        self.url=url.rstrip('/');self.key=key;self.transport=transport
    def call(self,method,path,body=None,token=None,*,auth=True,params=None,headers=None):
        try:
            with httpx.Client(timeout=15,transport=self.transport,follow_redirects=False) as client:
                response=client.request(method,self.url+('/auth/v1' if auth else '/rest/v1')+path,
                    json=body,params=params,headers={'apikey':self.key,**({'Authorization':'Bearer '+token} if token else {}),**(headers or {})})
            if response.status_code>=400:
                if response.status_code==429:reject(429,'rate_limited')
                reject(401 if auth and response.status_code<500 else 503,'invalid_credentials' if auth and response.status_code<500 else 'auth_unavailable' if auth else 'storage_unavailable')
            return response.json() if response.content else {}
        except (httpx.HTTPError,ValueError):reject(503,'auth_unavailable' if auth else 'storage_unavailable')
    def user(self,token):return self.call('GET','/user',token=token)
    def sign_in(self,email,password):return self.call('POST','/token?grant_type=password',{'email':email,'password':password})
    def refresh(self,token):return self.call('POST','/token?grant_type=refresh_token',{'refresh_token':token})
    def sign_up(self,email,password,name):return self.call('POST','/signup',{'email':email,'password':password,'data':{'full_name':name}})
    def recover(self,email):return self.call('POST','/recover',{'email':email})
    def verify(self,email,code,kind):return self.call('POST','/verify',{'email':email,'token':code,'type':kind})
    def password(self,token,password):return self.call('PUT','/user',{'password':password},token)
    def logout(self,token,scope='local'):return self.call('POST','/logout',token=token,params={'scope':scope})

def configured_provider():
    url=os.getenv('SUPABASE_URL','');key=os.getenv('SUPABASE_PUBLISHABLE_KEY','') or os.getenv('SUPABASE_ANON_KEY','')
    if not url or not key:return None
    try:return SupabaseProvider(url,key)
    except ValueError:return None
