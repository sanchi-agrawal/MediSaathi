import type { InstructionRecord,MedicineRecord } from './api'
import { ApiError,isMedicine } from './prescriptions'
import { validPayload } from './sections'
export const SLOTS=['morning','noon','night','bedtime'] as const
export type Slot=typeof SLOTS[number]
export interface SchedulePlan{dose_quantity:number;dose_unit:'tablet'|'capsule'|'mL'|'drop';duration_days:number;administrations_by_slot:Record<Slot,number>;start_date:string}
export interface ScheduleSuccess{name:string;status:'ok';reason:null;doses_by_slot:Record<Slot,number>;units_per_day:number;duration_days:number;total_units:number;unit:SchedulePlan['dose_unit'];start_date:string;end_date:string;refill_date:string|null}
export interface ScheduleRefusal{name:string;status:'needs_input'|'as_needed';reason:string}
export interface ScheduleContext{
  analysis_id:string;medicine_revision:string;instruction_revision:string;scheduling_revision:string;ready:boolean
  status:'blocked'|'ready'|'associated'|'reviewed'|'succeeded'|'needs_input'|'failed'
  medicines:MedicineRecord[];instructions:InstructionRecord[];instruction_issues:string[]
  association:{association_id:string;medicine_ref:string;instruction_id:string}|null
  plan:SchedulePlan|null;result:{derived_id:string;payload:ScheduleSuccess|ScheduleRefusal}|null
  error:{category:string;message:string}|null
}
const exact=(v:unknown,fields:string[]):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===fields.length&&fields.every(k=>Object.hasOwn(v,k))
const finite=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)&&v>=0
const iso=(v:unknown)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)
export function validPlan(v:unknown):v is SchedulePlan{
  if(!exact(v,['dose_quantity','dose_unit','duration_days','administrations_by_slot','start_date']))return false
  return finite(v.dose_quantity)&&Number(v.dose_quantity)>0&&Number(v.dose_quantity)<=1000&&['tablet','capsule','mL','drop'].includes(String(v.dose_unit))&&Number.isInteger(v.duration_days)&&Number(v.duration_days)>0&&Number(v.duration_days)<=365&&iso(v.start_date)&&exact(v.administrations_by_slot,[...SLOTS])&&Object.values(v.administrations_by_slot).every(n=>n===0||n===1)
}
export function validResult(v:unknown):v is ScheduleSuccess|ScheduleRefusal{
  if(!v||typeof v!=='object')return false
  const r=v as Record<string,unknown>
  if(r.status!=='ok')return exact(r,['name','status','reason'])&&typeof r.name==='string'&&['needs_input','as_needed'].includes(String(r.status))&&typeof r.reason==='string'
  return exact(r,['name','status','reason','doses_by_slot','units_per_day','duration_days','total_units','unit','start_date','end_date','refill_date'])&&typeof r.name==='string'&&r.reason===null&&exact(r.doses_by_slot,[...SLOTS])&&Object.values(r.doses_by_slot).every(finite)&&finite(r.units_per_day)&&Number(r.units_per_day)>0&&finite(r.total_units)&&Number(r.total_units)>0&&Number.isInteger(r.duration_days)&&Number(r.duration_days)>0&&['tablet','capsule','mL','drop'].includes(String(r.unit))&&iso(r.start_date)&&iso(r.end_date)&&(r.refill_date===null||iso(r.refill_date))
}
export function parseScheduling(v:unknown):ScheduleContext{
  const s=v as ScheduleContext
  if(!s||![s.analysis_id,s.medicine_revision,s.instruction_revision,s.scheduling_revision].every(v=>typeof v==='string'&&!!v)||typeof s.ready!=='boolean'||!['blocked','ready','associated','reviewed','succeeded','needs_input','failed'].includes(s.status)||!Array.isArray(s.medicines)||!s.medicines.every(isMedicine)||
    !validPayload({schema_version:'medication-instructions-v1',source_image_sha256:'0'.repeat(64),instructions:s.instructions,issues:s.instruction_issues,confirmation_required:true},'instructions')||
    !(s.association===null||(exact(s.association,['association_id','medicine_ref','instruction_id'])&&Object.values(s.association).every(v=>typeof v==='string'&&!!v)))||!(s.plan===null||validPlan(s.plan))||
    !(s.result===null||(exact(s.result,['derived_id','payload'])&&typeof s.result.derived_id==='string'&&validResult(s.result.payload)))||!(s.error===null||(typeof s.error?.category==='string'&&typeof s.error?.message==='string'))||
    (!s.ready&&(s.result!==null||s.association!==null||s.plan!==null))||(s.status==='succeeded'&&(!s.ready||!s.association||!s.plan||s.result?.payload.status!=='ok'))||
    (s.result!==null&&!['succeeded','needs_input'].includes(s.status)))throw new ApiError('invalid_response','Invalid scheduling response. No schedule is displayed.')
  return s
}
export function createSchedulingClient(fetcher:typeof fetch=(...args)=>fetch(...args)){
  function httpError(status:number,value?:unknown):ApiError{
    const detail=value&&typeof value==='object'?(value as {detail?:unknown}).detail:undefined
    if(detail&&typeof detail==='object'){
      const d=detail as {category?:unknown;message?:unknown}
      if(typeof d.category==='string'&&d.category.trim()&&typeof d.message==='string'&&d.message.trim())return new ApiError(d.category,d.message,status)
    }
    // Legacy FastAPI/proxy errors can have string detail, HTML or no body.
    // Retain the safe HTTP status, never echo an arbitrary upstream body.
    if(status===404||status===405)return new ApiError('api_route_unavailable','Scheduling endpoint returned HTTP '+status+'. Restart the current FastAPI API and check the Vite /api proxy.',status)
    if(status===401)return new ApiError('session_expired','The demo session is missing or expired. Review and confirm the prescription again.',status)
    if(status===403)return new ApiError('origin_rejected','The API rejected this frontend origin or action header. Check the local frontend/API configuration.',status)
    if(status===409)return new ApiError('request_conflict','The source or saved plan is no longer current. Refresh scheduling and review again.',status)
    if(status===422)return new ApiError('invalid_input','The API could not validate these scheduling inputs. Review the current records and plan.',status)
    if(status===429)return new ApiError('rate_limited','The API rate limit was reached. No automatic retry was made.',status)
    if(status>=500)return new ApiError('backend_unavailable','Scheduling backend returned HTTP '+status+'. Check the API server; no schedule was generated and no automatic retry was made.',status)
    return new ApiError('api_http_error','Scheduling request returned HTTP '+status+'. No successful schedule was received.',status)
  }
  async function request(path:string,method='GET',body?:unknown){
    let response:Response
    try{response=await fetcher('/api'+path,{method,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}
    catch{throw new ApiError('network_error','Could not reach scheduling. No automatic retry was made.')}
    let value:unknown;try{value=await response.json()}catch{if(!response.ok)throw httpError(response.status);throw new ApiError('invalid_response','Scheduling did not return JSON.',response.status)}
    if(!response.ok)throw httpError(response.status,value)
    return parseScheduling(value)
  }
  const path=(s:ScheduleContext)=>'/prescriptions/'+encodeURIComponent(s.analysis_id)
  const binding=(s:ScheduleContext)=>({medicine_revision:s.medicine_revision,instruction_revision:s.instruction_revision,scheduling_revision:s.scheduling_revision})
  const linked=(s:ScheduleContext)=>({...binding(s),association_id:s.association?.association_id})
  return {
    current:()=>request('/scheduling/current'),
    associate:(s:ScheduleContext,medicine_ref:string,instruction_id:string)=>request(path(s)+'/associations','POST',{...binding(s),medicine_ref,instruction_id}),
    clear:(s:ScheduleContext)=>request(path(s)+'/associations','DELETE',binding(s)),
    invalidate:(s:ScheduleContext)=>request(path(s)+'/schedule/invalidate','POST',linked(s)),
    review:(s:ScheduleContext,plan:SchedulePlan)=>{if(!validPlan(plan))return Promise.reject(new ApiError('invalid_input','Review every explicit schedule input.'));return request(path(s)+'/schedule/review','PUT',{...linked(s),plan})},
    approve:(s:ScheduleContext)=>request(path(s)+'/schedule/approve','POST',linked(s)),
  }
}
export const schedulingClient=createSchedulingClient()
export type SchedulingClient=ReturnType<typeof createSchedulingClient>
