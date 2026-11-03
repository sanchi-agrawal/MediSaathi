import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage,translateError } from '../lib/language'
import { PageHeading,Notice } from '../components/ui'
import { clockClient } from '../lib/clockScheduling'
import { ApiError } from '../lib/prescriptions'
import type { ClockState,ClockCourse,ClockMedicine } from '../lib/clockScheduling'
import { blockerEnglish } from '../lib/confirmedWorkflowHindi'
import { subscribeSchedulingInvalidation,subscribeSchedulingChanges } from '../lib/workflowEvents'
import '../clock-scheduling.css'

function ReviewDetails({details}:{details:ClockMedicine['review_details']}){
 const {t}=useLanguage()
 if(!details)return null
 const labels:Record<string,string>={raw_text:'Original medicine text',name:'Medicine name',salt:'Printed ingredient',strength:'Written strength',form:'Form',frequency_pattern:'Written frequency',duration_days:'Duration in days',timing:'Written timing',confidence:'Extraction confidence (uncalibrated)'}
 return <>{details.missing_fields.length>0&&<p>{t('Missing fields')}: {details.missing_fields.map(f=>t(labels[f]||f)).join(', ')}</p>}{details.unsupported_fields.length>0&&<p>{t('Values to verify against the source')}: {details.unsupported_fields.map(f=>t(labels[f]||f)).join(', ')}</p>}<p>{t(details.confidence_state==='unknown'?'Original confidence is unknown and cannot be invented.':details.confidence_state==='low'?'Original confidence is below the existing review threshold.':'Original confidence meets the existing threshold; it is not proof of medical accuracy.')}</p></>
}

export default function ClockSchedule(){
 const {t,language}=useLanguage()
 const [state,setState]=useState<ClockState|null>(null),[start,setStart]=useState(''),[times,setTimes]=useState<Record<string,string[]>>({}),[course,setCourse]=useState<ClockCourse|null>(null)
 const [busy,setBusy]=useState(false),[error,setError]=useState<Error|string>('');const epoch=useRef(0),lock=useRef(false)
 const binding=useRef('')
 function adopt(value:ClockState){
  const nextBinding=JSON.stringify([value.analysis_id,value.medicine_revision,value.instruction_revision,value.scheduling_revision])
  const unchanged=binding.current===nextBinding;binding.current=nextBinding
  setState(value)
  // A focus refresh must not discard unsaved clock preferences for the same
  // confirmed source. Source changes still revoke all old preferences/results.
  if(unchanged)return
  setCourse(value.course)
  setStart(value.course?.start_date||'')
  setTimes(value.course?Object.fromEntries(value.course.medicines.map(m=>[m.medicine_ref,m.clock_times])):{})
 }
 useEffect(()=>{let active=true;async function refresh(){
  // A focus GET must not supersede the in-flight generation POST's result.
  // Prescription invalidation still revokes its epoch immediately below.
  if(lock.current)return
  const version=++epoch.current;setBusy(true)
  try{const value=await clockClient.current();if(active&&version===epoch.current){adopt(value);setError('')}}catch(e){if(active&&version===epoch.current){
   // Temporary network/provider failures do not revoke a confirmed source.
   // Authentication expiry or a missing/stale workspace does revoke the view.
   if(e instanceof ApiError&&(e.status===401||e.status===409)){binding.current='';setState(null);setCourse(null);setTimes({});setStart('')}
   setError(e instanceof Error?e:String(e))
  }}finally{if(active&&version===epoch.current)setBusy(false)}
 }
 void refresh();const stop=subscribeSchedulingInvalidation(()=>{epoch.current++;binding.current='';setState(null);setCourse(null);setTimes({});setStart('');setBusy(lock.current)});const changed=subscribeSchedulingChanges(()=>void refresh());const focus=()=>void refresh();window.addEventListener('focus',focus)
 return()=>{active=false;epoch.current++;stop();changed();window.removeEventListener('focus',focus)}},[])
 const eligible=state?.medicines.filter(m=>m.eligible)||[]
 const complete=eligible.length>0&&!!start&&eligible.every(m=>(times[m.medicine_ref]||[]).length===m.administrations_per_day&&(times[m.medicine_ref]||[]).every(Boolean))
 const dateLabel=(value:string)=>new Intl.DateTimeFormat(language==='hi'?'hi-IN':'en-IN',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'))
 async function generate(){if(lock.current||!state||!complete)return;lock.current=true;setBusy(true);setError('');const version=epoch.current
  try{const fresh=await clockClient.current();if(version!==epoch.current)return;if(fresh.analysis_id!==state.analysis_id||fresh.medicine_revision!==state.medicine_revision||fresh.instruction_revision!==state.instruction_revision||fresh.scheduling_revision!==state.scheduling_revision){adopt(fresh);throw new Error(t('Prescription changed. Return to review before generating.'))}const value=await clockClient.generate(fresh,start,times);if(version===epoch.current)setCourse(value)}catch(e){if(version===epoch.current){if(e instanceof ApiError&&(e.status===401||e.status===409)){binding.current='';setState(null);setCourse(null);setTimes({});setStart('')}setError(e instanceof Error?e:String(e))}}finally{lock.current=false;setBusy(false)}}
 const issue=(code:string)=>t(code==='administration_count_unconfirmed'?'Clarify and confirm the daily administration count in Prescription Review.':code==='confirmation_required'?'Confirm medicines and instructions in Prescription Analysis first.':blockerEnglish[code]||'Additional review required')
 return <div className="clock-scheduling"><PageHeading title={t('Your Medicine Schedule')} eyebrow={t('YOUR CONFIRMED PRESCRIPTION')} description={t('Choose a start date and your medicine-taking times. Confirmed dosage and duration stay unchanged.')}/>
 <Notice>{t('Clock times are your preferences in India time (Asia/Kolkata). Follow the confirmed prescription and ask your clinician if timing is unclear. No notifications are sent.')}</Notice>
 {busy&&<p role="status">{t('Preparing your schedule...')}</p>}{error?<p role="alert">{translateError(error)}</p>:null}
 {!state&&!busy&&<Link className="button secondary" to="/dashboard/analysis">{t('Return to Prescription Review')}</Link>}
 {state&&<>{state.medicines.some(m=>!m.eligible)&&<Notice>{t('Complete medicines can be scheduled now. Medicines needing clarification stay visible and are excluded from generation.')}</Notice>}<section className="panel"><label>{t('Medicine start date')}<input type="date" disabled={busy} value={start} onChange={e=>{setStart(e.target.value);setCourse(null)}}/></label></section>
 <div className="medicine-records">{state.medicines.map(m=><section className="panel" key={m.medicine_ref}><h2>{m.name||t('Unknown medicine')}</h2>{m.eligible&&m.review_details&&<details className="ocr-technical-details"><summary>{t('OCR technical details and confirmed source summary')}</summary><ReviewDetails details={m.review_details}/></details>}<dl className="schedule-facts"><div><dt>{t('Confirmed dose and unit')}</dt><dd>{m.dose_quantity??t('Not yet confirmed')} {m.dose_unit?t(m.dose_unit):''}</dd></div><div><dt>{t('Confirmed duration')}</dt><dd>{m.duration_days===null?t('Not yet confirmed'):`${m.duration_days} ${t('days')}`}</dd></div>{m.food_timing&&<div><dt>{t('Food timing')}</dt><dd>{t(m.food_timing)}</dd></div>}</dl>
 {m.administrations_per_day>0&&<fieldset disabled={busy}><legend>{t('Medicine-taking times')}</legend><p>{t('{0} prescribed administrations each day',[m.administrations_per_day])}</p><div className="clock-inputs">{Array.from({length:m.administrations_per_day},(_,index)=><label key={index}>{t('{0} — administration {1}: {2}',[m.name,index+1,t(m.slots[index]||'Administration')])}<input type="time" value={times[m.medicine_ref]?.[index]||''} onChange={e=>{const next=Array.from({length:m.administrations_per_day},(_,i)=>times[m.medicine_ref]?.[i]||'');next[index]=e.target.value;setTimes(all=>({...all,[m.medicine_ref]:next}));setCourse(null)}}/></label>)}</div></fieldset>}{!m.eligible&&<Notice><ReviewDetails details={m.review_details}/>{m.issues.map(code=><p key={code}>{issue(code)}</p>)}<Link to={m.review_path}>{t('Return to Prescription Review')}</Link></Notice>}</section>)}</div>
 <button className="button" disabled={busy||!complete} onClick={()=>void generate()}>{t('Generate My Schedule')}</button></>}
 {course&&<section className="panel" aria-label={t('Calculated schedule')}><h2>{t('Your dated medicine schedule')}</h2>{course.blocked.length>0&&<Notice><p>{t('Not included in this schedule')}</p><ul>{course.blocked.map(m=><li key={m.medicine_ref}>{m.name||t('Unknown medicine')}: {m.issues.map(issue).join(' ')}</li>)}</ul></Notice>}{course.medicines.map(m=><article key={m.medicine_ref}><h3>{m.result.name}</h3><p>{dateLabel(m.result.start_date)} – {dateLabel(m.result.end_date)}</p><p>{t('Course total')}: {m.result.total_units} {t(m.result.unit)}</p><ul>{m.days.map(day=><li key={day.date}><strong>{dateLabel(day.date)}</strong><ul>{day.administrations.map(a=><li key={a.at}><time dateTime={a.at}>{a.time}</time> · {a.quantity} {t(a.unit)} · {a.slot?t(a.slot):t('Administration')}</li>)}</ul></li>)}</ul>{m.result.refill_date&&<p>{t('Refill planning date')}: {dateLabel(m.result.refill_date)}</p>}</article>)}</section>}
 </div>
}
