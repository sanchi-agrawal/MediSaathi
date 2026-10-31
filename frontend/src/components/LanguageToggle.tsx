import { useLanguage } from '../lib/language'
export function LanguageToggle(){const {language,setLanguage}=useLanguage();return <div className="language-toggle" role="group" aria-label="English / हिंदी">{(['en','hi'] as const).map(lang=><button key={lang} lang={lang} aria-pressed={language===lang} onClick={()=>setLanguage(lang)}>{lang==='en'?'English':'हिंदी'}</button>)}</div>}
