import { useEffect,useSyncExternalStore } from 'react'
import { ApiError } from './prescriptions'
export const LOCAL_AUTH=import.meta.env.VITE_MEDISAATHI_LOCAL_AUTH!=='0'
export interface LocalUser{id:string;full_name:string;email:string;expires_at:number;created_at?:number}
function parse(v:unknown):LocalUser{
  const u=(v as {user?:LocalUser})?.user
  if(!u||typeof u.id!=='string'||typeof u.full_name!=='string'||typeof u.email!=='string'||!Number.isFinite(u.expires_at))throw new ApiError('invalid_response','Invalid account response.')
  return u
}
export function createLocalClient(fetcher:typeof fetch=(...args)=>fetch(...args)){
  async function request(path:string,body?:unknown){
    let r:Response
    try{r=await fetcher('/api/local-auth/'+path,{method:body?'POST':'GET',credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch{throw new ApiError('network_error','Local server unavailable.')}
    let v:any;try{v=await r.json()}catch{throw new ApiError('invalid_response','Expected JSON from the local server.')}
    if(!r.ok)throw new ApiError(v?.detail?.category||'auth_failed','The account request failed.',r.status)
    return v
  }
  async function me(){try{return parse(await request('me'))}catch(e){if(e instanceof ApiError&&e.status===401)return null;throw e}}
  async function authenticate(path:string,body:unknown){await request(path,body);const u=await me();if(!u)throw new ApiError('cookie_unavailable','Session cookie was not retained.');return u}
  async function checked(path:string,body:unknown,flag:string){const r=await request(path,body);if(r[flag]!==true||(['password_changed','account_deleted'].includes(flag)&&r.signed_out!==true)||(flag==='account_deleted'&&r.medical_archives_deleted!==false))throw new ApiError('invalid_response','Invalid settings response.');return r}
  return {me,login:(email:string,password:string)=>authenticate('login',{email,password}),signup:(full_name:string,email:string,password:string)=>authenticate('signup',{full_name,email,password}),
    async updateName(full_name:string){return parse(await request('profile',{full_name}))},
    changePassword:(current_password:string,new_password:string)=>checked('change-password',{current_password,new_password},'password_changed'),
    deleteAccount:(current_password:string,confirm:true)=>checked('delete-account',{current_password,confirm},'account_deleted'),
    clearWorkspace:()=>checked('clear-workspace',{confirm:true},'workspace_cleared'),
    async logout(){const r=await request('logout',{});if(r.signed_out!==true)throw new ApiError('invalid_response','Logout failed.')}}
}
export const localClient=createLocalClient()
export type LocalClient=Pick<ReturnType<typeof createLocalClient>,'me'|'login'|'signup'|'logout'>
export type LocalSettingsClient=Pick<ReturnType<typeof createLocalClient>,'updateName'|'changePassword'|'deleteAccount'|'clearWorkspace'|'logout'>
let state={loading:true,user:null as LocalUser|null,error:false};let generation=0
const listeners=new Set<()=>void>();let pending:Promise<void>|null=null
export function setLocalUser(user:LocalUser|null){generation++;state={loading:false,user,error:false};listeners.forEach(f=>f())}
export function announceLocalChange(){try{const c=new BroadcastChannel('medisaathi-local-auth');c.postMessage('changed');c.close()}catch{/* Focus restoration remains available. */}}
export function refreshLocal(){
  if(pending)return pending
  const version=generation
  pending=(async()=>{try{const u=await localClient.me();if(version===generation)setLocalUser(u)}catch{if(version===generation){state={loading:false,user:null,error:true};listeners.forEach(f=>f())}}finally{pending=null}})();return pending
}
export function useLocalAccount(){
  const s=useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},()=>state)
  useEffect(()=>{void refreshLocal();const focus=()=>void refreshLocal();window.addEventListener('focus',focus);return()=>window.removeEventListener('focus',focus)},[])
  useEffect(()=>{let c:BroadcastChannel|undefined;try{c=new BroadcastChannel('medisaathi-local-auth');c.onmessage=e=>{if(e.data==='changed'){setLocalUser(null);void refreshLocal()}}}catch{/* Unsupported browsers restore on focus. */}return()=>c?.close()},[])
  useEffect(()=>{if(!s.user)return;const timer=setTimeout(()=>{setLocalUser(null);void refreshLocal()},Math.min(2147483647,Math.max(0,s.user.expires_at*1000-Date.now())));return()=>clearTimeout(timer)},[s.user])
  return s
}
