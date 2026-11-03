import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect, useRef, useState } from 'react'
import { Check, FileScan, ShieldCheck, Sparkles, AlertTriangle, LoaderCircle } from 'lucide-react'
import { Badge, Notice, PageHeading } from '../components/ui'
import ImageUploader from '../components/ImageUploader'
import PrescriptionExplanation from '../components/PrescriptionExplanation'
import type { Language, MedicineRecord, Section } from '../lib/api'
import SectionReview from '../components/SectionReview'
import { parseSection, sectionClient as connectedSectionClient } from '../lib/sections'
import type { ExtraScope, SectionClient, SectionSnapshot } from '../lib/sections'
import { ApiError, MEDICINE_FIELDS, prescriptionClient } from '../lib/prescriptions'
import type { AnalysisSnapshot, ExplanationPayload, PrescriptionClient } from '../lib/prescriptions'
import RecognitionPanel,{NumeralReading} from '../components/RecognitionPanel'
import PatientMedicineExplanation from '../components/PatientMedicineExplanation'
import ScheduleAssociations from '../components/ScheduleAssociations'
import type { RecognitionClient,RecognitionMode } from '../lib/recognition'

const labels:Record<keyof MedicineRecord,string>={raw_text:'Original medicine text',name:'Medicine name',salt:'Printed ingredient',strength:'Written strength',form:'Form',frequency_pattern:'Written frequency',duration_days:'Duration in days',timing:'Written timing',confidence:'Extraction confidence (uncalibrated)',needs_review:'Extraction review flag'}
export default function PrescriptionFlow({client=prescriptionClient,sections=connectedSectionClient,recognition}:{client?:PrescriptionClient;sections?:SectionClient;recognition?:RecognitionClient}) {
  const {language:interfaceLanguage}=useUiLanguage()

  const [file,setFile]=useState<File|null>(null)
  const [recognitionMode,setRecognitionMode]=useState<RecognitionMode|null>(null)
  const [restoredFile,setRestoredFile]=useState<File|null>(null)
  const [previewVersion,setPreviewVersion]=useState(0)
  const [restoreNotice,setRestoreNotice]=useState('')
  const [data,setData]=useState<AnalysisSnapshot|null>(null)
  const [records,setRecords]=useState<MedicineRecord[]>([])
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [dirty,setDirty]=useState(false)
  const [ack,setAck]=useState(false)
  const [language,setLanguage]=useState<Language>(interfaceLanguage)
  const [explanation,setExplanation]=useState<ExplanationPayload|null>(null)
  const [selected,setSelected]=useState<Section[]>(['medicines','instructions'])
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
  useEffect(()=>{restore();return()=>{sequence.current++;abort.current?.abort()}},[client])
  async function restore(){
    const version=sequence.current
    try{
      const fresh=await client.current()
      if(version!==sequence.current)return
      if(!fresh){if(currentData.current){setData(null);setRecords([]);setExtra({});setFile(null);setRestoredFile(null);setExplanation(null);setAck(false);setDirty(false);setBrowserTimings(null);setError('');setPreviewVersion(v=>v+1)}setRestoreNotice('No active prescription in this demo session. It may be new, expired or restarted. No account history is stored.');return}
      accept(fresh)
      const hydrated:Partial<Record<ExtraScope,SectionSnapshot>>={}
      for(const scope of ['instructions'] as const){if(fresh.sections?.[scope])hydrated[scope]=parseSection(fresh.sections[scope],scope,fresh.analysis_id)}
      setExtra(hydrated)
      setRestoreNotice('Restored the current server analysis and confirmations. No OCR was rerun. Unsaved browser edits are not part of the saved review.')
      try{const source=await client.image(fresh);if(version===sequence.current){setFile(source);setRestoredFile(source)}}
      catch(e){if(version===sequence.current)showError(e)}
    }catch(e){if(version===sequence.current)showError(e)}
  }
  useEffect(()=>{
    if(busy!=='Analyzing')return
    const start=performance.now();setElapsed(0)
    const interval=window.setInterval(()=>setElapsed(Math.floor((performance.now()-start)/1000)),1000)
    return()=>window.clearInterval(interval)
  },[busy])
  function showError(e:unknown){setError(e instanceof ApiError?`${e.category}: ${e.message}`:'The operation could not complete. Please try again.')}
  function sourceChanged(next:File|null){
    setRestoredFile(null);setRestoreNotice('')
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
    if((!file&&!data)||!scopes.length)return
    const started=performance.now();let uploadMs=0
    setPhase('uploading');setBrowserTimings(null)
    const version=sequence.current
    await clearQueue.current
    if(version!==sequence.current)return
    let uploaded=data
    if(!uploaded){const uploadStart=performance.now();uploaded=await client.upload(file!,signal);uploadMs=performance.now()-uploadStart;if(version!==sequence.current)return;setData(uploaded)}
    setPhase('extracting')
    const extractionStart=performance.now()
    if(scopes.includes('medicines')&&['not_requested','failed'].includes(uploaded.status)){
      setActiveSection('Medicines');setExplanation(null);setAck(false)
      setData({...uploaded,confirmed:false,reviewed:false})
      const result=await client.analyze(uploaded,signal)
      if(version!==sequence.current)return
      accept(result);uploaded=result
      if(result.error&&['configuration_error','quota_or_rate_limit','quota_exceeded','authentication_error','permission_denied','model_unavailable','provider_bad_request','provider_error','extraction_timeout','network_error'].includes(result.error.category)){
        setError('Extraction stopped after a service failure. Completed sections are preserved; other selected sections have not run.');return
      }
    }
    for(const scope of ['instructions'] as const){
      if(!scopes.includes(scope))continue
      setActiveSection('Dosage instructions')
      let snapshot=extra[scope]
      if(!snapshot||snapshot.analysis_id!==uploaded.analysis_id)snapshot=await sections.status(uploaded.analysis_id,scope,signal)
      if(version!==sequence.current)return
      setExtra(current=>({...current,[scope]:snapshot}))
      if(['succeeded','running'].includes(snapshot.status))continue
      const result=await sections.analyze(snapshot,signal)
      if(version!==sequence.current)return
      setExtra(current=>({...current,[scope]:result}))
      if(result.error&&['configuration_error','quota_or_rate_limit','quota_exceeded','authentication_error','permission_denied','model_unavailable','provider_bad_request','provider_error','extraction_timeout','network_error'].includes(result.error.category)){
        setError('Extraction stopped after a service failure. Completed sections are preserved; other selected sections have not run.');break
      }
    }
    setBrowserTimings({upload:uploadMs,extraction:performance.now()-extractionStart,total:performance.now()-started})
  })}
  function edit(index:number,field:keyof MedicineRecord,value:string){
    const previous=data
    const next=field==='duration_days'?(value===''?null:Number(value)):value.trim()===''?null:value
    setRecords(items=>items.map((record,i)=>i===index?{...record,[field]:next,needs_review:true}:record))
    setDirty(true);setAck(false);setExplanation(null)
    if(previous&&(previous.reviewed||previous.confirmed)){
      setData({...previous,confirmed:false,reviewed:false})
      void run('Invalidating confirmation',async()=>{const version=sequence.current;const fresh=await client.invalidate(previous);if(version===sequence.current)setData(fresh)})
    }
  }
  function save(){void run('Saving review',async()=>{if(!data)return;const version=sequence.current;const fresh=await client.review(data,records);if(version===sequence.current)accept(fresh)})}
  function confirm(){void run('Confirming',async()=>{if(!data||dirty||!ack)return;const version=sequence.current;const fresh=await client.confirm(data);if(version===sequence.current){setData(fresh);setExplanation(null)}})}
  function explain(chosen:Language=language){void run('Explaining',async()=>{if(!data?.confirmed||dirty)return;setExplanation(null);const version=sequence.current;const result=await client.explain(data,chosen);if(result.language!==chosen)throw new ApiError('invalid_response','The returned explanation language did not match your selection.');if(version===sequence.current)setExplanation(result)})}
  function selectLanguage(chosen:Language){setLanguage(chosen);setExplanation(null)}
  useEffect(()=>{selectLanguage(interfaceLanguage)},[interfaceLanguage])
  const failed=data?.status==='failed'
  const success=data?.status==='succeeded'
  const pending=selected.some(scope=>scope==='medicines'?!data||['not_requested','failed'].includes(data.status):!extra[scope]||['not_requested','failed'].includes(extra[scope]!.status))
  const partial=[data,...Object.values(extra)].some(s=>s?.status==='succeeded')&&[data,...Object.values(extra)].some(s=>s?.status==='failed')
  const selectedFailed=selected.some(scope=>scope==='medicines'?failed:extra[scope]?.status==='failed')
  return <><PageHeading eyebrow={tr("FROM IMAGE TO UNDERSTANDING")} title={tr("Prescription analysis")} description={tr("Upload, analyze, review and explicitly confirm. Your review always comes first.")} action={<Badge tone="coral">{tr("Temporary workspace · prescriptions are not saved to your account")}</Badge>}/>
    <RecognitionPanel client={recognition} onMode={setRecognitionMode}/>
    <div className="workflow-steps"><span className="current"><b>1</b>{tr(" Upload & analyze")}</span><span><b>2</b>{tr(" Review all ten fields")}</span><span><b>3</b>{tr(" Confirm & explain")}</span></div>
    <div className="analysis-grid"><section className="panel upload-panel"><div className="panel-heading"><span className="icon-box blue"><FileScan size={20}/></span><div><h2>{tr("Your prescription")}</h2><p>{tr("PNG · JPG · PDF · DOCX · TXT · Gemini extraction stays on Python.")}</p></div></div><ImageUploader allowDocuments key={previewVersion} onChange={sourceChanged} restoredFile={restoredFile}/><div className="section-selector"><h3>{tr("Choose extraction sections")}</h3>{([['medicines','Medicines'],['instructions','Dosage instructions']] as const).map(([scope,label])=><label className={'section-option '+(selected.includes(scope)?'checked':'')} key={scope}><input type="checkbox" checked={selected.includes(scope)} disabled={!!busy} onChange={e=>setSelected(items=>e.target.checked?[...items,scope]:items.filter(s=>s!==scope))}/><span>{tr(label)}<small>{tr("Independent extraction, review and confirmation")}</small></span><span className="custom-check">{selected.includes(scope)&&<Check size={12}/>}</span></label>)}</div><button className="button full-width" onClick={()=>analyze()} disabled={(!file&&!data)||!!busy||!selected.length||!pending}>{busy==='Analyzing'?<LoaderCircle className="spin" size={17}/>:<Sparkles size={17}/>} {busy==='Analyzing'?tr(recognitionMode==='offline_fixture'?"Loading fixture simulation…":"Analyzing prescription…"):selectedFailed?tr(recognitionMode==='offline_fixture'?"Retry fixture simulation":"Retry AI analysis"):tr(recognitionMode==='offline_fixture'?"Run fixture simulation":"Analyze Prescription with AI")}</button><p className="form-footnote">{tr(recognitionMode==='offline_fixture'?"Only this action uploads the registered image to the local fixture runner. It does not send it to Gemini.":"Only this explicit action sends the file to the Python server. The verified extraction mode determines whether Gemini is called.")}</p></section>
    <aside className="analysis-side"><section className="panel care-panel"><span className="eyebrow">{tr("A MOMENT OF CARE")}</span><h2>{tr("Keep the source.")}<br/>{tr("Check every detail.")}</h2><ul><li><Check size={16}/>{tr(" Use a sharp, well-lit image.")}</li><li><Check size={16}/>{tr(" Missing information stays unknown.")}</li><li><Check size={16}/>{tr(" Confirming does not resolve uncertainty.")}</li><li><Check size={16}/>{tr(" Edits remove prior confirmation.")}</li></ul><div className="handwriting-note"><AlertTriangle size={18}/><p><strong>{tr("Handwriting is experimental.")}</strong>{tr(" Check all extracted text against the original. This is not medical advice.")}</p></div></section><Notice>{tr("Prescription workspaces expire after 30 minutes and are held only in server memory. Images are sent only when you choose Analyze.")}</Notice></aside></div>
    {restoreNotice&&<Notice>{tr(restoreNotice)}</Notice>}<button className="text-link" disabled={!!busy||dirty} onClick={()=>{sequence.current++;void restore()}}>{tr("Restore current session")}</button>
    {busy&&<div className="notice" role="status" aria-live="polite"><LoaderCircle className="spin" size={17}/>{busy==='Analyzing'?<div><strong>{phase==='uploading'?tr("Uploading and validating your image…"):tr(recognitionMode==='offline_fixture'?"Loading static fixture results…":recognitionMode==='gemini'?"Waiting for Gemini extraction…":"Waiting for extraction service…")}</strong><p>{tr("Current section: ")}{tr(activeSection)}. {elapsed}{tr(" s elapsed. ")}{elapsed>=20?tr("The request is still pending. You can keep this page open; no automatic retry will be sent."):tr("Your original image and unknown values will be preserved for review.")}</p></div>:tr("{0}…",[tr(busy)])}</div>}
    {browserTimings&&<p className="form-footnote">{partial?tr("Analysis request finished with partial results"):success?tr(recognitionMode==='offline_fixture'?"Fixture simulation completed":"Analysis completed"):tr("Analysis request finished")}{tr(" in ")}{(browserTimings.total/1000).toFixed(1)}{tr(" s · Upload/session ")}{(browserTimings.upload/1000).toFixed(1)}{tr(" s · Extraction request ")}{(browserTimings.extraction/1000).toFixed(1)}{tr(" s")}</p>}
    {error&&<div className="error-message" role="alert">{uiError(error)}<button className="text-link" onClick={()=>{if(data)void run('Refreshing',async()=>{const version=sequence.current;const fresh=await client.status(data);if(version===sequence.current)accept(fresh)})}} disabled={!data||!!busy}>{tr("Refresh current server state")}</button></div>}
    {failed&&<div className="error-message" role="alert"><strong>{tr("Extraction failed — no successful result.")}</strong><p>{uiError(data.error)}</p>{data.diagnostic_reference&&<p>{tr("Diagnostic reference: {0}",[data.diagnostic_reference])}</p>}<p>{tr("No automatic API or network retry was made. A retry is a new explicit request; do not retry a consumed guarded diagnostic attempt.")}</p></div>}
    {partial&&<Notice>{tr("Partial results: completed sections are preserved. Review each successful section independently; failed sections require an explicit retry.")}</Notice>}<section className="results-section"><div className="section-heading"><div><span className="eyebrow">{tr("MEDICINES · INDEPENDENT CONFIRMATION SCOPE")}</span><h2>{tr("Review extracted medicines")}</h2></div><Badge tone={data?.confirmed&&!dirty?'green':'muted'}>{data?.confirmed&&!dirty?tr("Confirmed by server"):success?tr("Review required"):tr("Awaiting extraction")}</Badge></div>
    {!success?<section className="panel"><p>{failed?tr("The extraction failed. This is different from finding no medicines."):tr("No completed extraction yet. Upload an image, then choose Analyze with AI.")}</p></section>:<><p className="review-intro">{tr("Check every field, including unknown values, against the image. Confidence and the extraction review flag describe the original OCR result and are read-only. They are not measured accuracy or proof of clinical correctness.")}</p>{records.length===0&&<Notice>{tr("Extraction succeeded with zero medicines. No records were invented. You may explicitly review and confirm this empty result.")}</Notice>}
      <NumeralReading metadata={data}/><div className="medicine-records">{records.map((record,index)=><section className="panel" key={index}><div className="panel-topline"><h2>{tr("Medicine ")}{index+1}</h2><Badge tone={record.needs_review?'coral':'muted'}>{record.needs_review?tr(recognitionMode==='offline_fixture'?"Fixture flagged for review":"OCR flagged for review"):tr("Still requires your review")}</Badge></div><div className="source-text"><span className="micro">{tr(recognitionMode==='offline_fixture'?"ORIGINAL FIXTURE TEXT · NOT OCR":"ORIGINAL OCR TEXT · PRESERVED")}</span><p>{data.original_records?.[index]?.raw_text ?? tr("Unknown / not recorded")}</p></div><div className="medicine-fields">{MEDICINE_FIELDS.map(field=><label key={field}>{tr(labels[field])}{field==='confidence'||field==='needs_review'?<output className="read-only-value">{data.original_records?.[index]?.[field]===null?tr("Unknown / not recorded"):tr(String(data.original_records?.[index]?.[field]??record[field]))}</output>:field==='form'?<select aria-label={tr("{0} {1}",[tr(labels[field]),index+1])} disabled={!!busy} value={record.form??''} onChange={e=>edit(index,field,e.target.value)}><option value="">{tr("Unknown / not recorded")}</option>{['tablet','capsule','syrup','drops'].map(form=><option key={form} value={form}>{tr(form)}</option>)}</select>:field==='raw_text'?<textarea aria-label={tr("{0} {1}",[tr(labels[field]),index+1])} disabled={!!busy} value={record.raw_text??''} placeholder={tr("Unknown / not recorded")} onChange={e=>edit(index,field,e.target.value)}/>:<input aria-label={tr("{0} {1}",[tr(labels[field]),index+1])} disabled={!!busy} value={record[field]??''} type={field==='duration_days'?'number':'text'} min={field==='duration_days'?1:undefined} step={field==='duration_days'?1:undefined} placeholder={tr("Unknown / not recorded")} onChange={e=>edit(index,field,e.target.value)}/>}</label>)}</div><p className="review-warning"><AlertTriangle size={15}/>{tr("Unknown values remain null. Do not guess doses, ingredients or dates.")}</p><PatientMedicineExplanation source={data} index={index} contextKey={data.analysis_id+data.revision+(extra.instructions?.revision??'none')+String(extra.instructions?.confirmed)} disabled={!!busy||dirty||!data.confirmed}/></section>)}</div>
      <section className="panel confirmation-panel"><button className="button secondary" disabled={!!busy} onClick={save}>{data.reviewed&&!dirty?tr("Save review again"):tr("Save reviewed records")}</button><p>{dirty?tr("Unsaved edits. Confirmation and explanation are unavailable."):data.reviewed?tr("Current records saved for explicit confirmation."):tr("Save the current records, including any unknown values, before confirming.")}</p><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={!!busy||dirty||!data.reviewed} onChange={e=>setAck(e.target.checked)}/>{tr(" I have reviewed every field against the image, including unknown values and warnings. Confirmation does not authorize treatment or scheduling.")}</label><button className="button" onClick={confirm} disabled={!!busy||dirty||!data.reviewed||!ack||data.confirmed}><ShieldCheck size={16}/>{data.confirmed?tr("Confirmed by server"):tr("Confirm medicines")}</button></section>
    </>}</section>
    <div className="scoped-results" id="instruction-review">{(['instructions'] as const).map(scope=>extra[scope]&&<SectionReview key={(data?.analysis_id??'')+':'+scope} snapshot={extra[scope]!} client={sections} disabled={!!busy} onChange={snapshot=>{setExplanation(null);setExtra(current=>({...current,[scope]:snapshot}))}} onRetry={()=>analyze([scope])}/>)}</div>
    {data?.confirmed&&!dirty&&<ScheduleAssociations key={data.revision+(extra.instructions?.revision??'none')+String(extra.instructions?.confirmed)}/>}
    <PrescriptionExplanation language={language} onLanguage={selectLanguage} onExplain={()=>explain()} explanation={explanation} records={records} confirmed={!!data?.confirmed&&!dirty} busy={busy==='Explaining'} disabled={!!busy}/>
  </>
}
