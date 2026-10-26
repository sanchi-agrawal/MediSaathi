import type { Language, MedicineRecord } from './api'

export const MEDICINE_FIELDS = ['raw_text','name','salt','strength','form','frequency_pattern','duration_days','timing','confidence','needs_review'] as const
export interface AnalysisSnapshot {
  analysis_id: string; revision: string
  status: 'not_requested' | 'running' | 'succeeded' | 'failed'
  original_records: MedicineRecord[] | null; records: MedicineRecord[] | null
  error: { category: string; message: string } | null
  reviewed: boolean; confirmed: boolean
  performance?: Record<string,number>
}
export interface ExplanationPayload {
  schema_version: 'prescription-explanation-v1'; status: 'empty' | 'explained'; language: Language
  records_fingerprint: string
  medicines: {record_index:number; fields:{field:string; label:string; text:string; display_value:string; is_unknown:boolean}[]; glossary:{text:string}|null}[]
  issues: {record_index:number;field:string;code:string;text:string}[]; notice: string
}
export class ApiError extends Error {
  constructor(public category:string,message:string,public status=0){super(message)}
}
export function isMedicine(value:unknown):value is MedicineRecord {
  if(!value || typeof value!=='object' || Array.isArray(value))return false
  const r=value as Record<string,unknown>
  if(Object.keys(r).length!==10 || !MEDICINE_FIELDS.every(f=>Object.hasOwn(r,f)))return false
  if(!['raw_text','name','salt','strength','form','frequency_pattern','timing'].every(f=>r[f]===null || (typeof r[f]==='string' && (r[f] as string).trim().length>0)))return false
  return [null,'tablet','capsule','syrup','drops'].includes(r.form as MedicineRecord['form']) &&
    (r.duration_days===null || (typeof r.duration_days==='number'&&Number.isInteger(r.duration_days)&&r.duration_days>0)) &&
    (r.confidence===null || (typeof r.confidence==='number'&&Number.isFinite(r.confidence)&&r.confidence>=0&&r.confidence<=1)) && typeof r.needs_review==='boolean'
}
function parseSnapshot(value:unknown):AnalysisSnapshot {
  if(!value || typeof value!=='object')throw new ApiError('invalid_response','The API returned an invalid analysis.')
  const v=value as AnalysisSnapshot
  if(v.performance!==undefined && (!v.performance || typeof v.performance!=='object' || Array.isArray(v.performance) || !Object.values(v.performance).every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0)))throw new ApiError('invalid_response','Invalid performance metadata.')
  if(typeof v.analysis_id!=='string'||typeof v.revision!=='string'||!['not_requested','running','succeeded','failed'].includes(v.status)||typeof v.reviewed!=='boolean'||typeof v.confirmed!=='boolean'||
    ![v.records,v.original_records].every(records=>records===null||(Array.isArray(records)&&records.every(isMedicine)))||
    !(v.error===null||(typeof v.error?.category==='string'&&typeof v.error?.message==='string'))||
    (v.status==='succeeded'&&(!Array.isArray(v.records)||!Array.isArray(v.original_records))))throw new ApiError('invalid_response','The API returned an invalid medicine contract.')
  return v
}
function parseExplanation(value:unknown):ExplanationPayload {
  if(!value || typeof value!=='object')throw new ApiError('invalid_response','The explanation response is invalid.')
  const p=value as ExplanationPayload
  if(p.schema_version!=='prescription-explanation-v1'||!['empty','explained'].includes(p.status)||!['en','hi','hinglish'].includes(p.language)||typeof p.notice!=='string'||!Array.isArray(p.medicines)||!Array.isArray(p.issues)||
    !p.medicines.every(m=>typeof m.record_index==='number'&&Array.isArray(m.fields)&&m.fields.every(f=>typeof f.text==='string'&&typeof f.field==='string')&&(m.glossary===null||typeof m.glossary?.text==='string'))||!p.issues.every(i=>typeof i.text==='string'))throw new ApiError('invalid_response','The explanation response is invalid.')
  return p
}
export function createPrescriptionClient(fetcher:typeof fetch=(...args)=>fetch(...args)) {
  async function request(path:string,method='GET',body?:unknown,signal?:AbortSignal) {
    let response:Response
    try {response=await fetcher(`/api${path}`,{method,credentials:'include',cache:'no-store',signal,
      headers:{'X-MediSaathi-Action':'review',...(body instanceof File?{'Content-Type':body.type||'image/png'}:body!==undefined?{'Content-Type':'application/json'}:{})},
      body:body instanceof File?body:body===undefined?undefined:JSON.stringify(body)})}
    catch(error){if(error instanceof DOMException&&error.name==='AbortError')throw error;throw new ApiError('network_error','Could not reach the local Python API. Check that it is running.')}
    let payload:unknown
    try{payload=await response.json()}catch{throw new ApiError('invalid_response','The API did not return JSON. Check the API server and Vite proxy.',response.status)}
    if(!response.ok){const detail=(payload as {detail?:{category?:string;message?:string}})?.detail;throw new ApiError(detail?.category||'api_error',detail?.message||'The API request failed.',response.status)}
    return payload
  }
  const path=(data:AnalysisSnapshot)=>`/prescriptions/${encodeURIComponent(data.analysis_id)}`
  return {
    async upload(file:File,signal?:AbortSignal){await request('/session','POST',undefined,signal);return parseSnapshot(await request('/prescriptions','POST',file,signal))},
    async analyze(data:AnalysisSnapshot,signal?:AbortSignal){return parseSnapshot(await request(`${path(data)}/analyze`,'POST',{revision:data.revision},signal))},
    async status(data:AnalysisSnapshot,signal?:AbortSignal){return parseSnapshot(await request(path(data),'GET',undefined,signal))},
    async invalidate(data:AnalysisSnapshot){return parseSnapshot(await request(`${path(data)}/invalidate`,'POST',{revision:data.revision}))},
    async review(data:AnalysisSnapshot,records:MedicineRecord[]){if(!records.every(isMedicine))throw new ApiError('invalid_input','Check medicine field types. Blank text must be unknown.');return parseSnapshot(await request(`${path(data)}/review`,'PUT',{revision:data.revision,records}))},
    async confirm(data:AnalysisSnapshot){return parseSnapshot(await request(`${path(data)}/confirm`,'POST',{revision:data.revision}))},
    async explain(data:AnalysisSnapshot,language:Language){const result=await request(`${path(data)}/explanation`,'POST',{revision:data.revision,language}) as {revision?:string;analysis_id?:string;payload?:unknown};if(result.revision!==data.revision||result.analysis_id!==data.analysis_id)throw new ApiError('stale_result','The explanation is no longer current.');return parseExplanation(result.payload)},
    async clear(){await request('/prescriptions/current','DELETE')},
  }
}
export const prescriptionClient=createPrescriptionClient()
export type PrescriptionClient=ReturnType<typeof createPrescriptionClient>
