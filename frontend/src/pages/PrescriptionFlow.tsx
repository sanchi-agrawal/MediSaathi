import { useEffect, useRef, useState } from 'react'
import { Check, FileScan, Languages, ShieldCheck, Sparkles, AlertTriangle, LoaderCircle, LockKeyhole } from 'lucide-react'
import { Badge, Notice, PageHeading } from '../components/ui'
import ImageUploader from '../components/ImageUploader'
import type { Language, MedicineRecord, Section } from '../lib/api'
import SectionReview from '../components/SectionReview'
import { sectionClient as connectedSectionClient } from '../lib/sections'
import type { ExtraScope, SectionClient, SectionSnapshot } from '../lib/sections'
import { ApiError, MEDICINE_FIELDS, prescriptionClient } from '../lib/prescriptions'
import type { AnalysisSnapshot, ExplanationPayload, PrescriptionClient } from '../lib/prescriptions'

const labels:Record<keyof MedicineRecord,string>={raw_text:'Original medicine text',name:'Medicine name',salt:'Printed ingredient',strength:'Written strength',form:'Form',frequency_pattern:'Written frequency',duration_days:'Duration in days',timing:'Written timing',confidence:'Extraction confidence (uncalibrated)',needs_review:'Extraction review flag'}
export default function PrescriptionFlow({client=prescriptionClient,sections=connectedSectionClient}:{client?:PrescriptionClient;sections?:SectionClient}) {
  const [file,setFile]=useState<File|null>(null)
  const [data,setData]=useState<AnalysisSnapshot|null>(null)
  const [records,setRecords]=useState<MedicineRecord[]>([])
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [dirty,setDirty]=useState(false)
  const [ack,setAck]=useState(false)
  const [language,setLanguage]=useState<Language>('en')
  const [explanation,setExplanation]=useState<ExplanationPayload|null>(null)
  const [selected,setSelected]=useState<Section[]>(['medicines'])
  const [extra,setExtra]=useState<Partial<Record<ExtraScope,SectionSnapshot>>>({})
  const [activeSection,setActiveSection]=useState('Medicines')
  const [phase,setPhase]=useState<'uploading'|'extracting'>('uploading')
  const [elapsed,setElapsed]=useState(0)
  const [browserTimings,setBrowserTimings]=useState<{upload:number;extraction:number;total:number}|null>(null)
  const operation=useRef<symbol|null>(null)
  const abort=useRef<AbortController|null>(null)
  const sequence=useRef(0)
  const clearQueue=useRef<Promise<void>>(Promise.resolve())
  const currentData=useRef(data);currentData.current=data
  useEffect(()=>()=>{sequence.current++;abort.current?.abort()},[])
  useEffect(()=>{
    if(busy!=='Analyzing')return
    const start=performance.now();setElapsed(0)
    const interval=window.setInterval(()=>setElapsed(Math.floor((performance.now()-start)/1000)),1000)
    return()=>window.clearInterval(interval)
  },[busy])
  function showError(e:unknown){setError(e instanceof ApiError?`${e.category}: ${e.message}`:'The operation could not complete. Please try again.')}
  function sourceChanged(next:File|null){
    setExtra({})
    abort.current?.abort();operation.current=null;setBrowserTimings(null)
    sequence.current++;setFile(next);setData(null);setRecords([]);setAck(false);setExplanation(null);setDirty(false);setError('');setBusy('')
    if(currentData.current){clearQueue.current=clearQueue.current.catch(()=>{}).then(()=>client.clear());void clearQueue.current.catch(()=>{setError('Could not clear the old server analysis. Local confirmation has been removed. Refresh the page before continuing.')})}
  }
  async function run(action:string,fn:(signal:AbortSignal)=>Promise<void>){
    if(operation.current!==null)return
    const token=Symbol(action);operation.current=token
    const controller=new AbortController();abort.current=controller
    const version=sequence.current;setBusy(action);setError('')
    try{await fn(controller.signal)}catch(e){if(version===sequence.current)showError(e)}
    finally{if(operation.current===token){operation.current=null;abort.current=null;if(version===sequence.current)setBusy('')}}
  }
  function accept(next:AnalysisSnapshot){setData(next);setRecords(next.records??[]);setDirty(false);setAck(false);setExplanation(null)}
  function analyze(scopes:Section[]=selected){void run('Analyzing',async(signal)=>{
    if(!file||!scopes.length)return
    const started=performance.now();let uploadMs=0
    setPhase('uploading');setBrowserTimings(null)
    const version=sequence.current
    await clearQueue.current
    if(version!==sequence.current)return
    let uploaded=data
    if(!uploaded){const uploadStart=performance.now();uploaded=await client.upload(file,signal);uploadMs=performance.now()-uploadStart;if(version!==sequence.current)return;setData(uploaded)}
    setPhase('extracting')
    const extractionStart=performance.now()
    if(scopes.includes('medicines')&&['not_requested','failed'].includes(uploaded.status)){
      setActiveSection('Medicines');setExplanation(null);setAck(false)
      setData({...uploaded,confirmed:false,reviewed:false})
      const result=await client.analyze(uploaded,signal)
      if(version!==sequence.current)return
      accept(result);uploaded=result
      if(result.error&&['configuration_error','quota_or_rate_limit'].includes(result.error.category)){
        setError('Extraction stopped after a configuration/quota failure. Completed sections are preserved; other selected sections have not run.');return
      }
    }
    for(const scope of ['instructions','investigations'] as const){
      if(!scopes.includes(scope))continue
      setActiveSection(scope==='instructions'?'Dosage instructions':'Prescribed investigations')
      let snapshot=extra[scope]
      if(!snapshot||snapshot.analysis_id!==uploaded.analysis_id)snapshot=await sections.status(uploaded.analysis_id,scope,signal)
      if(version!==sequence.current)return
      setExtra(current=>({...current,[scope]:snapshot}))
      if(['succeeded','running'].includes(snapshot.status))continue
      const result=await sections.analyze(snapshot,signal)
      if(version!==sequence.current)return
      setExtra(current=>({...current,[scope]:result}))
      if(result.error&&['configuration_error','quota_or_rate_limit'].includes(result.error.category)){
        setError('Extraction stopped after a configuration/quota failure. Completed sections are preserved; remaining selected sections have not run.');break
      }
    }
    setBrowserTimings({upload:uploadMs,extraction:performance.now()-extractionStart,total:performance.now()-started})
  })}
  function edit(index:number,field:keyof MedicineRecord,value:string){
    const previous=data
    const next=field==='duration_days'?(value===''?null:Number(value)):value.trim()===''?null:value
    setRecords(items=>items.map((record,i)=>i===index?{...record,[field]:next}:record))
    setDirty(true);setAck(false);setExplanation(null)
    if(previous&&(previous.reviewed||previous.confirmed)){
      setData({...previous,confirmed:false,reviewed:false})
      void run('Invalidating confirmation',async()=>{const version=sequence.current;const fresh=await client.invalidate(previous);if(version===sequence.current)setData(fresh)})
    }
  }
  function save(){void run('Saving review',async()=>{if(!data)return;const version=sequence.current;const fresh=await client.review(data,records);if(version===sequence.current)accept(fresh)})}
  function confirm(){void run('Confirming',async()=>{if(!data||dirty||!ack)return;const version=sequence.current;const fresh=await client.confirm(data);if(version===sequence.current){setData(fresh);setExplanation(null)}})}
  function explain(){void run('Explaining',async()=>{if(!data?.confirmed||dirty)return;const version=sequence.current;const result=await client.explain(data,language);if(version===sequence.current)setExplanation(result)})}
  const failed=data?.status==='failed'
  const success=data?.status==='succeeded'
  const pending=selected.some(scope=>scope==='medicines'?!data||['not_requested','failed'].includes(data.status):!extra[scope]||['not_requested','failed'].includes(extra[scope]!.status))
  const partial=[data,...Object.values(extra)].some(s=>s?.status==='succeeded')&&[data,...Object.values(extra)].some(s=>s?.status==='failed')
  const selectedFailed=selected.some(scope=>scope==='medicines'?failed:extra[scope]?.status==='failed')
  return <><PageHeading eyebrow="FROM IMAGE TO UNDERSTANDING" title="Prescription analysis" description="Upload, analyze, review and explicitly confirm. Your review always comes first." action={<Badge tone="coral">Local demo session · no account authentication</Badge>}/>
    <div className="workflow-steps"><span className="current"><b>1</b> Upload & analyze</span><span><b>2</b> Review all ten fields</span><span><b>3</b> Confirm & explain</span></div>
    <div className="analysis-grid"><section className="panel upload-panel"><div className="panel-heading"><span className="icon-box blue"><FileScan size={20}/></span><div><h2>Your prescription</h2><p>PNG/JPEG · Gemini extraction stays on Python.</p></div></div><ImageUploader onChange={sourceChanged}/><div className="section-selector"><h3>Choose extraction sections</h3>{([['medicines','Medicines'],['instructions','Dosage instructions'],['investigations','Prescribed investigations']] as const).map(([scope,label])=><label className={'section-option '+(selected.includes(scope)?'checked':'')} key={scope}><input type="checkbox" checked={selected.includes(scope)} disabled={!!busy} onChange={e=>setSelected(items=>e.target.checked?[...items,scope]:items.filter(s=>s!==scope))}/><span>{label}<small>Independent extraction, review and confirmation</small></span><span className="custom-check">{selected.includes(scope)&&<Check size={12}/>}</span></label>)}<div className="section-option"><LockKeyhole size={15}/><span>Strip expiry<small>Separate image workflow; not integrated here</small></span></div></div><button className="button full-width" onClick={()=>analyze()} disabled={!file||!!busy||!selected.length||!pending}>{busy==='Analyzing'?<LoaderCircle className="spin" size={17}/>:<Sparkles size={17}/>} {busy==='Analyzing'?'Analyzing image\u2026':selectedFailed?'Retry AI analysis':'Analyze with AI'}</button><p className="form-footnote">Only this explicit action sends the image to the Python server and Gemini. Use fictional or privacy-approved images.</p></section>
    <aside className="analysis-side"><section className="panel care-panel"><span className="eyebrow">A MOMENT OF CARE</span><h2>Keep the source.<br/>Check every detail.</h2><ul><li><Check size={16}/> Use a sharp, well-lit image.</li><li><Check size={16}/> Missing information stays unknown.</li><li><Check size={16}/> Confirming does not resolve uncertainty.</li><li><Check size={16}/> Edits remove prior confirmation.</li></ul><div className="handwriting-note"><AlertTriangle size={18}/><p><strong>Handwriting is experimental.</strong> Check all extracted text against the original. This is not medical advice.</p></div></section><Notice>Demo sessions expire after 30 minutes and are held only in server memory. Authentication is not connected. Images are sent only when you choose Analyze.</Notice></aside></div>
    {busy&&<div className="notice" role="status" aria-live="polite"><LoaderCircle className="spin" size={17}/>{busy==='Analyzing'?<div><strong>{phase==='uploading'?'Uploading and validating your image…':'Waiting for Gemini extraction…'}</strong><p>Current section: {activeSection}. {elapsed} s elapsed. {elapsed>=20?'The request is still pending. You can keep this page open; no automatic retry will be sent.':'Your original image and unknown values will be preserved for review.'}</p></div>:`${busy}…`}</div>}
    {browserTimings&&<p className="form-footnote">{partial?'Analysis request finished with partial results':success?'Analysis completed':'Analysis request finished'} in {(browserTimings.total/1000).toFixed(1)} s · Upload/session {(browserTimings.upload/1000).toFixed(1)} s · Extraction request {(browserTimings.extraction/1000).toFixed(1)} s</p>}
    {error&&<div className="error-message" role="alert">{error}<button className="text-link" onClick={()=>{if(data)void run('Refreshing',async()=>{const version=sequence.current;const fresh=await client.status(data);if(version===sequence.current)accept(fresh)})}} disabled={!data||!!busy}>Refresh current server state</button></div>}
    {failed&&<div className="error-message" role="alert"><strong>Extraction failed — no successful result.</strong><p>{data.error?.category}: {data.error?.message}</p><p>No automatic API or network retry was made. A retry is a new explicit request; do not retry a consumed guarded diagnostic attempt.</p></div>}
    {partial&&<Notice>Partial results: completed sections are preserved. Review each successful section independently; failed sections require an explicit retry.</Notice>}<section className="results-section"><div className="section-heading"><div><span className="eyebrow">MEDICINES · INDEPENDENT CONFIRMATION SCOPE</span><h2>Review extracted medicines</h2></div><Badge tone={data?.confirmed&&!dirty?'green':'muted'}>{data?.confirmed&&!dirty?'Confirmed by server':success?'Review required':'Awaiting extraction'}</Badge></div>
    {!success?<section className="panel"><p>{failed?'The extraction failed. This is different from finding no medicines.':'No completed extraction yet. Upload an image, then choose Analyze with AI.'}</p></section>:<><p className="review-intro">Check every field, including unknown values, against the image. Confidence and the extraction review flag describe the original OCR result and are read-only. They are not measured accuracy or proof of clinical correctness.</p>{records.length===0&&<Notice>Extraction succeeded with zero medicines. No records were invented. You may explicitly review and confirm this empty result.</Notice>}
      <div className="medicine-records">{records.map((record,index)=><section className="panel" key={index}><div className="panel-topline"><h2>Medicine {index+1}</h2><Badge tone={record.needs_review?'coral':'muted'}>{record.needs_review?'OCR flagged for review':'Still requires your review'}</Badge></div><div className="source-text"><span className="micro">ORIGINAL OCR TEXT · PRESERVED</span><p>{data.original_records?.[index]?.raw_text??'Unknown / not recorded'}</p></div><div className="medicine-fields">{MEDICINE_FIELDS.map(field=><label key={field}>{labels[field]}{field==='confidence'||field==='needs_review'?<output className="read-only-value">{record[field]===null?'Unknown / not recorded':String(record[field])}</output>:field==='form'?<select aria-label={`${labels[field]} ${index+1}`} disabled={!!busy} value={record.form??''} onChange={e=>edit(index,field,e.target.value)}><option value="">Unknown / not recorded</option>{['tablet','capsule','syrup','drops'].map(form=><option key={form}>{form}</option>)}</select>:field==='raw_text'?<textarea aria-label={`${labels[field]} ${index+1}`} disabled={!!busy} value={record.raw_text??''} placeholder="Unknown / not recorded" onChange={e=>edit(index,field,e.target.value)}/>:<input aria-label={`${labels[field]} ${index+1}`} disabled={!!busy} value={record[field]??''} type={field==='duration_days'?'number':'text'} min={field==='duration_days'?1:undefined} step={field==='duration_days'?1:undefined} placeholder="Unknown / not recorded" onChange={e=>edit(index,field,e.target.value)}/>}</label>)}</div><p className="review-warning"><AlertTriangle size={15}/>Unknown values remain null. Do not guess doses, ingredients or dates.</p></section>)}</div>
      <section className="panel confirmation-panel"><button className="button secondary" disabled={!!busy} onClick={save}>{data.reviewed&&!dirty?'Save review again':'Save reviewed records'}</button><p>{dirty?'Unsaved edits. Confirmation and explanation are unavailable.':data.reviewed?'Current records saved for explicit confirmation.':'Save the current records, including any unknown values, before confirming.'}</p><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={!!busy||dirty||!data.reviewed} onChange={e=>setAck(e.target.checked)}/> I have reviewed every field against the image, including unknown values and warnings. Confirmation does not authorize treatment or scheduling.</label><button className="button" onClick={confirm} disabled={!!busy||dirty||!data.reviewed||!ack||data.confirmed}><ShieldCheck size={16}/>{data.confirmed?'Confirmed by server':'Confirm medicines'}</button></section>
    </>}</section>
    <div className="scoped-results">{(['instructions','investigations'] as const).map(scope=>extra[scope]&&<SectionReview key={(data?.analysis_id??'')+':'+scope} snapshot={extra[scope]!} client={sections} disabled={!!busy} onChange={snapshot=>setExtra(current=>({...current,[scope]:snapshot}))} onRetry={()=>analyze([scope])}/>)}</div>
    <section className="panel explanation-panel"><div><span className="icon-box coral"><Languages size={23}/></span><h2>Understanding, in your words.</h2><p>Explanations describe confirmed text using the existing controlled glossary. They do not provide treatment advice.</p><div className="language-options" role="group" aria-label="Explanation language">{([['en','English'],['hi','हिन्दी'],['hinglish','Hinglish']] as const).map(([id,label])=><button key={id} disabled={!!busy} className={language===id?'selected':''} aria-pressed={language===id} onClick={()=>{setLanguage(id);setExplanation(null)}}>{label}</button>)}</div><button className="button secondary" onClick={explain} disabled={!!busy||!data?.confirmed||dirty}>Explain confirmed medicines</button></div><div className="explanation-empty"><p>Review → Save → Explicitly confirm → Explain.</p><span>ENGLISH · हिन्दी · HINGLISH</span></div></section>
    {explanation&&<section className="panel real-explanation" aria-label="Confirmed medicine explanation"><h2>Explanation of your confirmed text</h2><p>{explanation.notice}</p>{explanation.status==='empty'&&<Notice>No confirmed medicines to explain.</Notice>}{explanation.medicines.map(m=><div key={m.record_index}><h3>Medicine {m.record_index+1}</h3>{m.fields.map(f=><p key={f.field}>{f.text}</p>)}{m.glossary&&<Notice>{m.glossary.text}</Notice>}</div>)}{explanation.issues.length>0&&<div><h3>Warnings and unknown values</h3>{explanation.issues.map((issue,i)=><p key={i}>{issue.text}</p>)}</div>}</section>}
  </>
}
