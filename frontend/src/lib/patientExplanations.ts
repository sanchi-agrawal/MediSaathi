import { ApiError } from './prescriptions'
import type { AnalysisSnapshot } from './prescriptions'
export interface PatientExplanation{status:'explained'|'identity_uncertain';record_index:number;language:'en'|'hi';analysis_id:string;revision:string;medicine_name:string|null;ingredient:string|null;cached:boolean;sections:{key:string;text:string}[];sources:string[];prescription:{original_medicine_text:string|null;confirmed_linked_instruction:{raw_text:string|null}|null}}
export async function explainMedicine(source:AnalysisSnapshot,record_index:number,language:'en'|'hi'):Promise<PatientExplanation>{
 let response:Response
 try{response=await fetch(`/api/prescriptions/${encodeURIComponent(source.analysis_id)}/medicines/explain`,{method:'POST',credentials:'include',cache:'no-store',headers:{'Content-Type':'application/json','X-MediSaathi-Action':'review'},body:JSON.stringify({revision:source.revision,record_index,language})})}catch{throw new ApiError('network_error','Could not reach the explanation service. No automatic retry was made.')}
 let value:unknown;try{value=await response.json()}catch{throw new ApiError('invalid_response','The explanation API did not return JSON.')}
 if(!response.ok){const d=(value as {detail?:{category?:string;message?:string}}).detail;if(response.status===404||response.status===405)throw new ApiError('api_route_unavailable','The per-medicine explanation endpoint is not loaded. Restart the current FastAPI backend and check the Vite proxy.',response.status);throw new ApiError(d?.category||'explanation_unavailable',d?.message||'Medicine explanation unavailable. No automatic retry was made.',response.status)}
 const p=value as PatientExplanation
 if(p.analysis_id!==source.analysis_id||p.revision!==source.revision||p.record_index!==record_index||p.language!==language||!['explained','identity_uncertain'].includes(p.status)||!Array.isArray(p.sections)||!p.sections.every(s=>typeof s.key==='string'&&typeof s.text==='string')||!Array.isArray(p.sources)||!p.sources.every(s=>typeof s==='string'&&s.startsWith('https://'))||!p.prescription)throw new ApiError('invalid_response','The medicine explanation response was invalid.')
 return p
}
