import { ApiError } from './prescriptions'

export interface ParsedExpiry { year:number;month:number;day:number|null;precision:'month'|'day';iso:string }
export interface DateObservation {
  raw_label:string|null;raw_date_text:string|null;raw_text:string|null
  association:'same_product'|'unclear';confidence:number|null;uncertain:boolean
  label_kind:'expiry'|'manufacturing'|'batch'|'use_before'|'unknown'
  parsed_date:ParsedExpiry|null;parse_issues:string[]
}
export interface StripPayload {
  schema_version:'strip-expiry-v1';medicine_name:string|null;batch_number:string|null
  product_association:'single_product'|'multiple_products'|'unclear'
  raw_expiry_text:string|null;expiry:ParsedExpiry|null;confidence:number|null
  confidence_kind:'uncalibrated';needs_review:boolean;issues:string[]
  date_observations:DateObservation[];confirmation_required:true
}
export interface StripEdits {
  medicine_name:string|null;batch_number:string|null;product_association:StripPayload['product_association']
  date_observations:Pick<DateObservation,'raw_label'|'raw_date_text'|'raw_text'|'association'>[]
}
export interface StripSnapshot {
  analysis_id:string;revision:string;scope:'strip';status:'not_requested'|'running'|'succeeded'|'failed'
  original_payload:StripPayload|null;payload:StripPayload|null
  reviewed:boolean;confirmed:boolean;error:{category:string;message:string}|null
  extractor_invocations:number;performance?:Record<string,number>
}
const text=(v:unknown)=>v===null||(typeof v==='string'&&!!v.trim())
const confidence=(v:unknown)=>v===null||(typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1)
const codes=(v:unknown)=>Array.isArray(v)&&v.every(i=>typeof i==='string'&&!!i.trim())&&new Set(v).size===v.length
function exact(v:unknown,fields:string[]):v is Record<string,unknown>{return !!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===fields.length&&fields.every(k=>Object.hasOwn(v,k))}
function parsed(v:unknown):boolean {
  if(v===null)return true
  if(!exact(v,['year','month','day','precision','iso']))return false
  return typeof v.year==='number'&&Number.isInteger(v.year)&&typeof v.month==='number'&&Number.isInteger(v.month)&&v.month>=1&&v.month<=12&&typeof v.iso==='string'&&
    (v.precision==='month'&&v.day===null&&/^\d{4}-\d{2}$/.test(v.iso)||v.precision==='day'&&typeof v.day==='number'&&Number.isInteger(v.day)&&v.day>=1&&v.day<=31&&/^\d{4}-\d{2}-\d{2}$/.test(v.iso))
}
export function validStrip(v:unknown):v is StripPayload {
  if(!exact(v,['schema_version','medicine_name','batch_number','product_association','raw_expiry_text','expiry','confidence','confidence_kind','needs_review','issues','date_observations','confirmation_required']))return false
  return v.schema_version==='strip-expiry-v1'&&v.confirmation_required===true&&v.confidence_kind==='uncalibrated'&&
    text(v.medicine_name)&&text(v.batch_number)&&text(v.raw_expiry_text)&&confidence(v.confidence)&&typeof v.needs_review==='boolean'&&codes(v.issues)&&parsed(v.expiry)&&
    ['single_product','multiple_products','unclear'].includes(String(v.product_association))&&Array.isArray(v.date_observations)&&v.date_observations.every(o=>
      exact(o,['raw_label','raw_date_text','raw_text','association','confidence','uncertain','label_kind','parsed_date','parse_issues'])&&
      text(o.raw_label)&&text(o.raw_date_text)&&text(o.raw_text)&&['same_product','unclear'].includes(String(o.association))&&confidence(o.confidence)&&typeof o.uncertain==='boolean'&&
      ['expiry','manufacturing','batch','use_before','unknown'].includes(String(o.label_kind))&&parsed(o.parsed_date)&&codes(o.parse_issues))
}
export function parseStrip(v:unknown):StripSnapshot {
  const s=v as StripSnapshot
  if(!s||typeof s.analysis_id!=='string'||typeof s.revision!=='string'||s.scope!=='strip'||!['not_requested','running','succeeded','failed'].includes(s.status)||typeof s.reviewed!=='boolean'||typeof s.confirmed!=='boolean'||!Number.isInteger(s.extractor_invocations)||s.extractor_invocations<0||
    ![s.payload,s.original_payload].every(p=>p===null||validStrip(p))||(s.status==='succeeded'&&(!s.payload||!s.original_payload))||
    !(s.error===null||(typeof s.error?.category==='string'&&typeof s.error?.message==='string')))throw new ApiError('invalid_response','Invalid strip extraction contract. No date was inferred.')
  return s
}
export function editableStrip(p:StripPayload):StripEdits {
  return {medicine_name:p.medicine_name,batch_number:p.batch_number,product_association:p.product_association,
    date_observations:p.date_observations.map(o=>({raw_label:o.raw_label,raw_date_text:o.raw_date_text,raw_text:o.raw_text,association:o.association}))}
}
export function stripResultLabel(p:StripPayload):string {
  if(p.expiry)return 'Expiry text parsed — verify against packaging'
  if(p.issues.includes('conflicting_expiry_dates'))return 'Conflicting dates — no expiry selected'
  if(p.issues.includes('no_explicit_expiry'))return 'No explicit expiry found'
  return 'Expiry unresolved — clarification required'
}
export function createStripClient(fetcher:typeof fetch=(...args)=>fetch(...args)){
  async function request(path:string,method='GET',body?:unknown,signal?:AbortSignal){
    let response:Response
    try{response=await fetcher('/api'+path,{method,signal,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body instanceof File?{'Content-Type':body.type||'image/png'}:body!==undefined?{'Content-Type':'application/json'}:{})},body:body instanceof File?body:body===undefined?undefined:JSON.stringify(body)})}
    catch{throw new ApiError('network_error','Could not reach the strip API. No automatic retry was made.')}
    let value:unknown;try{value=await response.json()}catch{throw new ApiError('invalid_response','Strip API did not return JSON.')}
    if(!response.ok){const d=(value as {detail?:{category?:string;message?:string}})?.detail;throw new ApiError(d?.category??'api_error',d?.message??'Strip operation failed.',response.status)}
    return value
  }
  const path=(s:StripSnapshot)=>'/strips/'+encodeURIComponent(s.analysis_id)
  return {
    async upload(file:File,signal?:AbortSignal){await request('/session','POST',undefined,signal);return parseStrip(await request('/strips','POST',file,signal))},
    async status(s:StripSnapshot){return parseStrip(await request(path(s)))},
    async analyze(s:StripSnapshot,signal?:AbortSignal){return parseStrip(await request(path(s)+'/analyze','POST',{revision:s.revision},signal))},
    async invalidate(s:StripSnapshot){return parseStrip(await request(path(s)+'/invalidate','POST',{revision:s.revision}))},
    async review(s:StripSnapshot,edits:StripEdits){return parseStrip(await request(path(s)+'/review','PUT',{revision:s.revision,...edits}))},
    async confirm(s:StripSnapshot){return parseStrip(await request(path(s)+'/confirm','POST',{revision:s.revision}))},
    async clear(){await request('/strips/current','DELETE')},
  }
}
export const stripClient=createStripClient()
export type StripClient=ReturnType<typeof createStripClient>
