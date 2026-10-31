import { ApiError } from './prescriptions'
import type { AnalysisSnapshot } from './prescriptions'
import type { ScheduleContext } from './scheduling'
export interface Candidate {candidate_id:string;name:string;salt:string|null;strength:string|null;form:string|null;score:number;review_reasons:string[];identity_verified:false}
export interface MatchRecord {medicine_ref:string;name:string|null;state:'review_required'|'unmatched';candidates:Candidate[];selected:string|null;message:string}
export interface Matches {analysis_id:string;revision:string;state:'not_requested'|'ready';records:MatchRecord[]}
export interface PriceItem {kind:'medicine'|'lab';item_id:string;name:string;pack_size:string|null}
export interface PriceResult {state:'unavailable'|'no_match'|'ambiguous';item:PriceItem|null;candidates:PriceItem[];quotes:never[];comparisons:never[];reasons:string[];message:string;comparisons_enabled:false;historical:true}
export interface Preview {analysis_id:string;medicine_revision:string;instruction_revision:string;scheduling_revision:string;association_id:string;state:'ready'|'no_upcoming_doses';timezone:'Asia/Kolkata';window_days:number;clock_times:Record<string,string>;doses:{slot:string;due_at:string;amount:number;unit:string}[];refill_notes:{name:string;level:string;message:string}[];notifications_enabled:false;notice:string}
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)
const strings=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(s=>typeof s==='string')
function invalid():never{throw new ApiError('invalid_response','The integration response could not be validated. No result is displayed.')}
function priceItem(v:unknown):v is PriceItem{return object(v)&&['medicine','lab'].includes(String(v.kind))&&typeof v.item_id==='string'&&typeof v.name==='string'&&(v.pack_size===null||typeof v.pack_size==='string')}
export function parseMatches(v:unknown):Matches{
  if(!object(v)||typeof v.analysis_id!=='string'||typeof v.revision!=='string'||!['ready','not_requested'].includes(String(v.state))||!Array.isArray(v.records))return invalid()
  for(const r of v.records){if(!object(r)||typeof r.medicine_ref!=='string'||!(r.name===null||typeof r.name==='string')||!['unmatched','review_required'].includes(String(r.state))||typeof r.message!=='string'||!Array.isArray(r.candidates))return invalid()
    for(const c of r.candidates)if(!object(c)||typeof c.candidate_id!=='string'||!c.candidate_id.startsWith('person2:catalogue:')||typeof c.name!=='string'||!['salt','strength','form'].every(k=>c[k]===null||typeof c[k]==='string')||typeof c.score!=='number'||!Number.isFinite(c.score)||c.score<0||c.score>100||!strings(c.review_reasons)||c.identity_verified!==false)return invalid()
    if(r.selected!==null&&!r.candidates.some((c:Candidate)=>c.candidate_id===r.selected))return invalid()
  }return v as unknown as Matches
}
export function parsePrice(v:unknown):PriceResult{
  if(!object(v)||!['unavailable','no_match','ambiguous'].includes(String(v.state))||!(v.item===null||priceItem(v.item))||!Array.isArray(v.candidates)||!v.candidates.every(priceItem)||!Array.isArray(v.quotes)||v.quotes.length||!Array.isArray(v.comparisons)||v.comparisons.length||!strings(v.reasons)||typeof v.message!=='string'||v.comparisons_enabled!==false||v.historical!==true)return invalid()
  return v as unknown as PriceResult
}
export function createTeamClient(fetcher:typeof fetch=(...a)=>fetch(...a)){
  async function request(path:string,method='GET',body?:unknown):Promise<unknown>{
    let res:Response;try{res=await fetcher('/api'+path,{method,credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch{throw new ApiError('network_error','Integration API unavailable. No automatic retry was made.')}
    let v:unknown;try{v=await res.json()}catch{return invalid()}
    if(!res.ok){const d=object(v)&&object(v.detail)?v.detail:null;throw new ApiError(d&&typeof d.category==='string'?d.category:'api_error',d&&typeof d.message==='string'?d.message:'The integration request failed.',res.status)}return v
  }
  const path=(s:AnalysisSnapshot)=>'/prescriptions/'+encodeURIComponent(s.analysis_id)
  const match=(v:unknown,s:AnalysisSnapshot)=>{const m=parseMatches(v);if(m.analysis_id!==s.analysis_id||m.revision!==s.revision)throw new ApiError('stale_result','Medicine revision changed. Reload current records.');return m}
  return {
    async current(s:AnalysisSnapshot){return match(await request('/matching/current'),s)},
    async match(s:AnalysisSnapshot){return match(await request(path(s)+'/matching','POST',{revision:s.revision}),s)},
    async select(s:AnalysisSnapshot,medicine_ref:string,candidate_id:string){return match(await request(path(s)+'/matching/selection','POST',{revision:s.revision,medicine_ref,candidate_id}),s)},
    async catalogue(kind:'medicine'|'lab'){
      await request('/session','POST');const v=await request('/pricing/catalogue?kind='+kind)
      if(!object(v)||v.verified_delhi_quote_count!==0||v.comparisons_enabled!==false||!Array.isArray(v.items)||!v.items.every(priceItem))return invalid();return v.items
    },
    async price(kind:'medicine'|'lab',query:{item_id?:string;name?:string}){return parsePrice(await request('/pricing/lookup','POST',{kind,...query}))},
    async preview(s:ScheduleContext,clock_times:Record<string,string>):Promise<Preview>{
      const binding={medicine_revision:s.medicine_revision,instruction_revision:s.instruction_revision,scheduling_revision:s.scheduling_revision,association_id:s.association?.association_id}
      const v=await request('/prescriptions/'+encodeURIComponent(s.analysis_id)+'/reminder-preview','POST',{...binding,clock_times})
      if(!object(v)||v.analysis_id!==s.analysis_id||!Object.entries(binding).every(([k,val])=>v[k]===val)||v.notifications_enabled!==false||v.timezone!=='Asia/Kolkata'||v.window_days!==7||!['ready','no_upcoming_doses'].includes(String(v.state))||typeof v.notice!=='string'||!object(v.clock_times)||JSON.stringify(v.clock_times)!==JSON.stringify(clock_times)||!Array.isArray(v.doses)||!v.doses.every(d=>object(d)&&typeof d.slot==='string'&&Object.hasOwn(clock_times,d.slot)&&typeof d.due_at==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+05:30$/.test(d.due_at)&&Number.isFinite(Date.parse(d.due_at))&&typeof d.amount==='number'&&Number.isFinite(d.amount)&&d.amount>0&&typeof d.unit==='string')||!Array.isArray(v.refill_notes)||!v.refill_notes.every(n=>object(n)&&typeof n.message==='string'))return invalid()
      return v as unknown as Preview
    },
  }
}
export const teamClient=createTeamClient()
export type TeamClient=ReturnType<typeof createTeamClient>
