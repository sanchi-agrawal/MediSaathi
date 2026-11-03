import {useEffect,useRef,useState} from 'react'
import {useLanguage} from '../lib/language'
import {manualUnitHindi} from '../lib/manualPlannerHindi'
import {plannerPrefillClient,restorePlannerTimes,savePlannerTimes,sourcePlanId} from '../lib/plannerPrefill'
import type {PlannerSource,PlannerTimes,PrefillMedicine} from '../lib/plannerPrefill'
import {validatePlan} from '../lib/manualPlanner'
import type {ManualPlan} from '../lib/manualPlanner'
import {subscribeSchedulingChanges,subscribeSchedulingInvalidation} from '../lib/workflowEvents'

export default function PrescriptionPlannerPrefill({owner,onGenerate}:{owner:string;onGenerate:(plans:ManualPlan[])=>void}){
 const {t,language}=useLanguage();const [source,setSource]=useState<PlannerSource|null>(null),[prefs,setPrefs]=useState(()=>restorePlannerTimes(owner)),[busy,setBusy]=useState(false),[error,setError]=useState(''),[storage,setStorage]=useState(false)
 const version=useRef(0),lock=useRef(false)
 useEffect(()=>{setStorage(!savePlannerTimes(owner,prefs))},[owner,prefs])
 useEffect(()=>{let active=true;async function refresh(){if(lock.current)return;const n=++version.current;setBusy(true);try{const data=await plannerPrefillClient.current(owner);if(active&&n===version.current){setSource(data);setError('')}}catch{if(active&&n===version.current){setSource(null);setError('Prescription prefill is unavailable. You can still add medicines manually.')}}finally{if(active&&n===version.current)setBusy(false)}}
  void refresh();const stop=subscribeSchedulingChanges(()=>void refresh());const invalidate=subscribeSchedulingInvalidation(()=>{version.current++;setSource(null);void refresh()});const focus=()=>void refresh();window.addEventListener('focus',focus)
  return()=>{active=false;version.current++;stop();invalidate();window.removeEventListener('focus',focus)}
 },[owner])
 const values=(m:PrefillMedicine):PlannerTimes=>{const existing=source?prefs[sourcePlanId(source,m)]:undefined;return {start:existing?.start||'',times:existing?.times?.length?existing.times:['']}}
 function change(m:PrefillMedicine,next:PlannerTimes){if(!source)return;setPrefs(all=>({...all,[sourcePlanId(source,m)]:next}));setError('')}
 // This is an on-screen plan entered by the user, not a clinically approved schedule.
 // The clinical eligibility flag may be false solely because a frequency was not established.
 const ready=(m:PrefillMedicine)=>!!m.name&&m.quantity!==null&&m.unit!==null&&m.days!==null&&!m.missing.some(v=>['medicine_review','instruction_review','instruction_uncertainty','medicine_name','dose_quantity','dose_unit','duration_days'].includes(v))
 const complete=source?.medicines.filter(m=>ready(m)&&values(m).start&&values(m).times.length>0&&values(m).times.every(Boolean))||[]
 async function generate(){if(lock.current||!source||!complete.length)return;lock.current=true;setBusy(true);setError('');const n=version.current
  try{const fresh=await plannerPrefillClient.current(owner);if(n!==version.current)return
   if(fresh.analysis_id!==source.analysis_id||complete.some(m=>!fresh.medicines.some(v=>v.medicine_ref===m.medicine_ref&&ready(v)&&v.fingerprint===m.fingerprint))){setSource(fresh);throw new Error('Reviewed prescription details changed. Check the current cards before generating.')}
   const plans=complete.map(m=>validatePlan({id:sourcePlanId(fresh,m),name:m.name,quantity:m.quantity,unit:m.unit,days:m.days,...values(m)}))
   onGenerate(plans)
  }catch(e){if(n===version.current)setError(e instanceof Error?e.message:'Prescription prefill is unavailable. You can still add medicines manually.')}finally{lock.current=false;setBusy(false)}
 }
 const labels:Record<string,string>={medicine_review:'Medicine review has not been saved.',instruction_review:'Instruction review has not been saved.',instruction_uncertainty:'The reviewed instruction contains unresolved uncertainty.',medicine_name:'Medicine name',dose_quantity:'Quantity per dose',dose_unit:'Unit',duration_days:'Duration in days'}
 const unit=(v:string)=>language==='hi'?(manualUnitHindi[v]||v):v
 return <section className="panel prescription-planner"><div className="manual-actions"><h2>{t('Reviewed prescription details')}</h2><a className="button secondary" href="#manual-medicine-form">{t('Add Medicine Manually')}</a></div><p>{t('Optional prefill for this demo planner. These values come from your saved review; no new confirmation or real-world action is created.')}</p>{busy&&<p role="status">{t('Loading reviewed medicines…')}</p>}{error&&<p role="alert">{t(error)}</p>}{storage&&<p role="status">{t('Tab storage is unavailable. Your plan is visible now but may not survive navigation or refresh.')}</p>}
 {!busy&&!source?.medicines.length&&<p>{t('No reviewed prescription is available. You can add medicines manually.')}</p>}
 <p>{t('Demo schedule based on your selected times. Follow the original prescription for actual medication use.')}</p>
 <div className="manual-summary">{source?.medicines.map(m=>{const p=values(m);return <article className="source-text" key={m.medicine_ref}><h3>{m.name||t('Unknown medicine')}</h3><dl><div><dt>{t('Quantity per dose')}</dt><dd>{m.quantity??t('Not recorded')} {m.unit?unit(m.unit):''}</dd></div><div><dt>{t('Duration in days')}</dt><dd>{m.days??t('Not recorded')}</dd></div>{m.administrations_per_day!==null&&<div><dt>{t('Reviewed daily administrations (reference only)')}</dt><dd>{m.administrations_per_day}</dd></div>}</dl>{ready(m)?<><label>{t('{0} — start date',[m.name])}<input type="date" value={p.start} disabled={busy} onChange={e=>change(m,{...p,start:e.target.value})}/></label><fieldset><legend>{t('Preferred daily times')}</legend><div className="manual-times">{p.times.map((clock,i)=><div key={i}><label>{t('{0} — time {1}',[m.name,i+1])}<input type="time" value={clock} disabled={busy} onChange={e=>change(m,{...p,times:p.times.map((v,index)=>index===i?e.target.value:v)})}/></label><button type="button" className="button secondary" aria-label={t('Remove time {0} for {1}',[i+1,m.name])} disabled={busy} onClick={()=>change(m,{...p,times:p.times.filter((_,index)=>index!==i)})}>×</button></div>)}</div><button type="button" className="button secondary" disabled={busy||p.times.length>=12} onClick={()=>change(m,{...p,times:[...p.times,'']})}>{t('Add Time')}</button></fieldset></>:<p>{t('Missing or unresolved information')}: {m.missing.filter(v=>v!=='administrations_per_day'&&v!=='instruction_relationship').map(v=>t(labels[v]||'The reviewed instruction contains unresolved uncertainty.')).join(' · ')}</p>}</article>})}</div>
 {!!source?.medicines.length&&<><p>{t('Only complete medicines with a selected date and all times are included. Other medicines remain available for manual planning.')}</p><button className="button" disabled={busy||!complete.length} onClick={()=>void generate()}>{t('Generate Schedule from Reviewed Medicines')}</button></>}
 </section>
}
