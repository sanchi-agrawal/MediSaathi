import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { useLanguage } from '../lib/language'
export function LanguageToggle(){
  useUiLanguage()
const {language,setLanguage}=useLanguage();return <div className="language-toggle" role="group" aria-label={tr("English / हिंदी")}>{(['en','hi'] as const).map(lang=><button key={lang} lang={lang} aria-pressed={language===lang} onClick={()=>setLanguage(lang)}>{lang==='en'?"English":"हिंदी"}</button>)}</div>}
