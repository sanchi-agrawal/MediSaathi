import type { MedicineRecord,InstructionEnvelope } from './api'
import { ApiError } from './prescriptions'
import { notifySchedulingChanged } from './workflowEvents'
export const namedSlots=['morning','afternoon','evening','night','bedtime'] as const
export type NamedSlot=typeof namedSlots[number]
export interface ReviewPair{medicine_ref:string;instruction_id:string|null;slots:NamedSlot[];status?:string}
export interface CourseMedicine{medicine_ref:string;name:string|null;dose_quantity:string|null;dose_unit:string|null;duration:string|null;food_timing:string|null;original_text:string|null;confirmed_slots:NamedSlot[];issues:string[];review_path:string}
export interface ConfirmedPrescription{snapshot_id:string;analysis_id:string;medicine_revision:string;instruction_revision:string;confirmed:true;medicines:CourseMedicine[]}
export interface Course{snapshot_id:string;start_date:string;blocked:CourseMedicine[];results:{medicine_ref:string;slots:NamedSlot[];result:{name:string;start_date:string;end_date:string;duration_days:number;unit:string;doses_by_slot:Record<string,number>;units_per_day:number;total_units:number;refill_date:string|null}}[]}
export interface WholeReview{analysis_id:string;medicine_revision:string;instruction_revision:string;records:MedicineRecord[];instructions:InstructionEnvelope|null;pairs:ReviewPair[];snapshot:ConfirmedPrescription|null;medicine_status:string;instruction_status:string;recognition_mode:string;review_requirements:{record_index:number;can_resolve:boolean;missing_fields:string[];unsupported_fields:string[];confidence_state:string}[]}
async function request<T>(path:string,body?:unknown):Promise<T>{
  let response:Response
  try{response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)})}catch{throw new ApiError('network_error','Could not reach the local Python API.')}
  let data:unknown
  try{data=await response.json()}catch{throw new ApiError('invalid_response','The API did not return JSON.')}
  if(!response.ok){const detail=(data as {detail?:{category?:string;message?:string}}).detail;throw new ApiError(detail?.category||'api_error',detail?.message||'The request failed.',response.status)}
  if(body!==undefined)notifySchedulingChanged()
  return data as T
}
export const confirmedClient={
  review:()=>request<WholeReview>('/prescription-review/current'),
  current:()=>request<{snapshot:ConfirmedPrescription|null;course:Course|null}>('/confirmed-prescription/current'),
  confirm:(review:WholeReview,resolved_records:number[],resolved_instructions:string[]=[])=>request<ConfirmedPrescription>(`/prescriptions/${encodeURIComponent(review.analysis_id)}/review/confirm-all`,{medicine_revision:review.medicine_revision,instruction_revision:review.instruction_revision,records:review.records,instructions:review.instructions,pairs:review.pairs.filter(p=>p.instruction_id).map(({medicine_ref,instruction_id,slots})=>({medicine_ref,instruction_id,slots})),resolved_records,resolved_instructions,acknowledge:true}),
  generate:(snapshot_id:string,start_date:string)=>request<Course>('/confirmed-prescription/generate',{snapshot_id,start_date}),
}
