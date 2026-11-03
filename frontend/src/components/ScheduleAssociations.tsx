import {useEffect,useRef,useState} from 'react'
import {useLanguage,translateError} from '../lib/language'
import {ApiError} from '../lib/prescriptions'
import {notifySchedulingChanged,subscribeSchedulingChanges} from '../lib/workflowEvents'
import {schedulingClient} from '../lib/scheduling'
import type {ScheduleContext,SchedulingClient} from '../lib/scheduling'
export default function ScheduleAssociations({client=schedulingClient}:{client?:SchedulingClient}){
 const {t}=useLanguage();const [data,setData]=useState<ScheduleContext|null>(null),[medicine,setMedicine]=useState(''),[instruction,setInstruction]=useState(''),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false);const lock=useRef(false),active=useRef(true)
 const [error,setError]=useState<unknown>(null),[saved,setSaved]=useState(false)
 const [notationAck,setNotationAck]=useState<Record<string,boolean>>({})
 useEffect(()=>setNotationAck({}),[data?.scheduling_revision])
 async function confirmNotation(association:NonNullable<ScheduleContext['association']>){
  if(!data||lock.current||!notationAck[association.association_id])return;lock.current=true;setBusy(true);setError(null)
  try{
   const fresh=await client.current();if(!sameSource(data,fresh)||!fresh.ready)throw new ApiError('stale_result',t('Refresh confirmed links'))
   const proposal=fresh.automatic?.find(e=>e.association?.association_id===association.association_id)?.proposed_slots??[]
   if(client.confirmSlots){if(!proposal.length)throw new ApiError('unavailable',t('Named timing proposals are unavailable. Restart the current API.'));await client.confirmSlots({...fresh,association},proposal)}
   else if(client.confirmNotation)await client.confirmNotation({...fresh,association})
   else throw new ApiError('unavailable',t('Refresh confirmed links'))
   const verified=await client.current();const entry=verified.automatic?.find(e=>e.association?.association_id===association.association_id)
   if(!sameSource(fresh,verified)||!entry||entry.issues.includes('notation_confirmation_required')||client.confirmSlots&&JSON.stringify(entry.confirmed_slots)!==JSON.stringify(proposal))throw new ApiError('stale_result',t('Refresh confirmed links'))
   if(active.current){setData(verified);notifySchedulingChanged()}
  }catch(e){if(active.current)setError(e)}finally{lock.current=false;if(active.current)setBusy(false)}
 }
 const links=(s:ScheduleContext)=>s.associations??(s.association?[s.association]:[])
 const sameSource=(a:ScheduleContext,b:ScheduleContext)=>a.analysis_id===b.analysis_id&&a.medicine_revision===b.medicine_revision&&a.instruction_revision===b.instruction_revision
 async function reload(){try{const fresh=await client.current();if(active.current){setData(fresh);setError(null);setFailed(false)}}catch(e){if(active.current){setError(e);setFailed(true)}}}
 useEffect(()=>{active.current=true;client.current().then(s=>{if(active.current)setData(s)}).catch(()=>{if(active.current)setFailed(true)});return()=>{active.current=false}},[client])
 useEffect(()=>subscribeSchedulingChanges(()=>{if(!lock.current)void reload()}),[client])
 useEffect(()=>{if(data&&window.location.hash==='#schedule-associations'){const target=document.getElementById('schedule-associations');target?.scrollIntoView?.({block:'center'});target?.focus()}},[data])
 async function associate(ref:string,id:string){
  if(!data||!ref||!id||lock.current)return;lock.current=true;setBusy(true);setFailed(false);setError(null);setSaved(false)
  try{
   const current=await client.current()
   if(!sameSource(data,current)||!current.ready)throw new ApiError('stale_result',t('Prescription confirmation changed. Review current records before linking.'))
   const response=await client.associate(current,ref,id)
   const persisted=await client.current()
   const contains=(s:ScheduleContext)=>links(s).some(a=>a.medicine_ref===ref&&a.instruction_id===id)
   if(!sameSource(response,current)||!sameSource(persisted,current)||!persisted.ready||!contains(response)||!contains(persisted)||links(current).some(a=>!links(persisted).some(b=>a.association_id===b.association_id)))throw new ApiError('stale_result',t('The confirmed link was not returned by the current server workspace. Refresh before continuing.'))
   if(active.current){setData(persisted);setSaved(true);setMedicine('');setInstruction('');notifySchedulingChanged()}
  }catch(e){if(active.current){setFailed(true);setError(e)}}finally{lock.current=false;if(active.current)setBusy(false)}
 }
 async function clear(){if(!data||lock.current)return;lock.current=true;setBusy(true);setSaved(false);setError(null);try{const current=await client.current();if(!sameSource(data,current))throw new ApiError('stale_result',t('Prescription confirmation changed. Review current records before linking.'));const fresh=await client.clear(current);if(active.current){setData(fresh);setMedicine('');setInstruction('');notifySchedulingChanged()}}catch(e){if(active.current)setError(e)}finally{lock.current=false;if(active.current)setBusy(false)}}
 const state=data?.instruction_state
 const conflict=!!data&&links(data).some(a=>a.medicine_ref===medicine||a.instruction_id===instruction)
 return <section className="panel" id="schedule-associations" tabIndex={-1}><h2>{t('Confirm medicine–instruction links')}</h2><p>{t('Exact, unique medicine names can suggest a pair. Check the original instruction and explicitly confirm each link. Suggestions are not approved associations.')}</p>
 {failed&&<p role="status">{t('Could not load or save associations. Refresh and check current confirmations.')}</p>}
 {error!=null&&<p className="error-message" role="alert">{translateError(error)}</p>}
 {saved&&<p role="status">{t('Link saved and verified in the current workspace.')}</p>}
 {conflict&&<p>{t('A selected record already has a confirmed link. Clear links explicitly before changing a pair.')}</p>}
 {!!data&&links(data).length>0&&<button className="button secondary" disabled={busy} onClick={()=>void clear()}>{t('Clear all links and schedules to correct a pair')}</button>}
 <button className="button secondary" disabled={busy} onClick={()=>void reload()}>{t('Refresh confirmed links')}</button>
 {!!data&&links(data).length>0&&<ul aria-label={t('Confirmed medicine-instruction links')}>{links(data).map(a=><li key={a.association_id}><span aria-hidden="true">✓ </span><strong>{data.medicines[Number(a.medicine_ref.slice(9))-1]?.name}</strong><p translate="no">{data.instructions.find(i=>i.instruction_id===a.instruction_id)?.raw_text}</p><span>{t('Association confirmed.')}</span><p>{t('Confirmed time-of-day slots')}: {data.automatic?.find(e=>e.association?.association_id===a.association_id)?.confirmed_slots?.map(slot=>t(slot)).join(', ')||t('Not yet confirmed')}</p>{data.automatic?.find(e=>e.association?.association_id===a.association_id)?.issues.includes('notation_confirmation_required')&&<div><p>{t('Original frequency text')}: {data.instructions.find(i=>i.instruction_id===a.instruction_id)?.frequency_raw}</p><p>{t('Proposed time-of-day slots')}: {data.automatic?.find(e=>e.association?.association_id===a.association_id)?.proposed_slots?.map(slot=>t(slot)).join(', ')||t('Additional review required')}</p><label><input type="checkbox" checked={!!notationAck[a.association_id]} onChange={e=>setNotationAck({...notationAck,[a.association_id]:e.target.checked})} disabled={busy}/>{t('I verified these time-of-day slots against the original prescription. Dose, unit and duration are confirmed separately.')}</label><button className="button secondary" disabled={busy||!notationAck[a.association_id]} onClick={()=>void confirmNotation(a)}>{t('Confirm named timing slots')}</button></div>}</li>)}</ul>}
 {data&&!data.ready&&<p>{t(state?.status==='not_requested'?'Dosage instructions have not been extracted. Select Dosage instructions and explicitly analyze that section.':state?.status==='failed'?'Instruction extraction failed. Return to the instruction section; no instructions were invented.':!state?.confirmed?'Save and confirm the extracted dosage instructions before preparing links.':'Confirm medicines and instructions independently before linking records.')}</p>}
 {data?.ready&&<>{data.association_proposals?.filter(p=>p.status!=='confirmed').map(p=>{const m=data.medicines[Number(p.medicine_ref.slice(9))-1];const ins=data.instructions.find(i=>i.instruction_id===p.instruction_id);return <div className="source-text" key={p.medicine_ref}><h3>{m?.name??t('Unknown medicine')}</h3>{ins&&<><p translate="no">{ins.raw_text}</p><p>{ins.dose_quantity_raw??t('Unknown / not recorded')} {ins.dose_unit_raw??''} · {ins.frequency_raw??t('Unknown / not recorded')} · {ins.timing_raw??t('Unknown / not recorded')} · {ins.duration_raw??t('Unknown / not recorded')}</p></>}{p.status==='proposed'?<button className="button secondary" disabled={busy} onClick={()=>void associate(p.medicine_ref,p.instruction_id!)}>{t('Confirm suggested link')}: {m?.name}</button>:<p>{t(p.status==='confirmed'?'Association confirmed.':p.status==='missing_instruction'?'No confirmed instruction record exists for this medicine.':p.status==='ambiguous'?'More than one pairing is possible. Compare the source and choose the correct pair below.':'No exact name match. Compare the source and explicitly choose a pair below; do not guess.')}</p>}</div>})}
 <details><summary>{t('Choose or correct a medicine–instruction link')}</summary><div className="medicine-fields"><label>{t('Confirmed medicine')}<select value={medicine} onChange={e=>setMedicine(e.target.value)} disabled={busy}><option value="">{t('Choose explicitly')}</option>{data.medicines.map((m,i)=><option key={i} value={'medicine_'+String(i+1).padStart(3,'0')}>{m.name??t('Unknown medicine')} · {m.raw_text}</option>)}</select></label><label>{t('Confirmed instruction')}<select value={instruction} onChange={e=>setInstruction(e.target.value)} disabled={busy}><option value="">{t('Choose explicitly')}</option>{data.instructions.map(i=><option key={i.instruction_id} value={i.instruction_id}>{i.raw_text}</option>)}</select></label></div><button className="button secondary" disabled={busy||!medicine||!instruction||conflict} onClick={()=>void associate(medicine,instruction)}>{t('Associate selected records')}</button></details>
 </>}
 </section>
}
