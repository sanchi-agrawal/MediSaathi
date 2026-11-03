import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import ImageUploader from '../components/ImageUploader'
import MedicineMatching from '../components/MedicineMatching'
import PrescriptionExplanation from '../components/PrescriptionExplanation'
import { Notice } from '../components/ui'
import { useLanguage,translateError } from '../lib/language'
import { prescriptionClient,MEDICINE_FIELDS,ApiError } from '../lib/prescriptions'
import type { AnalysisSnapshot,ExplanationPayload } from '../lib/prescriptions'
import { sectionClient,SECTION_FIELDS } from '../lib/sections'
import { confirmedClient,namedSlots } from '../lib/confirmedPrescription'
import type { WholeReview } from '../lib/confirmedPrescription'
import type { Language } from '../lib/api'
import { recognitionClient } from '../lib/recognition'
import '../confirmed-workflow.css'

const medicineLabels:Record<string,string>={raw_text:'Original medicine text',name:'Medicine name',salt:'Printed ingredient',strength:'Written strength',form:'Form',frequency_pattern:'Written frequency',duration_days:'Duration in days',timing:'Written timing',confidence:'Extraction confidence (uncalibrated)'}
const instructionLabels:Record<string,string>={medicine_name_raw:'Medicine name as written',raw_text:'Original instruction / test text',dose_quantity_raw:'Dose quantity as written',dose_unit_raw:'Dose unit as written',frequency_raw:'Frequency as written',route_raw:'Route as written',timing_raw:'Timing as written',duration_raw:'Duration as written'}

export default function UnifiedPrescriptionReview(){
  const {t}=useLanguage()
  const [review,setReview]=useState<WholeReview|null>(null),[source,setSource]=useState<AnalysisSnapshot|null>(null)
  const [file,setFile]=useState<File|null>(null),[restored,setRestored]=useState<File|null>(null)
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[resolved,setResolved]=useState<number[]>([])
  const [language,setLanguage]=useState<Language>('en'),[explanation,setExplanation]=useState<ExplanationPayload|null>(null)
  const [mode,setMode]=useState('')
  const [resolvedInstructions,setResolvedInstructions]=useState<string[]>([])
  const lock=useRef(false),dirty=useRef(false),epoch=useRef(0)
  useEffect(()=>{let active=true;recognitionClient.capabilities().then(c=>{if(active)setMode(c.mode)}).catch(e=>{if(active)setError(translateError(e))});return()=>{active=false}},[])
  async function hydrate(image=false){const s=await prescriptionClient.current();setSource(s);if(s){setReview(await confirmedClient.review());if(image){const f=await prescriptionClient.image(s);setFile(f);setRestored(f)}}else setReview(null);dirty.current=false;setResolved([]);setResolvedInstructions([])}
  async function run(action:()=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError('');try{await action()}catch(e){setError(translateError(e instanceof Error?e.message:String(e)))}finally{lock.current=false;setBusy(false)}}
  useEffect(()=>{let active=true;setBusy(true);void (async()=>{try{const s=await prescriptionClient.current();if(!active)return;setSource(s);if(s){const r=await confirmedClient.review();const f=await prescriptionClient.image(s);if(active){setReview(r);setFile(f);setRestored(f)}}}catch(e){if(active)setError(translateError(e instanceof Error?e.message:String(e)))}finally{if(active)setBusy(false)}})();return()=>{active=false;epoch.current++}},[])
  function edit(update:(value:WholeReview)=>WholeReview){
    setExplanation(null);setReview(r=>r?{...update(r),snapshot:null}:r)
    if(!dirty.current&&source){dirty.current=true;void run(async()=>{const s=await prescriptionClient.invalidate(source);setSource(s);setReview(r=>r?{...r,medicine_revision:s.revision,snapshot:null}:r)})}
  }
  async function analyze(){if(!file)return;await run(async()=>{let s=await prescriptionClient.upload(file);setSource(s);setReview(null);setExplanation(null);s=await prescriptionClient.analyze(s);setSource(s);if(s.status!=='succeeded')throw new ApiError(s.error?.category||'api_error',s.error?.message||'Extraction failed.');const section=await sectionClient.status(s.analysis_id,'instructions');await sectionClient.analyze(section);await hydrate();})}
  const confirmed=!!review?.snapshot
  return <div className="workflow-page"><header className="page-heading"><h1>{t('Prescription analysis')}</h1><p>{t('Review your medicine and its instructions together. Confirm once before scheduling.')}</p></header>
    <Notice>{t('Check every detail against the original prescription. Uncertain or missing medical information must be reviewed; never guessed.')}</Notice>
    <fieldset className="upload-fieldset" disabled={busy}><ImageUploader disabled={busy} onChange={f=>{epoch.current++;setFile(f);setExplanation(null);setReview(null);setResolved([]);setResolvedInstructions([]);if(source)void run(async()=>{await prescriptionClient.clear();setSource(null)})}} restoredFile={restored}/></fieldset>
    <div className="workflow-actions"><button className="button" disabled={busy||!file||!mode} onClick={()=>void analyze()}>{busy?t('Working…'):mode==='offline_fixture'?t('Run fixture simulation'):t('Analyze Prescription with AI')}</button><button className="button secondary" disabled={busy} onClick={()=>void run(()=>hydrate(true))}>{t('Restore current server state')}</button></div>
    {error&&<p role="alert">{error}</p>}
    {review&&<><p>{review.recognition_mode==='offline_fixture'?t('Fixture simulation — no Gemini OCR was performed.'):t('Extraction proposals require your review.')}</p>
      {review.instruction_status!=='succeeded'&&<Notice>{t('Instruction extraction has not succeeded. Analyze medicines and instructions before confirming.')}</Notice>}
      {review.records.map((medicine,index)=>{const pair=review.pairs.find(p=>p.medicine_ref===`medicine_${String(index+1).padStart(3,'0')}`);const instruction=review.instructions?.instructions.find(i=>i.instruction_id===pair?.instruction_id);const requirement=review.review_requirements[index];return <section className="panel" id={`medicine-${index}`} key={index}>
        <h2>{medicine.name||t('Unknown medicine')}</h2><details><summary>{t('Original extracted prescription')}</summary><p className="source-text">{source?.original_records?.[index]?.raw_text}</p></details>
        <div className="medicine-fields">{MEDICINE_FIELDS.filter(f=>f!=='needs_review').map(field=><label key={field}>{t(medicineLabels[field])}<input disabled={busy||field==='confidence'} value={medicine[field]??''} onChange={e=>edit(r=>({...r,records:r.records.map((m,i)=>i===index?{...m,[field]:e.target.value===''?null:field==='duration_days'?Number(e.target.value):e.target.value}:m)}))}/></label>)}</div>
        <label>{t('Corresponding prescription instruction')}<select id={`review-pair-${index}`} disabled={busy} value={pair?.instruction_id||''} onChange={e=>edit(r=>({...r,pairs:r.pairs.map(p=>p.medicine_ref===pair?.medicine_ref?{...p,instruction_id:e.target.value||null,slots:[]}:p)}))}><option value="">{t('Select the matching instruction')}</option>{review.instructions?.instructions.map(i=><option key={i.instruction_id} value={i.instruction_id}>{i.raw_text||i.instruction_id}</option>)}</select></label>
        {instruction&&<><p className="source-text">{instruction.raw_text}</p><div className="medicine-fields">{SECTION_FIELDS.instructions.map(field=><label key={field}>{t(instructionLabels[field])}<input id={`review-instruction-${index}-${field}`} disabled={busy} value={instruction[field]??''} onChange={e=>edit(r=>({...r,instructions:r.instructions?{...r.instructions,instructions:r.instructions.instructions.map(i=>i.instruction_id===instruction.instruction_id?{...i,[field]:e.target.value||null}:i)}:null}))}/></label>)}</div>
        <p>{t('Instruction review flag')}: {t(String(instruction.needs_review))}</p>{instruction.needs_review&&<label className="checkbox-label"><input type="checkbox" disabled={busy} checked={resolvedInstructions.includes(instruction.instruction_id)} onChange={e=>{setResolvedInstructions(ids=>e.target.checked?[...ids,instruction.instruction_id]:ids.filter(id=>id!==instruction.instruction_id));edit(r=>r)}}/>{t('I verified this instruction’s medicine, dose, unit, duration and named timing against the prescription. Unclear clinical details must remain unresolved.')}</label>}<fieldset id={`review-slots-${index}`} disabled={busy}><legend>{t('Verify prescribed time-of-day slots against the source')}</legend>{namedSlots.map(slot=><label key={slot}><input type="checkbox" checked={pair?.slots.includes(slot)||false} onChange={e=>edit(r=>({...r,pairs:r.pairs.map(p=>p.medicine_ref===pair?.medicine_ref?{...p,slots:e.target.checked?namedSlots.filter(s=>p.slots.includes(s)||s===slot):p.slots.filter(s=>s!==slot)}:p)}))}/>{t(slot)}</label>)}</fieldset><p>{t('Instruction review warnings')}: {instruction.uncertainty_reasons.map(value=>t(value)).join(', ')||t('None')}</p></>}
        {medicine.needs_review&&<Notice>{t('The original medicine remains flagged for review.')}<p>{t('Missing fields')}: {requirement?.missing_fields.map(value=>t(value)).join(', ')||t('None')}</p><p>{t('Unsupported source fields')}: {requirement?.unsupported_fields.map(value=>t(value)).join(', ')||t('None')}</p><p>{t('Confidence')}: {t(requirement?.confidence_state||'unknown')}</p><label><input type="checkbox" disabled={busy||!requirement?.can_resolve} checked={resolved.includes(index)} onChange={e=>{setResolved(a=>e.target.checked?[...a,index]:a.filter(i=>i!==index));edit(r=>r)}}/>{t('I verified every required medicine field against the source and resolved this review flag.')}</label></Notice>}
      </section>})}
      <button className="button" disabled={busy||confirmed||review.medicine_status!=='succeeded'||review.instruction_status!=='succeeded'} onClick={()=>void run(async()=>{const payload={...review,records:review.records.map((m,i)=>resolved.includes(i)?{...m,needs_review:false}:m)};await confirmedClient.confirm(payload,resolved,resolvedInstructions);await hydrate();setExplanation(null)})}>{confirmed?t('Prescription confirmed'):t('Confirm reviewed prescription')}</button>
      {confirmed&&<><Notice>{review.snapshot?.medicines.some(m=>m.issues.length)?t('Review is confirmed, but some medicines still need clarification before scheduling.'):t('Prescription confirmed. Scheduling needs only your start date.')}</Notice><Link className="button secondary" to="/dashboard/schedule">{t('Your Medicine Schedule')}</Link></>}
      <PrescriptionExplanation records={review.records} confirmed={confirmed} language={language} onLanguage={l=>{setLanguage(l);setExplanation(null)}} onExplain={()=>void run(async()=>{if(source)setExplanation(await prescriptionClient.explain(source,language))})} explanation={explanation} busy={busy}/>
      {confirmed&&source&&<MedicineMatching source={source}/>}</>}
  </div>
}
