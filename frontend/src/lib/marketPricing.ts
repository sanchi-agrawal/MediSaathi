import { ApiError } from './prescriptions'
export interface MarketMedicine{item_id:string;name:string;composition:string|null;strength:string|null;form:string|null;manufacturer:string|null;pack_size:null}
export interface MarketObservation{observation_id:string;item_id:string;platform:string;platform_name:string;listed_name:string;mrp_inr:string|null;selling_price_inr:string|null;availability:'in_stock'|'out_of_stock';city:string;url:string;category:string|null;verification_status:'provisional';historical:true;observed_at:null;pack_size:null;warnings:string[]}
export interface MarketResult{state:'listed'|'no_match';item:MarketMedicine|null;observations:MarketObservation[];comparisons_enabled:false;provisional:true}
async function request(path:string,body?:unknown){
 let r:Response
 try{r=await fetch('/api'+path,{method:body===undefined?'GET':'POST',credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch{throw new ApiError('network_error','Medicine listings are unavailable. Please try again.')}
 let value;try{value=await r.json()}catch{throw new ApiError('invalid_response','Pricing API did not return JSON. Check the API server and proxy.')}
 if(!r.ok)throw new ApiError(value?.detail?.category||'pricing_unavailable',r.status===401?'Sign in to view medicine listings.':r.status===404?'Restart the backend to load medicine listings.':'Medicine listings are unavailable. Please try again.',r.status)
 return value
}
export const marketClient={
 async catalogue():Promise<MarketMedicine[]>{await request('/session',{});const v=await request('/pricing/listings/catalogue');if(v.schema_version!=='market-listed-v1'||!Array.isArray(v.items)||v.comparisons_enabled!==false||!v.items.every((m:MarketMedicine)=>typeof m.item_id==='string'&&typeof m.name==='string'&&m.pack_size===null))throw new ApiError('invalid_response','Invalid medicine catalogue response.');return v.items},
 async lookup(item_id:string):Promise<MarketResult>{const v=await request('/pricing/listings/lookup',{item_id});if(v.schema_version!=='market-listed-v1'||!['listed','no_match'].includes(v.state)||v.comparisons_enabled!==false||v.provisional!==true||!Array.isArray(v.observations)||v.item&&v.item.item_id!==item_id||!v.observations.every((o:MarketObservation)=>o.item_id===item_id&&o.verification_status==='provisional'&&o.pack_size===null&&o.historical===true&&o.observed_at===null&&Array.isArray(o.warnings)&&[o.selling_price_inr,o.mrp_inr].every(p=>p===null||typeof p==='string'&&/^\d+\.\d{2}$/.test(p))&&safeListing(o.url)))throw new ApiError('invalid_response','Invalid medicine listing response.');return v},
}
export function safeListing(value:string){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&(!u.port||u.port==='443')&&['1mg.com','www.1mg.com','pharmeasy.in','www.pharmeasy.in','apollo247.com','www.apollo247.com','apollopharmacy.in','www.apollopharmacy.in'].includes(u.hostname)}catch{return false}}
