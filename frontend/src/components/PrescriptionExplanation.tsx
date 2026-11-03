import { translateReason as reason } from '../lib/language'
import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { Languages } from 'lucide-react'
import { Notice } from './ui'
import type { Language,MedicineRecord } from '../lib/api'
import type { ExplanationPayload } from '../lib/prescriptions'
import { explanationCopy } from '../lib/explanationCopy'

export default function PrescriptionExplanation({language,onLanguage,onExplain,explanation,records,confirmed,busy,disabled=busy}:{language:Language;onLanguage:(l:Language)=>void;onExplain:()=>void;explanation:ExplanationPayload|null;records:MedicineRecord[];confirmed:boolean;busy:boolean;disabled?:boolean}){
  const {language:interfaceLanguage}=useUiLanguage()

  const copy=explanationCopy[language]
  const shown=confirmed&&explanation?.language===language?explanation:null
  return <div lang={interfaceLanguage}><details className="ocr-technical-details"><summary>{tr("OCR technical details and confirmed source summary")}</summary>
    <section className="panel explanation-panel"><div><span className="icon-box coral"><Languages size={23}/></span><h2>{copy.title}</h2><p>{copy.help}</p><div className="language-options" role="group" aria-label={tr("Explanation language")}>{([['en','English'],['hi','हिन्दी'],['hinglish','Hinglish']] as const).map(([id,label])=><button key={id} disabled={disabled} className={language===id?'selected':''} aria-pressed={language===id} onClick={()=>onLanguage(id)}>{tr(label)}</button>)}</div><button className="button secondary" onClick={onExplain} disabled={disabled||!confirmed}>{copy.action}</button></div><div className="explanation-empty"><p>{copy.prerequisite}</p><span>ENGLISH · हिन्दी · HINGLISH</span></div></section>
    {busy&&<p role="status">{copy.loading}</p>}
    {shown&&<section className="panel real-explanation" lang={language==='hinglish'?'hi-Latn':language} aria-label={tr("Confirmed medicine explanation")}><h2>{shown.summary?.title ?? copy.summary}</h2><p>{shown.notice}</p>{shown.summary&&<p>{shown.summary.notice}</p>}<p>{copy.medicine}: {shown.medicines.length}</p>
      {shown.status==='empty'&&<Notice>{copy.unknown}</Notice>}
      {shown.medicines.map(m=><article key={m.record_index}><h3>{copy.medicine} {m.record_index+1} · {records[m.record_index]?.name ?? copy.unknown}</h3><div className="source-text"><span className="micro">{copy.original}</span><p>{records[m.record_index]?.raw_text ?? copy.unknown}</p></div>{m.fields.map(f=><p key={f.field}>{f.text}</p>)}{m.glossary&&<Notice>{m.glossary.text}</Notice>}</article>)}
      {shown.issues.length>0&&<div><h3>{copy.warnings}</h3>{shown.issues.map((issue,i)=><p key={i}>{issue.text}</p>)}</div>}
      {shown.summary&&(['instructions'] as const).map(scope=>{const section=shown.summary!.sections[scope];return <section key={scope} aria-label={section.title}><h3>{section.title}</h3>{!section.confirmed?<p>{copy.unconfirmed}</p>:section.records.length===0?<p>{copy.unknown}</p>:section.records.map(r=><article key={r.record_id}><div className="source-text"><span className="micro">{copy.original}</span><p>{r.original_text ?? copy.unknown}</p></div>{r.fields.map(f=><p key={f.field}>{f.text}</p>)}<p>{copy.warnings}: {r.uncertainty_reasons.map(reason).join(', ') || "—"} · {tr(String(r.needs_review))}</p></article>)}{section.issues.length>0&&<p>{copy.warnings}: {section.issues.map(reason).join(', ')}</p>}</section>})}
    </section>}
  </details></div>
}
