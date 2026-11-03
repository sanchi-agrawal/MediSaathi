import { translateReason as reason } from '../lib/language'
import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, ShieldCheck } from 'lucide-react'
import type { ExtraPayload, SectionClient, SectionSnapshot } from '../lib/sections'
import { SECTION_FIELDS, sectionRecords } from '../lib/sections'
import { ApiError } from '../lib/prescriptions'
import { Badge, Notice } from './ui'
import { NumeralReading } from './RecognitionPanel'

const labels:Record<string,string>={medicine_name_raw:'Medicine name as written',raw_text:'Original instruction / test text',dose_quantity_raw:'Dose quantity as written',dose_unit_raw:'Dose unit as written',frequency_raw:'Frequency as written',route_raw:'Route as written',timing_raw:'Timing as written',duration_raw:'Duration as written',test_name_raw:'Test name as written',order_context_raw:'Ordering context',specimen_raw:'Specimen as written',variant_raw:'Variant as written'}
export default function SectionReview({snapshot,client,onChange,onRetry,disabled=false}:{snapshot:SectionSnapshot;client:SectionClient;onChange:(s:SectionSnapshot)=>void;onRetry:()=>void;disabled?:boolean}){
  useUiLanguage()

  const [draft,setDraft]=useState<ExtraPayload|null>(snapshot.payload)
  const [dirty,setDirty]=useState(false)
  const [ack,setAck]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const active=useRef(true);const lock=useRef(false)
  useEffect(()=>{active.current=true;return()=>{active.current=false}},[])
  useEffect(()=>{if(!dirty)setDraft(snapshot.payload)},[snapshot.payload,snapshot.revision,dirty])
  useEffect(()=>{const target=document.getElementById(window.location.hash.slice(1));if(target){target.scrollIntoView?.({block:'center'});target.focus()}},[snapshot.payload])
  const scope=snapshot.scope
  const title=scope==='instructions'?'Dosage instructions':'Prescribed investigations'
  const reviewLabel=scope==='instructions'?'Dosage instructions review':'Prescribed investigations review'
  const saveLabel=scope==='instructions'?'Save dosage instructions review':'Save prescribed investigations review'
  const confirmLabel=scope==='instructions'?'Confirm dosage instructions':'Confirm prescribed investigations'
  const retryLabel=scope==='instructions'?'Retry dosage instructions':'Retry prescribed investigations'
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
  return <section className="panel scoped-review" aria-label={tr(reviewLabel)}><div className="panel-topline"><h2>{tr(title)}</h2><Badge tone={snapshot.confirmed&&!dirty?'green':'muted'}>{snapshot.confirmed&&!dirty?tr("Confirmed by server"):snapshot.status==='succeeded'?tr("Review required"):snapshot.status==='failed'?tr("Extraction failed"):snapshot.status==='running'?tr("Analyzing…"):tr("Not requested")}</Badge></div>
    {snapshot.status==='not_requested'&&<p>{tr("Select this section and choose Analyze with AI. No extraction has run for it.")}</p>}
    {snapshot.status==='failed'&&<div className="error-message" role="alert"><strong>{tr(title)}{tr(" extraction failed.")}</strong><p>{uiError(snapshot.error)}</p><p>{tr("Other successful sections are preserved. No automatic retry.")}</p><button className="button secondary" disabled={disabled||busy} onClick={onRetry}>{tr(retryLabel)}</button></div>}
    {snapshot.status==='succeeded'&&draft&&<><Notice>{tr("Verify every field against the original prescription with your doctor or pharmacist. This is transcription, not medical advice. No doses, medicine associations, test recommendations or schedules are inferred. Confirmation does not resolve uncertainty.")}</Notice>
      <NumeralReading metadata={snapshot}/>{draft.issues.length>0&&<div className="review-warning"><AlertTriangle size={17}/><span>{tr("Source warnings: ")}{draft.issues.map(reason).join(', ')}</span></div>}
      {sectionRecords(draft,scope).length===0&&<p>{tr("No {0} records were extracted. Unknown or absent information was not invented.",[tr(title)])}</p>}
      {sectionRecords(draft,scope).map((record,index)=>{
        const id=scope==='instructions'?'instruction_id':'investigation_id'
        const original=snapshot.original_payload?sectionRecords(snapshot.original_payload,scope).find(r=>r[id]===record[id]):undefined
        return <div className="scoped-record" key={String(record[id])}><div className="source-text"><span className="micro">{tr("ORIGINAL EXTRACTED TEXT · RECORD ")}{index+1}</span><p>{String(original?.raw_text ?? tr("Unknown / not recorded"))}</p></div><div className="medicine-fields">{SECTION_FIELDS[scope].map(field=><label key={field}>{tr(labels[field])}<input id={'review-'+record[id]+'-'+field} aria-label={tr("{0}: {1} {2}",[tr(title),tr(labels[field]),index+1])} disabled={disabled||busy} value={String(record[field]??'')} placeholder={tr("Unknown / not recorded")} onChange={e=>edit(index,field,e.target.value)}/></label>)}</div><p className="review-warning"><AlertTriangle size={15}/>{tr("Extraction review flag: ")}{tr(String(record.needs_review))}{tr(". Uncertainties: ")}{(record.uncertainty_reasons as string[]).map(reason).join(', ') || tr("None reported; still review every field.")}</p></div>
      })}<div className="confirmation-panel"><button className="button secondary" disabled={disabled||busy} onClick={save}>{tr(saveLabel)}</button><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={disabled||busy||dirty||!snapshot.reviewed} onChange={e=>setAck(e.target.checked)}/>{tr("I reviewed the {0} section against the image, including unknowns and uncertainty warnings.",[tr(title)])}</label><button className="button" disabled={disabled||busy||dirty||!ack||!snapshot.reviewed||snapshot.confirmed} onClick={confirm}><ShieldCheck size={16}/>{snapshot.confirmed?tr("Confirmed by server"):tr(confirmLabel)}</button>{dirty&&<p>{tr("Edits invalidate this section’s approval. Save and confirm again.")}</p>}</div></>}
    {busy&&<p role="status"><Check size={15}/>{tr(" Saving section state…")}</p>}{error&&<div className="error-message" role="alert">{uiError(error)}</div>}
  </section>
}
