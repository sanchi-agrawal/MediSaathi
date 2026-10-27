import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays,LoaderCircle,ShieldCheck } from 'lucide-react'
import { Badge,Notice,PageHeading } from '../components/ui'
import { ApiError } from '../lib/prescriptions'
import { schedulingClient,SLOTS,validPlan } from '../lib/scheduling'
import type { ScheduleContext,SchedulePlan,SchedulingClient,Slot } from '../lib/scheduling'
import { subscribeSchedulingInvalidation } from '../lib/workflowEvents'
import '../schedule.css'

const blank=()=>({quantity:'',unit:'',days:'',start:'',slots:{morning:false,noon:false,night:false,bedtime:false}})
type Draft=ReturnType<typeof blank>
function draftFrom(p:SchedulePlan):Draft{return {quantity:String(p.dose_quantity),unit:p.dose_unit,days:String(p.duration_days),start:p.start_date,slots:Object.fromEntries(SLOTS.map(s=>[s,p.administrations_by_slot[s]===1])) as Draft['slots']}}

export default function Schedule({client=schedulingClient}:{client?:SchedulingClient}){
  const [data,setData]=useState<ScheduleContext|null>(null)
  const [medicine,setMedicine]=useState('');const [instruction,setInstruction]=useState('')
  const [draft,setDraft]=useState(blank);const [ack,setAck]=useState(false)
  const [busy,setBusy]=useState('');const [error,setError]=useState('')
  const sequence=useRef(0);const lock=useRef<symbol|null>(null)
  function accept(s:ScheduleContext,reset=false){setData(s);setAck(false);if(reset){setMedicine(s.association?.medicine_ref??'');setInstruction(s.association?.instruction_id??'');setDraft(s.plan?draftFrom(s.plan):blank())}}
  async function run(label:string,action:(version:number)=>Promise<void>){
    if(lock.current)return
    const token=Symbol();lock.current=token;const version=sequence.current;setBusy(label);setError('')
    try{await action(version)}catch(e){if(version===sequence.current){setData(null);setAck(false);setError(e instanceof ApiError?e.category+': '+e.message:'The scheduling operation failed. Refresh current state before continuing.')}}
    finally{if(lock.current===token){lock.current=null;if(version===sequence.current)setBusy('')}}
  }
  function refresh(){void run('Loading current review',async version=>{setData(null);setAck(false);const fresh=await client.current();if(version===sequence.current)accept(fresh,true)})}
  useEffect(()=>{
    refresh()
    const unsubscribe=subscribeSchedulingInvalidation(()=>{sequence.current++;lock.current=null;setData(null);setAck(false);setBusy('');setError('Prescription information changed. Refresh current state; earlier schedules are hidden.')})
    const focus=()=>refresh();window.addEventListener('focus',focus)
    const visible=()=>{if(document.visibilityState==='visible')refresh()};document.addEventListener('visibilitychange',visible)
    return()=>{sequence.current++;lock.current=null;unsubscribe();window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',visible)}
    // The client is the sole transport dependency; handlers use generation checks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[client])
  function selection(kind:'medicine'|'instruction',value:string){
    if(lock.current)return
    if(kind==='medicine')setMedicine(value);else setInstruction(value)
    setDraft(blank());setAck(false)
    if(data?.association){const previous=data;setData({...data,association:null,plan:null,result:null,status:'ready'});void run('Clearing prior association',async version=>{const fresh=await client.clear(previous);if(version===sequence.current)accept(fresh)})}
  }
  function edit(next:Draft){
    if(lock.current)return
    setDraft(next);setAck(false)
    if(data?.plan){const previous=data;setData({...data,plan:null,result:null,status:'associated'});void run('Invalidating plan',async version=>{const fresh=await client.invalidate(previous);if(version===sequence.current)accept(fresh)})}
  }
  function associate(){void run('Associating reviewed records',async version=>{if(!data||!medicine||!instruction)return;const fresh=await client.associate(data,medicine,instruction);if(version===sequence.current){accept(fresh);setDraft(blank())}})}
  function save(){
    const plan={dose_quantity:Number(draft.quantity),dose_unit:draft.unit,duration_days:Number(draft.days),start_date:draft.start,administrations_by_slot:Object.fromEntries(SLOTS.map(s=>[s,draft.slots[s]?1:0]))}
    if(!validPlan(plan)){setError('Enter an explicit positive dose, unit, whole-day duration and start date. Do not guess missing information.');return}
    void run('Saving plan for review',async version=>{if(!data)return;const fresh=await client.review(data,plan);if(version===sequence.current)accept(fresh)})
  }
  function approve(){void run('Calculating approved schedule',async version=>{if(!data||!ack||data.status!=='reviewed')return;setData({...data,result:null});setAck(false);const fresh=await client.approve(data);if(version===sequence.current)accept(fresh)})}
  const selectedMedicine=data?.medicines[Number(medicine.replace('medicine_',''))-1]
  const selectedInstruction=data?.instructions.find(i=>i.instruction_id===instruction)
  const result=data?.ready&&data.status==='succeeded'&&data.result?.payload.status==='ok'?data.result.payload:null
  return <><PageHeading eyebrow="REVIEW BEFORE ROUTINE" title="Schedule & refill planning" description="Connect separately confirmed records. Approve each calculation explicitly." action={<Badge tone="coral">Demo session · no notification delivery</Badge>}/>
    <Notice>Verify the prescription with your clinician or pharmacist. This is a calculation from reviewed text, not prescribing advice. Unknown or unsupported instructions remain blocked. No reminders, notifications or inventory records are created.</Notice>
    <div className="schedule-toolbar"><Link className="button secondary" to="/dashboard/analysis">Review prescription</Link><button className="button secondary" disabled={!!busy} onClick={refresh}>Refresh current state</button></div>
    {busy&&<p className="notice" role="status"><LoaderCircle className="spin" size={17}/>{busy}…</p>}{error&&<div className="error-message" role="alert">{error}</div>}
    {data&&!data.ready&&<section className="panel schedule-panel"><h2>Confirmation required</h2><p>Review, save and confirm both medicines and dosage instructions on Prescription Analysis. No schedule or association is available from unconfirmed sections.</p></section>}
    {data?.ready&&<><section className="panel schedule-panel" aria-label="Explicit record association"><h2>1. Associate the records you verified</h2><p>Nothing is linked by medicine name automatically. Select the exact medicine and instruction after comparing their source text.</p><div className="medicine-fields"><label>Confirmed medicine<select aria-label="Confirmed medicine" disabled={!!busy} value={medicine} onChange={e=>selection('medicine',e.target.value)}><option value="">Choose explicitly</option>{data.medicines.map((m,i)=><option key={i} value={'medicine_'+String(i+1).padStart(3,'0')}>{i+1}. {m.name??'Unknown medicine'}</option>)}</select></label><label>Confirmed instruction<select aria-label="Confirmed instruction" disabled={!!busy} value={instruction} onChange={e=>selection('instruction',e.target.value)}><option value="">Choose explicitly</option>{data.instructions.map((i,index)=><option key={i.instruction_id} value={i.instruction_id}>{index+1}. {i.medicine_name_raw??'Unknown name'} · {i.instruction_id}</option>)}</select></label></div>
      {selectedMedicine&&<div className="source-text"><span className="micro">MEDICINE SOURCE</span><p>{selectedMedicine.raw_text??'Unknown'}</p><p>Form: {selectedMedicine.form??'Unknown'} · Frequency: {selectedMedicine.frequency_pattern??'Unknown'} · Duration: {selectedMedicine.duration_days??'Unknown'} · Extraction review flag: {String(selectedMedicine.needs_review)}</p></div>}
      {selectedInstruction&&<div className="source-text"><span className="micro">INSTRUCTION SOURCE</span><p>{selectedInstruction.raw_text??'Unknown'}</p><dl className="schedule-facts">{(['dose_quantity_raw','dose_unit_raw','frequency_raw','duration_raw','timing_raw'] as const).map(k=><div key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{selectedInstruction[k]??'Unknown / not recorded'}</dd></div>)}</dl><p>Review flag: {String(selectedInstruction.needs_review)} · Uncertainties: {selectedInstruction.uncertainty_reasons.join(', ')||'None reported'}</p></div>}
      {data.instruction_issues.length>0&&<p className="review-warning">Source warnings: {data.instruction_issues.join(', ')}</p>}
      {!data.medicines.length||!data.instructions.length?<p>No pair is available. Empty extraction does not imply a medicine or instruction.</p>:null}
      <button className="button" disabled={!!busy||!medicine||!instruction||!!data.association} onClick={associate}>Associate selected records</button>{data.association&&<p className="review-warning">Association saved by the server. Changing either selection removes the plan and result.</p>}
    </section>
    {data.association&&<section className="panel schedule-panel" aria-label="Schedule input review"><h2>2. Review the explicit schedule inputs</h2><p>Copy only the supported values written in the confirmed source. No dose is inferred from strength. Saving inputs does not establish that they are supported; Python checks the source again on approval.</p><Notice>Only simple decimal quantities, exact units, integer day durations, and literal English morning/noon/night/bedtime timing with supported BD/BID/TDS/TID/QID/HS frequencies can proceed. Fractions, numeric patterns, OD, PRN/SOS, ranges, tapers, ambiguous clocks and conflicting slots require clarification.</Notice>
      <div className="medicine-fields"><label>Dose quantity<input aria-label="Dose quantity" type="number" min="0" max="1000" step="any" disabled={!!busy} value={draft.quantity} onChange={e=>edit({...draft,quantity:e.target.value})}/></label><label>Dose unit<select aria-label="Dose unit" disabled={!!busy} value={draft.unit} onChange={e=>edit({...draft,unit:e.target.value})}><option value="">Unknown / choose from source</option>{['tablet','capsule','mL','drop'].map(u=><option key={u}>{u}</option>)}</select></label><label>Duration in whole days<input aria-label="Duration in whole days" type="number" min="1" max="365" step="1" disabled={!!busy} value={draft.days} onChange={e=>edit({...draft,days:e.target.value})}/></label><label>Course start date<input aria-label="Course start date" type="date" disabled={!!busy} value={draft.start} onChange={e=>edit({...draft,start:e.target.value})}/></label></div><fieldset className="schedule-slots"><legend>Slots explicitly written in the source (not inferred from abbreviations)</legend>{SLOTS.map((s:Slot)=><label className="checkbox-label" key={s}><input type="checkbox" checked={draft.slots[s]} disabled={!!busy} onChange={e=>edit({...draft,slots:{...draft.slots,[s]:e.target.checked}})}/>{s}</label>)}</fieldset>
      <button className="button secondary" disabled={!!busy} onClick={save}>Save plan for review</button>
      {data.plan&&<div className="confirmation-panel"><h3>Saved inputs</h3><p>{data.plan.dose_quantity} {data.plan.dose_unit} per administration · {data.plan.duration_days} days · Starts {data.plan.start_date}</p><p>Slots: {SLOTS.filter(s=>data.plan!.administrations_by_slot[s]===1).join(', ')||'None — unsupported'}</p><label className="checkbox-label"><input aria-label="Approve reviewed schedule inputs" type="checkbox" checked={ack} disabled={!!busy||data.status!=='reviewed'} onChange={e=>setAck(e.target.checked)}/>I verified this association and every schedule input against the prescription. Generate only if Python validates them.</label><button className="button" disabled={!!busy||!ack||data.status!=='reviewed'} onClick={approve}><ShieldCheck size={17}/>Approve & generate schedule</button></div>}
    </section>}
    {data.status==='needs_input'&&<div className="notice" role="alert">Requires clarification: {data.result?.payload.reason} No calculated schedule is available.</div>}
    {data.error&&<div className="error-message" role="alert">{data.error.category}: {data.error.message}</div>}
    {result&&<section className="panel schedule-panel" aria-label="Calculated schedule"><div className="panel-topline"><h2><CalendarDays size={20}/> Calculated schedule · {result.name}</h2><Badge tone="green">Server calculated</Badge></div><dl className="schedule-facts">{SLOTS.map(s=><div key={s}><dt>{s}</dt><dd>{result.doses_by_slot[s]} {result.unit}</dd></div>)}<div><dt>Per day</dt><dd>{result.units_per_day} {result.unit}</dd></div><div><dt>Course total</dt><dd>{result.total_units} {result.unit}</dd></div><div><dt>Start date</dt><dd>{result.start_date}</dd></div><div><dt>End date</dt><dd>{result.end_date}</dd></div><div><dt>Refill planning date</dt><dd>{result.refill_date??'Not calculated for this course'}</dd></div></dl><p>Refill dates use the existing engine’s rule for courses of at least 30 days, three days before the course end. This is not inventory tracking or notification delivery. Edits remove this result and require review and approval again.</p></section>}
    </>}
  </>
}
