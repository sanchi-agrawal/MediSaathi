import { useEffect,useSyncExternalStore } from 'react'
import { ApiError } from './prescriptions'
export const DEMO_ACCESS=import.meta.env.VITE_MEDISAATHI_DEMO_ACCESS==='1'
export interface DemoStatus{mode:'demo-access';display_name:string|null;active:boolean;expires_in:number;email_verified:false;account_authentication:false}
function parse(value:unknown):DemoStatus{
  const v=value as DemoStatus
  if(!v||(v.display_name!==null&&(typeof v.display_name!=='string'||v.display_name.length>100))||v.mode!=='demo-access'||typeof v.active!=='boolean'||!Number.isInteger(v.expires_in)||v.expires_in<0||v.email_verified!==false||v.account_authentication!==false)throw new ApiError('invalid_response','Invalid demo session response.')
  return v
}
export function createDemoClient(fetcher:typeof fetch=(...a)=>fetch(...a)){
  async function request(path:string,method='GET',body?:unknown){
    let r:Response;try{r=await fetcher('/api/demo-access/'+path,{method,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch{throw new ApiError('network_error','Demo server unavailable.')}
    let value:unknown;try{value=await r.json()}catch{throw new ApiError('invalid_response','Demo server returned an invalid response.')}
    if(!r.ok)throw new ApiError('demo_failed','Demo request failed.',r.status)
    return value
  }
  return {
    async status(){return parse(await request('status'))},
    async login(email:string){await request('login','POST',{email});const s=parse(await request('status'));if(!s.active)throw new ApiError('cookie_unavailable','The browser did not retain the demo cookie.');return s},
    async signup(email:string,display_name:string){await request('signup','POST',{email,display_name});const s=parse(await request('status'));if(!s.active)throw new ApiError('cookie_unavailable','The browser did not retain the demo cookie.');return s},
    async logout(){const v=await request('logout','POST') as {signed_out?:boolean};if(v.signed_out!==true)throw new ApiError('invalid_response','Demo logout failed.')},
  }
}
export const demoClient=createDemoClient()
export type DemoClient=ReturnType<typeof createDemoClient>
let current={loading:true,active:false,expiresAt:0,error:false,displayName:null as string|null};const listeners=new Set<()=>void>();let pending:Promise<void>|null=null
function emit(v:typeof current){current=v;listeners.forEach(f=>f())}
let generation=0
export function acceptDemo(s:DemoStatus){generation++;emit({loading:false,active:s.active,expiresAt:Date.now()+s.expires_in*1000,error:false,displayName:s.active?s.display_name:null})}
export function clearDemo(){generation++;emit({loading:false,active:false,expiresAt:0,error:false,displayName:null})}
export function refreshDemo(){
  if(pending)return pending
  const started=generation
  pending=(async()=>{try{const s=await demoClient.status();if(started===generation)acceptDemo(s)}catch{if(started===generation)emit({loading:false,active:false,expiresAt:0,error:true,displayName:null})}finally{pending=null}})();return pending
}
export function useDemoAccess(){
  const s=useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},()=>current)
  useEffect(()=>{void refreshDemo();const fn=()=>void refreshDemo();window.addEventListener('focus',fn);return()=>window.removeEventListener('focus',fn)},[])
  useEffect(()=>{if(!s.active)return;const id=window.setTimeout(()=>void refreshDemo(),Math.max(50,s.expiresAt-Date.now()+50));return()=>clearTimeout(id)},[s.active,s.expiresAt])
  return s
}
