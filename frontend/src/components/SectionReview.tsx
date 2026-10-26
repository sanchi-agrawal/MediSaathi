import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, ShieldCheck } from 'lucide-react'
import type { ExtraPayload, SectionClient, SectionSnapshot } from '../lib/sections'
import { SECTION_FIELDS, sectionRecords } from '../lib/sections'
import { ApiError } from '../lib/prescriptions'
import { Badge, Notice } from './ui'

const labels:Record<string,string>={medicine_name_raw:'Medicine name as written',raw_text:'Original instruction / test text',dose_quantity_raw:'Dose quantity as written',dose_unit_raw:'Dose unit as written',frequency_raw:'Frequency as written',route_raw:'Route as written',timing_raw:'Timing as written',duration_raw:'Duration as written',test_name_raw:'Test name as written',order_context_raw:'Ordering context',specimen_raw:'Specimen as written',variant_raw:'Variant as written'}
export default function SectionReview({snapshot,client,onChange,onRetry,disabled=false}:{snapshot:SectionSnapshot;client:SectionClient;onChange:(s:SectionSnapshot)=>void;onRetry:()=>void;disabled?:boolean}){
  const [draft,setDraft]=useState<ExtraPayload|null>(snapshot.payload)
  const [dirty,setDirty]=useState(false)
  const [ack,setAck]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const active=useRef(true);const lock=useRef(false)
  useEffect(()=>{active.current=true;return()=>{active.current=false}},[])
  useEffect(()=>{if(!dirty)setDraft(snapshot.payload)},[snapshot.payload,snapshot.revision,dirty])
  const scope=snapshot.scope
  const title=scope==='instructions'?'Dosage instructions':'Prescribed investigations'
  async function run(action:()=>Promise<void>){
    if(lock.current||disabled)return;lock.current=true;setBusy(true);setError('')
    try{await action()}catch(e){if(active.current)setError(e instanceof ApiError?`${e.category}: ${e.message}`:'The section operation failed.')}
    finally{lock.current=false;if(active.current)setBusy(false)}
  }
  function edit(index:number,field:string,value:string){
    if(!draft||disabled||lock.current)return
    const records=sectionRecords(draft,scope).map((r,i)=>i===index?{...r,[field]:value.trim()?value:null}:r)
    setDraft({...draft,[scope]:records} as ExtraPayload);setDirty(true);setAck(false)
    if(snapshot.confirmed||snapshot.reviewed){
      onChange({...snapshot,confirmed:false,reviewed:false})
      void run(async()=>{const fresh=await client.invalidate(snapshot);if(active.current)onChange(fresh)})
    }
  }
  function save(){void run(async()=>{if(!draft)return;const fresh=await client.review(snapshot,draft);if(active.current){setDraft(fresh.payload);setDirty(false);setAck(false);onChange(fresh)}})}
  function confirm(){void run(async()=>{if(!ack||dirty||!snapshot.reviewed)return;const fresh=await client.confirm(snapshot);if(active.current)onChange(fresh)})}
  return <section className="panel scoped-review" aria-label={`${title} review`}><div className="panel-topline"><h2>{title}</h2><Badge tone={snapshot.confirmed&&!dirty?'green':'muted'}>{snapshot.confirmed&&!dirty?'Confirmed by server':snapshot.status==='succeeded'?'Review required':snapshot.status==='failed'?'Extraction failed':snapshot.status==='running'?'Analyzing…':'Not requested'}</Badge></div>
    {snapshot.status==='not_requested'&&<p>Select this section and choose Analyze with AI. No extraction has run for it.</p>}
    {snapshot.status==='failed'&&<div className="error-message" role="alert"><strong>{title} extraction failed.</strong><p>{snapshot.error?.category}: {snapshot.error?.message}</p><p>Other successful sections are preserved. No automatic retry.</p><button className="button secondary" disabled={disabled||busy} onClick={onRetry}>Retry {title.toLowerCase()}</button></div>}
    {snapshot.status==='succeeded'&&draft&&<><Notice>Verify every field against the original prescription with your doctor or pharmacist. This is transcription, not medical advice. No doses, medicine associations, test recommendations or schedules are inferred. Confirmation does not resolve uncertainty.</Notice>
      {draft.issues.length>0&&<div className="review-warning"><AlertTriangle size={17}/><span>Source warnings: {draft.issues.join(', ')}</span></div>}
      {sectionRecords(draft,scope).length===0&&<p>Extraction succeeded with no {title.toLowerCase()} records. Unknown or absent information was not invented.</p>}
      {sectionRecords(draft,scope).map((record,index)=>{
        const id=scope==='instructions'?'instruction_id':'investigation_id'
        const original=snapshot.original_payload?sectionRecords(snapshot.original_payload,scope).find(r=>r[id]===record[id]):undefined
        return <div className="scoped-record" key={String(record[id])}><div className="source-text"><span className="micro">ORIGINAL EXTRACTED TEXT · RECORD {index+1}</span><p>{String(original?.raw_text??'Unknown / not recorded')}</p></div><div className="medicine-fields">{SECTION_FIELDS[scope].map(field=><label key={field}>{labels[field]}<input aria-label={`${title}: ${labels[field]} ${index+1}`} disabled={disabled||busy} value={String(record[field]??'')} placeholder="Unknown / not recorded" onChange={e=>edit(index,field,e.target.value)}/></label>)}</div><p className="review-warning"><AlertTriangle size={15}/>Extraction review flag: {String(record.needs_review)}. Uncertainties: {(record.uncertainty_reasons as string[]).join(', ')||'None reported; still review every field.'}</p></div>
      })}<div className="confirmation-panel"><button className="button secondary" disabled={disabled||busy} onClick={save}>Save {title.toLowerCase()} review</button><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={disabled||busy||dirty||!snapshot.reviewed} onChange={e=>setAck(e.target.checked)}/> I reviewed this {scope} section against the image, including unknowns and uncertainty warnings.</label><button className="button" disabled={disabled||busy||dirty||!ack||!snapshot.reviewed||snapshot.confirmed} onClick={confirm}><ShieldCheck size={16}/>{snapshot.confirmed?'Confirmed by server':`Confirm ${title.toLowerCase()}`}</button>{dirty&&<p>Edits invalidate this section’s approval. Save and confirm again.</p>}</div></>}
    {busy&&<p role="status"><Check size={15}/> Saving section state…</p>}{error&&<div className="error-message" role="alert">{error}</div>}
  </section>
}
