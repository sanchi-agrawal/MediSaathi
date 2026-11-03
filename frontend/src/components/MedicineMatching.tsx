import { translateReason as reason } from '../lib/language'
import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { teamClient } from '../lib/team'
import type { Matches,TeamClient } from '../lib/team'
import type { AnalysisSnapshot } from '../lib/prescriptions'
import { useLanguage } from '../lib/language'
import { Notice } from './ui'
export default function MedicineMatching({source,client=teamClient}:{source:AnalysisSnapshot;client?:TeamClient}){
  useUiLanguage()

  const {language}=useLanguage();const hi=language==='hi'
  const [data,setData]=useState<Matches|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const generation=useRef(0),lock=useRef(false)
  useEffect(()=>{const v=++generation.current;setData(null);setError('');client.current(source).then(d=>{if(v===generation.current)setData(d)}).catch(()=>{if(v===generation.current)setError('Catalogue state unavailable. Use the button to try explicitly.')});return()=>{generation.current++}},[source.analysis_id,source.revision,client])
  async function run(action:()=>Promise<Matches>){if(lock.current)return;lock.current=true;setBusy(true);setError('');const v=generation.current;try{const d=await action();if(v===generation.current)setData(d)}catch(e){if(v===generation.current){setData(null);setError(e instanceof Error?e.message:'Catalogue unavailable')}}finally{lock.current=false;if(v===generation.current)setBusy(false)}}
  return <section className="panel schedule-panel" aria-label={tr("Medicine catalogue candidates")}><h2>{hi?"दवा कैटलॉग के संभावित परिणाम":tr("Medicine catalogue candidates")}</h2><Notice>{hi?"यह केवल संभावित पहचान है, दवा बदलने की अनुमति नहीं।":tr("Candidate identification only, not substitution approval.")}{tr(" Catalogue details are unverified examples. Missing salt, strength, form or release type requires professional review. Cheaper alternatives are disabled.")}</Notice>
    <button className="button secondary" disabled={busy} onClick={()=>void run(()=>client.match(source))}>{busy?tr("Working…"):hi?"संभावित दवाएँ खोजें":tr("Find catalogue candidates")}</button> <Link to="/dashboard/medicine-pricing">{hi?"मूल्य की उपलब्धता":tr("Check price availability")}</Link>
    <div className="market-prescription-links">{source.confirmed&&(source.records||[]).map((medicine,index)=>medicine.name&&<p key={index}>{medicine.name} · <Link to={`/dashboard/medicine-pricing?q=${encodeURIComponent(medicine.name)}&medicine_ref=medicine_${String(index+1).padStart(3,'0')}`}>{tr('Compare Prices')}</Link></p>)}</div>
    {error&&<p role="alert">{uiError(error)}</p>}{data?.records.map(r=><div className="source-text" key={r.medicine_ref}><h3>{r.name ?? tr("Unknown medicine")}</h3><p>{tr(r.message)}</p>{!r.candidates.length&&<p>{tr("No compatible catalogue candidate. Unknown details remain unknown.")}</p>}{r.candidates.map(c=><div key={c.candidate_id}><p>{c.name}{tr(" · Salt: ")}{c.salt ?? tr("Unknown")}{tr(" · Strength: ")}{c.strength ?? tr("Unknown")}{tr(" · Form: ")}{c.form ?? tr("Unknown")}</p><small>{c.candidate_id}{tr(" · Text similarity ")}{c.score}{tr("/100 · Review: ")}{c.review_reasons.map(reason).join(', ') || tr("Unverified catalogue identity")}</small><div><button className="button secondary" disabled={busy||r.selected===c.candidate_id} onClick={()=>void run(()=>client.select(source,r.medicine_ref,c.candidate_id))}>{r.selected===c.candidate_id?tr("Selected by user — identity still requires review"):tr("Select this candidate")}</button></div></div>)}</div>)}
  </section>
}
