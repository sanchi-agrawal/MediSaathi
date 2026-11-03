import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
export default function OfflineDemoNotice(){
  const {language}=useUiLanguage()

  if(import.meta.env.VITE_MEDISAATHI_PREVIEW==='1')return <div className="notice" role="status">{language==='hi'?'सार्वजनिक डेमो: केवल काल्पनिक जानकारी इस्तेमाल करें। खाते और पर्चे स्थायी चिकित्सा रिकॉर्ड नहीं हैं।':'Public preview: use fictional information only. Accounts and prescriptions are not durable medical records.'}</div>
  if(import.meta.env.VITE_MEDISAATHI_ACCOUNT_TEST==='1')return <div className="notice" role="status">{tr("FICTIONAL OCR / REAL AUTH TEST — Accounts use the configured Supabase provider. No Gemini calls or notification delivery.")}</div>
  return null
}
