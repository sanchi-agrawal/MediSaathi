import type { InstructionEnvelope, InvestigationEnvelope } from './api'
import { ApiError } from './prescriptions'

export type ExtraScope='instructions'|'investigations'
export type ExtraPayload=InstructionEnvelope|InvestigationEnvelope
export interface SectionSnapshot {
  analysis_id:string; scope:ExtraScope; revision:string
  status:'not_requested'|'running'|'succeeded'|'failed'
  original_payload:ExtraPayload|null; payload:ExtraPayload|null
  error:{category:string;message:string}|null; reviewed:boolean;confirmed:boolean
  extractor_invocations:number;performance?:Record<string,number>
}
export const SECTION_FIELDS={
  instructions:['medicine_name_raw','raw_text','dose_quantity_raw','dose_unit_raw','frequency_raw','route_raw','timing_raw','duration_raw'],
  investigations:['test_name_raw','raw_text','order_context_raw','specimen_raw','variant_raw','timing_raw'],
} as const
export function sectionRecords(payload:ExtraPayload,scope:ExtraScope):Record<string,unknown>[] {
  return (scope==='instructions'?(payload as InstructionEnvelope).instructions:(payload as InvestigationEnvelope).investigations) as unknown as Record<string,unknown>[]
}
function codes(value:unknown):value is string[]{return Array.isArray(value)&&value.every(v=>typeof v==='string'&&!!v.trim())&&new Set(value).size===value.length}
export function validPayload(payload:unknown,scope:ExtraScope):payload is ExtraPayload {
  if(!payload||typeof payload!=='object'||Array.isArray(payload))return false
  const p=payload as Record<string,unknown>
  const expected=['schema_version','source_image_sha256',scope,'issues','confirmation_required']
  if(Object.keys(p).length!==expected.length||!expected.every(k=>Object.hasOwn(p,k))||p.confirmation_required!==true||
    p.schema_version!==(scope==='instructions'?'medication-instructions-v1':'prescribed-investigations-v1')||
    typeof p.source_image_sha256!=='string'||!/^[a-f0-9]{64}$/.test(p.source_image_sha256)||!codes(p.issues)||!Array.isArray(p[scope]))return false
  const id=scope==='instructions'?'instruction_id':'investigation_id'
  const fields=[...SECTION_FIELDS[scope],id,'uncertainty_reasons','needs_review','confirmation_required']
  const ids=new Set<string>()
  return (p[scope] as unknown[]).every(value=>{
    if(!value||typeof value!=='object'||Array.isArray(value))return false
    const r=value as Record<string,unknown>
    if(Object.keys(r).length!==fields.length||!fields.every(k=>Object.hasOwn(r,k))||typeof r[id]!=='string'||!(r[id] as string).trim()||ids.has(r[id] as string)||
      typeof r.needs_review!=='boolean'||r.confirmation_required!==true||!codes(r.uncertainty_reasons)||
      !SECTION_FIELDS[scope].every(k=>r[k]===null||(typeof r[k]==='string'&&!!(r[k] as string).trim())))return false
    ids.add(r[id] as string);return true
  })
}
export function parseSection(value:unknown,scope:ExtraScope,analysisId:string):SectionSnapshot {
  if(!value||typeof value!=='object')throw new ApiError('invalid_response','Invalid section response.')
  const s=value as SectionSnapshot
  if(s.analysis_id!==analysisId||s.scope!==scope||typeof s.revision!=='string'||!['not_requested','running','succeeded','failed'].includes(s.status)||
    typeof s.reviewed!=='boolean'||typeof s.confirmed!=='boolean'||!Number.isInteger(s.extractor_invocations)||s.extractor_invocations<0||
    ![s.original_payload,s.payload].every(p=>p===null||validPayload(p,scope))||
    (s.status==='succeeded'&&(!s.original_payload||!s.payload))||
    !(s.error===null||(typeof s.error?.category==='string'&&typeof s.error?.message==='string')))throw new ApiError('invalid_response','The section response violates its separate extraction contract.')
  return s
}
export function createSectionClient(fetcher:typeof fetch=(...args)=>fetch(...args)) {
  async function request(analysis:string,scope:ExtraScope,action='',method='GET',body?:unknown,signal?:AbortSignal){
    let response:Response
    try{response=await fetcher(`/api/prescriptions/${encodeURIComponent(analysis)}/sections/${scope}${action}`,{
      method,signal,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}
    catch{throw new ApiError('network_error','Could not reach the section API. No automatic retry was made.')}
    let value:unknown
    try{value=await response.json()}catch{throw new ApiError('invalid_response','The section API did not return JSON.')}
    if(!response.ok){const detail=(value as {detail?:{category?:string;message?:string}})?.detail;throw new ApiError(detail?.category??'api_error',detail?.message??'The section operation failed.',response.status)}
    return parseSection(value,scope,analysis)
  }
  return {
    status:(analysis:string,scope:ExtraScope,signal?:AbortSignal)=>request(analysis,scope,'','GET',undefined,signal),
    analyze:(s:SectionSnapshot,signal?:AbortSignal)=>request(s.analysis_id,s.scope,'/analyze','POST',{revision:s.revision},signal),
    invalidate:(s:SectionSnapshot)=>request(s.analysis_id,s.scope,'/invalidate','POST',{revision:s.revision}),
    review:(s:SectionSnapshot,payload:ExtraPayload)=>{if(!validPayload(payload,s.scope))return Promise.reject(new ApiError('invalid_input','Check section field types; missing text must stay unknown.'));return request(s.analysis_id,s.scope,'/review','PUT',{revision:s.revision,payload})},
    confirm:(s:SectionSnapshot)=>request(s.analysis_id,s.scope,'/confirm','POST',{revision:s.revision}),
  }
}
export const sectionClient=createSectionClient()
export type SectionClient=ReturnType<typeof createSectionClient>
