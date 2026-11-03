import { useEffect,useSyncExternalStore } from 'react'
import { ApiError } from './prescriptions'
export interface AccountUser{id:string;email:string;name:string|null}
export interface AccountState{loading:boolean;configured:boolean;storage_configured:boolean;user:AccountUser|null;error:string}
export interface ArchiveMeta{id:string;version:string;created_at:string;expires_at:string;historical:true}
export interface ArchiveView extends ArchiveMeta{payload:{captured_at:string;prescription:{analysis_id:string;sections:Record<string,{payload:unknown;reviewed:unknown}>};confirmed_scopes:string[];scheduling_state:unknown};image_saved:boolean;approval_authority_restored:false}
type Binding={analysis_id:string;revision:string;section_revisions:Record<string,string>;scheduling_revision:string}
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)
const user=(v:unknown):v is AccountUser=>object(v)&&typeof v.id==='string'&&typeof v.email==='string'&&(v.name===null||typeof v.name==='string')
const meta=(v:unknown):v is ArchiveMeta=>object(v)&&['id','version','created_at','expires_at'].every(k=>typeof v[k]==='string')&&v.historical===true
export function createAccountClient(fetcher:typeof fetch=(...a)=>fetch(...a)){
  async function request(path:string,method='GET',body?:unknown):Promise<any>{
    let response:Response;try{response=await fetcher('/api'+path,{method,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch{throw new ApiError('network_error','Account service unavailable.')}
    let value:unknown;try{value=await response.json()}catch{throw new ApiError('invalid_response','Account service returned an invalid response.')}
    if(!response.ok){const d=object(value)&&object(value.detail)?value.detail:null;throw new ApiError(d&&typeof d.category==='string'?d.category:'auth_unavailable','The account request could not be completed.',response.status)}
    return value
  }
  return {
    async status(){const s=await request('/auth/status');if(!object(s)||typeof s.configured!=='boolean'||typeof s.storage_configured!=='boolean')throw new ApiError('invalid_response','Invalid account status.');return {configured:s.configured,storage_configured:s.storage_configured}},
    async me(){try{const s=await request('/auth/me');if(!user(s.user))throw new ApiError('invalid_response','Invalid user.');return s.user}catch(e){if(e instanceof ApiError&&e.status===401)return null;throw e}},
    async login(email:string,password:string){const s=await request('/auth/login','POST',{email,password});if(!user(s.user))throw new ApiError('invalid_response','Invalid user.');return s.user},
    signup:(name:string,email:string,password:string)=>request('/auth/signup','POST',{name,email,password}),
    verify:(email:string,code:string)=>request('/auth/verify','POST',{email,code}),
    forgot:(email:string)=>request('/auth/forgot-password','POST',{email}),
    reset:(email:string,code:string,password:string)=>request('/auth/reset-password','POST',{email,code,password}),
    logout:()=>request('/auth/logout','POST'),
    async history():Promise<ArchiveMeta[]>{const v=await request('/account/prescriptions');if(!Array.isArray(v.records)||!v.records.every(meta))throw new ApiError('invalid_response','Invalid history.');return v.records},
    async save(save_image:boolean):Promise<ArchiveMeta>{const b=await request('/account/workspace') as Binding;const v=await request('/account/prescriptions','POST',{...b,consent:true,save_image});if(!meta(v))throw new ApiError('invalid_response','Invalid saved record.');return v},
    async view(id:string):Promise<ArchiveView>{const v=await request('/account/prescriptions/'+encodeURIComponent(id));if(!meta(v)||!object(v)||v.approval_authority_restored!==false||typeof v.image_saved!=='boolean'||!object(v.payload)||!object(v.payload.prescription))throw new ApiError('invalid_response','Invalid archive.');return v as unknown as ArchiveView},
    remove:(id:string)=>request('/account/prescriptions/'+encodeURIComponent(id),'DELETE'),
    async resume(v:ArchiveView,image_base64?:string){const r=await request('/account/prescriptions/'+encodeURIComponent(v.id)+'/continue','POST',{version:v.version,acknowledge_reconfirmation:true,...(image_base64?{image_base64}:{})});if(r.reconfirmation_required!==true||typeof r.analysis_id!=='string')throw new ApiError('invalid_response','Invalid review workspace.');return r},
  }
}
export const accountClient=createAccountClient()
export type AccountClient=ReturnType<typeof createAccountClient>
let state:AccountState={loading:true,configured:false,storage_configured:false,user:null,error:''}
const listeners=new Set<()=>void>();let pending:Promise<void>|null=null
function emit(next:AccountState){state=next;listeners.forEach(fn=>fn())}
export async function refreshAccount(){
  if(pending)return pending
  pending=(async()=>{try{const s=await accountClient.status();const u=s.configured?await accountClient.me():null;emit({loading:false,...s,user:u,error:''})}catch(e){emit({...state,loading:false,user:null,error:e instanceof ApiError?e.category:'auth_unavailable'})}finally{pending=null}})()
  return pending
}
export function setAccountUser(u:AccountUser|null){emit({...state,loading:false,user:u})}
export function useAccount(){const s=useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},()=>state);useEffect(()=>{void refreshAccount();const fn=()=>void refreshAccount();window.addEventListener('focus',fn);return()=>window.removeEventListener('focus',fn)},[]);return s}
