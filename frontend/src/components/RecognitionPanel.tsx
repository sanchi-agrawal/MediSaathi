import { useEffect } from 'react'
import { useLanguage } from '../lib/language'
import { recognitionClient } from '../lib/recognition'
import type { RecognitionClient,RecognitionMetadata,RecognitionMode } from '../lib/recognition'
export function NumeralReading({metadata}:{metadata?:RecognitionMetadata}){
  const {t}=useLanguage()
  const previews=(metadata?.numeric_previews??[]).filter(p=>Number.isInteger(p.record_index)&&p.record_index>=0&&['strength','frequency_pattern','timing','dose_quantity_raw','duration_raw'].includes(p.field)&&typeof p.original==='string'&&typeof p.digit_reading==='string')
  if(!previews.length)return null
  return <section className="notice" aria-label={t('Numeral reading aid')}><div><strong>{t('Numeral reading aid')}</strong><p>{t('Digits only are shown in 0–9 for comparison. Original values and medicine names are not changed; this does not establish a dose.')}</p><dl>{previews.map((p,i)=><div key={i}><dt>{t(p.field)} · {p.record_index+1}</dt><dd><span translate="no">{p.original}</span> → <span translate="no">{p.digit_reading}</span></dd></div>)}</dl></div></section>
}
// Headless mode lookup: intentionally renders no panel, badge or spacing.
export default function RecognitionPanel({client=recognitionClient,onMode}:{client?:RecognitionClient;onMode?:(mode:RecognitionMode|null)=>void}){
  useEffect(()=>{let active=true;client.capabilities().then(s=>{if(active)onMode?.(s.mode)}).catch(()=>{if(active)onMode?.(null)});return()=>{active=false}},[client,onMode])
  return null
}
