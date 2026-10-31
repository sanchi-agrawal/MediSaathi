import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge,Notice,PageHeading } from '../components/ui'
import { ApiError,prescriptionClient } from '../lib/prescriptions'
import type { AnalysisSnapshot,PrescriptionClient } from '../lib/prescriptions'
import { parseSection,sectionRecords,SECTION_FIELDS } from '../lib/sections'
import { subscribeSchedulingInvalidation } from '../lib/workflowEvents'
import MedicineMatching from '../components/MedicineMatching'

export default function CurrentWorkspace({kind,client=prescriptionClient}:{kind:'medicines'|'investigations';client?:Pick<PrescriptionClient,'current'>}){
  const [data,setData]=useState<AnalysisSnapshot|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true)
  const generation=useRef(0)
  async function load(){const version=++generation.current;setLoading(true);setData(null);setError('');try{const next=await client.current();if(version===generation.current)setData(next)}catch(e){if(version===generation.current)setError(e instanceof ApiError?e.category+': '+e.message:'Current session could not be restored.')}finally{if(version===generation.current)setLoading(false)}}
  useEffect(()=>{void load();const unsubscribe=subscribeSchedulingInvalidation(()=>{generation.current++;setData(null);setLoading(false);setError('Source information changed. Refresh to load the current server review.')});const focus=()=>void load();window.addEventListener('focus',focus);return()=>{generation.current++;unsubscribe();window.removeEventListener('focus',focus)}},[client])
  const inv=data?.sections?.investigations?parseSection(data.sections.investigations,'investigations',data.analysis_id):null
  const confirmed=kind==='medicines'?!!data?.confirmed:!!inv?.confirmed
  return <><PageHeading eyebrow="YOUR CURRENT SERVER WORKSPACE" title={kind==='medicines'?'My medicines':'Investigations'} description="Restored from the current demo session. Navigation does not repeat OCR." action={<Badge tone="coral">Session only · no account history</Badge>}/><Notice>This is the current prescription, not a durable account archive. Server restart or session expiry removes it. Save reviewed changes before navigating.</Notice><div className="schedule-toolbar"><Link className="button secondary" to="/dashboard/analysis">Continue review</Link><Link className="button secondary" to="/dashboard/schedule">Schedule</Link><button className="button secondary" disabled={loading} onClick={()=>void load()}>Refresh current records</button></div>{loading&&<p role="status">Restoring current server records…</p>}{error&&<p role="alert" className="error-message">{error}</p>}
    {!loading&&!data&&!error&&<section className="panel"><h2>No current prescription in this session</h2><p>Upload a prescription or return to the same origin and valid demo session. No account data has been saved.</p></section>}
    {data&&<><Badge tone={confirmed?'green':'muted'}>{confirmed?'Confirmed by server':'Review and confirmation required'}</Badge>
      {kind==='medicines'?(data.records??[]).map((r,i)=><section className="panel schedule-panel" key={i}><h2>{r.name??'Unknown medicine'}</h2><p className="source-text">{data.original_records?.[i]?.raw_text??'Unknown / not recorded'}</p><dl className="schedule-facts">{Object.entries(r).map(([field,value])=><div key={field}><dt>{field.replaceAll('_',' ')}</dt><dd>{value===null?'Unknown / not recorded':String(value)}</dd></div>)}</dl></section>):inv?.payload?sectionRecords(inv.payload,'investigations').map((r,i)=><section className="panel schedule-panel" key={i}><h2>{String(r.test_name_raw??'Unknown test')}</h2><dl className="schedule-facts">{SECTION_FIELDS.investigations.map(field=><div key={field}><dt>{field.replaceAll('_',' ')}</dt><dd>{String(r[field]??'Unknown / not recorded')}</dd></div>)}</dl><p>Uncertainties: {(r.uncertainty_reasons as string[]).join(', ')||'None reported'} · Review flag: {String(r.needs_review)}</p></section>):<p>No investigations extraction in the current prescription.</p>}
      {kind==='medicines'&&data.records?.length===0&&<p>No extracted medicine records. Empty results are not extraction failures.</p>}<Notice>Scheduling needs separately confirmed medicines and instructions, explicit association and plan approval. No schedule, matching, pricing or test recommendation is inferred here.</Notice>
    {kind==='medicines'&&data.confirmed&&<MedicineMatching key={data.analysis_id+data.revision} source={data}/>}
    </>}
  </>
}
