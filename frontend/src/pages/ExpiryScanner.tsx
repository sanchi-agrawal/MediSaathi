import { useEffect,useRef,useState } from 'react'
import '../strip.css'
import { AlertTriangle,LoaderCircle,ScanLine,ShieldCheck } from 'lucide-react'
import { Badge,Notice,PageHeading } from '../components/ui'
import ImageUploader from '../components/ImageUploader'
import { ApiError } from '../lib/prescriptions'
import { editableStrip,stripClient,stripResultLabel } from '../lib/strip'
import type { StripClient,StripEdits,StripSnapshot } from '../lib/strip'

const nullable=(s:string)=>s.trim()?s:null
export default function ExpiryScanner({client=stripClient}:{client?:StripClient}){
  const [file,setFile]=useState<File|null>(null)
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
  return <><PageHeading eyebrow="CHECK THE SMALL PRINT" title="Medicine expiry scanner" description="Transcribe printed strip labels. Keep unclear dates unknown." action={<Badge tone="coral">Local demo · no account authentication</Badge>}/>
    <div className="analysis-grid"><section className="panel upload-panel"><div className="panel-heading"><span className="icon-box coral"><ScanLine size={22}/></span><div><h2>Your medicine-strip image</h2><p>Separate from every prescription image and confirmation.</p></div></div><ImageUploader label="Medicine strip image" onChange={changed}/><button className="button full-width" disabled={!file||!!busy||data?.status==='succeeded'} onClick={analyze}>{busy==='Analyzing'?<LoaderCircle className="spin" size={17}/>:<ScanLine size={17}/>} {busy==='Analyzing'?'Analyzing strip…':data?.status==='failed'?'Retry strip analysis':'Analyze strip with AI'}</button><p className="form-footnote">Only this explicit action sends the image to Python and Gemini. Use fictional or privacy-approved images.</p></section><aside><Notice>Never infer expiry from manufacturing/batch dates, an unclear label or shelf life. USE BEFORE is preserved separately. Verify all details with a pharmacist.</Notice><Notice>A product link inside this photo is not an association with a prescription medicine. This workflow creates no medicine inventory, schedule or reminders.</Notice></aside></div>
    {busy&&<div className="notice" role="status"><LoaderCircle className="spin" size={17}/>{busy}… {busy==='Analyzing'&&<span>{elapsed} s elapsed. No automatic API/network retry.</span>}</div>}
    {error&&<div className="error-message" role="alert">{error}{data&&<button className="text-link" disabled={!!busy} onClick={()=>void run('Refreshing',async(_signal,version)=>{const fresh=await client.status(data);if(version===sequence.current)accept(fresh)})}>Refresh current strip state</button>}</div>}
    {data?.status==='failed'&&<div className="error-message" role="alert"><strong>Strip extraction failed — no successful result.</strong><p>{data.error?.category}: {data.error?.message}</p><p>This is different from successful extraction with an unknown expiry. Retry only by an explicit permitted action.</p></div>}
    {!payload&&data?.status!=='failed'&&<section className="panel strip-results"><h2>No strip analysis yet</h2><p>Upload an image and choose Analyze. No date has been inferred.</p></section>}
    {payload&&draft&&<section className="panel strip-results" aria-label="Strip review"><div className="panel-topline"><div><span className="eyebrow">VISIBLE LABEL TRANSCRIPTION</span><h2>{dirty?'Unsaved changes — save to parse reviewed text':stripResultLabel(payload)}</h2></div><Badge tone={data.confirmed&&!dirty?'green':'muted'}>{data.confirmed&&!dirty?'Confirmed by server':'Explicit review required'}</Badge></div>
      <div className="expiry-reading"><strong>{dirty?'Pending server review':payload.expiry?.iso??'Unknown / no expiry selected'}</strong><p>{dirty?'The previously parsed date is withheld until the corrected text is saved and parsed on Python.':payload.expiry?.precision==='month'?'Month precision only. No exact day is supplied or inferred.':payload.expiry?'Day precision preserved from the explicit source.':'Review every observation and warning below. Do not choose between conflicting dates by guessing.'}</p></div>
      <Notice>This is not an assessment of whether the medicine is safe to use. Confirmation acknowledges the reviewed text; it does not resolve uncertainty or authorize taking medicine.</Notice>
      <div className="source-text"><span className="micro">ORIGINAL EXTRACTED EXPIRY LINE</span><p>{data.original_payload?.raw_expiry_text??'Unknown / no single consistent expiry line'}</p></div>
      <div className="medicine-fields"><label>Printed medicine name<input aria-label="Printed medicine name" disabled={!!busy} value={draft.medicine_name??''} placeholder="Unknown / not recorded" onChange={e=>edit({...draft,medicine_name:nullable(e.target.value)})}/></label><label>Printed batch number<input aria-label="Printed batch number" disabled={!!busy} value={draft.batch_number??''} placeholder="Unknown / not recorded" onChange={e=>edit({...draft,batch_number:nullable(e.target.value)})}/></label><label>Products visible in this photo<select aria-label="Products visible in this photo" disabled={!!busy} value={draft.product_association} onChange={e=>edit({...draft,product_association:e.target.value as StripEdits['product_association']})}><option value="single_product">Single product</option><option value="multiple_products">Multiple products</option><option value="unclear">Unclear</option></select></label></div>
      <p className="review-warning"><AlertTriangle size={17}/>Extraction review flag: {String(payload.needs_review)} · Confidence: {payload.confidence??'Unknown'} (uncalibrated, not measured accuracy)</p>
      <div className="strip-issues"><h3>Warnings and unresolved information</h3>{payload.issues.length?<ul>{payload.issues.map(issue=><li key={issue}>{issue}</li>)}</ul>:<p>No issue codes reported. Explicit verification is still required.</p>}</div>
      <h3>All date observations</h3>{draft.date_observations.length===0&&<p>No date observations were extracted.</p>}
      {draft.date_observations.map((observation,index)=>{
        const source=payload.date_observations[index];const original=data.original_payload?.date_observations[index]
        function update(field:'raw_label'|'raw_date_text'|'raw_text'|'association',value:string){edit({...draft!,date_observations:draft!.date_observations.map((o,i)=>i===index?{...o,[field]:field==='association'?value:nullable(value)}:o)})}
        return <article className="scoped-record" key={index}><div className="source-text"><span className="micro">ORIGINAL OBSERVATION {index+1}</span><p>{original?.raw_text??'Unknown / not recorded'}</p></div><div className="medicine-fields">{(['raw_label','raw_date_text','raw_text'] as const).map(field=><label key={field}>{field==='raw_label'?'Printed label':field==='raw_date_text'?'Date text as written':'Full source line'}<input aria-label={(field==='raw_label'?'Printed label':field==='raw_date_text'?'Date text as written':'Full source line')+' '+(index+1)} disabled={!!busy} value={observation[field]??''} placeholder="Unknown / not recorded" onChange={e=>update(field,e.target.value)}/></label>)}<label>Date-to-product link inside this photo<select aria-label={'Date-to-product link '+(index+1)} disabled={!!busy} value={observation.association} onChange={e=>update('association',e.target.value)}><option value="same_product">Same product in photo</option><option value="unclear">Unclear</option></select></label></div><p>Backend label classification: {source.label_kind}. Parsed date token: {source.parsed_date?.iso??'Unknown'}. A parsed manufacturing/batch token is not an expiry.</p><p>Observation uncertainty: {String(source.uncertain)} · Confidence: {source.confidence??'Unknown'} (uncalibrated)</p>{source.parse_issues.length>0&&<p className="review-warning">Parse warnings: {source.parse_issues.join(', ')}</p>}</article>
      })}
      <div className="confirmation-panel"><button className="button secondary" disabled={!!busy} onClick={save}>Save reviewed strip details</button><p>Saving corrections runs the existing conservative parser on Python, without another Gemini request. {dirty?'Unsaved edits have removed prior confirmation.':''}</p><label className="checkbox-label"><input type="checkbox" checked={ack} disabled={!!busy||dirty||!data.reviewed} onChange={e=>setAck(e.target.checked)}/> I checked every label, date observation, unknown value and warning against the packaging. This does not establish medicine safety.</label><button className="button" disabled={!!busy||dirty||!ack||!data.reviewed||data.confirmed} onClick={confirm}><ShieldCheck size={16}/>{data.confirmed?'Confirmed by server':'Confirm strip details'}</button></div>
    </section>}
  </>
}
