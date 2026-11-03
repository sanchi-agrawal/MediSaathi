import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge,Notice,PageHeading } from '../components/ui'
import { ApiError,prescriptionClient } from '../lib/prescriptions'
import type { AnalysisSnapshot,PrescriptionClient } from '../lib/prescriptions'
import { parseSection,sectionRecords,SECTION_FIELDS } from '../lib/sections'
import { subscribeSchedulingInvalidation } from '../lib/workflowEvents'
import MedicineMatching from '../components/MedicineMatching'

export default function CurrentWorkspace({kind,client=prescriptionClient}:{kind:'medicines'|'investigations';client?:Pick<PrescriptionClient,'current'>}){
  useUiLanguage()

  const [data,setData]=useState<AnalysisSnapshot|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true)
  const generation=useRef(0)
  async function load(){const version=++generation.current;setLoading(true);setData(null);setError('');try{const next=await client.current();if(version===generation.current)setData(next)}catch(e){if(version===generation.current)setError(e instanceof ApiError?e.category+': '+e.message:'Current session could not be restored.')}finally{if(version===generation.current)setLoading(false)}}
  useEffect(()=>{void load();const unsubscribe=subscribeSchedulingInvalidation(()=>{generation.current++;setData(null);setLoading(false);setError('Source information changed. Refresh to load the current server review.')});const focus=()=>void load();window.addEventListener('focus',focus);return()=>{generation.current++;unsubscribe();window.removeEventListener('focus',focus)}},[client])
  const inv=data?.sections?.investigations?parseSection(data.sections.investigations,'investigations',data.analysis_id):null
  const confirmed=kind==='medicines'?!!data?.confirmed:!!inv?.confirmed
  return <><PageHeading eyebrow={tr("YOUR CURRENT SERVER WORKSPACE")} title={kind==='medicines'?tr("My medicines"):tr("Investigations")} description={tr("Restored from the current demo session. Navigation does not repeat OCR.")} action={<Badge tone="coral">{tr("Session only · no account history")}</Badge>}/><Notice>{tr("This is the current prescription, not a durable account archive. Server restart or session expiry removes it. Save reviewed changes before navigating.")}</Notice><div className="schedule-toolbar"><Link className="button secondary" to="/dashboard/analysis">{tr("Continue review")}</Link><Link className="button secondary" to="/dashboard/schedule">{tr("Schedule")}</Link><button className="button secondary" disabled={loading} onClick={()=>void load()}>{tr("Refresh current records")}</button></div>{loading&&<p role="status">{tr("Restoring current server records…")}</p>}{error&&<p role="alert" className="error-message">{uiError(error)}</p>}
    {!loading&&!data&&!error&&<section className="panel"><h2>{tr("No current prescription in this session")}</h2><p>{tr("Upload a prescription or return to the same origin and valid demo session. No account data has been saved.")}</p></section>}
    {data&&<><Badge tone={confirmed?'green':'muted'}>{confirmed?tr("Confirmed by server"):tr("Review and confirmation required")}</Badge>
      {kind==='medicines'?(data.records??[]).map((r,i)=><section className="panel schedule-panel" key={i}><h2>{r.name ?? tr("Unknown medicine")}</h2><p className="source-text">{data.original_records?.[i]?.raw_text ?? tr("Unknown / not recorded")}</p><dl className="schedule-facts">{Object.entries(r).map(([field,value])=><div key={field}><dt>{tr(field.replaceAll('_',' '))}</dt><dd>{value===null?tr("Unknown / not recorded"):String(value)}</dd></div>)}</dl></section>):inv?.payload?sectionRecords(inv.payload,'investigations').map((r,i)=><section className="panel schedule-panel" key={i}><h2>{String(r.test_name_raw ?? tr("Unknown test"))}</h2><dl className="schedule-facts">{SECTION_FIELDS.investigations.map(field=><div key={field}><dt>{tr(field.replaceAll('_',' '))}</dt><dd>{String(r[field] ?? tr("Unknown / not recorded"))}</dd></div>)}</dl><p>{tr("Uncertainties: ")}{(r.uncertainty_reasons as string[]).join(', ') || tr("None reported")}{tr(" · Review flag: ")}{tr(String(r.needs_review))}</p></section>):<p>{tr("No investigations extraction in the current prescription.")}</p>}
      {kind==='medicines'&&data.records?.length===0&&<p>{tr("No extracted medicine records. Empty results are not extraction failures.")}</p>}<Notice>{tr("Scheduling needs separately confirmed medicines and instructions, explicit association and plan approval. No schedule, matching, pricing or test recommendation is inferred here.")}</Notice>
    {kind==='medicines'&&data.confirmed&&<MedicineMatching key={data.analysis_id+data.revision} source={data}/>}
    </>}
  </>
}
