import { useEffect,useRef,useState } from 'react'
import { useLanguage,translateError } from '../lib/language'
import { explainMedicine } from '../lib/patientExplanations'
import type { PatientExplanation } from '../lib/patientExplanations'
import type { AnalysisSnapshot } from '../lib/prescriptions'
import { subscribeSchedulingInvalidation,subscribeSchedulingChanges } from '../lib/workflowEvents'
import '../patient-explanations.css'

const labels:Record<string,string>={what:'What this medicine is',uses:'Common uses',benefits:'Benefits',works:'How it works',side_effects:'Common side effects',precautions:'Important precautions',urgent_signs:'Serious warning signs'}
export default function PatientMedicineExplanation({source,index,contextKey,disabled}:{source:AnalysisSnapshot;index:number;contextKey:string;disabled:boolean}){
 const {language,t}=useLanguage();const [cache,setCache]=useState<Record<string,PatientExplanation>>({}),[expanded,setExpanded]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null)
 const version=useRef(0),lock=useRef(false)
 useEffect(()=>{version.current++;setCache({});setExpanded(false);setError(null);setBusy(false);lock.current=false;return()=>{version.current++}},[contextKey])
 useEffect(()=>{setExpanded(false);setError(null)},[language])
 useEffect(()=>{const clear=()=>{version.current++;setCache({});setExpanded(false);setError(null);setBusy(false);lock.current=false};const stop=subscribeSchedulingInvalidation(clear),changed=subscribeSchedulingChanges(clear);return()=>{stop();changed()}},[])
 const name=source.records?.[index]?.name||t('Unknown medicine'),shown=cache[language]
 async function show(){if(disabled||lock.current)return;if(shown){setExpanded(!expanded);return}lock.current=true;setBusy(true);setError(null);const requestVersion=version.current;try{const value=await explainMedicine(source,index,language);if(requestVersion===version.current){setCache(c=>({...c,[value.language]:value}));setExpanded(true)}}catch(e){if(requestVersion===version.current)setError(e)}finally{if(requestVersion===version.current){lock.current=false;setBusy(false)}}}
 return <div className="patient-medicine-explanation"><button className="button secondary" aria-label={t('Explain {0}',[name])} aria-expanded={expanded&&!!shown} disabled={disabled||busy} onClick={()=>void show()}>{busy?t('Generating medicine information…'):expanded&&shown?t('Close explanation'):t('Explain Medicine')}</button>
 {!source.confirmed&&<p>{t('Confirm your medicine review before requesting general medicine information.')}</p>}
 {busy&&<p role="status">{t('Generating medicine information…')}</p>}{error?<p role="alert">{translateError(error)}</p>:null}
 {expanded&&shown&&!disabled&&<section aria-label={t('Medicine information for {0}',[name])} lang={language}><h3>{name}</h3>{shown.status==='identity_uncertain'?<p>{t('Medicine identity or composition could not be verified. Check the packaging with a pharmacist; no drug-specific claims were generated.')}</p>:<><p><strong>{t('Active ingredient — reference match')}: </strong>{shown.ingredient}</p><p>{t('Reference matching does not verify your physical medicine pack. General information is not your diagnosis or a treatment recommendation.')}</p><div className="patient-fact-grid">{shown.sections.map(s=><section key={s.key} className={s.key==='urgent_signs'?'patient-urgent':''}><h4>{t(labels[s.key]||'Medicine information')}</h4><p>{s.text}</p></section>)}</div><p>{t('This is a short overview, not a complete leaflet. Ask a clinician about pregnancy, children, interactions or symptoms that concern you.')}</p><div className="patient-sources"><h4>{t('Trusted reference sources')}</h4>{shown.sources.map((url,i)=><a key={url} href={url} target="_blank" rel="noreferrer">{t('Reference {0}',[i+1])}</a>)}</div></>}
 <section className="patient-instructions"><h4>{t('Your extracted prescription instructions — separate from general information')}</h4><p className="source-text">{shown.prescription.confirmed_linked_instruction?.raw_text||shown.prescription.original_medicine_text||t('Unknown / not recorded')}</p>{!shown.prescription.confirmed_linked_instruction&&<p>{t('No separately confirmed instruction link is available. The original confirmed medicine text is shown without adding instructions.')}</p>}</section>
 </section>}
 </div>
}
