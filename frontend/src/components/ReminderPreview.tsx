import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useRef,useState } from 'react'
import { translateRefill } from '../lib/language'
import type { ScheduleContext } from '../lib/scheduling'
import { SLOTS } from '../lib/scheduling'
import { teamClient } from '../lib/team'
import type { Preview,TeamClient } from '../lib/team'
import { useLanguage } from '../lib/language'
export default function ReminderPreview({schedule,client=teamClient}:{schedule:ScheduleContext;client?:TeamClient}){
  useUiLanguage()

  const {language}=useLanguage();const active=SLOTS.filter(s=>schedule.result?.payload.status==='ok'&&schedule.result.payload.doses_by_slot[s]>0)
  const [times,setTimes]=useState<Record<string,string>>({}),[preview,setPreview]=useState<Preview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');const lock=useRef(false)
  async function generate(){if(lock.current)return;lock.current=true;setBusy(true);setPreview(null);setError('');try{setPreview(await client.preview(schedule,times))}catch(e){setError(e instanceof Error?e.message:'Preview unavailable')}finally{lock.current=false;setBusy(false)}}
  return <section className="panel schedule-panel" aria-label={tr("Reminder preview")}><h2>{language==='hi'?"रिमाइंडर पूर्वावलोकन — सूचनाएँ चालू नहीं हैं।":tr("Reminder Preview — Notifications not enabled.")}</h2><p>{tr("Enter your own clock-time preferences in Asia/Kolkata. Morning/night slots do not imply a clock time. No dose log, notifications or background jobs are created. Upcoming entries cover at most seven days within the approved course.")}</p><div className="medicine-fields">{active.map(slot=><label key={tr(slot)}>{tr(slot)}{tr(" preference (Asia/Kolkata)")}<input aria-label={tr("{0} preference time",[tr(slot)])} type="time" disabled={busy} value={times[slot]??''} onChange={e=>{setPreview(null);setError('');setTimes({...times,[slot]:e.target.value})}}/></label>)}</div><button className="button secondary" disabled={busy||!active.length||active.some(s=>!times[s])} onClick={()=>void generate()}>{busy?tr("Preparing preview…"):tr("Preview approved schedule")}</button>{error&&<p role="alert">{uiError(error)}</p>}{preview&&<div role="status"><p>{tr(preview.notice)}</p>{preview.state==='no_upcoming_doses'&&<p>{tr("No upcoming doses within this approved course and preview window.")}</p>}<ul>{preview.doses.map(d=><li key={d.due_at+d.slot}>{new Intl.DateTimeFormat(language==='hi'?'hi-IN':'en-IN',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kolkata'}).format(new Date(d.due_at))}{tr(" Asia/Kolkata · ")}{tr(d.slot)} · {d.amount} {d.unit}</li>)}</ul>{preview.refill_notes.map((n,i)=><p key={i}>{translateRefill(n.name,n.message)}</p>)}</div>}</section>
}
