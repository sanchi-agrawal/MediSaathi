import { useEffect,useRef,useState } from 'react'
import { Link } from 'react-router-dom'
import { teamClient } from '../lib/team'
import type { Matches,TeamClient } from '../lib/team'
import type { AnalysisSnapshot } from '../lib/prescriptions'
import { useLanguage } from '../lib/language'
import { Notice } from './ui'
export default function MedicineMatching({source,client=teamClient}:{source:AnalysisSnapshot;client?:TeamClient}){
  const {language}=useLanguage();const hi=language==='hi'
  const [data,setData]=useState<Matches|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const generation=useRef(0),lock=useRef(false)
  useEffect(()=>{const v=++generation.current;setData(null);setError('');client.current(source).then(d=>{if(v===generation.current)setData(d)}).catch(()=>{if(v===generation.current)setError('Catalogue state unavailable. Use the button to try explicitly.')});return()=>{generation.current++}},[source.analysis_id,source.revision,client])
  async function run(action:()=>Promise<Matches>){if(lock.current)return;lock.current=true;setBusy(true);setError('');const v=generation.current;try{const d=await action();if(v===generation.current)setData(d)}catch(e){if(v===generation.current){setData(null);setError(e instanceof Error?e.message:'Catalogue unavailable')}}finally{lock.current=false;if(v===generation.current)setBusy(false)}}
  return <section className="panel schedule-panel" aria-label="Medicine catalogue candidates"><h2>{hi?'दवा कैटलॉग के संभावित परिणाम':'Medicine catalogue candidates'}</h2><Notice>{hi?'यह केवल संभावित पहचान है, दवा बदलने की अनुमति नहीं।':'Candidate identification only, not substitution approval.'} Catalogue details are unverified examples. Missing salt, strength, form or release type requires professional review. Cheaper alternatives are disabled.</Notice>
    <button className="button secondary" disabled={busy} onClick={()=>void run(()=>client.match(source))}>{busy?'Working…':hi?'संभावित दवाएँ खोजें':'Find catalogue candidates'}</button> <Link to="/dashboard/medicine-pricing">{hi?'मूल्य की उपलब्धता':'Check price availability'}</Link>
    {error&&<p role="alert">{error}</p>}{data?.records.map(r=><div className="source-text" key={r.medicine_ref}><h3>{r.name??'Unknown medicine'}</h3><p>{r.message}</p>{!r.candidates.length&&<p>No compatible catalogue candidate. Unknown details remain unknown.</p>}{r.candidates.map(c=><div key={c.candidate_id}><p>{c.name} · Salt: {c.salt??'Unknown'} · Strength: {c.strength??'Unknown'} · Form: {c.form??'Unknown'}</p><small>{c.candidate_id} · Text similarity {c.score}/100 · Review: {c.review_reasons.join(', ')||'Unverified catalogue identity'}</small><div><button className="button secondary" disabled={busy||r.selected===c.candidate_id} onClick={()=>void run(()=>client.select(source,r.medicine_ref,c.candidate_id))}>{r.selected===c.candidate_id?'Selected by user — identity still requires review':'Select this candidate'}</button></div></div>)}</div>)}
  </section>
}
