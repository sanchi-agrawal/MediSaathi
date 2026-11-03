import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { confirmedClient } from '../lib/confirmedPrescription'
import type { ConfirmedPrescription,Course } from '../lib/confirmedPrescription'
import { useLanguage,translateError } from '../lib/language'
import { blockerEnglish } from '../lib/confirmedWorkflowHindi'
import { Notice } from '../components/ui'
import { subscribeSchedulingInvalidation,subscribeSchedulingChanges } from '../lib/workflowEvents'
import '../confirmed-workflow.css'

export default function UnifiedSchedule(){
  const {t,language}=useLanguage();const [snapshot,setSnapshot]=useState<ConfirmedPrescription|null>(null),[course,setCourse]=useState<Course|null>(null)
  const [start,setStart]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');const lock=useRef(false),generation=useRef(0)
  useEffect(()=>{let active=true;setBusy(true);confirmedClient.current().then(v=>{if(active){setSnapshot(v.snapshot);setCourse(v.course);setStart(v.course?.start_date||'')}}).catch(e=>{if(active)setError(translateError(e.message))}).finally(()=>{if(active)setBusy(false)});return()=>{active=false}},[])
  useEffect(()=>{let active=true;const refresh=()=>{setCourse(null);void confirmedClient.current().then(v=>{if(active){setSnapshot(v.snapshot);setCourse(v.course)}}).catch(()=>{if(active){setSnapshot(null);setCourse(null)}})};const invalid=subscribeSchedulingInvalidation(()=>{generation.current++;setSnapshot(null);setCourse(null)});const changed=subscribeSchedulingChanges(refresh);window.addEventListener('focus',refresh);return()=>{active=false;invalid();changed();window.removeEventListener('focus',refresh)}},[])
  const date=(value:string)=>new Intl.DateTimeFormat(language==='hi'?'hi-IN':'en-IN',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'))
  async function generate(){if(lock.current||!snapshot)return;lock.current=true;const epoch=generation.current;setBusy(true);setError('');setCourse(null);try{const current=await confirmedClient.current();if(current.snapshot?.snapshot_id!==snapshot.snapshot_id){setSnapshot(current.snapshot);throw new Error('The prescription changed. Return to review.')}const next=await confirmedClient.generate(snapshot.snapshot_id,start);if(epoch===generation.current)setCourse(next)}catch(e){setError(translateError(e instanceof Error?e.message:String(e)))}finally{lock.current=false;setBusy(false)}}
  return <div className="workflow-page"><header className="page-heading"><h1>{t('Your Medicine Schedule')}</h1><p>{t('Your schedule is prepared using your verified prescription.')}</p></header>
    {busy&&<p role="status">{t('Working…')}</p>}{error&&<p role="alert">{error}</p>}
    {!snapshot&&!busy&&<Notice>{t('Confirm your prescription in Prescription Analysis before scheduling.')} <Link to="/dashboard/analysis">{t('Return to Prescription Review')}</Link></Notice>}
    {snapshot?.medicines.map(m=><section className="panel" key={m.medicine_ref}><h2>{m.name||t('Unknown medicine')}</h2><dl><dt>{t('Confirmed dose and unit')}</dt><dd>{m.dose_quantity||t('Missing confirmed dose')} {m.dose_unit||''}</dd><dt>{t('Confirmed time-of-day slots')}</dt><dd>{m.confirmed_slots.map(value=>t(value)).join(', ')||t('Additional review required')}</dd><dt>{t('Confirmed duration')}</dt><dd>{m.duration||t('Missing duration')}</dd><dt>{t('Food timing')}</dt><dd>{m.food_timing||t('Not specified')}</dd></dl>{m.issues.length>0&&<Notice>{m.issues.map(code=><p key={code}>{t(blockerEnglish[code]||'Additional review required')}</p>)}<Link to={m.review_path}>{t('Return to Prescription Review')}</Link></Notice>}</section>)}
    {snapshot&&<section className="panel"><label>{t('When will you start taking your medicine?')}<input type="date" value={start} disabled={busy} onChange={e=>{setStart(e.target.value);setCourse(null)}}/></label><button className="button" disabled={busy||!start||!snapshot.medicines.some(m=>!m.issues.length)} onClick={()=>void generate()}>{t('Generate My Schedule')}</button></section>}
    {course&&<section className="panel"><h2>{t('Generated medicine calendar')}</h2>{course.results.map(({medicine_ref,slots,result})=><article key={medicine_ref}><h3>{result.name}</h3><p>{date(result.start_date)} – {date(result.end_date)} · {result.duration_days} {t('days')}</p><p>{t('Total quantity')}: {result.total_units} {result.unit}</p>{result.refill_date&&<p>{t('Refill date')}: {date(result.refill_date)}</p>}<ul>{Array.from({length:result.duration_days},(_,index)=>{const day=new Date(result.start_date+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+index);return <li key={index}>{date(day.toISOString().slice(0,10))}: {slots.map(slot=>`${t(slot)}: ${result.doses_by_slot[slot==='afternoon'?'noon':slot]} ${result.unit}`).join(' · ')}</li>})}</ul></article>)}{course.blocked.length>0&&<Notice>{t('Some medicines still require prescription review.')}<Link to="/dashboard/analysis">{t('Return to Prescription Review')}</Link></Notice>}</section>}
    <Notice>{t('This is a calculation from your confirmed prescription, not new medical advice. No notifications are sent.')}</Notice>
  </div>
}
