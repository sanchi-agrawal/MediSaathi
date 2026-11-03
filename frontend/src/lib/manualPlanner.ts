// On-screen user-entered demo plans only. No clinical inference or API client.
export const units=['tablet','capsule','mL','drop','dose'] as const
export interface ManualPlan{id:string;name:string;quantity:number;unit:typeof units[number];days:number;start:string;times:string[]}
export interface ManualEvent{planId:string;name:string;quantity:number;unit:ManualPlan['unit'];date:string;time:string}
export function dateValue(value:string){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(value))throw new Error('Choose a valid start date.')
 const date=new Date(value+'T00:00:00.000Z')
 if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value)throw new Error('Choose a valid start date.')
 return date
}
export function addDays(value:string,days:number){const date=dateValue(value);date.setUTCDate(date.getUTCDate()+days);const result=date.toISOString();if(!/^\d{4}-/.test(result))throw new Error('Choose a valid start date.');return result.slice(0,10)}
export function validatePlan(value:unknown):ManualPlan{
 const p=value as ManualPlan
 if(!p||typeof p.id!=='string'||!p.id||p.id.length>128||typeof p.name!=='string'||!p.name.trim()||p.name.length>100)throw new Error('Enter a medicine name (up to 100 characters).')
 if(typeof p.quantity!=='number'||!Number.isFinite(p.quantity)||p.quantity<=0||p.quantity>1000)throw new Error('Enter a positive quantity per dose, up to 1,000.')
 if(!units.includes(p.unit))throw new Error('Choose a supported unit.')
 if(!Number.isInteger(p.days)||p.days<1||p.days>366)throw new Error('Enter a duration from 1 to 366 days.')
 dateValue(p.start);addDays(p.start,p.days-1)
 if(!Array.isArray(p.times)||!p.times.length||p.times.length>12||p.times.some(t=>typeof t!=='string'||!/^([01]\d|2[0-3]):[0-5]\d$/.test(t))||new Set(p.times).size!==p.times.length)throw new Error('Choose 1–12 distinct valid clock times.')
 return {id:p.id,name:p.name.trim(),quantity:p.quantity,unit:p.unit,days:p.days,start:p.start,times:[...p.times].sort()}
}
export function validatePlans(value:unknown):ManualPlan[]{
 if(!Array.isArray(value)||value.length>20)throw new Error('This demo supports up to 20 medicines and 10,000 dose events.')
 const plans=value.map(validatePlan)
 if(new Set(plans.map(p=>p.id)).size!==plans.length||plans.reduce((n,p)=>n+p.days*p.times.length,0)>10000)throw new Error('This demo supports up to 20 medicines and 10,000 dose events.')
 return plans
}
export function eventsFor(plans:ManualPlan[]):ManualEvent[]{return validatePlans(plans).flatMap(p=>Array.from({length:p.days},(_,i)=>p.times.map(time=>({planId:p.id,name:p.name,quantity:p.quantity,unit:p.unit,date:addDays(p.start,i),time}))).flat()).sort((a,b)=>a.date.localeCompare(b.date)||a.time.localeCompare(b.time)||a.name.localeCompare(b.name))}
export const plannerKey=(owner:string)=>'medisaathi.manual-planner.v1:'+owner
export function restorePlans(owner:string|null){if(!owner)return {plans:[] as ManualPlan[],warning:false};try{const raw=sessionStorage.getItem(plannerKey(owner));return {plans:raw?validatePlans(JSON.parse(raw)):[],warning:false}}catch{return {plans:[] as ManualPlan[],warning:true}}}
export function savePlans(owner:string|null,plans:ManualPlan[]){if(!owner)return false;try{sessionStorage.setItem(plannerKey(owner),JSON.stringify(validatePlans(plans)));return true}catch{return false}}
