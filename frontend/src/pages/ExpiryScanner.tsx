import { translateReason as reason } from '../lib/language'
import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect,useRef,useState } from 'react'
import '../strip.css'
import { AlertTriangle,LoaderCircle,ScanLine,ShieldCheck } from 'lucide-react'
import { Badge,Notice,PageHeading } from '../components/ui'
import ImageUploader from '../components/ImageUploader'
import { ApiError } from '../lib/prescriptions'
import { editableStrip,stripClient,stripResultLabel } from '../lib/strip'
import type { StripClient,StripEdits,StripSnapshot } from '../lib/strip'
import {recognitionClient} from '../lib/recognition'
import type {RecognitionMode} from '../lib/recognition'

const nullable=(s:string)=>s.trim()?s:null
export default function ExpiryScanner({client=stripClient}:{client?:StripClient}){
  useUiLanguage()

  const [file,setFile]=useState<File|null>(null)
  const [mode,setMode]=useState<RecognitionMode|null>(null)
  useEffect(()=>{let active=true;recognitionClient.capabilities().then(s=>{if(active)setMode(s.mode)}).catch(()=>{});return()=>{active=false}},[])
  const [data,setData]=useState<StripSnapshot|null>(null)
  const [draft,setDraft]=useState<StripEdits|null>(null)
  const [dirty,setDirty]=useState(false)
  const [ack,setAck]=useState(false)
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [elapsed,setElapsed]=useState(0)
  const sequence=useRef(0);const operation=useRef<symbol|null>(null);const abort=useRef<AbortController|null>(null)
  const current=useRef(data);current.current=data
  const clearing=useRef<Promise<void>>(Promise.resolve())
  useEffect(()=>()=>{sequence.current++;abort.current?.abort()},[])
  useEffect(()=>{if(busy!=='Analyzing')return;const start=performance.now();setElapsed(0);const id=window.setInterval(()=>setElapsed(Math.floor((performance.now()-start)/1000)),1000);return()=>window.clearInterval(id)},[busy])
  function changed(next:File|null){
    sequence.current++;abort.current?.abort();operation.current=null;setFile(next);setData(null);setDraft(null);setDirty(false);setAck(false);setBusy('');setError('')
    if(current.current){clearing.current=clearing.current.catch(()=>{}).then(()=>client.clear());void clearing.current.catch(()=>setError('Could not clear the prior strip workflow. Reload before continuing.'))}
  }
  async function run(label:string,action:(signal:AbortSignal,version:number)=>Promise<void>){
    if(operation.current)return
    const token=Symbol();operation.current=token;const controller=new AbortController();abort.current=controller
    const version=sequence.current;setBusy(label);setError('')
    try{await action(controller.signal,version)}catch(e){if(version===sequence.current)setError(e instanceof ApiError?e.category+': '+e.message:'The strip operation could not complete.')}
    finally{if(operation.current===token){operation.current=null;abort.current=null;if(version===sequence.current)setBusy('')}}
  }
  function accept(s:StripSnapshot){setData(s);setDraft(s.payload?editableStrip(s.payload):null);setDirty(false);setAck(false)}
  function analyze(){void run('Analyzing',async(signal,version)=>{
    if(!file)return;await clearing.current;if(version!==sequence.current)return
    let uploaded=data
    if(!uploaded){uploaded=await client.upload(file,signal);if(version!==sequence.current)return;setData(uploaded)}
    if(!['not_requested','failed'].includes(uploaded.status))return
    const result=await client.analyze(uploaded,signal);if(version===sequence.current)accept(result)
  })}
  function edit(next:StripEdits){
    if(busy)return
    setDraft(next);setDirty(true);setAck(false)
    if(data&&(data.confirmed||data.reviewed)){
      const previous=data;setData({...data,confirmed:false,reviewed:false})
      void run('Invalidating review',async(_signal,version)=>{const fresh=await client.invalidate(previous);if(version===sequence.current)setData(fresh)})
    }
  }
  function save(){void run('Saving review',async(_signal,version)=>{if(!data||!draft)return;const fresh=await client.review(data,draft);if(version===sequence.current)accept(fresh)})}
  function confirm(){void run('Confirming',async(_signal,version)=>{if(!data||dirty||!ack||!data.reviewed)return;const fresh=await client.confirm(data);if(version===sequence.current)setData(fresh)})}
  const payload=data?.payload
  const extractionMode=data?.recognition_mode??mode
  const expiryState=!dirty&&data?.confirmed?data.expiry_status?.state:'unclear'
  return <><PageHeading eyebrow={tr("CHECK THE SMALL PRINT")} title={tr("Medicine Strip Expiry Scanner")} description={tr("Transcribe printed strip labels. Keep unclear dates unknown.")} action={<Badge tone="coral">{tr("Temporary workspace · prescriptions are not saved to your account")}</Badge>}/>
    <div className="analysis-grid"><section className="panel upload-panel"><div className="panel-heading"><span className="icon-box coral"><ScanLine size={22}/></span><div><h2>{tr("Your medicine-strip image")}</h2><p>{tr("Separate from every prescription image and confirmation.")}</p></div></div><ImageUploader label={tr("Medicine strip image")} onChange={changed}/><button className="button full-width" disabled={!file||!!busy||data?.status==='succeeded'} onClick={analyze}>{busy==='Analyzing'?<LoaderCircle className="spin" size={17}/>:<ScanLine size={17}/>} {busy==='Analyzing'?tr("Analyzing strip…"):data?.status==='failed'?tr("Retry strip analysis"):tr(extractionMode==='offline_fixture'?'Run strip fixture simulation':extractionMode==='gemini'?'Analyze strip with AI':'Analyze strip image')}</button><p className="form-footnote">{tr("Only an explicit action submits the image. Gemini mode performs real OCR; offline fixture mode returns static simulated data.")}</p></section><aside><Notice>{tr("Never infer expiry from manufacturing/batch dates, an unclear label or shelf life. USE BEFORE is preserved separately. Verify all details with a pharmacist.")}</Notice><Notice>{tr("A product link inside this photo is not an association with a prescription medicine. This workflow creates no medicine inventory, schedule or reminders.")}</Notice></aside></div>
    {<p className="form-footnote">{tr(extractionMode==='gemini'?'Gemini extraction mode':extractionMode==='offline_fixture'?'Offline fixture simulation':'Extraction mode unavailable')}</p>}
    <section className="panel" aria-label={tr('Expiry status')}>{data?.expiry_status&&<p>{tr('Compared on')}: {data.expiry_status.as_of}</p>}<h2>{tr(expiryState==='expired'?'Expired':expiryState==='not_expired_by_date'?'Not expired according to the confirmed date':'Expiry date unclear / not confirmed')}</h2><p>{tr('Month-only dates are compared by calendar month: a past month is expired, a future month is not expired by date, and the current month remains unclear. No expiry day is invented.')}</p><p>{tr('A printed expiry date does not establish medicine safety or storage quality.')}</p></section>
    {busy&&<div className="notice" role="status"><LoaderCircle className="spin" size={17}/>{tr(busy)}… {busy==='Analyzing'&&<span>{elapsed}{tr(" s elapsed. No automatic API/network retry.")}</span>}</div>}
    {error&&<div className="error-message" role="alert">{uiError(error)}{data&&<button className="text-link" disabled={!!busy} onClick={()=>void run('Refreshing',async(_signal,version)=>{const fresh=await client.status(data);if(version===sequence.current)accept(fresh)})}>{tr("Refresh current strip state")}</button>}</div>}
    {data?.status==='failed'&&<div className="error-message" role="alert"><strong>{tr("Strip extraction failed — no successful result.")}</strong><p>{uiError(data.error)}</p><p>{tr("This is different from successful extraction with an unknown expiry. Retry only by an explicit permitted action.")}</p></div>}
    {!payload&&data?.status!=='failed'&&<section className="panel strip-results"><h2>{tr("No strip analysis yet")}</h2><p>{tr("Upload an image and choose Analyze. No date has been inferred.")}</p></section>}
    {payload&&draft&&<section className="panel strip-results" aria-label={tr("Strip review")}><div className="panel-topline"><div><span className="eyebrow">{tr("VISIBLE LABEL TRANSCRIPTION")}</span><h2>{dirty?tr("Unsaved changes — save to parse reviewed text"):tr(stripResultLabel(payload))}</h2></div><Badge tone={data.confirmed&&!dirty?'green':'muted'}>{data.confirmed&&!dirty?tr("Confirmed by server"):tr("Explicit review required")}</Badge></div>
      <div className="expiry-reading"><strong>{dirty?tr("Pending server review"):payload.expiry?.iso ?? tr("Unknown / no expiry selected")}</strong><p>{dirty?tr("The previously parsed date is withheld until the corrected text is saved and parsed on Python."):payload.expiry?.precision==='month'?tr("Month precision only. No exact day is supplied or inferred."):payload.expiry?tr("Day precision preserved from the explicit source."):tr("Review every observation and warning below. Do not choose between conflicting dates by guessing.")}</p></div>
      <Notice>{tr("This is not an assessment of whether the medicine is safe to use. Confirmation acknowledges the reviewed text; it does not resolve uncertainty or authorize taking medicine.")}</Notice>
      <div className="source-text"><span className="micro">{tr("ORIGINAL EXTRACTED EXPIRY LINE")}</span><p>{data.original_payload?.raw_expiry_text ?? tr("Unknown / no single consistent expiry line")}</p></div>
      <div className="medicine-fields"><label>{tr("Printed medicine name")}<input aria-label={tr("Printed medicine name")} disabled={!!busy} value={draft.medicine_name??''} placeholder={tr("Unknown / not recorded")} onChange={e=>edit({...draft,medicine_name:nullable(e.target.value)})}/></label><label>{tr("Printed batch number")}<input aria-label={tr("Printed batch number")} disabled={!!busy} value={draft.batch_number??''} placeholder={tr("Unknown / not recorded")} onChange={e=>edit({...draft,batch_number:nullable(e.target.value)})}/></label><label>{tr("Products visible in this photo")}<select aria-label={tr("Products visible in this photo")} disabled={!!busy} value={draft.product_association} onChange={e=>edit({...draft,product_association:e.target.value as StripEdits['product_association']})}><option value="single_product">{tr("Single product")}</option><option value="multiple_products">{tr("Multiple products")}</option><option value="unclear">{tr("Unclear")}</option></select></label></div>
      <p className="review-warning"><AlertTriangle size={17}/>{tr("Extraction review flag: ")}{tr(String(payload.needs_review))}{tr(" · Confidence: ")}{payload.confidence ?? tr("Unknown")}{tr(" (uncalibrated, not measured accuracy)")}</p>
      <div className="strip-issues"><h3>{tr("Warnings and unresolved information")}</h3>{payload.issues.length?<ul>{payload.issues.map(issue=><li key={reason(issue)}>{reason(issue)}</li>)}</ul>:<p>{tr("No issue codes reported. Explicit verification is still required.")}</p>}</div>
      <h3>{tr("All date observations")}</h3>{draft.date_observations.length===0&&<p>{tr("No date observations were extracted.")}</p>}
      {draft.date_observations.map((observation,index)=>{
        const source=payload.date_observations[index];const original=data.original_payload?.date_observations[index]
        function update(field:'raw_label'|'raw_date_text'|'raw_text'|'association',value:string){edit({...draft!,date_observations:draft!.date_observations.map((o,i)=>i===index?{...o,[field]:field==='association'?value:nullable(value)}:o)})}
        return <article className="scoped-record" key={index}><div className="source-text"><span className="micro">{tr("ORIGINAL OBSERVATION ")}{index+1}</span><p>{original?.raw_text ?? tr("Unknown / not recorded")}</p></div><div className="medicine-fields">{(['raw_label','raw_date_text','raw_text'] as const).map(field=><label key={field}>{field==='raw_label'?tr("Printed label"):field==='raw_date_text'?tr("Date text as written"):tr("Full source line")}<input aria-label={tr(field==='raw_label'?'Printed label':field==='raw_date_text'?'Date text as written':'Full source line')+' '+(index+1)} disabled={!!busy} value={observation[field]??''} placeholder={tr("Unknown / not recorded")} onChange={e=>update(field,e.target.value)}/></label>)}<label>{tr("Date-to-product link inside this photo")}<select aria-label={tr("Date-to-product link {0}",[index+1])} disabled={!!busy} value={observation.association} onChange={e=>update('association',e.target.value)}><option value="same_product">{tr("Same product in photo")}</option><option value="unclear">{tr("Unclear")}</option></select></label></div><p>{tr("Backend label classification: ")}{tr(source.label_kind)}{tr(". Parsed date token: ")}{source.parsed_date?.iso ?? tr("Unknown")}{tr(". A parsed manufacturing/batch token is not an expiry.")}</p><p>{tr("Observation uncertainty: ")}{tr(String(source.uncertain))}{tr(" · Confidence: ")}{source.confidence ?? tr("Unknown")}{tr(" (uncalibrated)")}</p>{source.parse_issues.length>0&&<p className="review-warning">{tr("Parse warnings: ")}{source.parse_issues.map(reason).join(', ')}</p>}</article>
      })}
      <div className="confirmation-panel"><button className="button secondary" disabled={!!busy} onClick={save}>{tr("Save reviewed strip details")}</button><p>{tr("Saving corrections runs the existing conservative parser on Python, without another Gemini request. ")}{dirty?tr("Unsaved edits have removed prior confirmation."):""}</p><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={!!busy||dirty||!data.reviewed} onChange={e=>setAck(e.target.checked)}/>{tr(" I checked every label, date observation, unknown value and warning against the packaging. This does not establish medicine safety.")}</label><button className="button" disabled={!!busy||dirty||!ack||!data.reviewed||data.confirmed} onClick={confirm}><ShieldCheck size={16}/>{data.confirmed?tr("Confirmed by server"):tr("Confirm strip details")}</button></div>
    </section>}
  </>
}
