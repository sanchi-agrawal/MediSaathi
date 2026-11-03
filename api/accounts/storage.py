"""Encrypted immutable archives via user JWT + owner predicates + database RLS."""
import json
from uuid import uuid4,UUID
from datetime import datetime,timedelta,timezone,date
from cryptography.fernet import Fernet,InvalidToken
from .provider import reject
def serialize(value):
    if isinstance(value,(date,datetime)):return value.isoformat()
    raise TypeError('Unsupported archive value')
class ArchiveRepository:
    def __init__(self,provider,key):self.provider=provider;self.cipher=Fernet(key.encode() if isinstance(key,str) else key)
    def save(self,record,payload):
        encoded=json.dumps(payload,ensure_ascii=False,default=serialize,allow_nan=False).encode()
        if len(encoded)>16*1024*1024:reject(413,'archive_too_large')
        row={'id':str(uuid4()),'owner_id':record.user['id'],'version':str(uuid4()),'schema_version':1,
             'expires_at':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),
             'payload_ciphertext':self.cipher.encrypt(encoded).decode()}
        rows=self.provider.call('POST','/prescription_archives',row,record.access,auth=False,headers={'Prefer':'return=representation'})
        if not isinstance(rows,list) or len(rows)!=1 or rows[0].get('owner_id')!=record.user['id']:reject(503,'storage_unavailable')
        return self.metadata(rows[0])
    def query(self,record,archive_id=None,*,cipher=False,method='GET'):
        params={'owner_id':'eq.'+record.user['id'],'select':'*' if cipher else 'id,owner_id,version,schema_version,created_at,expires_at'}
        if archive_id is None and method=='GET':params.update(order='created_at.desc',limit='100')
        if archive_id is not None:
            try:params['id']='eq.'+str(UUID(archive_id))
            except ValueError:reject(404,'not_found')
        rows=self.provider.call(method,'/prescription_archives',token=record.access,auth=False,params=params,headers={'Prefer':'return=representation'})
        if not isinstance(rows,list) or any(r.get('owner_id')!=record.user['id'] for r in rows):reject(503,'storage_unavailable')
        rows=[r for r in rows if datetime.fromisoformat(r['expires_at'].replace('Z','+00:00'))>datetime.now(timezone.utc)]
        if archive_id is not None and not rows:reject(404,'not_found')
        return rows
    def metadata(self,row):return {k:row[k] for k in ('id','version','created_at','expires_at')}|{'historical':True}
    def list(self,record):return [self.metadata(row) for row in self.query(record)]
    def get(self,record,archive_id):
        row=self.query(record,archive_id,cipher=True)[0]
        try:
            payload=json.loads(self.cipher.decrypt(row['payload_ciphertext'].encode()))
            if payload['owner_id']!=record.user['id'] or payload['schema_version']!='account-archive-v1':raise ValueError
        except (InvalidToken,ValueError,KeyError,TypeError):reject(503,'storage_unavailable')
        return self.metadata(row),payload
    def delete(self,record,archive_id):self.query(record,archive_id,method='DELETE');return {'deleted':True}
